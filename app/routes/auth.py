import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.config import settings
from app.exceptions import GitHubAuthError

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_SCOPE = "repo"
FRONTEND_CALLBACK_PATH = "/auth/callback"
FRONTEND_TOKEN_PARAM = "token"  # noqa: S105 # nosec B105
OAUTH_STATE_COOKIE_NAME = "github_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/auth/github"
OAUTH_STATE_COOKIE_MAX_AGE_SECONDS = 600
OAUTH_STATE_BYTES = 32
HTTPS_SCHEME = "https"
INVALID_OAUTH_STATE_MESSAGE = "Invalid or expired OAuth state — log in again"

router = APIRouter(prefix="/auth/github", tags=["auth"])


@router.get("")
async def github_login(req: Request) -> RedirectResponse:
    """Redirect the user to GitHub's OAuth consent page with a CSRF state.

    The state is also stored in a short-lived HttpOnly cookie scoped to the
    callback path, so the callback can verify GitHub echoed back the value
    this browser was issued.
    """
    client_id = req.app.state.github_service.client_id
    oauth_state = secrets.token_urlsafe(OAUTH_STATE_BYTES)
    query = urlencode(
        {"client_id": client_id, "scope": GITHUB_OAUTH_SCOPE, "state": oauth_state}
    )
    response = RedirectResponse(f"{GITHUB_OAUTH_AUTHORIZE_URL}?{query}")
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        oauth_state,
        max_age=OAUTH_STATE_COOKIE_MAX_AGE_SECONDS,
        path=OAUTH_STATE_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=req.url.scheme == HTTPS_SCHEME,
    )
    return response


@router.get("/callback")
async def github_callback(code: str, state: str, req: Request) -> RedirectResponse:
    """Verify the OAuth state, exchange the code for a token, and redirect.

    The token is passed in the URL fragment rather than the query string —
    fragments are never sent to servers, so it stays out of server logs and
    Referer headers.
    """
    expected_state = req.cookies.get(OAUTH_STATE_COOKIE_NAME)
    if expected_state is None or not secrets.compare_digest(state, expected_state):
        raise GitHubAuthError(INVALID_OAUTH_STATE_MESSAGE)
    access_token = await req.app.state.github_service.exchange_code_for_token(code)
    fragment = urlencode({FRONTEND_TOKEN_PARAM: access_token})
    response = RedirectResponse(
        f"{settings.frontend_url}{FRONTEND_CALLBACK_PATH}#{fragment}"
    )
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)
    return response
