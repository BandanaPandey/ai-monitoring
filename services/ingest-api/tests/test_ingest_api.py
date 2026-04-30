from fastapi.testclient import TestClient

from ingest_api import app as app_module
from ingest_api.storage import MemoryEventStore


def build_payload() -> dict:
    return {
        "request_id": "req-1234567890",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "latency_ms": 123,
        "system_prompt": "Email me at jane@example.com",
        "input_messages": [{"role": "user", "content": "Call +1 999 333 2222"}],
        "output_messages": [{"role": "assistant", "content": "Done"}],
        "tokens": {"input": 10, "output": 20},
        "user_id": "user-1234567890",
    }


def test_ingest_accepts_valid_log_and_redacts_pii():
    app_module.store = MemoryEventStore()
    client = TestClient(app_module.app)

    response = client.post("/v1/logs", json=build_payload(), headers={"x-api-key": "demo-ingest-key"})

    assert response.status_code == 200
    assert response.json()["deduplicated"] is False
    stored = app_module.store.items["req-1234567890"]
    assert "[redacted-email]" in stored.system_prompt
    assert "[redacted-phone]" in stored.input_messages[0].content
    assert stored.request_id == "req-1234567890"
    assert stored.user_id == "user-1234567890"


def test_ingest_marks_duplicate_request_ids():
    app_module.store = MemoryEventStore()
    client = TestClient(app_module.app)

    first = client.post("/v1/logs", json=build_payload(), headers={"x-api-key": "demo-ingest-key"})
    second = client.post("/v1/logs", json=build_payload(), headers={"x-api-key": "demo-ingest-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["deduplicated"] is True
