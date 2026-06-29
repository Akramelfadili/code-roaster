from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import AIProviderError, MalformedAIResponseError
from app.reviewer import CodeReviewer
from app.routes.review import router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.reviewer = CodeReviewer()
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


app.include_router(router)
