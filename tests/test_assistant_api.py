"""Conversation HTTP ownership, CSRF, origin and payload contracts; no live APIs."""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.assistant import AssistantService
from app.chat_model import ChatPlan
from app.models import ExtractionUsage


@pytest.fixture
def conversation_client(catalog, monkeypatch):
    attempts = []
    async def planner(context):
        attempts.append(context)
        return ChatPlan(action="clarify", reply="سلام! چه کالایی می‌خواهی؟", search=None,
                        product_id=None, offer_ids=[], suggestions=["گوشی"]), ExtractionUsage(total_tokens=5)
    async def unused(*args, **kwargs):
        pytest.fail("Clarification and invalid native actions must not call another provider")
    service = AssistantService(catalog, planner=planner, explainer=unused, router=unused, modes=("car",))
    monkeypatch.setattr(main, "catalog", catalog)
    monkeypatch.setattr(main, "shopping_assistant", service)
    with TestClient(main.app) as client:
        config = client.get("/api/config").json()
        client.headers["X-App-Token"] = config["csrf_token"]
        yield client, service, attempts


def create(client):
    response = client.post("/api/conversations")
    assert response.status_code == 200
    return response.json()["id"]


def stable_state(view):
    return {key: value for key, value in view.items() if key != "expires_in_seconds"}


def test_conversation_create_turn_read_delete_and_owner_isolation(conversation_client):
    client, service, attempts = conversation_client
    conversation_id = create(client)
    endpoint = f"/api/conversations/{conversation_id}"
    first = client.get(endpoint)
    assert first.status_code == 200 and first.json()["stage"] == 1
    assert first.headers["cache-control"] == "no-store"
    result = client.post(endpoint + "/turns", json={"request_id": "hello", "message": "سلام"})
    assert result.status_code == 200 and result.json()["messages"][-1]["text"] == "سلام! چه کالایی می‌خواهی؟"
    assert result.json()["usage"][0]["total_tokens"] == 5 and len(attempts) == 1
    assert stable_state(client.get(endpoint).json()) == stable_state(result.json())
    with TestClient(main.app) as stranger:
        stranger.headers["X-App-Token"] = stranger.get("/api/config").json()["csrf_token"]
        assert stranger.get(endpoint).status_code == 404
        assert stranger.post(endpoint + "/turns", json={"request_id": "steal", "message": "سلام"}).status_code == 404
        assert stranger.delete(endpoint).status_code == 404
    assert len(attempts) == 1
    assert client.delete(endpoint).json() == {"deleted": True}
    assert client.get(endpoint).status_code == 404 and conversation_id not in service.sessions


def test_every_conversation_write_checks_csrf_and_origin(conversation_client):
    client, _, attempts = conversation_client
    endpoint = f"/api/conversations/{create(client)}"
    writes = [("POST", "/api/conversations", None),
              ("POST", endpoint + "/turns", {"request_id": "x", "message": "سلام"}),
              ("DELETE", endpoint, None)]
    for method, path, body in writes:
        assert client.request(method, path, json=body, headers={"X-App-Token": ""}).status_code == 403
        assert client.request(method, path, json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert attempts == [] and client.get(endpoint).status_code == 200


def test_request_replay_and_conflict_have_http_contract(conversation_client):
    client, _, attempts = conversation_client
    endpoint = f"/api/conversations/{create(client)}/turns"
    body = {"request_id": "same", "message": "سلام"}
    first = client.post(endpoint, json=body)
    duplicate = client.post(endpoint, json=body)
    assert first.status_code == duplicate.status_code == 200 and stable_state(first.json()) == stable_state(duplicate.json())
    assert client.post(endpoint, json={**body, "message": "گوشی"}).status_code == 409
    assert len(attempts) == 1


@pytest.mark.parametrize("body", [
    {"request_id": "x", "message": "x" * 2001},
    {"request_id": "x", "message": "سلام", "sql": "SELECT * FROM stores"},
    {"request_id": "x", "action": "execute_tool", "message": "سلام"},
    {"request_id": "x", "action": "compare", "offer_ids": ["p0", "p0"]},
    {"request_id": "x", "action": "compare", "offer_ids": ["p0"]},
    {"request_id": "x", "action": "inquiry", "offer_ids": ["p0", "p1"]},
    {"request_id": "x", "action": "set_location", "location": {"latitude": 91, "longitude": 51}, "travel_mode": "car"},
    {"request_id": "x", "action": "message", "message": "سلام", "location": {"latitude": 35, "longitude": 51}},
    {"request_id": "x", "action": "set_location", "location": {"latitude": 35, "longitude": 51}, "travel_mode": "bicycle"},
])
def test_invalid_and_unbounded_turn_payloads_rejected(conversation_client, body):
    client, _, attempts = conversation_client
    endpoint = f"/api/conversations/{create(client)}/turns"
    assert client.post(endpoint, json=body).status_code == 422 and attempts == []


def test_forged_native_ids_and_expired_conversation(conversation_client):
    client, service, attempts = conversation_client
    conversation_id = create(client)
    endpoint = f"/api/conversations/{conversation_id}"
    for body in [
        {"request_id": "fakeproduct", "action": "select_product", "product_id": "p0"},
        {"request_id": "fakeoffer", "action": "inquiry", "offer_ids": ["p0"]},
        {"request_id": "fakecompare", "action": "compare", "offer_ids": ["p0", "p1"]},
    ]:
        assert client.post(endpoint + "/turns", json=body).status_code == 422
    assert attempts == []
    service.sessions[conversation_id].created -= 3601
    assert client.get(endpoint).status_code == 404
    assert client.post(endpoint + "/turns", json={"request_id": "expired", "message": "سلام"}).status_code == 404
    assert client.delete(endpoint).status_code == 404


def test_conversation_config_does_not_expose_private_chat_or_route_keys(conversation_client, monkeypatch):
    client, _, _ = conversation_client
    monkeypatch.setenv("BOXAPI_API_KEY", "test-private-chat-secret")
    monkeypatch.setenv("BOXAPI_CHAT_MODEL", "approved-chat-model")
    monkeypatch.setenv("NESHAN_ROUTING_API_KEY", "test-private-routing-secret")
    response = client.get("/api/config")
    config = response.json()
    assert config["chat_configured"] is True and config["chat_missing"] == []
    assert config["routing_configured"] is True and config["travel_modes"] == ["car"]
    assert "test-private-chat-secret" not in response.text and "test-private-routing-secret" not in response.text
