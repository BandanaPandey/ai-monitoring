from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from .models import IngestLogRequest


RAW_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_logs (
    workspace_id String,
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
ORDER BY (workspace_id, timestamp, request_id)
"""

DAILY_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_daily_metrics (
    workspace_id String,
    bucket_date Date,
    total_requests UInt64,
    error_count UInt64,
    total_cost Float64,
    average_latency_ms Float64,
    p50_latency_ms Float64,
    p95_latency_ms Float64
) ENGINE = MergeTree
ORDER BY (workspace_id, bucket_date)
"""

ERROR_GROUPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_error_groups (
    workspace_id String,
    error_type String,
    count UInt64
) ENGINE = MergeTree
ORDER BY (workspace_id, error_type)
"""

POSTGRES_AUTH_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memberships (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (user_id, workspace_id)
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    api_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@dataclass(slots=True)
class ClickHouseDsn:
    host: str
    port: int
    username: str
    password: str
    database: str
    secure: bool


def parse_clickhouse_dsn(dsn: str) -> ClickHouseDsn:
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    scheme = parsed.scheme or "clickhouse"
    secure = scheme.endswith("s") or query.get("secure", ["0"])[0] in {"1", "true", "True"}
    default_port = 8443 if secure else 8123
    return ClickHouseDsn(
        host=parsed.hostname or "localhost",
        port=parsed.port or default_port,
        username=parsed.username or "default",
        password=parsed.password or "",
        database=(parsed.path or "/default").lstrip("/") or "default",
        secure=secure,
    )


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_clickhouse_tables(client: Any) -> None:
    client.command(RAW_LOG_TABLE_SQL)
    client.command(DAILY_METRICS_TABLE_SQL)
    client.command(ERROR_GROUPS_TABLE_SQL)


def ensure_postgres_schema(conn: Any) -> None:
    with conn.cursor() as cursor:
        cursor.execute(POSTGRES_AUTH_SQL)


def seed_workspace_auth(
    conn: Any,
    *,
    workspace_id: str,
    workspace_name: str,
    workspace_slug: str,
    user_id: str,
    user_email: str,
    password: str,
    api_key: str,
) -> None:
    password_hash = hash_password(password)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO workspaces (id, name, slug)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug
            """,
            (workspace_id, workspace_name, workspace_slug),
        )
        cursor.execute(
            """
            INSERT INTO users (id, email, password_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, password_hash = EXCLUDED.password_hash
            """,
            (user_id, user_email, password_hash),
        )
        cursor.execute(
            """
            INSERT INTO memberships (user_id, workspace_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, workspace_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (user_id, workspace_id, "owner"),
        )
        cursor.execute(
            """
            INSERT INTO api_keys (id, workspace_id, api_key, name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (api_key) DO UPDATE SET workspace_id = EXCLUDED.workspace_id, name = EXCLUDED.name
            """,
            (str(uuid.uuid4()), workspace_id, api_key, "default"),
        )


def log_to_clickhouse_row(payload: IngestLogRequest) -> list[Any]:
    row = payload.model_dump(mode="json")
    return [
        row.get("workspace_id") or "unknown-workspace",
        row["request_id"],
        row.get("trace_id"),
        row.get("span_id"),
        row["timestamp"],
        row["provider"],
        row["model"],
        row.get("model_version"),
        row.get("system_prompt"),
        json.dumps(row.get("input_messages", [])),
        json.dumps(row.get("output_messages", [])),
        json.dumps(row.get("raw_request", {})),
        json.dumps(row.get("raw_response", {})),
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
        json.dumps(row.get("tags", [])),
        json.dumps(row.get("metadata", {})),
    ]


def clickhouse_columns() -> list[str]:
    return [
        "workspace_id",
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
    ]


def clickhouse_row_to_log(row: dict[str, Any]) -> IngestLogRequest:
    return IngestLogRequest.model_validate(
        {
            "workspace_id": row["workspace_id"],
            "request_id": row["request_id"],
            "trace_id": row.get("trace_id"),
            "span_id": row.get("span_id"),
            "timestamp": row["timestamp"] if isinstance(row["timestamp"], datetime) else str(row["timestamp"]),
            "provider": row["provider"],
            "model": row["model"],
            "model_version": row.get("model_version"),
            "system_prompt": row.get("system_prompt"),
            "input_messages": json.loads(row.get("input_messages") or "[]"),
            "output_messages": json.loads(row.get("output_messages") or "[]"),
            "raw_request": json.loads(row.get("raw_request") or "{}"),
            "raw_response": json.loads(row.get("raw_response") or "{}"),
            "latency_ms": row["latency_ms"],
            "status": row["status"],
            "error_type": row.get("error_type"),
            "error_code": row.get("error_code"),
            "error_message": row.get("error_message"),
            "tokens": {
                "input": row["tokens_input"],
                "output": row["tokens_output"],
                "total": row["tokens_total"],
            },
            "cost_input": row["cost_input"],
            "cost_output": row["cost_output"],
            "cost_total": row["cost_total"],
            "currency": row["currency"],
            "user_id": row.get("user_id"),
            "session_id": row.get("session_id"),
            "feature": row.get("feature"),
            "endpoint": row.get("endpoint"),
            "environment": row.get("environment"),
            "tags": json.loads(row.get("tags") or "[]"),
            "metadata": json.loads(row.get("metadata") or "{}"),
        }
    )
