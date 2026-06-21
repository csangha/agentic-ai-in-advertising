"""
Tests for Shared State — read/write, concurrency conflicts, transactions, TTL.
"""

import pytest
from datetime import datetime, timedelta
from services.shared_state import (
    SharedStateManager, StateEntry, VersionConflictError, StateNamespace
)


@pytest.fixture
def state_manager():
    return SharedStateManager()


@pytest.fixture
def populated_state(state_manager):
    """Pre-populate state with campaign data."""
    state_manager.write(
        namespace=StateNamespace.CAMPAIGN,
        key="camp-001",
        value={"status": "active", "budget_remaining": 45000},
        writer_id="orchestrator",
    )
    state_manager.write(
        namespace=StateNamespace.WORKFLOW,
        key="wf-001",
        value={"stage": "monitoring", "step": 3},
        writer_id="orchestrator",
    )
    return state_manager


class TestReadWrite:
    """Basic read/write operations."""

    def test_write_and_read(self, state_manager):
        state_manager.write(
            namespace=StateNamespace.CAMPAIGN,
            key="camp-001",
            value={"status": "active"},
            writer_id="agent-001",
        )
        entry = state_manager.read(StateNamespace.CAMPAIGN, "camp-001")
        assert entry is not None
        assert entry.value == {"status": "active"}

    def test_read_nonexistent_returns_none(self, state_manager):
        entry = state_manager.read(StateNamespace.CAMPAIGN, "nonexistent")
        assert entry is None

    def test_write_increments_version(self, state_manager):
        state_manager.write(StateNamespace.CAMPAIGN, "camp-001", {"v": 1}, "agent-001")
        entry1 = state_manager.read(StateNamespace.CAMPAIGN, "camp-001")
        assert entry1.version == 1

        state_manager.write(StateNamespace.CAMPAIGN, "camp-001", {"v": 2}, "agent-001")
        entry2 = state_manager.read(StateNamespace.CAMPAIGN, "camp-001")
        assert entry2.version == 2

    def test_write_records_writer(self, state_manager):
        state_manager.write(StateNamespace.AGENT, "agent-001", {"status": "running"}, "system")
        entry = state_manager.read(StateNamespace.AGENT, "agent-001")
        assert entry.writer_id == "system"

    def test_namespaces_are_isolated(self, state_manager):
        state_manager.write(StateNamespace.CAMPAIGN, "key-1", {"source": "campaign"}, "a")
        state_manager.write(StateNamespace.WORKFLOW, "key-1", {"source": "workflow"}, "b")

        camp = state_manager.read(StateNamespace.CAMPAIGN, "key-1")
        wf = state_manager.read(StateNamespace.WORKFLOW, "key-1")
        assert camp.value["source"] == "campaign"
        assert wf.value["source"] == "workflow"


class TestConcurrencyConflict:
    """Optimistic locking and version conflict detection."""

    def test_conditional_write_success(self, populated_state):
        entry = populated_state.read(StateNamespace.CAMPAIGN, "camp-001")
        populated_state.write(
            namespace=StateNamespace.CAMPAIGN,
            key="camp-001",
            value={"status": "paused", "budget_remaining": 45000},
            writer_id="optimizer",
            expected_version=entry.version,
        )
        updated = populated_state.read(StateNamespace.CAMPAIGN, "camp-001")
        assert updated.value["status"] == "paused"

    def test_version_conflict_raises(self, populated_state):
        # Simulate stale version
        with pytest.raises(VersionConflictError):
            populated_state.write(
                namespace=StateNamespace.CAMPAIGN,
                key="camp-001",
                value={"status": "paused"},
                writer_id="slow-agent",
                expected_version=0,  # Wrong version
            )

    def test_concurrent_writers_one_wins(self, populated_state):
        entry = populated_state.read(StateNamespace.CAMPAIGN, "camp-001")
        version = entry.version

        # First writer succeeds
        populated_state.write(
            StateNamespace.CAMPAIGN, "camp-001",
            {"status": "optimizing"}, "agent-A",
            expected_version=version,
        )

        # Second writer with same old version fails
        with pytest.raises(VersionConflictError):
            populated_state.write(
                StateNamespace.CAMPAIGN, "camp-001",
                {"status": "monitoring"}, "agent-B",
                expected_version=version,
            )


class TestTransactions:
    """Multi-key transactional writes."""

    def test_transaction_commits_all(self, state_manager):
        writes = [
            (StateNamespace.CAMPAIGN, "camp-001", {"status": "active"}),
            (StateNamespace.CAMPAIGN, "camp-002", {"status": "active"}),
            (StateNamespace.WORKFLOW, "wf-001", {"stage": "start"}),
        ]
        result = state_manager.transaction_write(writes, writer_id="orchestrator")
        assert result.success is True
        assert state_manager.read(StateNamespace.CAMPAIGN, "camp-001") is not None
        assert state_manager.read(StateNamespace.CAMPAIGN, "camp-002") is not None
        assert state_manager.read(StateNamespace.WORKFLOW, "wf-001") is not None

    def test_transaction_rollback_on_conflict(self, populated_state):
        # Pre-existing state at version 1
        writes = [
            (StateNamespace.CAMPAIGN, "camp-001", {"status": "new"}),
            (StateNamespace.CAMPAIGN, "camp-new", {"status": "active"}),
        ]
        # Force a version conflict on first key
        result = populated_state.transaction_write(
            writes, writer_id="agent-x", expected_versions={"campaign:camp-001": 0}
        )
        assert result.success is False
        # camp-new should NOT have been created (rollback)
        assert populated_state.read(StateNamespace.CAMPAIGN, "camp-new") is None


class TestTTL:
    """Time-to-live for ephemeral state entries."""

    def test_ttl_entry_expires(self, state_manager):
        state_manager.write(
            StateNamespace.AGENT, "heartbeat-001",
            {"alive": True}, "agent-001",
            ttl_seconds=30,
        )
        entry = state_manager.read(StateNamespace.AGENT, "heartbeat-001")
        assert entry is not None

        # Simulate expiration
        entry.expires_at = datetime.utcnow() - timedelta(seconds=1)
        state_manager._store["agent:heartbeat-001"] = entry
        expired = state_manager.read(StateNamespace.AGENT, "heartbeat-001")
        assert expired is None

    def test_no_ttl_never_expires(self, state_manager):
        state_manager.write(
            StateNamespace.CAMPAIGN, "camp-permanent",
            {"status": "active"}, "system",
        )
        entry = state_manager.read(StateNamespace.CAMPAIGN, "camp-permanent")
        assert entry is not None
        assert entry.expires_at is None

    def test_cleanup_removes_expired(self, state_manager):
        state_manager.write(
            StateNamespace.AGENT, "temp-1", {"x": 1}, "sys", ttl_seconds=1,
        )
        state_manager.write(
            StateNamespace.AGENT, "temp-2", {"x": 2}, "sys", ttl_seconds=1,
        )
        state_manager.write(
            StateNamespace.AGENT, "perm", {"x": 3}, "sys",
        )

        # Expire the temp entries
        for key in ["agent:temp-1", "agent:temp-2"]:
            state_manager._store[key].expires_at = datetime.utcnow() - timedelta(seconds=10)

        removed = state_manager.cleanup_expired()
        assert removed == 2
        assert state_manager.read(StateNamespace.AGENT, "perm") is not None
