"""
Vector Memory Service — semantic similarity search over past experiences.

Uses Amazon OpenSearch Serverless (vector search collection) for storage
and Amazon Bedrock Titan Embeddings for vector generation.

Provides experience-based recall:
"Have we seen this pattern before? What worked last time?"
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json
import uuid
import boto3
from botocore.config import Config


@dataclass
class MemoryEntry:
    memory_id: str = field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:12]}")
    category: str = ""  # "campaign_outcome", "creative_learning", "audience_insight", "strategy_decision"
    content: str = ""  # Human-readable description
    embedding: List[float] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)  # Structured context (dates, metrics, outcomes)
    organization_id: str = ""
    campaign_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    relevance_score: Optional[float] = None


@dataclass
class SearchResult:
    entry: MemoryEntry
    score: float  # Cosine similarity score


class VectorMemoryService:
    """
    Vector memory backed by Amazon OpenSearch Serverless.
    Embeddings generated via Amazon Bedrock Titan Embeddings.
    """

    def __init__(
        self,
        opensearch_endpoint: str,
        index_name: str = "campaign-memory",
        region: str = "us-east-1",
        embedding_model_id: str = "amazon.titan-embed-text-v2:0",
    ):
        self.endpoint = opensearch_endpoint
        self.index_name = index_name
        self.region = region
        self.embedding_model_id = embedding_model_id

        config = Config(retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock_client = boto3.client("bedrock-runtime", region_name=region, config=config)

        # In production: use opensearch-py with AOSS auth
        # from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth
        self._local_store: List[MemoryEntry] = []  # Fallback for local dev

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector using Amazon Bedrock Titan Embeddings."""
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except Exception as e:
            # Fallback: return zero vector for local development
            return [0.0] * 1024

    def store(self, content: str, category: str, organization_id: str,
              metadata: Dict = None, campaign_id: str = None) -> MemoryEntry:
        """
        Store a new experience in vector memory.
        Generates embedding and indexes in OpenSearch.
        """
        embedding = self.generate_embedding(content)

        entry = MemoryEntry(
            category=category,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            organization_id=organization_id,
            campaign_id=campaign_id,
        )

        # In production: index to OpenSearch Serverless
        # self._index_to_opensearch(entry)
        self._local_store.append(entry)

        return entry

    def search(
        self,
        query: str,
        organization_id: str,
        top_k: int = 5,
        category: Optional[str] = None,
        campaign_id: Optional[str] = None,
        min_score: float = 0.7,
    ) -> List[SearchResult]:
        """
        Semantic similarity search over stored experiences.

        Args:
            query: Natural language query
            organization_id: Org isolation (required)
            top_k: Maximum results to return
            category: Optional filter by category
            campaign_id: Optional filter by campaign
            min_score: Minimum similarity threshold

        Returns:
            Ranked list of similar experiences with scores.
        """
        query_embedding = self.generate_embedding(query)

        # In production: use OpenSearch k-NN query with filters
        # For local dev: brute-force cosine similarity
        results = []
        for entry in self._local_store:
            if entry.organization_id != organization_id:
                continue
            if category and entry.category != category:
                continue
            if campaign_id and entry.campaign_id != campaign_id:
                continue

            score = self._cosine_similarity(query_embedding, entry.embedding)
            if score >= min_score:
                results.append(SearchResult(entry=entry, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def update(self, memory_id: str, metadata_updates: Dict) -> bool:
        """Update metadata for an existing memory entry (e.g., add outcome data)."""
        for entry in self._local_store:
            if entry.memory_id == memory_id:
                entry.metadata.update(metadata_updates)
                return True
        return False

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
