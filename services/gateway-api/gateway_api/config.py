from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    storage_backend: str
    postgres_dsn: str
    clickhouse_dsn: str
    file_store_path: str
    aggregate_store_path: str
    auth_email: str
    auth_password: str
    auth_secret: str
    access_token_ttl_seconds: int
    default_workspace_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            storage_backend=os.getenv("GATEWAY_STORAGE_BACKEND", "memory"),
            postgres_dsn=os.getenv("GATEWAY_POSTGRES_DSN", ""),
            clickhouse_dsn=os.getenv("GATEWAY_CLICKHOUSE_DSN", ""),
            file_store_path=os.getenv("GATEWAY_FILE_STORE_PATH", "./var/data/logs.jsonl"),
            aggregate_store_path=os.getenv("GATEWAY_AGGREGATE_STORE_PATH", "./var/data/aggregates.json"),
            auth_email=os.getenv("GATEWAY_AUTH_EMAIL", "admin@example.com"),
            auth_password=os.getenv("GATEWAY_AUTH_PASSWORD", "changeme"),
            auth_secret=os.getenv("GATEWAY_AUTH_SECRET", "local-dev-secret"),
            access_token_ttl_seconds=int(os.getenv("GATEWAY_ACCESS_TOKEN_TTL_SECONDS", "3600")),
            default_workspace_id=os.getenv("GATEWAY_DEFAULT_WORKSPACE_ID", "demo-workspace"),
        )
