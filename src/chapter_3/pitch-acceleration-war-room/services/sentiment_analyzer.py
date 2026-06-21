"""
Sentiment Analyzer — aspect-based sentiment with ensemble voting.

Features:
- Aspect extraction (product features, brand attributes)
- Ensemble of 3 models with majority voting
- Confidence calibration
- Temporal sentiment tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import statistics


class Sentiment(Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


@dataclass
class AspectSentiment:
    """Sentiment for a specific aspect of a product or brand."""
    aspect: str
    sentiment: Sentiment
    confidence: float
    text_evidence: str = ""
    model_votes: list[str] = field(default_factory=list)


@dataclass
class SentimentResult:
    """Complete sentiment analysis result for a text."""
    text: str
    overall_sentiment: Sentiment
    overall_confidence: float
    aspects: list[AspectSentiment]
    ensemble_agreement: float  # 0.0-1.0, how much models agreed
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ModelPrediction:
    """A single model's sentiment prediction."""
    model_name: str
    sentiment: Sentiment
    confidence: float
    aspects: dict[str, Sentiment] = field(default_factory=dict)


class SentimentModel:
    """Base class for sentiment models in the ensemble."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, text: str, aspects: list[str]) -> ModelPrediction:
        """Predict sentiment for text and specified aspects."""
        raise NotImplementedError


class RuleBasedModel(SentimentModel):
    """Rule-based sentiment using keyword matching."""

    POSITIVE_WORDS = {
        "love", "great", "amazing", "excellent", "perfect", "best",
        "fantastic", "wonderful", "outstanding", "impressive", "innovative",
    }
    NEGATIVE_WORDS = {
        "hate", "terrible", "awful", "worst", "broken", "disappointing",
        "horrible", "useless", "waste", "frustrating", "overpriced",
    }

    def __init__(self):
        super().__init__("rule_based")

    def predict(self, text: str, aspects: list[str]) -> ModelPrediction:
        words = set(text.lower().split())
        pos_count = len(words & self.POSITIVE_WORDS)
        neg_count = len(words & self.NEGATIVE_WORDS)

        if pos_count > neg_count:
            sentiment = Sentiment.POSITIVE if pos_count - neg_count < 3 else Sentiment.VERY_POSITIVE
            confidence = min(0.9, 0.5 + (pos_count - neg_count) * 0.1)
        elif neg_count > pos_count:
            sentiment = Sentiment.NEGATIVE if neg_count - pos_count < 3 else Sentiment.VERY_NEGATIVE
            confidence = min(0.9, 0.5 + (neg_count - pos_count) * 0.1)
        else:
            sentiment = Sentiment.NEUTRAL
            confidence = 0.5

        aspect_sentiments = {}
        for aspect in aspects:
            # Simple: check if aspect mentioned near positive/negative words
            aspect_lower = aspect.lower()
            if aspect_lower in text.lower():
                aspect_sentiments[aspect] = sentiment
            else:
                aspect_sentiments[aspect] = Sentiment.NEUTRAL

        return ModelPrediction(
            model_name=self.model_name,
            sentiment=sentiment,
            confidence=confidence,
            aspects=aspect_sentiments,
        )


class VaderStyleModel(SentimentModel):
    """VADER-style valence scoring model."""

    VALENCE_SCORES = {
        "love": 0.8, "great": 0.6, "amazing": 0.7, "good": 0.4,
        "hate": -0.8, "terrible": -0.7, "bad": -0.5, "awful": -0.8,
        "excellent": 0.7, "poor": -0.6, "fantastic": 0.7, "horrible": -0.8,
        "innovative": 0.5, "overpriced": -0.6, "reliable": 0.5, "broken": -0.7,
        "comfortable": 0.4, "accurate": 0.5, "inaccurate": -0.6, "sleek": 0.4,
    }

    def __init__(self):
        super().__init__("vader_style")

    def predict(self, text: str, aspects: list[str]) -> ModelPrediction:
        words = text.lower().split()
        scores = [self.VALENCE_SCORES.get(w, 0.0) for w in words]
        compound = sum(scores) / max(len(words), 1)

        if compound >= 0.3:
            sentiment = Sentiment.VERY_POSITIVE
        elif compound >= 0.1:
            sentiment = Sentiment.POSITIVE
        elif compound <= -0.3:
            sentiment = Sentiment.VERY_NEGATIVE
        elif compound <= -0.1:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL

        confidence = min(0.95, 0.5 + abs(compound))

        aspect_sentiments = {aspect: sentiment for aspect in aspects}
        return ModelPrediction(
            model_name=self.model_name,
            sentiment=sentiment,
            confidence=confidence,
            aspects=aspect_sentiments,
        )


class TransformerProxyModel(SentimentModel):
    """
    Proxy for transformer-based sentiment model.
    In production, this would call a fine-tuned model on SageMaker.
    """

    def __init__(self):
        super().__init__("transformer_proxy")

    def predict(self, text: str, aspects: list[str]) -> ModelPrediction:
        # Simplified proxy — in production calls SageMaker endpoint
        text_lower = text.lower()
        pos_signals = sum(1 for w in ["love", "great", "amazing", "best", "innovative", "excellent"] if w in text_lower)
        neg_signals = sum(1 for w in ["hate", "terrible", "worst", "broken", "overpriced", "disappointing"] if w in text_lower)

        score = (pos_signals - neg_signals) / max(pos_signals + neg_signals, 1)

        if score > 0.5:
            sentiment = Sentiment.VERY_POSITIVE
        elif score > 0:
            sentiment = Sentiment.POSITIVE
        elif score < -0.5:
            sentiment = Sentiment.VERY_NEGATIVE
        elif score < 0:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL

        confidence = min(0.92, 0.6 + abs(score) * 0.3)
        aspect_sentiments = {aspect: sentiment for aspect in aspects}

        return ModelPrediction(
            model_name=self.model_name,
            sentiment=sentiment,
            confidence=confidence,
            aspects=aspect_sentiments,
        )


class SentimentAnalyzer:
    """
    Ensemble sentiment analyzer using majority voting across 3 models.

    Combines rule-based, VADER-style, and transformer proxy models.
    Final sentiment is determined by majority vote with confidence
    weighted by model agreement.
    """

    SENTIMENT_ORDER = [
        Sentiment.VERY_NEGATIVE,
        Sentiment.NEGATIVE,
        Sentiment.NEUTRAL,
        Sentiment.POSITIVE,
        Sentiment.VERY_POSITIVE,
    ]

    def __init__(self):
        self.models: list[SentimentModel] = [
            RuleBasedModel(),
            VaderStyleModel(),
            TransformerProxyModel(),
        ]

    def analyze(self, text: str, aspects: list[str] = None) -> SentimentResult:
        """
        Analyze sentiment using ensemble of 3 models with majority vote.

        Args:
            text: Text to analyze
            aspects: Optional list of aspects to evaluate

        Returns:
            SentimentResult with overall and per-aspect sentiment
        """
        if aspects is None:
            aspects = []

        # Collect predictions from all models
        predictions = [model.predict(text, aspects) for model in self.models]

        # Majority vote for overall sentiment
        overall_votes = [p.sentiment for p in predictions]
        overall_sentiment = self._majority_vote(overall_votes)
        agreement = self._compute_agreement(overall_votes)

        # Average confidence weighted by agreement
        confidences = [p.confidence for p in predictions]
        overall_confidence = statistics.mean(confidences) * agreement

        # Per-aspect sentiment via majority vote
        aspect_results = []
        for aspect in aspects:
            aspect_votes = [p.aspects.get(aspect, Sentiment.NEUTRAL) for p in predictions]
            aspect_sentiment = self._majority_vote(aspect_votes)
            aspect_agreement = self._compute_agreement(aspect_votes)

            aspect_results.append(AspectSentiment(
                aspect=aspect,
                sentiment=aspect_sentiment,
                confidence=statistics.mean(confidences) * aspect_agreement,
                model_votes=[v.value for v in aspect_votes],
            ))

        return SentimentResult(
            text=text,
            overall_sentiment=overall_sentiment,
            overall_confidence=overall_confidence,
            aspects=aspect_results,
            ensemble_agreement=agreement,
        )

    def _majority_vote(self, votes: list[Sentiment]) -> Sentiment:
        """Return the most common sentiment (majority vote)."""
        if not votes:
            return Sentiment.NEUTRAL

        counts: dict[Sentiment, int] = {}
        for v in votes:
            counts[v] = counts.get(v, 0) + 1

        max_count = max(counts.values())
        winners = [s for s, c in counts.items() if c == max_count]

        if len(winners) == 1:
            return winners[0]

        # Tie-break: pick the one closest to neutral (conservative)
        neutral_idx = self.SENTIMENT_ORDER.index(Sentiment.NEUTRAL)
        return min(winners, key=lambda s: abs(self.SENTIMENT_ORDER.index(s) - neutral_idx))

    def _compute_agreement(self, votes: list[Sentiment]) -> float:
        """Compute agreement ratio (1.0 = unanimous, 0.33 = all different)."""
        if not votes:
            return 0.0
        most_common_count = max(votes.count(v) for v in set(votes))
        return most_common_count / len(votes)
