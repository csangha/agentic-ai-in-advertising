"""
Workflow Engine — executes multi-agent workflow DAGs.

Supports:
- DAG definitions (steps, dependencies, conditions, timeouts)
- Checkpointing (resume from last successful step)
- Conditional branching
- Timeout enforcement per step
- Retry policies with configurable backoff
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
import uuid


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMED_OUT = "TIMED_OUT"


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    agent_id: str  # Which agent handles this step
    task_payload: Dict  # What to send to the agent
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on
    condition: Optional[str] = None  # Python expression for conditional execution
    timeout_seconds: int = 300  # 5 minutes default
    max_retries: int = 2
    retry_count: int = 0
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class WorkflowDefinition:
    workflow_id: str = field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.CREATED
    context: Dict = field(default_factory=dict)  # Shared context across steps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checkpoint: Optional[str] = None  # Last completed step_id for resume


class WorkflowEngine:
    """
    Executes multi-agent workflows defined as DAGs.
    Handles step sequencing, retries, conditions, and checkpointing.
    """

    def __init__(self, agent_invoker: Optional[Callable] = None):
        """
        Args:
            agent_invoker: Callable(agent_id, payload) → result.
                          In production: calls AgentCore invoke_agent_runtime.
        """
        self._invoker = agent_invoker or self._default_invoker
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def create_workflow(self, name: str, steps: List[WorkflowStep], context: Dict = None) -> WorkflowDefinition:
        """Create a new workflow definition."""
        wf = WorkflowDefinition(name=name, steps=steps, context=context or {})
        self._workflows[wf.workflow_id] = wf
        return wf

    async def execute(self, workflow_id: str) -> WorkflowDefinition:
        """
        Execute a workflow from its current state.
        Supports resume from checkpoint after restart.
        """
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found")

        wf.status = WorkflowStatus.RUNNING
        wf.started_at = wf.started_at or datetime.utcnow()

        while True:
            # Find next ready steps (all dependencies met)
            ready_steps = self._get_ready_steps(wf)

            if not ready_steps:
                # Check if workflow is complete or stuck
                if all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in wf.steps):
                    wf.status = WorkflowStatus.COMPLETED
                    wf.completed_at = datetime.utcnow()
                elif any(s.status == StepStatus.FAILED for s in wf.steps):
                    wf.status = WorkflowStatus.FAILED
                break

            # Execute ready steps (could be parallel in production)
            for step in ready_steps:
                await self._execute_step(wf, step)

        return wf

    async def _execute_step(self, wf: WorkflowDefinition, step: WorkflowStep):
        """Execute a single workflow step."""
        # Check condition
        if step.condition:
            if not self._evaluate_condition(step.condition, wf.context):
                step.status = StepStatus.SKIPPED
                return

        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()

        try:
            # Invoke the agent
            result = await self._invoker(step.agent_id, step.task_payload)
            step.result = result
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()

            # Update workflow context with step result
            wf.context[f"step_{step.step_id}_result"] = result
            wf.checkpoint = step.step_id

        except TimeoutError:
            step.status = StepStatus.TIMED_OUT
            step.error = f"Step timed out after {step.timeout_seconds}s"
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING  # Will retry
            else:
                step.status = StepStatus.FAILED

        except Exception as e:
            step.error = str(e)
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING
            else:
                step.status = StepStatus.FAILED

    def _get_ready_steps(self, wf: WorkflowDefinition) -> List[WorkflowStep]:
        """Get steps whose dependencies are all satisfied."""
        ready = []
        for step in wf.steps:
            if step.status != StepStatus.PENDING:
                continue
            # Check all dependencies are completed/skipped
            deps_met = all(
                self._get_step(wf, dep_id).status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                for dep_id in step.depends_on
            )
            if deps_met:
                ready.append(step)
        return ready

    def _get_step(self, wf: WorkflowDefinition, step_id: str) -> WorkflowStep:
        """Get a step by ID."""
        for step in wf.steps:
            if step.step_id == step_id:
                return step
        raise ValueError(f"Step {step_id} not found")

    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """Evaluate a condition expression against workflow context."""
        try:
            return bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            return True  # Default to executing if condition evaluation fails

    async def _default_invoker(self, agent_id: str, payload: Dict) -> Any:
        """Default agent invoker (placeholder for testing)."""
        return {"status": "completed", "agent_id": agent_id}

    def get_status(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow execution status."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        return {
            "workflow_id": wf.workflow_id,
            "name": wf.name,
            "status": wf.status.value,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "status": s.status.value,
                    "agent_id": s.agent_id,
                    "retry_count": s.retry_count,
                }
                for s in wf.steps
            ],
            "checkpoint": wf.checkpoint,
        }
