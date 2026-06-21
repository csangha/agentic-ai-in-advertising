"""
Tests for Workflow Engine — DAG execution, conditional branching, retry, checkpoint.
"""

import pytest
from datetime import datetime
from services.workflow_engine import (
    WorkflowEngine, WorkflowDAG, WorkflowNode, WorkflowEdge,
    NodeStatus, WorkflowStatus, RetryPolicy, CheckpointData
)


@pytest.fixture
def engine():
    return WorkflowEngine(max_retries=3, retry_delay_seconds=1)


@pytest.fixture
def simple_dag():
    """Linear workflow: ingest → analyze → optimize → report."""
    nodes = [
        WorkflowNode(node_id="ingest", agent_id="agent-monitor", action="ingest_metrics"),
        WorkflowNode(node_id="analyze", agent_id="agent-monitor", action="detect_anomalies"),
        WorkflowNode(node_id="optimize", agent_id="agent-optimizer", action="adjust_bids"),
        WorkflowNode(node_id="report", agent_id="agent-orchestrator", action="generate_report"),
    ]
    edges = [
        WorkflowEdge(from_node="ingest", to_node="analyze"),
        WorkflowEdge(from_node="analyze", to_node="optimize"),
        WorkflowEdge(from_node="optimize", to_node="report"),
    ]
    return WorkflowDAG(
        workflow_id="wf-simple-001",
        name="Simple Campaign Cycle",
        nodes=nodes,
        edges=edges,
    )


@pytest.fixture
def branching_dag():
    """DAG with conditional branch: analyze → (if anomaly: escalate, else: continue)."""
    nodes = [
        WorkflowNode(node_id="analyze", agent_id="agent-monitor", action="detect_anomalies"),
        WorkflowNode(node_id="escalate", agent_id="agent-orchestrator", action="escalate_to_human"),
        WorkflowNode(node_id="continue", agent_id="agent-optimizer", action="routine_optimization"),
        WorkflowNode(node_id="complete", agent_id="agent-orchestrator", action="mark_complete"),
    ]
    edges = [
        WorkflowEdge(from_node="analyze", to_node="escalate", condition="anomaly_detected == True"),
        WorkflowEdge(from_node="analyze", to_node="continue", condition="anomaly_detected == False"),
        WorkflowEdge(from_node="escalate", to_node="complete"),
        WorkflowEdge(from_node="continue", to_node="complete"),
    ]
    return WorkflowDAG(
        workflow_id="wf-branch-001",
        name="Branching Campaign Cycle",
        nodes=nodes,
        edges=edges,
    )


