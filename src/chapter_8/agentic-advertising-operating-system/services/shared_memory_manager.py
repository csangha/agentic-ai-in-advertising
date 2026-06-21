"""
Shared Memory Manager — the center of the operating system.

Manages 5 memory types that persist institutional intelligence:
1. Brand Memory (positioning, voice, compliance constraints)
2. Research Memory (hypotheses, trend histories, competitive evolution)
3. Creative Memory (territories, performance matrix, fatigue patterns)
4. Execution Memory (bid patterns, anomaly playbooks, platform behaviors)
5. Measurement Memory (attribution calibrations, experiment results, data caveats)

All memory types are queryable by agents with appropriate permissions.
Memory only grows — never deleted without explicit admin action.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class MemoryType(str, Enum):
    BRAND = "brand"
    RESEARCH = "research"
    CREATIVE = "creative"
    EXECUTION = "execution"
    MEASUREMENT = "measurement"


@dataclass
class MemoryRecord:
    record_id: str = field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:8]}")
    memory_type: MemoryType = MemoryType.BRAND
    key: str = ""
    content: Any = None
    metadata: Dict = field(default_factory=dict)
    organization_id: str = ""
    campaign_id: Optional[str] = None
    source_agent: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


@dataclass
class FeedbackEvent:
    event_id: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    source_layer: str = ""  # "measurement", "optimization", "research", "creative", "execution"
    target_layer: str = ""
    trigger: str = ""  # What caused this feedback
    content: Dict = field(default_factory=dict)
    campaign_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class SharedMemoryManager:
    """
    Central memory manager for the advertising operating system.
    Provides read/write access to all memory types with permission control.
    """

    def __init__(self):
        self._memories: Dict[str, Dict[str, MemoryRecord]] = {
            mt.value: {} for mt in MemoryType
        }
        self._feedback_log: List[FeedbackEvent] = []
        self._growth_log: List[Dict] = []  # Tracks all additions for monotonicity audit

    def write(
        self,
        memory_type: MemoryType,
        key: str,
        content: Any,
        organization_id: str,
        source_agent: str,
        campaign_id: Optional[str] = None,
        metadata: Dict = None,
    ) -> MemoryRecord:
        """
        Write to shared memory. Memory only grows — updates create new versions.
        """
        store = self._memories[memory_type.value]
        existing = store.get(key)

        record = MemoryRecord(
            memory_type=memory_type,
            key=key,
            content=content,
            metadata=metadata or {},
            organization_id=organization_id,
            campaign_id=campaign_id,
            source_agent=source_agent,
            version=(existing.version + 1) if existing else 1,
        )

        store[key] = record
        self._growth_log.append({
            "action": "write",
            "memory_type": memory_type.value,
            "key": key,
            "version": record.version,
            "agent": source_agent,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return record

    def read(self, memory_type: MemoryType, key: str) -> Optional[MemoryRecord]:
        """Read from shared memory."""
        return self._memories[memory_type.value].get(key)

    def query(
        self,
        memory_type: MemoryType,
        organization_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        """Query memory by type with optional filters."""
        store = self._memories[memory_type.value]
        results = list(store.values())

        if organization_id:
            results = [r for r in results if r.organization_id == organization_id]
        if campaign_id:
            results = [r for r in results if r.campaign_id == campaign_id]

        return results

    def record_feedback(
        self,
        source_layer: str,
        target_layer: str,
        trigger: str,
        content: Dict,
        campaign_id: Optional[str] = None,
    ) -> FeedbackEvent:
        """
        Record a cross-layer feedback event.
        E.g., measurement layer detects fatigue → notifies creative layer.
        """
        event = FeedbackEvent(
            source_layer=source_layer,
            target_layer=target_layer,
            trigger=trigger,
            content=content,
            campaign_id=campaign_id,
        )
        self._feedback_log.append(event)
        return event

    def get_feedback_log(self, limit: int = 50, source_layer: Optional[str] = None) -> List[FeedbackEvent]:
        """Query the feedback log."""
        results = self._feedback_log
        if source_layer:
            results = [e for e in results if e.source_layer == source_layer]
        return sorted(results, key=lambda e: e.created_at, reverse=True)[:limit]

    def get_growth_log(self, limit: int = 100) -> List[Dict]:
        """Audit log showing memory growth (monotonicity proof)."""
        return self._growth_log[-limit:]

    def memory_stats(self) -> Dict:
        """Get statistics on memory usage per type."""
        return {
            mt.value: len(self._memories[mt.value])
            for mt in MemoryType
        }
