from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    clickhouse_dsn: str
    postgres_dsn: str
    interval_seconds: int
    mode: str
    file_store_path: str
    aggregate_store_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            clickhouse_dsn=os.getenv("PROCESSOR_CLICKHOUSE_DSN", ""),
            postgres_dsn=os.getenv("PROCESSOR_POSTGRES_DSN", ""),
            interval_seconds=int(os.getenv("PROCESSOR_INTERVAL_SECONDS", "60")),
            mode=os.getenv("PROCESSOR_MODE", "dry-run"),
            file_store_path=os.getenv("PROCESSOR_FILE_STORE_PATH", "./var/data/logs.jsonl"),
            aggregate_store_path=os.getenv("PROCESSOR_AGGREGATE_STORE_PATH", "./var/data/aggregates.json"),
        )
