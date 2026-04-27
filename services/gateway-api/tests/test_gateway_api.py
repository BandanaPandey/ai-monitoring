import json
from pathlib import Path

from fastapi.testclient import TestClient

from gateway_api import app as app_module
from gateway_api.query_service import build_query_facade


client = TestClient(app_module.app)


def seed_logs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "request_id": "req-a",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "latency_ms": 120,
            "tokens": {"input": 5, "output": 7, "total": 12},
            "cost_total": 0.0012,
            "input_messages": [{"role": "user", "content": "summarize"}],
            "output_messages": [{"role": "assistant", "content": "summary"}],
        },
        {
            "request_id": "req-b",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "latency_ms": 850,
            "status": "error",
            "error_type": "timeout",
            "tokens": {"input": 5, "output": 0, "total": 5},
            "cost_total": 0.0006,
            "input_messages": [{"role": "user", "content": "report"}],
            "output_messages": [{"role": "assistant", "content": "timeout"}],
        },
    ]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def auth_header() -> dict[str, str]:
    response = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_summary_requires_auth():
    response = client.get("/v1/dashboard/summary")
    assert response.status_code == 401


def test_dashboard_summary_and_log_detail(tmp_path):
    file_path = tmp_path / "logs.jsonl"
    seed_logs(file_path)
    app_module.query_service = build_query_facade("file", str(file_path), str(tmp_path / "aggregates.json"))

    summary = client.get("/v1/dashboard/summary", headers=auth_header())
    assert summary.status_code == 200
    assert summary.json()["total_requests"] >= 2

    logs = client.get("/v1/logs", headers=auth_header())
    assert logs.status_code == 200
    first = logs.json()["items"][0]["request_id"]

    detail = client.get(f"/v1/logs/{first}", headers=auth_header())
    assert detail.status_code == 200
    assert detail.json()["request_id"] == first


def test_compare_and_filters(tmp_path):
    file_path = tmp_path / "logs.jsonl"
    seed_logs(file_path)
    app_module.query_service = build_query_facade("file", str(file_path), str(tmp_path / "aggregates.json"))

    filtered = client.get("/v1/logs?status=error", headers=auth_header())
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    compared = client.post(
        "/v1/logs/compare",
        json={"left_request_id": "req-a", "right_request_id": "req-b"},
        headers=auth_header(),
    )
    assert compared.status_code == 200
    assert "left_text" in compared.json()
