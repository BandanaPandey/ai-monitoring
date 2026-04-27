from __future__ import annotations

from abc import ABC, abstractmethod

from .models import DashboardSummary, IngestLogRequest, LogDetail, LogListResponse


class EventWriter(ABC):
    @abstractmethod
    def write_log(self, payload: IngestLogRequest) -> bool:
        raise NotImplementedError


class AnalyticsReader(ABC):
    @abstractmethod
    def get_dashboard_summary(self, workspace_id: str) -> DashboardSummary:
        raise NotImplementedError

    @abstractmethod
    def list_logs(self, workspace_id: str, limit: int = 50, search: str | None = None) -> LogListResponse:
        raise NotImplementedError

    @abstractmethod
    def get_log_detail(self, workspace_id: str, request_id: str) -> LogDetail | None:
        raise NotImplementedError

