"""CORS wiring for the deployed frontend.

In production the frontend is served from Netlify and calls the API on Render
directly, so the browser sends an ``Origin`` header and preflights every
``application/json`` POST. ``FRONTEND_ORIGIN`` names the one origin allowed to
do that. When it is unset — local development, which is same-origin through the
Vite dev proxy — no middleware is added at all.

These expected header values come from the Fetch spec's CORS protocol, not from
``plans/``: cross-origin deployment postdates the P0 acceptance table.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from arbitrageiq.api import _configure_cors

ORIGIN = "https://arbitrageiq2.netlify.app"


def _app(monkeypatch, origin: str | None) -> FastAPI:
    """The smallest app that carries the same CORS wiring as the real one."""
    if origin is None:
        monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("FRONTEND_ORIGIN", origin)
    app = FastAPI()
    _configure_cors(app)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:  # pragma: no cover - trivial probe route
        return {"status": "ok"}

    @app.post("/api/v1/simulate/sku")
    def simulate() -> dict[str, bool]:  # pragma: no cover - trivial probe route
        return {"ok": True}

    return app


def _preflight(client: TestClient, path: str, method: str = "POST") -> Response:
    return client.options(
        path,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_preflight_from_frontend_origin_is_allowed(monkeypatch):
    response = _preflight(TestClient(_app(monkeypatch, ORIGIN)), "/api/v1/simulate/sku")

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN
    allowed = response.headers["access-control-allow-methods"]
    assert "POST" in allowed and "OPTIONS" in allowed
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_actual_request_carries_the_allow_origin_header(monkeypatch):
    client = TestClient(_app(monkeypatch, ORIGIN))

    response = client.get("/api/v1/health", headers={"Origin": ORIGIN})

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unset_origin_adds_no_cors_wiring(monkeypatch):
    client = TestClient(_app(monkeypatch, None))

    assert "access-control-allow-origin" not in client.get("/api/v1/health").headers
    assert "access-control-allow-origin" not in _preflight(client, "/api/v1/health").headers


def test_other_origins_are_not_allowed(monkeypatch):
    client = TestClient(_app(monkeypatch, ORIGIN))

    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_origin_is_normalised_before_it_is_allowed(monkeypatch):
    """A trailing slash in the dashboard value must not break the exact match."""
    client = TestClient(_app(monkeypatch, f"{ORIGIN}/"))

    response = client.get("/api/v1/health", headers={"Origin": ORIGIN})

    assert response.headers["access-control-allow-origin"] == ORIGIN
