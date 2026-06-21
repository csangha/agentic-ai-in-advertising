"""
Tests for Agent Registry — registration, discovery, heartbeat, deregistration.
"""

import pytest
from datetime import datetime, timedelta
from services.agent_registry import (
    AgentRegistry, AgentRegistration, AgentStatus, AgentCapability
)


@pytest.fixture
def registry():
    return AgentRegistry(heartbeat_timeout_seconds=60)


@pytest.fixture
def sample_agent():
    return AgentRegistration(
        agent_id="agent-monitor-001",
        name="Monitoring Agent",
        capabilities=[
            AgentCapability(name="metrics_ingestion", version="1.0"),
            AgentCapability(name="anomaly_detection", version="1.0"),
        ],
        endpoint="http://localhost:9001",
        role="monitor",
    )


@pytest.fixture
def sample_agents(registry):
    """Register multiple agents for discovery tests."""
    agents = [
        AgentRegistration(
            agent_id="agent-monitor-001",
            name="Monitoring Agent",
            capabilities=[
                AgentCapability(name="metrics_ingestion", version="1.0"),
                AgentCapability(name="anomaly_detection", version="1.0"),
            ],
            endpoint="http://localhost:9001",
            role="monitor",
        ),
        AgentRegistration(
            agent_id="agent-optimize-001",
            name="Optimization Agent",
            capabilities=[
                AgentCapability(name="bid_optimization", version="1.0"),
                AgentCapability(name="budget_allocation", version="1.0"),
            ],
            endpoint="http://localhost:9002",
            role="worker",
        ),
        AgentRegistration(
            agent_id="agent-orchestrator-001",
            name="Campaign Orchestrator",
            capabilities=[
                AgentCapability(name="workflow_coordination", version="1.0"),
                AgentCapability(name="task_delegation", version="1.0"),
            ],
            endpoint="http://localhost:9000",
            role="orchestrator",
        ),
    ]
    for agent in agents:
        registry.register(agent)
    return agents


class TestRegistration:
    """Agent registration lifecycle."""

    def test_register_new_agent(self, registry, sample_agent):
        result = registry.register(sample_agent)
        assert result.success is True
        assert result.agent_id == "agent-monitor-001"

    def test_register_assigns_timestamp(self, registry, sample_agent):
        registry.register(sample_agent)
        stored = registry.get(sample_agent.agent_id)
        assert stored is not None
        assert stored.registered_at is not None

    def test_register_duplicate_updates(self, registry, sample_agent):
        registry.register(sample_agent)
        sample_agent.endpoint = "http://localhost:9999"
        result = registry.register(sample_agent)
        assert result.success is True
        stored = registry.get(sample_agent.agent_id)
        assert stored.endpoint == "http://localhost:9999"

    def test_registry_count(self, registry, sample_agents):
        assert registry.count() == 3


class TestDiscovery:
    """Agent discovery by capability, role, status."""

    def test_discover_by_capability(self, registry, sample_agents):
        results = registry.discover(capability="anomaly_detection")
        assert len(results) == 1
        assert results[0].agent_id == "agent-monitor-001"

    def test_discover_by_role(self, registry, sample_agents):
        results = registry.discover(role="orchestrator")
        assert len(results) == 1
        assert results[0].agent_id == "agent-orchestrator-001"

    def test_discover_all_active(self, registry, sample_agents):
        results = registry.discover(status=AgentStatus.ACTIVE)
        assert len(results) == 3

    def test_discover_no_match(self, registry, sample_agents):
        results = registry.discover(capability="creative_generation")
        assert len(results) == 0

    def test_discover_partial_capability_match(self, registry, sample_agents):
        results = registry.discover(capability="optimization")
        assert len(results) >= 1


class TestHeartbeat:
    """Heartbeat monitoring and timeout detection."""

    def test_heartbeat_updates_timestamp(self, registry, sample_agent):
        registry.register(sample_agent)
        old_ts = registry.get(sample_agent.agent_id).last_heartbeat
        registry.heartbeat(sample_agent.agent_id)
        new_ts = registry.get(sample_agent.agent_id).last_heartbeat
        assert new_ts >= old_ts

    def test_missed_heartbeat_marks_inactive(self, registry, sample_agent):
        registry.register(sample_agent)
        # Simulate stale heartbeat
        stored = registry.get(sample_agent.agent_id)
        stored.last_heartbeat = datetime.utcnow() - timedelta(seconds=120)
        registry._agents[sample_agent.agent_id] = stored

        inactive = registry.discover(status=AgentStatus.INACTIVE)
        assert len(inactive) >= 1
        assert any(a.agent_id == sample_agent.agent_id for a in inactive)

    def test_heartbeat_timeout_configurable(self):
        registry = AgentRegistry(heartbeat_timeout_seconds=10)
        agent = AgentRegistration(
            agent_id="agent-test",
            name="Test",
            capabilities=[],
            endpoint="http://localhost:8000",
            role="worker",
        )
        registry.register(agent)
        stored = registry.get(agent.agent_id)
        stored.last_heartbeat = datetime.utcnow() - timedelta(seconds=15)
        registry._agents[agent.agent_id] = stored

        inactive = registry.discover(status=AgentStatus.INACTIVE)
        assert any(a.agent_id == "agent-test" for a in inactive)


class TestDeregistration:
    """Agent deregistration."""

    def test_deregister_removes_agent(self, registry, sample_agent):
        registry.register(sample_agent)
        result = registry.deregister(sample_agent.agent_id)
        assert result.success is True
        assert registry.get(sample_agent.agent_id) is None

    def test_deregister_nonexistent_fails(self, registry):
        result = registry.deregister("agent-nonexistent")
        assert result.success is False

    def test_deregister_reduces_count(self, registry, sample_agents):
        assert registry.count() == 3
        registry.deregister("agent-monitor-001")
        assert registry.count() == 2
