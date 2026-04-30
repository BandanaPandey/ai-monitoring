from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    storage_backend: str
    postgres_dsn: str
    clickhouse_dsn: str
    cors_allowed_origins: tuple[str, ...]
    file_store_path: str
    aggregate_store_path: str
    default_workspace_name: str
    default_workspace_slug: str
    default_user_id: str
    auth_email: str
    auth_password: str
    auth_secret: str
    access_token_ttl_seconds: int
    default_workspace_id: str
    default_api_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        cors_allowed_origins = tuple(
            origin.strip()
            for origin in os.getenv("GATEWAY_CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
            if origin.strip()
        )
        return cls(
            storage_backend=os.getenv("GATEWAY_STORAGE_BACKEND", "file"),
            postgres_dsn=os.getenv("GATEWAY_POSTGRES_DSN", ""),
            clickhouse_dsn=os.getenv("GATEWAY_CLICKHOUSE_DSN", ""),
            cors_allowed_origins=cors_allowed_origins,
            file_store_path=os.getenv("GATEWAY_FILE_STORE_PATH", "./var/data/logs.jsonl"),
            aggregate_store_path=os.getenv("GATEWAY_AGGREGATE_STORE_PATH", "./var/data/aggregates.json"),
            default_workspace_name=os.getenv("GATEWAY_DEFAULT_WORKSPACE_NAME", "Default Workspace"),
            default_workspace_slug=os.getenv("GATEWAY_DEFAULT_WORKSPACE_SLUG", "default-workspace"),
            default_user_id=os.getenv("GATEWAY_DEFAULT_USER_ID", "user-admin"),
            auth_email=os.getenv("GATEWAY_AUTH_EMAIL", "admin@example.com"),
            auth_password=os.getenv("GATEWAY_AUTH_PASSWORD", "changeme"),
            auth_secret=os.getenv("GATEWAY_AUTH_SECRET", "local-dev-secret"),
            access_token_ttl_seconds=int(os.getenv("GATEWAY_ACCESS_TOKEN_TTL_SECONDS", "3600")),
            default_workspace_id=os.getenv("GATEWAY_DEFAULT_WORKSPACE_ID", "workspace-default"),
            default_api_key=os.getenv("GATEWAY_DEFAULT_API_KEY", "demo-ingest-key"),
        )
