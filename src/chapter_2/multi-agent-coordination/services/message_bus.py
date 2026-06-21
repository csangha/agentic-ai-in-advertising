"""
A2A Message Bus — reliable message delivery between agents.

Supports:
- Request/Response (synchronous via AgentCore invoke)
- Fire-and-Forget (async via Kafka)
- Broadcast (publish to topic, all subscribers receive)
- Message persistence for audit (30-day retention)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional
import uuid
import json


class MessageType(str, Enum):
    TASK_REQUEST = "TASK_REQUEST"
    TASK_RESPONSE = "TASK_RESPONSE"
    NOTIFICATION = "NOTIFICATION"
    QUERY = "QUERY"
    HANDOFF = "HANDOFF"


class Priority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class TaskMessage:
    message_id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:8]}")
    sender_id: str = ""
    recipient_id: str = ""  # "*" for broadcast
    message_type: MessageType = MessageType.TASK_REQUEST
    priority: Priority = Priority.NORMAL
    payload: Dict = field(default_factory=dict)
    timeout_ms: int = 30000
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    parent_message_id: Optional[str] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


class MessageBus:
    """
    In-memory message bus (production: backed by Kafka + AgentCore A2A).
    Provides at-least-once delivery semantics.
    """

    def __init__(self):
        self._queues: Dict[str, List[TaskMessage]] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[TaskMessage] = []
        self._dead_letter: List[TaskMessage] = []

    def send(self, message: TaskMessage) -> str:
        """
        Send a message to a specific agent or broadcast.
        Returns the message_id for tracking.
        """
        self._history.append(message)

        if message.recipient_id == "*":
            # Broadcast to all subscribers
            for queue_messages in self._queues.values():
                queue_messages.append(message)
            for callbacks in self._subscribers.values():
                for cb in callbacks:
                    cb(message)
        else:
            # Direct delivery
            if message.recipient_id not in self._queues:
                self._queues[message.recipient_id] = []
            self._queues[message.recipient_id].append(message)

            # Notify subscribers
            if message.recipient_id in self._subscribers:
                for cb in self._subscribers[message.recipient_id]:
                    cb(message)

        return message.message_id

    def receive(self, agent_id: str, max_messages: int = 10) -> List[TaskMessage]:
        """Receive pending messages for an agent (FIFO, priority-ordered)."""
        if agent_id not in self._queues:
            return []

        queue = self._queues[agent_id]
        # Sort by priority (CRITICAL first) then by created_at
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.NORMAL: 2, Priority.LOW: 3}
        queue.sort(key=lambda m: (priority_order.get(m.priority, 2), m.created_at))

        messages = queue[:max_messages]
        self._queues[agent_id] = queue[max_messages:]
        return messages

    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge receipt of a message."""
        for msg in self._history:
            if msg.message_id == message_id:
                msg.acknowledged = True
                msg.acknowledged_at = datetime.utcnow()
                return True
        return False

    def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe to messages for an agent (real-time notification)."""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        self._subscribers[agent_id].append(callback)

    def get_history(self, correlation_id: Optional[str] = None, limit: int = 100) -> List[TaskMessage]:
        """Query message history for audit."""
        if correlation_id:
            return [m for m in self._history if m.correlation_id == correlation_id][:limit]
        return self._history[-limit:]

    def get_dead_letter(self) -> List[TaskMessage]:
        """Get undeliverable messages."""
        return self._dead_letter
