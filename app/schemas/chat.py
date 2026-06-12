from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Schema for validating client question input."""
    question: str
    document_id: int
    conversation_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    """Schema for returning messages details."""
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Schema for basic conversation details."""
    id: int
    title: str
    document_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    """Schema for conversation including its full chat messages history."""
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True
