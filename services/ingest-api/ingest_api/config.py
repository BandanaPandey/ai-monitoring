from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    api_keys: set[str]
    storage_backend: str
    clickhouse_dsn: str
    postgres_dsn: str
    file_store_path: str
    redact_emails: bool
    redact_phones: bool

    @classmethod
    def from_env(cls) -> "Settings":
        keys = {key.strip() for key in os.getenv("INGEST_API_KEYS", "demo-ingest-key").split(",") if key.strip()}
        return cls(
            api_keys=keys,
            storage_backend=os.getenv("INGEST_STORAGE_BACKEND", "memory"),
            clickhouse_dsn=os.getenv("INGEST_CLICKHOUSE_DSN", ""),
            postgres_dsn=os.getenv("INGEST_POSTGRES_DSN", ""),
            file_store_path=os.getenv("INGEST_FILE_STORE_PATH", "./var/data/logs.jsonl"),
            redact_emails=os.getenv("INGEST_REDACT_EMAILS", "true").lower() == "true",
            redact_phones=os.getenv("INGEST_REDACT_PHONES", "true").lower() == "true",
        )
