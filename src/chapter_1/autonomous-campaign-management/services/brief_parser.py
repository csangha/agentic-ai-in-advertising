"""
Brief Parser — uses Bedrock Claude to parse natural language campaign briefs
into structured parameters.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import boto3
from botocore.config import Config


@dataclass
class ParsedBrief:
    budget_total: float
    target_cpa: float
    audience_description: str
    platforms: List[str]
    sentiment_threshold: float
    geographic_targeting: Optional[str]
    age_range: Optional[str]
    interests: Optional[List[str]]
    campaign_duration_days: Optional[int]
    constraints: Dict[str, str]
    is_valid: bool
    validation_errors: List[str]


class BriefParser:
    """
    Parses natural language campaign briefs using Claude on Amazon Bedrock.
    Extracts structured parameters and validates for contradictions.
    """

    def __init__(self, region: str = "us-east-1", model_id: str = "us.anthropic.claude-sonnet-4-20250514"):
        self.region = region
        self.model_id = model_id
        config = Config(retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock_client = boto3.client(
            "bedrock-runtime", region_name=region, config=config
        )

    def parse(self, raw_text: str) -> ParsedBrief:
        """
        Parse a natural language brief into structured parameters.

        Example input:
        "Launch a premium fitness tracker campaign. $50,000 budget.
        Target affluent, health-conscious consumers aged 25–55 in major U.S. metros.
        Achieve $35 CPA. Maintain sentiment above 75%."
        """
        extraction_prompt = self._build_extraction_prompt(raw_text)

        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "temperature": 0.0,
                    "messages": [
                        {"role": "user", "content": extraction_prompt}
                    ],
                }),
            )

            result = json.loads(response["body"].read())
            content = result["content"][0]["text"]

            # Parse the JSON response from Claude
            parsed = json.loads(content)
            return self._build_result(parsed)

        except Exception as e:
            return ParsedBrief(
                budget_total=0,
                target_cpa=0,
                audience_description="",
                platforms=[],
                sentiment_threshold=0.75,
                geographic_targeting=None,
                age_range=None,
                interests=None,
                campaign_duration_days=None,
                constraints={},
                is_valid=False,
                validation_errors=[f"Failed to parse brief: {str(e)}"],
            )

    def _build_extraction_prompt(self, raw_text: str) -> str:
        return f"""Extract structured campaign parameters from this brief. Return ONLY valid JSON.

Brief:
\"\"\"{raw_text}\"\"\"

Extract and return JSON with these fields:
{{
    "budget_total": <number in dollars>,
    "target_cpa": <number in dollars>,
    "audience_description": "<free text description>",
    "platforms": ["meta", "google", "tiktok", "amazon"],
    "sentiment_threshold": <0-1 decimal>,
    "geographic_targeting": "<geography or null>",
    "age_range": "<e.g. 25-55 or null>",
    "interests": ["<interest1>", "<interest2>"] or null,
    "campaign_duration_days": <number or null>,
    "constraints": {{"key": "value"}}
}}

Rules:
- If a value is not specified, use null
- Default platforms to ["meta", "google", "tiktok", "amazon"] if not specified
- Default sentiment_threshold to 0.75 if not specified
- Budget and CPA must be numbers (remove $ signs)
- Return ONLY the JSON object, no other text"""

    def _build_result(self, parsed: dict) -> ParsedBrief:
        """Build ParsedBrief from LLM output and validate."""
        errors = []

        budget = parsed.get("budget_total", 0) or 0
        cpa = parsed.get("target_cpa", 0) or 0
        platforms = parsed.get("platforms") or ["meta", "google", "tiktok", "amazon"]
        sentiment = parsed.get("sentiment_threshold", 0.75) or 0.75

        # Validation checks
        if budget <= 0:
            errors.append("Budget must be a positive number.")
        if cpa <= 0:
            errors.append("Target CPA must be a positive number.")
        if budget > 0 and cpa > 0 and budget < cpa:
            errors.append(f"Budget (${budget}) is less than target CPA (${cpa}) — cannot acquire even 1 customer.")
        if not platforms:
            errors.append("At least one platform must be specified.")
        if sentiment < 0 or sentiment > 1:
            errors.append("Sentiment threshold must be between 0 and 1.")

        return ParsedBrief(
            budget_total=budget,
            target_cpa=cpa,
            audience_description=parsed.get("audience_description", ""),
            platforms=platforms,
            sentiment_threshold=sentiment,
            geographic_targeting=parsed.get("geographic_targeting"),
            age_range=parsed.get("age_range"),
            interests=parsed.get("interests"),
            campaign_duration_days=parsed.get("campaign_duration_days"),
            constraints=parsed.get("constraints", {}),
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )
