from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .types import MessageRole

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class Document(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_size: int
    content: str
    chunks: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4000)
    document_ids: Optional[List[str]] = None

class ChatResponse(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}