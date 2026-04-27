from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ai_monitoring_contracts.models import DashboardSummary, ErrorSummary, IngestLogRequest, MetricPoint, ProcessorJob


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1))
    return float(ordered[index])


@dataclass
class JobRunner:
    mode: str
    file_store_path: str
    aggregate_store_path: str

    def _load_logs(self) -> list[IngestLogRequest]:
        path = Path(self.file_store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        items: list[IngestLogRequest] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                items.append(IngestLogRequest.model_validate(json.loads(stripped)))
        return items

    def _build_summary(self, logs: list[IngestLogRequest]) -> DashboardSummary:
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

    def run_once(self) -> list[dict[str, str]]:
        logs = self._load_logs()
        summary = self._build_summary(logs)
        aggregate_path = Path(self.aggregate_store_path)
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        aggregate_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        return [
            {"job": ProcessorJob.ROLLUP_METRICS.value, "mode": self.mode, "status": "completed"},
            {"job": ProcessorJob.GROUP_ERRORS.value, "mode": self.mode, "status": "completed"},
            {"job": ProcessorJob.NORMALIZE_COSTS.value, "mode": self.mode, "status": "completed"},
        ]
