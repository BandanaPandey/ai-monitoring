from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

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

    def list_records(self) -> list[IngestLogRequest]:
        return list(self.items.values())


@dataclass
class FileQueryService:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def list_records(self) -> list[IngestLogRequest]:
        items: list[IngestLogRequest] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                items.append(IngestLogRequest.model_validate(json.loads(stripped)))
        return items


class QueryFacade:
    def __init__(self, storage: MemoryQueryService | FileQueryService, aggregate_path: Path | None = None):
        self.storage = storage
        self.aggregate_path = aggregate_path

    def _load_aggregate_summary(self) -> DashboardSummary | None:
        if self.aggregate_path is None or not self.aggregate_path.exists():
            return None
        payload = json.loads(self.aggregate_path.read_text(encoding="utf-8"))
        return DashboardSummary.model_validate(payload)

    def get_dashboard_summary(self, workspace_id: str) -> DashboardSummary:
        snapshot = self._load_aggregate_summary()
        if snapshot is not None:
            return snapshot
        logs = self.storage.list_records()
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
        logs = [item for item in self.storage.list_records() if _matches(item, filters)]
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
        for item in self.storage.list_records():
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


def build_query_facade(backend: str, file_store_path: str, aggregate_store_path: str) -> QueryFacade:
    if backend == "file":
        return QueryFacade(FileQueryService(Path(file_store_path)), Path(aggregate_store_path))
    return QueryFacade(MemoryQueryService())
