import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import (
    AIProviderError,
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    InvalidPRUrlError,
    MalformedAIResponseError,
    PRNotFoundError,
)
from app.reviewer import CodeReviewer
from app.routes.auth import router as auth_router
from app.routes.pr import router as pr_router
from app.routes.review import router as review_router
from app.services.github import GitHubService

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.reviewer = CodeReviewer()
    app.state.github_service = GitHubService(
        client_id=os.environ["GITHUB_CLIENT_ID"],
        client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    )
    yield


app = FastAPI(
    title="Code Roaster",
    description="AI-powered code review via the Anthropic API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(AIProviderError)
async def ai_provider_handler(req: Request, exc: AIProviderError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "AI provider unavailable"})


@app.exception_handler(MalformedAIResponseError)
async def malformed_response_handler(
    req: Request, exc: MalformedAIResponseError
) -> JSONResponse:
    return JSONResponse(
        status_code=500, content={"detail": "Unexpected response from AI"}
    )


@app.exception_handler(InvalidPRUrlError)
async def invalid_pr_url_handler(req: Request, exc: InvalidPRUrlError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(GitHubAuthError)
async def github_auth_handler(req: Request, exc: GitHubAuthError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(PRNotFoundError)
async def pr_not_found_handler(req: Request, exc: PRNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(GitHubRateLimitError)
async def github_rate_limit_handler(
    req: Request, exc: GitHubRateLimitError
) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(GitHubError)
async def github_error_handler(req: Request, exc: GitHubError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "GitHub API unavailable"})


app.include_router(review_router)
app.include_router(auth_router)
app.include_router(pr_router)
