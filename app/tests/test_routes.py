from unittest.mock import MagicMock

from httpx import AsyncClient

from app.tests.mocks import SAMPLE_CODE


class TestHealth:
    async def test_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReview:
    async def test_happy_path_returns_non_empty_review(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/review", json={"code": SAMPLE_CODE, "language": "python"}
        )
        assert response.status_code == 200
        assert response.json()["review"]

    async def test_empty_code_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/review", json={"code": "   "})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("empty" in e["msg"].lower() for e in errors)

    async def test_missing_language_defaults_to_python(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        response = await client.post("/review", json={"code": SAMPLE_CODE})
        assert response.status_code == 200
        mock_reviewer.review.assert_awaited_once_with(SAMPLE_CODE, "python")


class TestReviewStream:
    async def test_happy_path_returns_content(self, client: AsyncClient) -> None:
        response = await client.post("/review/stream", json={"code": SAMPLE_CODE})
        assert response.status_code == 200
        assert response.text

    async def test_empty_code_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/review/stream", json={"code": ""})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("empty" in e["msg"].lower() for e in errors)


class TestReviewStructured:
    async def test_happy_path_returns_all_fields(self, client: AsyncClient) -> None:
        response = await client.post("/review/structured", json={"code": SAMPLE_CODE})
        assert response.status_code == 200
        data = response.json()
        for field in (
            "summary",
            "severity",
            "score",
            "bugs",
            "security_issues",
            "suggestions",
            "positives",
        ):
            assert field in data

    async def test_score_is_between_1_and_10(self, client: AsyncClient) -> None:
        response = await client.post("/review/structured", json={"code": SAMPLE_CODE})
        assert 1 <= response.json()["score"] <= 10

    async def test_severity_is_valid_literal(self, client: AsyncClient) -> None:
        response = await client.post("/review/structured", json={"code": SAMPLE_CODE})
        assert response.json()["severity"] in ("low", "medium", "high", "critical")

    async def test_empty_code_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/review/structured", json={"code": "  "})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("empty" in e["msg"].lower() for e in errors)
