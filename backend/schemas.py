"""Modelos Pydantic de request/response de los endpoints de la API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class MemberStatsOut(BaseModel):
    author: str
    messages_in_range: int
    last_message_at: datetime
    days_since_last_message: float
    inactivity_score: float


class DailyActivityOut(BaseModel):
    day: date
    count: int


class DailySnapshotOut(BaseModel):
    day: date
    message_count: int
    active_members: int
    top_author: str | None
    top_author_messages: int


class HeatmapCellOut(BaseModel):
    weekday: int
    hour: int
    count: int


class TimelineEventOut(BaseModel):
    kind: str
    at: datetime
    title: str
    description: str


class PhaseSummaryOut(BaseModel):
    label: str
    start_day: date
    end_day: date
    description: str


class ReactivationLeaderOut(BaseModel):
    author: str
    attempts: int


class InteractionEdgeOut(BaseModel):
    source: str
    target: str
    weight: float
    avg_latency_seconds: float


class InteractionGraphOut(BaseModel):
    nodes: list[str]
    edges: list[InteractionEdgeOut]
    centrality: dict[str, float]
    communities: list[list[str]]


class AnalysisResultOut(BaseModel):
    group_name: str | None = None
    reference_date: datetime
    range_start: datetime
    range_end: datetime
    total_members: int
    total_messages_in_range: int
    members: list[MemberStatsOut]
    top3: list[MemberStatsOut]
    activity_by_day: list[DailyActivityOut]
    daily_snapshots: list[DailySnapshotOut]
    hourly_heatmap: list[HeatmapCellOut]
    timeline_events: list[TimelineEventOut]
    probable_cause: str
    conversation_pattern: str
    reactivation_attempts: int
    reactivation_leaders: list[ReactivationLeaderOut]
    phase_summary: list[PhaseSummaryOut]
    interaction_graph: InteractionGraphOut


class VeredictoIARequest(BaseModel):
    provider: Literal["anthropic", "openai", "gemini", "groq"]
    api_key: str
    model: str | None = None
    tone: Literal["forense", "neutral", "bardero"] = "forense"
    group_name: str | None = None
    total_members: int
    total_messages_in_range: int
    conversation_pattern: str
    reactivation_attempts: int
    top3: list[MemberStatsOut]
    reactivation_leaders: list[ReactivationLeaderOut]
    phase_summary: list[PhaseSummaryOut]
    rule_based_cause: str


class VeredictoIAResponse(BaseModel):
    verdict: str
