from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    storage_backend: str
    clickhouse_dsn: str
    postgres_dsn: str
    file_store_path: str
    default_workspace_id: str
    default_workspace_name: str
    default_workspace_slug: str
    default_user_id: str
    default_user_email: str
    default_user_password: str
    default_api_key: str
    redact_emails: bool
    redact_phones: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            storage_backend=os.getenv("INGEST_STORAGE_BACKEND", "file"),
            clickhouse_dsn=os.getenv("INGEST_CLICKHOUSE_DSN", ""),
            postgres_dsn=os.getenv("INGEST_POSTGRES_DSN", ""),
            file_store_path=os.getenv("INGEST_FILE_STORE_PATH", "./var/data/logs.jsonl"),
            default_workspace_id=os.getenv("INGEST_DEFAULT_WORKSPACE_ID", "workspace-default"),
            default_workspace_name=os.getenv("INGEST_DEFAULT_WORKSPACE_NAME", "Default Workspace"),
            default_workspace_slug=os.getenv("INGEST_DEFAULT_WORKSPACE_SLUG", "default-workspace"),
            default_user_id=os.getenv("INGEST_DEFAULT_USER_ID", "user-admin"),
            default_user_email=os.getenv("INGEST_DEFAULT_USER_EMAIL", "admin@example.com"),
            default_user_password=os.getenv("INGEST_DEFAULT_USER_PASSWORD", "changeme"),
            default_api_key=os.getenv("INGEST_DEFAULT_API_KEY", "demo-ingest-key"),
            redact_emails=os.getenv("INGEST_REDACT_EMAILS", "true").lower() == "true",
            redact_phones=os.getenv("INGEST_REDACT_PHONES", "true").lower() == "true",
        )
