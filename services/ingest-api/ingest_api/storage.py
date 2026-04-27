from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Any

from ai_monitoring_contracts.models import IngestLogRequest

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{7,}\d")


def _redact_string(value: str, redact_emails: bool, redact_phones: bool) -> str:
    if redact_emails:
        value = EMAIL_RE.sub("[redacted-email]", value)
    if redact_phones:
        value = PHONE_RE.sub("[redacted-phone]", value)
    return value


def redact_payload(payload: IngestLogRequest, redact_emails: bool, redact_phones: bool) -> IngestLogRequest:
    data = payload.model_dump()

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return _redact_string(value, redact_emails, redact_phones)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    return IngestLogRequest.model_validate(walk(data))


@dataclass
class MemoryEventStore:
    items: dict[str, IngestLogRequest] = field(default_factory=dict)

    def write_log(self, payload: IngestLogRequest) -> bool:
        if payload.request_id in self.items:
            return False
        self.items[payload.request_id] = payload
        return True


@dataclass
class FileEventStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def _load(self) -> dict[str, IngestLogRequest]:
        items: dict[str, IngestLogRequest] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = IngestLogRequest.model_validate(json.loads(stripped))
                items[payload.request_id] = payload
        return items

    def write_log(self, payload: IngestLogRequest) -> bool:
        items = self._load()
        if payload.request_id in items:
            return False
        row = payload.model_dump(mode="json")
        row["_ingested_at"] = datetime.utcnow().isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return True


class ClickHouseEventStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def write_log(self, payload: IngestLogRequest) -> bool:
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError("clickhouse-connect is required for ClickHouse storage") from exc

        client = clickhouse_connect.get_client(dsn=self.dsn)
        client.command(
            """
            CREATE TABLE IF NOT EXISTS llm_logs (
                request_id String,
                trace_id Nullable(String),
                span_id Nullable(String),
                timestamp DateTime64(3),
                provider String,
                model String,
                model_version Nullable(String),
                system_prompt Nullable(String),
                input_messages String,
                output_messages String,
                raw_request String,
                raw_response String,
                latency_ms UInt32,
                status String,
                error_type Nullable(String),
                error_code Nullable(String),
                error_message Nullable(String),
                tokens_input UInt32,
                tokens_output UInt32,
                tokens_total UInt32,
                cost_input Float64,
                cost_output Float64,
                cost_total Float64,
                currency String,
                user_id Nullable(String),
                session_id Nullable(String),
                feature Nullable(String),
                endpoint Nullable(String),
                environment Nullable(String),
                tags String,
                metadata String
            ) ENGINE = MergeTree
            ORDER BY (timestamp, request_id)
            """
        )
        existing = client.query(
            "SELECT count() AS count FROM llm_logs WHERE request_id = %(request_id)s",
            parameters={"request_id": payload.request_id},
        )
        if existing.result_rows and existing.result_rows[0][0] > 0:
            return False

        row = payload.model_dump(mode="json")
        client.insert(
            "llm_logs",
            [[
                row["request_id"],
                row.get("trace_id"),
                row.get("span_id"),
                row["timestamp"],
                row["provider"],
                row["model"],
                row.get("model_version"),
                row.get("system_prompt"),
                str(row.get("input_messages", [])),
                str(row.get("output_messages", [])),
                str(row.get("raw_request", {})),
                str(row.get("raw_response", {})),
                row["latency_ms"],
                row["status"],
                row.get("error_type"),
                row.get("error_code"),
                row.get("error_message"),
                row["tokens"]["input"],
                row["tokens"]["output"],
                row["tokens"]["total"],
                row["cost_input"],
                row["cost_output"],
                row["cost_total"],
                row["currency"],
                row.get("user_id"),
                row.get("session_id"),
                row.get("feature"),
                row.get("endpoint"),
                row.get("environment"),
                str(row.get("tags", [])),
                str(row.get("metadata", {})),
            ]],
            column_names=[
                "request_id",
                "trace_id",
                "span_id",
                "timestamp",
                "provider",
                "model",
                "model_version",
                "system_prompt",
                "input_messages",
                "output_messages",
                "raw_request",
                "raw_response",
                "latency_ms",
                "status",
                "error_type",
                "error_code",
                "error_message",
                "tokens_input",
                "tokens_output",
                "tokens_total",
                "cost_input",
                "cost_output",
                "cost_total",
                "currency",
                "user_id",
                "session_id",
                "feature",
                "endpoint",
                "environment",
                "tags",
                "metadata",
            ],
        )
        return True


def build_store(backend: str, clickhouse_dsn: str, file_store_path: str) -> MemoryEventStore | FileEventStore | ClickHouseEventStore:
    if backend == "clickhouse":
        return ClickHouseEventStore(clickhouse_dsn)
    if backend == "file":
        return FileEventStore(Path(file_store_path))
    return MemoryEventStore()
