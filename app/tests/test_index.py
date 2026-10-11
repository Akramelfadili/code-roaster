from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.constants import IndexingJobState, IndexingStage
from app.exceptions import InvalidRepoUrlError, RepoNotFoundError
from app.models import IndexingJobStatus
from app.tests.mocks import SAMPLE_REPO_ID, SAMPLE_REPO_URL

_INDEX_REQUEST = {"repo_url": SAMPLE_REPO_URL, "github_token": "gh-token"}


class TestIndexRepo:
    async def test_happy_path_returns_202_with_pending_job(
        self, client: AsyncClient
    ) -> None:
        response = await client.post("/index/repo", json=_INDEX_REQUEST)

        assert response.status_code == 202
        data = response.json()
        assert data["repo_id"] == SAMPLE_REPO_ID
        assert data["state"] == IndexingJobState.PENDING
        assert "github_token" not in data

    async def test_runs_indexer_in_background_with_repo_collection(
        self, client: AsyncClient, mock_indexer: MagicMock
    ) -> None:
        await client.post("/index/repo", json=_INDEX_REQUEST)

        args = mock_indexer.index_repository.call_args.args
        assert args == (SAMPLE_REPO_URL, "gh-token", SAMPLE_REPO_ID)

    async def test_empty_repo_url_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/index/repo", json={"repo_url": "  ", "github_token": "gh-token"}
        )
        assert response.status_code == 422

    async def test_invalid_repo_url_returns_400(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        mock_github_service.parse_repo_url.side_effect = InvalidRepoUrlError("bad")
        response = await client.post("/index/repo", json=_INDEX_REQUEST)
        assert response.status_code == 400

    async def test_job_already_running_returns_409(
        self, client: AsyncClient, indexing_jobs: dict[str, IndexingJobStatus]
    ) -> None:
        indexing_jobs[SAMPLE_REPO_ID] = IndexingJobStatus(
            repo_id=SAMPLE_REPO_ID,
            repo_url=SAMPLE_REPO_URL,
            state=IndexingJobState.RUNNING,
        )
        response = await client.post("/index/repo", json=_INDEX_REQUEST)
        assert response.status_code == 409

    async def test_finished_job_can_be_reindexed(
        self, client: AsyncClient, mock_indexer: MagicMock
    ) -> None:
        await client.post("/index/repo", json=_INDEX_REQUEST)
        response = await client.post("/index/repo", json=_INDEX_REQUEST)

        assert response.status_code == 202
        assert mock_indexer.index_repository.await_count == 2


class TestIndexStatus:
    async def test_completed_job_returns_summary(self, client: AsyncClient) -> None:
        await client.post("/index/repo", json=_INDEX_REQUEST)

        response = await client.get(f"/index/status/{SAMPLE_REPO_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == IndexingJobState.COMPLETED
        assert data["stage"] is None
        assert data["summary"]["chunks_stored"] == 7
        assert data["error"] is None

    async def test_domain_failure_returns_failed_with_message(
        self, client: AsyncClient, mock_indexer: MagicMock
    ) -> None:
        async def fail_while_fetching(
            repo_url: str,
            github_token: str,
            collection_name: str,
            on_stage: Callable[[IndexingStage], None],
        ) -> None:
            on_stage(IndexingStage.FETCHING)
            raise RepoNotFoundError("Repository not found")

        mock_indexer.index_repository = AsyncMock(side_effect=fail_while_fetching)
        await client.post("/index/repo", json=_INDEX_REQUEST)

        data = (await client.get(f"/index/status/{SAMPLE_REPO_ID}")).json()

        assert data["state"] == IndexingJobState.FAILED
        assert data["stage"] == IndexingStage.FETCHING
        assert data["error"] == "Repository not found"
        assert data["summary"] is None

    async def test_unexpected_failure_hides_real_message(
        self, client: AsyncClient, mock_indexer: MagicMock
    ) -> None:
        mock_indexer.index_repository = AsyncMock(
            side_effect=RuntimeError("secret internals")
        )
        await client.post("/index/repo", json=_INDEX_REQUEST)

        data = (await client.get(f"/index/status/{SAMPLE_REPO_ID}")).json()

        assert data["state"] == IndexingJobState.FAILED
        assert data["error"] == "Internal server error"

    async def test_unknown_repo_id_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/index/status/nobody__nothing")
        assert response.status_code == 404
