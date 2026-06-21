"""
Approval Queue — manages human-in-the-loop decision approvals.

Features:
- SLA enforcement (decisions must be reviewed within deadline)
- Priority ordering (critical > high > normal)
- Batch approval for similar decisions
- Auto-escalation on SLA breach
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import uuid
import heapq


class ApprovalPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_ESCALATED = "auto_escalated"


@dataclass
class ApprovalRequest:
    """A decision awaiting human approval."""
    request_id: str = field(default_factory=lambda: f"apr-{uuid.uuid4().hex[:8]}")
    decision_id: str = ""
    decision_type: str = ""
    description: str = ""
    proposed_action: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    confidence_score: float = 0.0
    risk_level: str = "medium"
    impact_estimate_usd: float = 0.0
    priority: ApprovalPriority = ApprovalPriority.NORMAL
    status: ApprovalStatus = ApprovalStatus.PENDING
    sla_deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: str = ""
    campaign_id: str = ""
    batch_key: Optional[str] = None


@dataclass
class ApprovalResult:
    """Result of an approval action."""
    request_id: str
    status: ApprovalStatus
    reviewer_id: Optional[str] = None
    notes: str = ""
    reviewed_at: Optional[datetime] = None


class ApprovalQueue:
    """
    Priority queue for human approval of AI-generated decisions.

    Implements SLA tracking, batch approvals, and auto-escalation.
    """

    def __init__(self, default_sla_hours: float = 4.0, escalation_channel: str = "slack"):
        self.default_sla_hours = default_sla_hours
        self.escalation_channel = escalation_channel
        self._queue: list[tuple[int, float, ApprovalRequest]] = []  # (neg_priority, timestamp, request)
        self._requests: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalResult] = []

    def submit(self, request: ApprovalRequest) -> ApprovalRequest:
        """Submit a decision for human approval."""
        if not request.sla_deadline:
            sla_hours = self._compute_sla(request)
            request.sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

        self._requests[request.request_id] = request
        # Use negative priority for max-heap behavior with heapq (min-heap)
        heapq.heappush(
            self._queue,
            (-request.priority.value, request.created_at.timestamp(), request),
        )
        return request

    def _compute_sla(self, request: ApprovalRequest) -> float:
        """Compute SLA deadline based on priority and risk."""
        if request.priority == ApprovalPriority.CRITICAL:
            return 0.5  # 30 minutes
        elif request.priority == ApprovalPriority.HIGH:
            return 1.0
        elif request.risk_level == "high":
            return 2.0
        return self.default_sla_hours

    def get_next(self) -> Optional[ApprovalRequest]:
        """Get the highest priority pending request."""
        while self._queue:
            neg_priority, ts, request = self._queue[0]
            if request.status == ApprovalStatus.PENDING:
                return request
            heapq.heappop(self._queue)
        return None

    def get_pending(self, limit: int = 50) -> list[ApprovalRequest]:
        """Get all pending requests ordered by priority then creation time."""
        pending = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]
        pending.sort(key=lambda r: (-r.priority.value, r.created_at))
        return pending[:limit]

    def approve(self, request_id: str, reviewer_id: str, notes: str = "") -> ApprovalResult:
        """Approve a pending request."""
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} not found or not pending")

        request.status = ApprovalStatus.APPROVED
        request.reviewed_at = datetime.utcnow()
        request.reviewer_id = reviewer_id
        request.reviewer_notes = notes

        result = ApprovalResult(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            reviewer_id=reviewer_id,
            notes=notes,
            reviewed_at=request.reviewed_at,
        )
        self._history.append(result)
        return result

    def reject(self, request_id: str, reviewer_id: str, notes: str = "") -> ApprovalResult:
        """Reject a pending request."""
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} not found or not pending")

        request.status = ApprovalStatus.REJECTED
        request.reviewed_at = datetime.utcnow()
        request.reviewer_id = reviewer_id
        request.reviewer_notes = notes

        result = ApprovalResult(
            request_id=request_id,
            status=ApprovalStatus.REJECTED,
            reviewer_id=reviewer_id,
            notes=notes,
            reviewed_at=request.reviewed_at,
        )
        self._history.append(result)
        return result

    def batch_approve(
        self, batch_key: str, reviewer_id: str, notes: str = ""
    ) -> list[ApprovalResult]:
        """Approve all pending requests with the same batch key."""
        results = []
        matching = [
            r for r in self._requests.values()
            if r.batch_key == batch_key and r.status == ApprovalStatus.PENDING
        ]
        for request in matching:
            result = self.approve(request.request_id, reviewer_id, notes)
            results.append(result)
        return results

    def check_sla_breaches(self) -> list[ApprovalRequest]:
        """Find requests that have breached their SLA deadline."""
        now = datetime.utcnow()
        breached = []
        for request in self._requests.values():
            if request.status != ApprovalStatus.PENDING:
                continue
            if request.sla_deadline and now > request.sla_deadline:
                request.status = ApprovalStatus.AUTO_ESCALATED
                breached.append(request)
        return breached

    def get_stats(self) -> dict:
        """Get queue statistics."""
        pending = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]
        approved = [r for r in self._requests.values() if r.status == ApprovalStatus.APPROVED]
        rejected = [r for r in self._requests.values() if r.status == ApprovalStatus.REJECTED]

        avg_review_time = None
        reviewed = [r for r in self._requests.values() if r.reviewed_at]
        if reviewed:
            times = [(r.reviewed_at - r.created_at).total_seconds() for r in reviewed]
            avg_review_time = sum(times) / len(times)

        return {
            "total_requests": len(self._requests),
            "pending": len(pending),
            "approved": len(approved),
            "rejected": len(rejected),
            "avg_review_time_seconds": avg_review_time,
            "approval_rate": len(approved) / max(len(approved) + len(rejected), 1),
        }
