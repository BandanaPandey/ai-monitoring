from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class TokenUsage(BaseModel):
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, ge=0)

    @field_validator("total", mode="before")
    @classmethod
    def populate_total(cls, value: int | None, info: Any) -> int:
        if value is not None:
            return value
        data = info.data
        return int(data.get("input", 0)) + int(data.get("output", 0))


class LLMExchange(BaseModel):
    role: str
    content: str


class IngestLogRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    trace_id: str | None = None
    span_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    model_version: str | None = None
    system_prompt: str | None = None
    input_messages: list[LLMExchange] = Field(default_factory=list)
    output_messages: list[LLMExchange] = Field(default_factory=list)
    raw_request: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    latency_ms: int = Field(ge=0)
    status: RequestStatus = RequestStatus.SUCCESS
    error_type: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    cost_input: float = Field(default=0.0, ge=0)
    cost_output: float = Field(default=0.0, ge=0)
    cost_total: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    user_id: str | None = None
    session_id: str | None = None
    feature: str | None = None
    endpoint: str | None = None
    environment: str | None = None
    workspace_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cost_total", mode="before")
    @classmethod
    def populate_cost_total(cls, value: float | None, info: Any) -> float:
        if value is not None:
            return value
        data = info.data
        return float(data.get("cost_input", 0.0)) + float(data.get("cost_output", 0.0))


class IngestLogResponse(BaseModel):
    accepted: bool
    request_id: str
    deduplicated: bool = False


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class ErrorSummary(BaseModel):
    error_type: str
    count: int


class DashboardSummary(BaseModel):
    total_requests: int
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    error_rate: float
    total_cost: float
    request_volume: list[MetricPoint] = Field(default_factory=list)
    latency_series: list[MetricPoint] = Field(default_factory=list)
    cost_series: list[MetricPoint] = Field(default_factory=list)
    top_errors: list[ErrorSummary] = Field(default_factory=list)


class LogListItem(BaseModel):
    request_id: str
    timestamp: datetime
    provider: str
    model: str
    feature: str | None = None
    user_id: str | None = None
    status: RequestStatus
    latency_ms: int
    total_cost: float
    tokens_total: int
    preview: str


class LogDetail(LogListItem):
    trace_id: str | None = None
    span_id: str | None = None
    model_version: str | None = None
    endpoint: str | None = None
    session_id: str | None = None
    system_prompt: str | None = None
    input_messages: list[LLMExchange] = Field(default_factory=list)
    output_messages: list[LLMExchange] = Field(default_factory=list)
    raw_request: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    error_type: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    cost_input: float = 0.0
    cost_output: float = 0.0
    currency: str = "USD"


class LogListResponse(BaseModel):
    items: list[LogListItem]
    total: int


class LogQueryFilters(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    search: str | None = None
    status: RequestStatus | None = None
    model: str | None = None
    feature: str | None = None
    user_id: str | None = None
    from_timestamp: datetime | None = Field(default=None, alias="from")
    to_timestamp: datetime | None = Field(default=None, alias="to")

    model_config = ConfigDict(populate_by_name=True)


class CompareLogsRequest(BaseModel):
    left_request_id: str
    right_request_id: str


class CompareLogsResponse(BaseModel):
    left: LogDetail
    right: LogDetail
    left_text: str
    right_text: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    workspace_id: str | None = None
    user_id: str | None = None


class AuthenticatedIdentity(BaseModel):
    user_id: str
    email: str
    workspace_id: str


class ProcessorJob(str, Enum):
    ROLLUP_METRICS = "rollup_metrics"
    GROUP_ERRORS = "group_errors"
    NORMALIZE_COSTS = "normalize_costs"
