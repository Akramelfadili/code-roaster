import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import AppError
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.pr import router as pr_router
from app.routes.review import router as review_router
from app.services.github import GitHubService
from app.services.reviewer import CodeReviewer

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.reviewer = CodeReviewer()
    app.state.github_service = GitHubService(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
    )
    yield


app = FastAPI(
    title="Code Roaster",
    description="AI-powered code review via the Anthropic API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(req: Request, exc: AppError) -> JSONResponse:
    """Log every domain exception once, then translate it to an HTTP response.

    This is the single place in the app responsible for both logging and
    HTTP translation. FastAPI resolves exception handlers by walking the
    exception's MRO, so registering this on `AppError` also catches every
    subclass (`GitHubError`, `PRNotFoundError`, `AIProviderError`, ...) —
    a new domain exception just needs to subclass `AppError` and set
    `status_code` (and optionally `log_level` / `user_message`); it never
    needs a handler function of its own.
    """
    message = f"{req.method} {req.url.path} -> {type(exc).__name__}: {exc}"
    if exc.debug_context:
        message = f"{message} ({exc.debug_context})"
    logger.log(
        exc.log_level, message, exc_info=exc if exc.log_level >= logging.ERROR else None
    )
    detail = exc.user_message if exc.user_message is not None else str(exc)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(req: Request, exc: Exception) -> JSONResponse:
    """Backstop for anything that isn't a modeled AppError — i.e. a real bug.

    Without this, an unmodeled exception falls through to Starlette's
    default handling, which never logs it through our logger (only uvicorn
    does, in its own format, with no request context) and returns a bare
    text response instead of our usual `{"detail": ...}` JSON shape.
    Always logs at ERROR with a full traceback and never exposes the raw
    exception message to the client, since it wasn't written with a client
    in mind.
    """
    logger.error(
        "%s %s -> unhandled %s: %s",
        req.method,
        req.url.path,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(review_router)
app.include_router(auth_router)
app.include_router(pr_router)
app.include_router(health_router)
