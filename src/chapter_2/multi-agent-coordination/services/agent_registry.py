"""
Agent Registry — manages agent discovery, registration, and health monitoring.

Agents register their capabilities (AgentCard) and other agents discover
them via capability-based queries. Health is monitored via heartbeat.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
import uuid


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"
    DRAINING = "DRAINING"


@dataclass
class AgentCard:
    agent_id: str
    name: str
    version: str
    capabilities: List[str]  # e.g., ["creative_generation", "trend_detection"]
    supported_tasks: List[str]  # e.g., ["generate_ad_copy", "analyze_sentiment"]
    tools_required: List[str]  # MCP tools this agent needs
    endpoint: str  # A2A endpoint (AgentCore runtime ARN or URL)
    status: AgentStatus = AgentStatus.ACTIVE
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)


class AgentRegistry:
    """
    In-memory agent registry with Redis-backed persistence.
    Supports dynamic discovery and health monitoring.
    """

    def __init__(self, heartbeat_timeout_seconds: int = 30):
        self._agents: Dict[str, AgentCard] = {}
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)

    def register(self, card: AgentCard) -> AgentCard:
        """Register or update an agent. Rejects duplicates unless re-registering same agent."""
        if card.agent_id in self._agents:
            existing = self._agents[card.agent_id]
            if existing.name != card.name:
                raise ValueError(f"Agent ID {card.agent_id} already registered to {existing.name}")
        card.last_heartbeat = datetime.utcnow()
        card.status = AgentStatus.ACTIVE
        self._agents[card.agent_id] = card
        return card

    def deregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def heartbeat(self, agent_id: str) -> bool:
        """Record a heartbeat from an agent."""
        if agent_id in self._agents:
            self._agents[agent_id].last_heartbeat = datetime.utcnow()
            self._agents[agent_id].status = AgentStatus.ACTIVE
            return True
        return False

    def discover(self, capability: Optional[str] = None, task: Optional[str] = None) -> List[AgentCard]:
        """
        Discover agents by capability or supported task.
        Only returns ACTIVE agents.
        """
        self._check_health()
        results = []
        for agent in self._agents.values():
            if agent.status != AgentStatus.ACTIVE:
                continue
            if capability and capability not in agent.capabilities:
                continue
            if task and task not in agent.supported_tasks:
                continue
            results.append(agent)
        return results

    def get(self, agent_id: str) -> Optional[AgentCard]:
        """Get a specific agent by ID."""
        self._check_health()
        return self._agents.get(agent_id)

    def list_all(self) -> List[AgentCard]:
        """List all registered agents."""
        self._check_health()
        return list(self._agents.values())

    def _check_health(self):
        """Mark agents as UNAVAILABLE if heartbeat is stale."""
        now = datetime.utcnow()
        for agent in self._agents.values():
            if agent.status == AgentStatus.ACTIVE:
                if now - agent.last_heartbeat > self._heartbeat_timeout:
                    agent.status = AgentStatus.UNAVAILABLE
