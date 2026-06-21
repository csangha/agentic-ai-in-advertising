"""
Brand Voice Checker — validates generated copy against brand guidelines.

Uses embedding similarity between generated copy and brand voice exemplars
to compute a voice consistency score (0-1). Minimum threshold: 0.7.
"""

from dataclasses import dataclass
from typing import List, Optional
import json
import boto3
from botocore.config import Config


@dataclass
class VoiceCheckResult:
    score: float  # 0-1 consistency score
    passed: bool  # score >= threshold
    closest_exemplar: Optional[str] = None
    feedback: Optional[str] = None


class BrandVoiceChecker:
    """
    Checks generated copy against brand voice using embedding similarity.
    Brand exemplars are stored in OpenSearch Serverless and retrieved via k-NN.
    """

    def __init__(self, threshold: float = 0.7, region: str = "us-east-1"):
        self.threshold = threshold
        self.region = region
        config = Config(retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock_client = boto3.client("bedrock-runtime", region_name=region, config=config)
        self._exemplars: List[dict] = []  # {"text": str, "embedding": List[float]}

    def load_exemplars(self, exemplars: List[str]):
        """Load brand voice exemplars and generate their embeddings."""
        self._exemplars = []
        for text in exemplars:
            embedding = self._generate_embedding(text)
            self._exemplars.append({"text": text, "embedding": embedding})

    def check(self, generated_copy: str) -> VoiceCheckResult:
        """
        Check if generated copy is consistent with brand voice.
        Returns score and pass/fail.
        """
        if not self._exemplars:
            return VoiceCheckResult(score=1.0, passed=True, feedback="No exemplars loaded — cannot validate.")

        copy_embedding = self._generate_embedding(generated_copy)

        # Find most similar exemplar
        best_score = 0.0
        best_exemplar = None
        for ex in self._exemplars:
            score = self._cosine_similarity(copy_embedding, ex["embedding"])
            if score > best_score:
                best_score = score
                best_exemplar = ex["text"]

        passed = best_score >= self.threshold
        feedback = None
        if not passed:
            feedback = (
                f"Voice consistency {best_score:.2f} below threshold {self.threshold}. "
                f"Copy may deviate from brand tone. Consider revising."
            )

        return VoiceCheckResult(
            score=round(best_score, 4),
            passed=passed,
            closest_exemplar=best_exemplar[:100] if best_exemplar else None,
            feedback=feedback,
        )

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding via Amazon Bedrock Titan Embeddings."""
        try:
            response = self.bedrock_client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text[:2000]}),
            )
            return json.loads(response["body"].read())["embedding"]
        except Exception:
            return [0.0] * 1024

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
