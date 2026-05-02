from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_monitoring_contracts.models import (
    CompareLogsResponse,
    DashboardSummary,
    ErrorSummary,
    IngestLogRequest,
    LogDetail,
    LogListItem,
    LogListResponse,
    LogQueryFilters,
    MetricPoint,
)
from ai_monitoring_contracts.persistence import (
    clickhouse_row_to_log,
    ensure_clickhouse_tables,
    parse_clickhouse_dsn,
)


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1))
    return float(ordered[index])


def _preview(item: IngestLogRequest) -> str:
    if item.output_messages:
        return item.output_messages[0].content[:120]
    if item.input_messages:
        return item.input_messages[0].content[:120]
    return (item.system_prompt or "")[:120]


def _to_detail(item: IngestLogRequest) -> LogDetail:
    return LogDetail(
        request_id=item.request_id,
        timestamp=item.timestamp,
        provider=item.provider,
        model=item.model,
        feature=item.feature,
        user_id=item.user_id,
        status=item.status,
        latency_ms=item.latency_ms,
        total_cost=item.cost_total,
        tokens_total=item.tokens.total,
        preview=_preview(item),
        trace_id=item.trace_id,
        span_id=item.span_id,
        model_version=item.model_version,
        endpoint=item.endpoint,
        session_id=item.session_id,
        system_prompt=item.system_prompt,
        input_messages=item.input_messages,
        output_messages=item.output_messages,
        raw_request=item.raw_request,
        raw_response=item.raw_response,
        error_type=item.error_type,
        error_code=item.error_code,
        error_message=item.error_message,
        metadata=item.metadata,
        tags=item.tags,
        cost_input=item.cost_input,
        cost_output=item.cost_output,
        currency=item.currency,
    )


def _matches(item: IngestLogRequest, filters: LogQueryFilters) -> bool:
    if filters.status and item.status != filters.status:
        return False
    if filters.model and item.model != filters.model:
        return False
    if filters.feature and item.feature != filters.feature:
        return False
    if filters.user_id and item.user_id != filters.user_id:
        return False
    if filters.from_timestamp and item.timestamp < filters.from_timestamp:
        return False
    if filters.to_timestamp and item.timestamp > filters.to_timestamp:
        return False
    if filters.search:
        lowered = filters.search.lower()
        searchable = [
            item.request_id,
            item.system_prompt or "",
            item.error_message or "",
            " ".join(message.content for message in item.input_messages),
            " ".join(message.content for message in item.output_messages),
        ]
        if not any(lowered in value.lower() for value in searchable):
            return False
    return True


@dataclass
class MemoryQueryService:
    items: dict[str, IngestLogRequest] = field(default_factory=dict)

    def bootstrap(self) -> None:
        return None

    def list_records(self, workspace_id: str) -> list[IngestLogRequest]:
        return [item for item in self.items.values() if item.workspace_id in {None, workspace_id}]


@dataclass
class FileQueryService:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def bootstrap(self) -> None:
        return None

    def list_records(self, workspace_id: str) -> list[IngestLogRequest]:
        items: list[IngestLogRequest] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = IngestLogRequest.model_validate(json.loads(stripped))
                if payload.workspace_id in {None, workspace_id}:
                    items.append(payload)
        return items


