from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import persona_ai.fastapi_app as fastapi_app
from persona_ai.chat_contract import TokenChunk


class FakeProvider:
    provider_name = "fake-provider"

    def __init__(self, model: str = "fake-model", error: str | None = None) -> None:
        self.model = model
        self._error = error

    def stream(self, request):  # noqa: ANN001
        if self._error:
            yield TokenChunk(trace_id=request.trace_id, index=0, text=self._error, done=True)
            return

        text = "streamed assistant response"
        words = text.split()
        for idx, word in enumerate(words):
            yield TokenChunk(
                trace_id=request.trace_id,
                index=idx,
                text=f"{word}{'' if idx == len(words) - 1 else ' '}",
                done=idx == len(words) - 1,
            )


@pytest.fixture()
def client(monkeypatch):
    runtime = fastapi_app.AppRuntime()
    monkeypatch.setattr(fastapi_app, "runtime", runtime)
    monkeypatch.setattr(runtime, "provider_for", lambda provider, model: FakeProvider(model or "fake-model"))
    return TestClient(fastapi_app.app)


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_turn_returns_structured_payload(client: TestClient) -> None:
    payload = {
        "provider": "openai",
        "userText": "hello",
        "messages": [{"role": "user", "content": "hello"}],
        "turnId": 1,
        "user_id": "u-test",
        "session_id": "s-test",
    }
    resp = client.post("/api/v1/chat/turn", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["assistantText"] == "streamed assistant response"
    assert body["memory"]["l1"]["turnId"] == 1
    assert "traceId" in body


def test_chat_stream_sse_contains_token_and_done(client: TestClient) -> None:
    payload = {
        "provider": "openai",
        "userText": "hello stream",
        "messages": [{"role": "user", "content": "hello stream"}],
        "turnId": 2,
        "user_id": "u-stream",
        "session_id": "s-stream",
    }
    resp = client.post("/api/v1/chat/stream", json=payload)
    assert resp.status_code == 200
    text = resp.text
    assert "event: token" in text
    assert "event: done" in text
    assert "streamed assistant response" in text


def test_profile_and_wordcloud_endpoints(client: TestClient) -> None:
    payload = {
        "provider": "openai",
        "userText": "I prefer concise answers",
        "messages": [{"role": "user", "content": "I prefer concise answers"}],
        "turnId": 1,
        "user_id": "u-profile",
        "session_id": "s-profile",
    }
    chat_resp = client.post("/api/v1/chat/turn", json=payload)
    assert chat_resp.status_code == 200

    profile_resp = client.get("/api/v1/profiles/u-profile/current")
    assert profile_resp.status_code == 200
    assert profile_resp.json()["profile"] is not None

    cloud_resp = client.get("/api/v1/profiles/u-profile/visualization/wordcloud")
    assert cloud_resp.status_code == 200
    assert isinstance(cloud_resp.json()["entries"], list)


def test_delete_user_scope(client: TestClient) -> None:
    payload = {
        "provider": "openai",
        "userText": "hello",
        "messages": [{"role": "user", "content": "hello"}],
        "turnId": 1,
        "user_id": "u-delete",
        "session_id": "s-delete",
    }
    resp = client.post("/api/v1/chat/turn", json=payload)
    assert resp.status_code == 200

    delete_resp = client.delete("/api/v1/users/u-delete", params={"scope": "complete"})
    assert delete_resp.status_code == 200
    body = delete_resp.json()
    assert "deleted" in body


def test_provider_auth_error_maps_to_401(monkeypatch) -> None:
    runtime = fastapi_app.AppRuntime()
    monkeypatch.setattr(fastapi_app, "runtime", runtime)
    monkeypatch.setattr(
        runtime,
        "provider_for",
        lambda provider, model: FakeProvider(model or "fake-model", "[ProviderError:auth] HTTP Error 403: Forbidden"),
    )

    client = TestClient(fastapi_app.app)
    payload = {
        "provider": "openai",
        "userText": "hello",
        "messages": [{"role": "user", "content": "hello"}],
        "turnId": 1,
        "user_id": "u-auth",
        "session_id": "s-auth",
    }
    resp = client.post("/api/v1/chat/turn", json=payload)
    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail["code"] == "provider_auth"


def test_provider_health_endpoint(monkeypatch) -> None:
    runtime = fastapi_app.AppRuntime()
    monkeypatch.setattr(fastapi_app, "runtime", runtime)
    monkeypatch.setattr(runtime, "provider_for", lambda provider, model: FakeProvider(model or "fake-model"))

    client = TestClient(fastapi_app.app)
    resp = client.get("/api/v1/providers/health", params={"provider": "openai"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
