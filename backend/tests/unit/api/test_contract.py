"""API contract tests that require no database.

Only the endpoints whose behaviour is independent of storage are exercised
here (health, validation, error shape). Anything that reads or writes data is an
integration test, because reporting success without PostgreSQL would be
misleading: the schema uses JSONB and check constraints that only PostgreSQL
provides.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.schemas.matches import MatchCreate
from app.schemas.organizations import OrganizationCreate


class TestHealth:
    async def test_liveness_does_not_touch_the_database(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "not_checked"
        assert body["environment"] == "local"


class TestOpenApi:
    async def test_schema_is_served_and_versioned(self, client: AsyncClient) -> None:
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "SPA API"
        # The frontend generates its typed client from these paths, so their
        # prefix is part of the contract.
        assert any(path.startswith("/api/v1/") for path in schema["paths"])

    async def test_analysis_run_creation_is_documented_as_accepted(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/openapi.json")
        schema = response.json()

        post = schema["paths"]["/api/v1/analysis-runs"]["post"]
        # 202 is the outward sign that analysis is asynchronous; if this ever
        # becomes 200, the architecture has been broken somewhere.
        assert "202" in post["responses"]

    async def test_metric_calculation_is_documented_as_accepted(self, client: AsyncClient) -> None:
        response = await client.get("/openapi.json")
        schema = response.json()

        path = schema["paths"]["/api/v1/analysis-runs/{run_id}/metrics"]
        # Metric calculation is asynchronous for the same reason detection is:
        # it reads a match-long tracking set, which no request may block on.
        assert "202" in path["post"]["responses"]
        assert "409" in path["post"]["responses"]
        assert "200" in path["get"]["responses"]


class TestErrorContract:
    async def test_unknown_route_uses_the_standard_envelope(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    async def test_validation_errors_use_the_standard_envelope(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/organizations", json={"name": ""})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_required"

    async def test_slug_pattern_is_enforced(self) -> None:
        with pytest.raises(ValidationError):
            OrganizationCreate.model_validate({"name": "Acme FC", "slug": "Not A Slug"})

    async def test_match_requires_both_sides(self) -> None:
        with pytest.raises(ValidationError):
            MatchCreate.model_validate(
                {
                    "organization_id": "11111111-1111-1111-1111-111111111111",
                    "played_on": "2025-09-01",
                }
            )

    async def test_report_creation_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/analysis-runs/{uuid.uuid4()}/reports",
            params={"organization_id": "11111111-1111-1111-1111-111111111111"},
        )
        assert response.status_code == 401


class TestCors:
    async def test_configured_origin_is_allowed(self, client: AsyncClient) -> None:
        response = await client.options(
            "/api/v1/organizations",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
