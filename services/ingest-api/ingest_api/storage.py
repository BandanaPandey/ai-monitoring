from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_monitoring_contracts.models import IngestLogRequest
from ai_monitoring_contracts.persistence import (
    clickhouse_columns,
    ensure_clickhouse_tables,
    ensure_postgres_schema,
    log_to_clickhouse_row,
    parse_clickhouse_dsn,
    seed_workspace_auth,
)

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

    def bootstrap(self) -> None:
        return None

    def resolve_workspace(self, api_key: str) -> str | None:
        return "workspace-default" if api_key else None

    def write_log(self, payload: IngestLogRequest) -> bool:
        if payload.request_id in self.items:
            return False
        self.items[payload.request_id] = payload
        return True


@dataclass
class FileEventStore:
    path: Path
    default_api_key: str
    default_workspace_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def bootstrap(self) -> None:
        return None

    def resolve_workspace(self, api_key: str) -> str | None:
        if api_key == self.default_api_key:
            return self.default_workspace_id
        return None

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


@dataclass
class ClickHouseEventStore:
    clickhouse_dsn: str
    postgres_dsn: str
    default_workspace_id: str
    default_workspace_name: str
    default_workspace_slug: str
    default_user_id: str
    default_user_email: str
    default_user_password: str
    default_api_key: str

    def _clickhouse_client(self) -> Any:
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError("clickhouse-connect is required for ClickHouse storage") from exc

        parsed = parse_clickhouse_dsn(self.clickhouse_dsn)
        return clickhouse_connect.get_client(
            host=parsed.host,
            port=parsed.port,
            username=parsed.username,
            password=parsed.password,
            database=parsed.database,
            secure=parsed.secure,
        )

    def _postgres_conn(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for Postgres auth storage") from exc
        return psycopg.connect(self.postgres_dsn, autocommit=True)

    def bootstrap(self) -> None:
        client = self._clickhouse_client()
        ensure_clickhouse_tables(client)
        with self._postgres_conn() as conn:
            ensure_postgres_schema(conn)
            seed_workspace_auth(
                conn,
                workspace_id=self.default_workspace_id,
                workspace_name=self.default_workspace_name,
                workspace_slug=self.default_workspace_slug,
                user_id=self.default_user_id,
                user_email=self.default_user_email,
                password=self.default_user_password,
                api_key=self.default_api_key,
            )

    def resolve_workspace(self, api_key: str) -> str | None:
        with self._postgres_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT workspace_id FROM api_keys WHERE api_key = %s", (api_key,))
                row = cursor.fetchone()
        return row[0] if row else None

    def write_log(self, payload: IngestLogRequest) -> bool:
        client = self._clickhouse_client()
        ensure_clickhouse_tables(client)
        existing = client.query(
            "SELECT count() AS count FROM llm_logs WHERE workspace_id = %(workspace_id)s AND request_id = %(request_id)s",
            parameters={"workspace_id": payload.workspace_id, "request_id": payload.request_id},
        )
        if existing.result_rows and existing.result_rows[0][0] > 0:
            return False
        client.insert("llm_logs", [log_to_clickhouse_row(payload)], column_names=clickhouse_columns())
        return True


def build_store(settings: Any) -> MemoryEventStore | FileEventStore | ClickHouseEventStore:
    if settings.storage_backend == "clickhouse":
        return ClickHouseEventStore(
            clickhouse_dsn=settings.clickhouse_dsn,
            postgres_dsn=settings.postgres_dsn,
            default_workspace_id=settings.default_workspace_id,
            default_workspace_name=settings.default_workspace_name,
            default_workspace_slug=settings.default_workspace_slug,
            default_user_id=settings.default_user_id,
            default_user_email=settings.default_user_email,
            default_user_password=settings.default_user_password,
            default_api_key=settings.default_api_key,
        )
    if settings.storage_backend == "file":
        return FileEventStore(Path(settings.file_store_path), settings.default_api_key, settings.default_workspace_id)
    return MemoryEventStore()
