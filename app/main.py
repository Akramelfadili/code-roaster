from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

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

app.include_router(router)
