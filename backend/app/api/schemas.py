from typing import Any
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str
    system_prompt: str | None = None
    model: str | None = None

    @field_validator("model")
    @classmethod
    def _clean_model(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed or None

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not 1 <= len(trimmed) <= 128:
            raise ValueError("session_id must be 1-128 characters after trimming")
        return trimmed

    @field_validator("message")
    @classmethod
    def _trim_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not 1 <= len(trimmed) <= 4000:
            raise ValueError("message must be 1-4000 characters after trimming")
        return trimmed


class ChatMetadata(BaseModel):
    resolution_source: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: str | None = None
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata


class HistoryMessage(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] | None = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]
    system_prompt: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    system_prompt: str | None = None
    created_at: str
    updated_at: str
    message_count: int


class SessionsResponse(BaseModel):
    sessions: list[SessionSummary]


class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool


class ModelsResponse(BaseModel):
    default_model: str
    models: list[str]
