from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import router
from app.config import get_settings
from app.db.repository import ChatRepository
from app.gateway.llm_gateway import LLMGateway
from app.services.chat_service import ChatService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repo = ChatRepository(settings.db_url)
    repo.init_schema()

    gateway = LLMGateway(
        keys=settings.keys,
        model=settings.model,
        timeout=settings.timeout_seconds,
        fallback_models=settings.fallback_models,
    )
    chat_service = ChatService(
        repo=repo,
        gateway=gateway,
        default_system_prompt=settings.system_prompt,
    )

    app.state.settings = settings
    app.state.repo = repo
    app.state.gateway = gateway
    app.state.chat_service = chat_service
    yield
    await gateway.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LLM Chatbot Gateway",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
