import os
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient


def _fake_optimizer_result() -> Dict[str, Any]:
    return {
        "success_spec": {
            "intent_summary": "Summarize intent",
            "expected_behavior": "Expected behavior",
            "key_constraints": ["Must be concise"],
        },
        "final_synthesis": {"prompt": "Optimized prompt"},
    }


def test_optimize_tribunal_disabled_no_outbound_calls(monkeypatch: pytest.MonkeyPatch):
    # Ensure Tribunal is disabled
    monkeypatch.setenv("TRIBUNAL_ENABLED", "false")

    import api_server

    class FakeOptimizer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, idea: str) -> Dict[str, Any]:
            return _fake_optimizer_result()

    def _raise_if_called():
        raise AssertionError("get_tribunal_service() should not be called when TRIBUNAL_ENABLED=false")

    monkeypatch.setattr(api_server, "PromptimaV2", FakeOptimizer)
    monkeypatch.setattr(api_server, "get_tribunal_service", _raise_if_called)

    client = TestClient(api_server.app)
    resp = client.post(
        "/api/optimize",
        json={"idea": "hello world", "use_cache": True},
        headers={"X-User-Tier": "synapse"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    tribunal = body["tribunal"]
    assert set(["run_id", "status", "verdicts_url"]).issubset(set(tribunal.keys()))
    assert tribunal["status"] == "disabled"
    assert tribunal["run_id"] is None
    assert tribunal["verdicts_url"] is None


def test_tribunal_service_calls_upload_intent_trigger_in_order(monkeypatch: pytest.MonkeyPatch):
    """Smoke-test the Promptly -> CVA contract: /upload -> /api/intent -> /api/trigger_scan.

    Uses a fake httpx.AsyncClient so no network calls are made.
    """

    import consensus_prompt_optimizer.tribunal_service as ts

    # Patch module-level constants used by TribunalService.__init__
    monkeypatch.setattr(ts, "TRIBUNAL_API_URL", "http://mock-cva:8001")
    monkeypatch.setattr(ts, "TRIBUNAL_API_TOKEN", "test-token")

    calls: List[Dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: Optional[Dict[str, Any]] = None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self) -> Dict[str, Any]:
            return self._payload

    class FakeAsyncClient:
        def __init__(self, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            calls.append({"url": url, **kwargs})

            if url.endswith("/upload"):
                return FakeResponse(200, {})

            if url.endswith("/api/intent"):
                # Ensure webhook-first hooks are passed when provided
                body = kwargs.get("json") or {}
                assert "run_id" in body
                assert "project_id" in body
                assert "success_spec" in body
                assert body.get("initiator", {}).get("callback_url") == "https://example.com/webhook"
                assert body.get("initiator", {}).get("callback_bearer_token") == "cb-token"
                return FakeResponse(200, {})

            if url.endswith("/api/trigger_scan"):
                body = kwargs.get("json") or {}
                assert "run_id" in body
                return FakeResponse(202, {"status": "queued", "verdicts_url": "http://mock-cva:8001/api/verdicts/xyz"})

            return FakeResponse(404, {})

    monkeypatch.setattr(ts.httpx, "AsyncClient", FakeAsyncClient)

    from consensus_prompt_optimizer.schemas import SuccessSpec

    svc = ts.TribunalService()
    # Call async path via asyncio.run so we can include webhook-first callback args
    import asyncio

    resp = asyncio.run(
        svc.submit_for_verification_async(
            success_spec=SuccessSpec(intent_summary="i", expected_behavior="e", key_constraints=[]),
            optimized_prompt="opt",
            original_idea="orig",
            user_tier="synapse",
            callback_url="https://example.com/webhook",
            callback_bearer_token="cb-token",
            scan_mode="full",
        )
    )

    assert resp.success is True
    assert resp.status == "queued"
    assert resp.run_id
    assert resp.verdicts_url

    urls = [c["url"] for c in calls]
    assert len(urls) == 3
    assert urls[0].endswith("/upload")
    assert urls[1].endswith("/api/intent")
    assert urls[2].endswith("/api/trigger_scan")

    # Ensure Authorization header is present
    for c in calls:
        headers = c.get("headers") or {}
        assert headers.get("Authorization") == "Bearer test-token"