@dataclass
class ClickHouseQueryService:
    clickhouse_dsn: str

    def _client(self) -> Any:
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError("clickhouse-connect is required for ClickHouse queries") from exc

        parsed = parse_clickhouse_dsn(self.clickhouse_dsn)
        return clickhouse_connect.get_client(
            host=parsed.host,
            port=parsed.port,
            username=parsed.username,
            password=parsed.password,
            database=parsed.database,
            secure=parsed.secure,
        )

    def bootstrap(self) -> None:
        ensure_clickhouse_tables(self._client())

    def list_records(self, workspace_id: str) -> list[IngestLogRequest]:
        client = self._client()
        ensure_clickhouse_tables(client)
        result = client.query(
            """
            SELECT *
            FROM llm_logs
            WHERE workspace_id = %(workspace_id)s
            ORDER BY timestamp DESC
            LIMIT 1000
            """,
            parameters={"workspace_id": workspace_id},
        )
        rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
        return [clickhouse_row_to_log(row) for row in rows]

    def fetch_daily_metrics(self, workspace_id: str) -> list[dict[str, Any]]:
        client = self._client()
        ensure_clickhouse_tables(client)
        result = client.query(
            """
            SELECT bucket_date, total_requests, error_count, total_cost, average_latency_ms, p50_latency_ms, p95_latency_ms
            FROM llm_daily_metrics
            WHERE workspace_id = %(workspace_id)s
            ORDER BY bucket_date ASC
            """,
            parameters={"workspace_id": workspace_id},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]

    def fetch_headline_metrics(self, workspace_id: str) -> dict[str, Any]:
        client = self._client()
        ensure_clickhouse_tables(client)
        result = client.query(
            """
            SELECT
                count() AS total_requests,
                countIf(status = 'error') AS error_count,
                sum(cost_total) AS total_cost,
                avg(latency_ms) AS average_latency_ms,
                quantileExact(0.50)(latency_ms) AS p50_latency_ms,
                quantileExact(0.95)(latency_ms) AS p95_latency_ms
            FROM llm_logs
            WHERE workspace_id = %(workspace_id)s
            """,
            parameters={"workspace_id": workspace_id},
        )
        if not result.result_rows:
            return {
                "total_requests": 0,
                "error_count": 0,
                "total_cost": 0.0,
                "average_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
            }
        row = result.result_rows[0]
        return {
            "total_requests": int(row[0] or 0),
            "error_count": int(row[1] or 0),
            "total_cost": float(row[2] or 0.0),
            "average_latency_ms": float(row[3] or 0.0),
            "p50_latency_ms": float(row[4] or 0.0),
            "p95_latency_ms": float(row[5] or 0.0),
        }

    def fetch_error_groups(self, workspace_id: str) -> list[dict[str, Any]]:
        client = self._client()
        ensure_clickhouse_tables(client)
        result = client.query(
            """
            SELECT error_type, count
            FROM llm_error_groups
            WHERE workspace_id = %(workspace_id)s
            ORDER BY count DESC
            LIMIT 5
            """,
            parameters={"workspace_id": workspace_id},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]


