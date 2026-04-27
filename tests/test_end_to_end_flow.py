import json
from pathlib import Path

from gateway_api.query_service import build_query_facade
from ingest_api.storage import FileEventStore, redact_payload
from processor.job_runner import JobRunner

from ai_monitoring_contracts.models import IngestLogRequest, LogQueryFilters


def test_file_backed_end_to_end_flow(tmp_path: Path):
    log_path = tmp_path / "logs.jsonl"
    aggregate_path = tmp_path / "aggregates.json"

    store = FileEventStore(log_path)
    payload = IngestLogRequest(
        request_id="req-e2e",
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="Contact me at sam@example.com",
        input_messages=[{"role": "user", "content": "Call +1 202 555 0111"}],
        output_messages=[{"role": "assistant", "content": "Support call summary"}],
        latency_ms=315,
        tokens={"input": 8, "output": 12},
        cost_total=0.0024,
        feature="support-summary",
    )
    assert store.write_log(redact_payload(payload, True, True)) is True

    runner = JobRunner(mode="file", file_store_path=str(log_path), aggregate_store_path=str(aggregate_path))
    runner.run_once()

    facade = build_query_facade("file", str(log_path), str(aggregate_path))
    summary = facade.get_dashboard_summary("demo-workspace")
    logs = facade.list_logs("demo-workspace", LogQueryFilters(limit=10))
    detail = facade.get_log_detail("demo-workspace", "req-e2e")

    assert summary.total_requests == 1
    assert logs.total == 1
    assert detail is not None
    assert "[redacted-email]" in (detail.system_prompt or "")
    assert "[redacted-phone]" in detail.input_messages[0].content
