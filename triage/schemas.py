"""
Classification schemas and data validation models.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


CategoryType = Literal[
    'sales_inquiry',
    'billing',
    'technical_support',
    'account_access',
    'project_status',
    'complaint',
    'cancellation',
    'general_inquiry',
    'other',
]

UrgencyType = Literal['low', 'normal', 'high', 'critical']
SentimentType = Literal['positive', 'neutral', 'frustrated', 'angry']


class ClassificationSchema(BaseModel):
    """Structured output schema for email triage."""
    category: CategoryType = Field(
        ...,
        description="The primary operational category of the client inquiry."
    )
    urgency: UrgencyType = Field(
        ...,
        description="Assessed priority level based on business impact, client tier, and deadlines."
    )
    sentiment: SentimentType = Field(
        ...,
        description="Emotional tone and sentiment detected in the message."
    )
    intent_summary: str = Field(
        ...,
        description="Concise 1-2 sentence summary of what the client is communicating."
    )
    requested_action: str = Field(
        ...,
        description="The specific action, deliverable, or response requested by the sender."
    )
    suggested_team: str = Field(
        default="General Support",
        description="Recommended internal team or department (e.g. Tier 1 Support, Engineering, Billing)."
    )
    confidence_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Model confidence in the categorization between 0.0 and 1.0."
    )
    is_escalation_required: bool = Field(
        default=False,
        description="True if an immediate supervisor, account manager, or specialized engineer must be alerted."
    )
    urgency_reasoning: str = Field(
        default="",
        description="Clear justification for why the chosen urgency level was assigned."
    )
    escalation_reasoning: str = Field(
        default="",
        description="Justification for whether staff escalation is required."
    )
