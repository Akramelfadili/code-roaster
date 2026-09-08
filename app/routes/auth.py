from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.config import settings

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_SCOPE = "repo"
FRONTEND_CALLBACK_PATH = "/auth/callback"
FRONTEND_TOKEN_PARAM = "token"  # noqa: S105 # nosec B105

router = APIRouter(prefix="/auth/github", tags=["auth"])


@router.get("")
async def github_login(req: Request) -> RedirectResponse:
    """Redirect the user to GitHub's OAuth consent page."""
    client_id = req.app.state.github_service.client_id
    query = urlencode({"client_id": client_id, "scope": GITHUB_OAUTH_SCOPE})
    return RedirectResponse(f"{GITHUB_OAUTH_AUTHORIZE_URL}?{query}")


@router.get("/callback")
async def github_callback(code: str, req: Request) -> RedirectResponse:
    """Exchange the OAuth code for an access token and redirect to the frontend."""
    access_token = await req.app.state.github_service.exchange_code_for_token(code)
    frontend_url = settings.frontend_url
    query = urlencode({FRONTEND_TOKEN_PARAM: access_token})
    return RedirectResponse(f"{frontend_url}{FRONTEND_CALLBACK_PATH}?{query}")
