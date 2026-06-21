"""
Coordination MCP Server — tools for multi-agent coordination.

Provides agent registration, discovery, messaging, shared state,
and vector memory search capabilities.

Deployed to Amazon Bedrock AgentCore.
Tools:
- register_agent: Register an agent with capabilities
- discover_agents: Find agents by capability or role
- send_message: Send a message to another agent via the event bus
- read_state: Read from shared state store
- write_state: Write to shared state store with optimistic locking
- search_memory: Semantic search over vector memory
"""

from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
from typing import Optional
import json
import os

mcp = FastMCP("coordination", description="Multi-agent coordination tools")

# In-memory registry (production uses Aurora + Redis)
_agent_registry: dict = {}
_shared_state: dict = {}
_message_log: list = []


@mcp.tool()
def register_agent(
    agent_id: str,
    name: str,
    capabilities: str,
    endpoint: str,
    role: str = "worker",
) -> str:
    """
    Register an agent in the coordination registry.

    Args:
        agent_id: Unique identifier for the agent
        name: Human-readable agent name
        capabilities: Comma-separated list of capabilities
        endpoint: A2A endpoint URL for the agent
        role: Agent role (orchestrator, worker, monitor)

    Returns:
        JSON confirmation with registration details
    """
    registration = {
        "agent_id": agent_id,
        "name": name,
        "capabilities": [c.strip() for c in capabilities.split(",")],
        "endpoint": endpoint,
        "role": role,
        "registered_at": datetime.utcnow().isoformat(),
        "last_heartbeat": datetime.utcnow().isoformat(),
        "status": "active",
    }
    _agent_registry[agent_id] = registration

    return json.dumps({
        "success": True,
        "agent_id": agent_id,
        "message": f"Agent '{name}' registered successfully",
        "total_agents": len(_agent_registry),
    }, indent=2)


@mcp.tool()
def discover_agents(
    capability: Optional[str] = None,
    role: Optional[str] = None,
    status: str = "active",
) -> str:
    """
    Discover registered agents by capability, role, or status.

    Args:
        capability: Filter by capability keyword (partial match)
        role: Filter by role (orchestrator, worker, monitor)
        status: Filter by status (active, inactive)

    Returns:
        JSON list of matching agents with their endpoints and capabilities
    """
    heartbeat_timeout = datetime.utcnow() - timedelta(seconds=60)
    results = []

    for agent in _agent_registry.values():
        # Check heartbeat freshness
        last_hb = datetime.fromisoformat(agent["last_heartbeat"])
        is_active = last_hb > heartbeat_timeout
        agent_status = "active" if is_active else "inactive"

        if status and agent_status != status:
            continue
        if role and agent["role"] != role:
            continue
        if capability:
            cap_match = any(capability.lower() in c.lower() for c in agent["capabilities"])
            if not cap_match:
                continue

        results.append({
            "agent_id": agent["agent_id"],
            "name": agent["name"],
            "capabilities": agent["capabilities"],
            "endpoint": agent["endpoint"],
            "role": agent["role"],
            "status": agent_status,
            "last_heartbeat": agent["last_heartbeat"],
        })

    return json.dumps({
        "agents": results,
        "count": len(results),
        "query": {"capability": capability, "role": role, "status": status},
        "retrieved_at": datetime.utcnow().isoformat(),
    }, indent=2)


@mcp.tool()
def send_message(
    from_agent_id: str,
    to_agent_id: str,
    message_type: str,
    payload: str,
    priority: str = "normal",
) -> str:
    """
    Send a message to another agent via the event bus.

    Args:
        from_agent_id: Sender agent ID
        to_agent_id: Recipient agent ID
        message_type: Message type (task, query, response, event, heartbeat)
        payload: JSON payload string
        priority: Message priority (low, normal, high, urgent)

    Returns:
        JSON confirmation with message ID and delivery status
    """
    message = {
        "message_id": f"msg-{len(_message_log)+1:06d}",
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "message_type": message_type,
        "payload": payload,
        "priority": priority,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "delivered" if to_agent_id in _agent_registry else "queued",
    }
    _message_log.append(message)

    # Update heartbeat for sender
    if from_agent_id in _agent_registry:
        _agent_registry[from_agent_id]["last_heartbeat"] = datetime.utcnow().isoformat()

    return json.dumps({
        "success": True,
        "message_id": message["message_id"],
        "status": message["status"],
        "recipient_found": to_agent_id in _agent_registry,
    }, indent=2)


@mcp.tool()
def read_state(
    namespace: str,
    key: str,
) -> str:
    """
    Read a value from the shared state store.

    Args:
        namespace: State namespace (e.g., 'campaign', 'workflow', 'agent')
        key: State key within the namespace

    Returns:
        JSON with the stored value and metadata (version, last_updated)
    """
    full_key = f"{namespace}:{key}"
    entry = _shared_state.get(full_key)

    if entry is None:
        return json.dumps({
            "found": False,
            "namespace": namespace,
            "key": key,
            "value": None,
        }, indent=2)

    return json.dumps({
        "found": True,
        "namespace": namespace,
        "key": key,
        "value": entry["value"],
        "version": entry["version"],
        "last_updated": entry["last_updated"],
        "updated_by": entry.get("updated_by"),
    }, indent=2)


@mcp.tool()
def write_state(
    namespace: str,
    key: str,
    value: str,
    expected_version: int = -1,
    updated_by: str = "unknown",
) -> str:
    """
    Write a value to the shared state store with optimistic locking.

    Args:
        namespace: State namespace (e.g., 'campaign', 'workflow', 'agent')
        key: State key within the namespace
        value: JSON value to store
        expected_version: Expected current version for optimistic locking (-1 to skip)
        updated_by: Agent ID performing the write

    Returns:
        JSON confirmation with new version number, or conflict error
    """
    full_key = f"{namespace}:{key}"
    existing = _shared_state.get(full_key)
    current_version = existing["version"] if existing else 0

    # Optimistic locking check
    if expected_version >= 0 and existing and existing["version"] != expected_version:
        return json.dumps({
            "success": False,
            "error": "version_conflict",
            "message": f"Expected version {expected_version} but current is {existing['version']}",
            "current_version": existing["version"],
        }, indent=2)

    new_version = current_version + 1
    _shared_state[full_key] = {
        "value": value,
        "version": new_version,
        "last_updated": datetime.utcnow().isoformat(),
        "updated_by": updated_by,
    }

    return json.dumps({
        "success": True,
        "namespace": namespace,
        "key": key,
        "version": new_version,
        "previous_version": current_version,
    }, indent=2)


@mcp.tool()
def search_memory(
    query: str,
    namespace: str = "all",
    top_k: int = 5,
) -> str:
    """
    Semantic search over the vector memory store.

    Args:
        query: Natural language search query
        namespace: Memory namespace to search ('all' for cross-namespace)
        top_k: Number of results to return

    Returns:
        JSON list of relevant memory entries with similarity scores
    """
    # In production: vector search via OpenSearch Serverless
    # Placeholder with sample results
    results = {
        "query": query,
        "namespace": namespace,
        "results": [
            {
                "id": "mem-001",
                "content": f"Previous coordination context related to: {query}",
                "namespace": namespace if namespace != "all" else "workflow",
                "similarity_score": 0.89,
                "metadata": {
                    "source_agent": "orchestrator",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
        ],
        "total_results": 1,
        "retrieved_at": datetime.utcnow().isoformat(),
    }
    return json.dumps(results, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