class TestDAGExecution:
    """DAG execution ordering and completion."""

    def test_execute_simple_dag(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        assert execution.status == WorkflowStatus.RUNNING

        # Simulate completing each node in order
        engine.complete_node(execution.execution_id, "ingest", result={"rows": 1000})
        engine.complete_node(execution.execution_id, "analyze", result={"anomalies": 0})
        engine.complete_node(execution.execution_id, "optimize", result={"adjustments": 2})
        engine.complete_node(execution.execution_id, "report", result={"report_id": "rpt-001"})

        execution = engine.get_execution(execution.execution_id)
        assert execution.status == WorkflowStatus.COMPLETED

    def test_node_ordering_respects_dependencies(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        ready = engine.get_ready_nodes(execution.execution_id)
        # Only 'ingest' has no dependencies
        assert len(ready) == 1
        assert ready[0].node_id == "ingest"

    def test_parallel_nodes_both_ready(self, engine):
        """Nodes without dependencies on each other are both ready."""
        nodes = [
            WorkflowNode(node_id="start", agent_id="orch", action="begin"),
            WorkflowNode(node_id="task_a", agent_id="agent-a", action="do_a"),
            WorkflowNode(node_id="task_b", agent_id="agent-b", action="do_b"),
            WorkflowNode(node_id="end", agent_id="orch", action="finish"),
        ]
        edges = [
            WorkflowEdge(from_node="start", to_node="task_a"),
            WorkflowEdge(from_node="start", to_node="task_b"),
            WorkflowEdge(from_node="task_a", to_node="end"),
            WorkflowEdge(from_node="task_b", to_node="end"),
        ]
        dag = WorkflowDAG(workflow_id="wf-par", name="Parallel", nodes=nodes, edges=edges)
        execution = engine.start(dag)
        engine.complete_node(execution.execution_id, "start", result={})
        ready = engine.get_ready_nodes(execution.execution_id)
        ready_ids = {n.node_id for n in ready}
        assert ready_ids == {"task_a", "task_b"}

    def test_execution_tracks_duration(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        assert execution.started_at is not None
        for node_id in ["ingest", "analyze", "optimize", "report"]:
            engine.complete_node(execution.execution_id, node_id, result={})
        execution = engine.get_execution(execution.execution_id)
        assert execution.completed_at is not None


class TestConditionalBranching:
    """Conditional edge evaluation."""

    def test_branch_on_anomaly_detected(self, engine, branching_dag):
        execution = engine.start(branching_dag)
        engine.complete_node(
            execution.execution_id, "analyze",
            result={"anomaly_detected": True},
        )
        ready = engine.get_ready_nodes(execution.execution_id)
        ready_ids = [n.node_id for n in ready]
        assert "escalate" in ready_ids
        assert "continue" not in ready_ids

    def test_branch_no_anomaly_continues(self, engine, branching_dag):
        execution = engine.start(branching_dag)
        engine.complete_node(
            execution.execution_id, "analyze",
            result={"anomaly_detected": False},
        )
        ready = engine.get_ready_nodes(execution.execution_id)
        ready_ids = [n.node_id for n in ready]
        assert "continue" in ready_ids
        assert "escalate" not in ready_ids

    def test_both_branches_converge(self, engine, branching_dag):
        execution = engine.start(branching_dag)
        engine.complete_node(execution.execution_id, "analyze", result={"anomaly_detected": True})
        engine.complete_node(execution.execution_id, "escalate", result={"escalated": True})
        engine.complete_node(execution.execution_id, "complete", result={})

        execution = engine.get_execution(execution.execution_id)
        assert execution.status == WorkflowStatus.COMPLETED


class TestRetry:
    """Retry logic for failed nodes."""

    def test_failed_node_retries(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        engine.fail_node(execution.execution_id, "ingest", error="Connection timeout")

        node_status = engine.get_node_status(execution.execution_id, "ingest")
        assert node_status.status == NodeStatus.RETRYING
        assert node_status.retry_count == 1

    def test_max_retries_exhausted(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        for i in range(3):
            engine.fail_node(execution.execution_id, "ingest", error=f"Failure {i+1}")

        node_status = engine.get_node_status(execution.execution_id, "ingest")
        assert node_status.status == NodeStatus.FAILED
        assert node_status.retry_count == 3

    def test_workflow_fails_on_unrecoverable_node(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        for i in range(3):
            engine.fail_node(execution.execution_id, "ingest", error="Fatal error")

        execution = engine.get_execution(execution.execution_id)
        assert execution.status == WorkflowStatus.FAILED

    def test_retry_policy_custom(self, engine):
        nodes = [WorkflowNode(
            node_id="fragile",
            agent_id="agent-a",
            action="fragile_action",
            retry_policy=RetryPolicy(max_retries=5, delay_seconds=2),
        )]
        dag = WorkflowDAG(workflow_id="wf-retry", name="Retry Test", nodes=nodes, edges=[])
        execution = engine.start(dag)
        # Should allow up to 5 retries
        for i in range(4):
            engine.fail_node(execution.execution_id, "fragile", error=f"Attempt {i+1}")
        node_status = engine.get_node_status(execution.execution_id, "fragile")
        assert node_status.status == NodeStatus.RETRYING
        assert node_status.retry_count == 4


class TestCheckpoint:
    """Workflow checkpointing and resumption."""

    def test_checkpoint_saves_state(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        engine.complete_node(execution.execution_id, "ingest", result={"rows": 500})
        engine.complete_node(execution.execution_id, "analyze", result={"anomalies": 1})

        checkpoint = engine.checkpoint(execution.execution_id)
        assert checkpoint is not None
        assert checkpoint.completed_nodes == ["ingest", "analyze"]
        assert checkpoint.pending_nodes == ["optimize", "report"]

    def test_resume_from_checkpoint(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        engine.complete_node(execution.execution_id, "ingest", result={"rows": 500})
        engine.complete_node(execution.execution_id, "analyze", result={"anomalies": 1})

        checkpoint = engine.checkpoint(execution.execution_id)

        # Simulate restart — resume from checkpoint
        new_execution = engine.resume(simple_dag, checkpoint)
        ready = engine.get_ready_nodes(new_execution.execution_id)
        ready_ids = [n.node_id for n in ready]
        assert "optimize" in ready_ids
        assert "ingest" not in ready_ids
        assert "analyze" not in ready_ids

    def test_checkpoint_includes_results(self, engine, simple_dag):
        execution = engine.start(simple_dag)
        engine.complete_node(execution.execution_id, "ingest", result={"rows": 1000})

        checkpoint = engine.checkpoint(execution.execution_id)
        assert checkpoint.node_results["ingest"] == {"rows": 1000}
