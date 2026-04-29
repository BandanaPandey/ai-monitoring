import json

from processor.job_runner import JobRunner


def test_job_runner_writes_aggregate_snapshot(tmp_path):
    file_store = tmp_path / "logs.jsonl"
    aggregate_store = tmp_path / "aggregates.json"
    file_store.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "request_id": "req-1",
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "latency_ms": 120,
                        "tokens": {"input": 2, "output": 3, "total": 5},
                        "cost_total": 0.001,
                        "input_messages": [{"role": "user", "content": "hello"}],
                        "output_messages": [{"role": "assistant", "content": "hi"}],
                    }
                ),
                json.dumps(
                    {
                        "request_id": "req-2",
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "latency_ms": 480,
                        "status": "error",
                        "error_type": "timeout",
                        "tokens": {"input": 2, "output": 0, "total": 2},
                        "cost_total": 0.0005,
                        "input_messages": [{"role": "user", "content": "test"}],
                        "output_messages": [{"role": "assistant", "content": "timeout"}],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    runner = JobRunner(
        mode="file",
        file_store_path=str(file_store),
        aggregate_store_path=str(aggregate_store),
        clickhouse_dsn="",
    )
    results = runner.run_once()

    assert len(results) == 3
    snapshot = json.loads(aggregate_store.read_text(encoding="utf-8"))
    assert snapshot["total_requests"] == 2
    assert snapshot["top_errors"][0]["error_type"] == "timeout"
