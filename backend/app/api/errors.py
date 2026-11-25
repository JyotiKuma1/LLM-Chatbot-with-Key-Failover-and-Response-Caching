import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.gateway.llm_gateway import AllProvidersUnavailable

logger = logging.getLogger("errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AllProvidersUnavailable)
    async def providers_unavailable_handler(
        request: Request, exc: AllProvidersUnavailable
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "all providers unavailable"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        serializable_errors = []
        for err in exc.errors():
            item = dict(err)
            if "ctx" in item and isinstance(item["ctx"], dict):
                item["ctx"] = {k: str(v) for k, v in item["ctx"].items()}
            serializable_errors.append(item)
        return JSONResponse(
            status_code=422,
            content={"detail": serializable_errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("Unhandled exception type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error"},
        )
