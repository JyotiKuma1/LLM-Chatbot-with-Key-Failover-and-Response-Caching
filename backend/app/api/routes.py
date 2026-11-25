import asyncio
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.schemas import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    HistoryMessage,
    HistoryResponse,
    ModelsResponse,
    SessionSummary,
    SessionsResponse,
)
from app.gateway.simulate import parse_simulate_header

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    repo = request.app.state.repo
    gateway = request.app.state.gateway

    db_ok = False
    try:
        db_ok = await asyncio.to_thread(repo.ping)
    except Exception:
        db_ok = False

    keys_count = len(gateway.keys)
    cache_enabled = gateway.cache_enabled

    if not db_ok or keys_count < 1:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "database or keys unavailable",
                "keys_configured": keys_count,
                "cache_enabled": cache_enabled,
            },
        )

    return HealthResponse(
        status="ok",
        keys_configured=keys_count,
        cache_enabled=cache_enabled,
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models(request: Request):
    settings = request.app.state.settings
    return ModelsResponse(
        default_model=settings.model,
        models=settings.models,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    x_simulate_failure: str | None = Header(default=None, alias="X-Simulate-Failure"),
):
    settings = request.app.state.settings
    chat_service = request.app.state.chat_service

    simulate = parse_simulate_header(x_simulate_failure, settings.simulation_enabled)
    reply, metadata = await chat_service.chat(
        session_id=payload.session_id,
        message=payload.message,
        system_prompt=payload.system_prompt,
        simulate=simulate,
        model=payload.model,
    )

    return ChatResponse(
        session_id=payload.session_id,
        reply=reply,
        metadata=ChatMetadata(**metadata),
    )


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions(request: Request):
    repo = request.app.state.repo
    rows = await asyncio.to_thread(repo.list_sessions)
    return SessionsResponse(sessions=[SessionSummary(**row) for row in rows])


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    repo = request.app.state.repo
    deleted = await asyncio.to_thread(repo.delete_session, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "deleted", "session_id": session_id}


@router.get(
    "/sessions/{session_id}/messages",
    response_model=HistoryResponse,
    response_model_exclude_none=True,
)
async def get_session_messages(session_id: str, request: Request):
    repo = request.app.state.repo
    exists = await asyncio.to_thread(repo.session_exists, session_id)
    if not exists:
        raise HTTPException(status_code=404, detail="session not found")

    rows = await asyncio.to_thread(repo.get_messages_with_metadata, session_id)
    sys_prompt = await asyncio.to_thread(repo.get_session_prompt, session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryMessage(**row) for row in rows],
        system_prompt=sys_prompt,
    )
