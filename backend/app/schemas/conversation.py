"""Pydantic schemas for conversations and pre-RAG questions."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PolicyContextSummary(BaseModel):
    """Context of the currently resolved policy within a conversation."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    policy_number: str
    customer_id: str
    customer_name: str
    line_of_business: Optional[str] = None
    product_name: Optional[str] = None
    status: Optional[str] = None


class ConversationCreateRequest(BaseModel):
    """Request payload to initiate a new conversation session."""

    policy_id: Optional[str] = None


class ConversationContextUpdateRequest(BaseModel):
    """Request payload to set/update resolved policy context for a conversation."""

    policy_id: str = Field(..., min_length=1, description="Policy UUID to bind to context")


class ConversationResponse(BaseModel):
    """Conversation session response with optional policy context."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    employee_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    policy_context: Optional[PolicyContextSummary] = None


class QuestionSubmitRequest(BaseModel):
    """Request payload for submitting a policy question."""

    question: str = Field(..., min_length=1, description="Question text submitted by employee")


class QuestionSubmitResponse(BaseModel):
    """Pre-RAG structured question response ready for evidence retrieval."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    question: str
    policy_context: PolicyContextSummary
    timestamp: datetime
    status: str = "ready_for_retrieval"


class QuestionHistoryItem(BaseModel):
    """Historical question entry within a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    question: str
    policy_id: Optional[str] = None
    status: str
    created_at: datetime