class QueryFacade:
    def __init__(self, storage: MemoryQueryService | FileQueryService | ClickHouseQueryService):
        self.storage = storage

    def bootstrap(self) -> None:
        self.storage.bootstrap()

    def get_dashboard_summary(self, workspace_id: str) -> DashboardSummary:
        if isinstance(self.storage, ClickHouseQueryService):
            headline = self.storage.fetch_headline_metrics(workspace_id)
            metrics = self.storage.fetch_daily_metrics(workspace_id)
            error_groups = self.storage.fetch_error_groups(workspace_id)
            if headline["total_requests"] or metrics:
                return DashboardSummary(
                    total_requests=headline["total_requests"],
                    average_latency_ms=headline["average_latency_ms"],
                    p50_latency_ms=headline["p50_latency_ms"],
                    p95_latency_ms=headline["p95_latency_ms"],
                    error_rate=(
                        headline["error_count"] / headline["total_requests"]
                        if headline["total_requests"]
                        else 0.0
                    ),
                    total_cost=round(headline["total_cost"], 6),
                    request_volume=[
                        MetricPoint(
                            timestamp=datetime.combine(row["bucket_date"], datetime.min.time(), timezone.utc),
                            value=float(row["total_requests"]),
                        )
                        for row in metrics
                    ],
                    latency_series=[
                        MetricPoint(
                            timestamp=datetime.combine(row["bucket_date"], datetime.min.time(), timezone.utc),
                            value=float(row["average_latency_ms"]),
                        )
                        for row in metrics
                    ],
                    cost_series=[
                        MetricPoint(
                            timestamp=datetime.combine(row["bucket_date"], datetime.min.time(), timezone.utc),
                            value=float(row["total_cost"]),
                        )
                        for row in metrics
                    ],
                    top_errors=[
                        ErrorSummary(error_type=row["error_type"], count=int(row["count"])) for row in error_groups
                    ],
                )

        logs = self.storage.list_records(workspace_id)
        latencies = [item.latency_ms for item in logs]
        total_cost = sum(item.cost_total for item in logs)
        error_count = sum(1 for item in logs if item.status.value == "error")
        volume_by_day = Counter(item.timestamp.date().isoformat() for item in logs)
        latency_by_day: dict[str, list[int]] = {}
        cost_by_day: dict[str, float] = {}
        errors = Counter(item.error_type or "unknown" for item in logs if item.status.value == "error")
        for item in logs:
            day = item.timestamp.date().isoformat()
            latency_by_day.setdefault(day, []).append(item.latency_ms)
            cost_by_day[day] = cost_by_day.get(day, 0.0) + item.cost_total
        return DashboardSummary(
            total_requests=len(logs),
            average_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            error_rate=(error_count / len(logs)) if logs else 0.0,
            total_cost=round(total_cost, 6),
            request_volume=[
                MetricPoint(timestamp=f"{day}T00:00:00+00:00", value=float(count))
                for day, count in sorted(volume_by_day.items())
            ],
            latency_series=[
                MetricPoint(timestamp=f"{day}T00:00:00+00:00", value=float(sum(values) / len(values)))
                for day, values in sorted(latency_by_day.items())
            ],
            cost_series=[
                MetricPoint(timestamp=f"{day}T00:00:00+00:00", value=round(value, 6))
                for day, value in sorted(cost_by_day.items())
            ],
            top_errors=[ErrorSummary(error_type=error, count=count) for error, count in errors.most_common(5)],
        )

    def list_logs(self, workspace_id: str, filters: LogQueryFilters) -> LogListResponse:
        logs = [item for item in self.storage.list_records(workspace_id) if _matches(item, filters)]
        logs = sorted(logs, key=lambda item: item.timestamp, reverse=True)
        limited = logs[: filters.limit]
        return LogListResponse(
            items=[
                LogListItem(
                    request_id=item.request_id,
                    timestamp=item.timestamp,
                    provider=item.provider,
                    model=item.model,
                    feature=item.feature,
                    user_id=item.user_id,
                    status=item.status,
                    latency_ms=item.latency_ms,
                    total_cost=item.cost_total,
                    tokens_total=item.tokens.total,
                    preview=_preview(item),
                )
                for item in limited
            ],
            total=len(logs),
        )

    def get_log_detail(self, workspace_id: str, request_id: str) -> LogDetail | None:
        for item in self.storage.list_records(workspace_id):
            if item.request_id == request_id:
                return _to_detail(item)
        return None

    def compare_logs(self, workspace_id: str, left_request_id: str, right_request_id: str) -> CompareLogsResponse | None:
        left = self.get_log_detail(workspace_id, left_request_id)
        right = self.get_log_detail(workspace_id, right_request_id)
        if left is None or right is None:
            return None
        return CompareLogsResponse(
            left=left,
            right=right,
            left_text="\n".join(message.content for message in left.output_messages),
            right_text="\n".join(message.content for message in right.output_messages),
        )


def build_query_facade(backend: str, file_store_path: str, clickhouse_dsn: str) -> QueryFacade:
    if backend == "clickhouse":
        return QueryFacade(ClickHouseQueryService(clickhouse_dsn))
    if backend == "file":
        return QueryFacade(FileQueryService(Path(file_store_path)))
    return QueryFacade(MemoryQueryService())
