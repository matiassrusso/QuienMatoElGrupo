"""Calculo de rango de fechas, metricas por miembro y senales de actividad."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np
import ruptures as rpt
from dateutil.relativedelta import relativedelta

from parser import Message

RangeType = Literal["24h", "days", "weeks", "months"]


@dataclass
class MemberStats:
    author: str
    messages_in_range: int
    last_message_at: datetime
    days_since_last_message: float
    inactivity_score: float


@dataclass
class DailyActivity:
    day: date
    count: int


@dataclass
class DailySnapshot:
    day: date
    message_count: int
    active_members: int
    top_author: str | None
    top_author_messages: int


@dataclass
class HeatmapCell:
    weekday: int
    hour: int
    count: int


@dataclass
class TimelineEvent:
    kind: str
    at: datetime
    title: str
    description: str


@dataclass
class PhaseSummary:
    label: str
    start_day: date
    end_day: date
    description: str


@dataclass
class ReactivationLeader:
    author: str
    attempts: int


@dataclass
class AnalysisResult:
    reference_date: datetime
    range_start: datetime
    range_end: datetime
    total_members: int
    total_messages_in_range: int
    members: list[MemberStats]
    top3: list[MemberStats]
    activity_by_day: list[DailyActivity]
    daily_snapshots: list[DailySnapshot]
    hourly_heatmap: list[HeatmapCell]
    timeline_events: list[TimelineEvent]
    probable_cause: str
    conversation_pattern: str
    reactivation_attempts: int
    reactivation_leaders: list[ReactivationLeader]
    phase_summary: list[PhaseSummary]


def resolve_range_start(reference_now: datetime, range_type: RangeType, range_value: int | None) -> datetime:
    if range_type == "24h":
        return reference_now - timedelta(hours=24)
    if range_value is None or range_value <= 0:
        raise ValueError("range_value debe ser un entero positivo para este range_type.")
    if range_type == "days":
        return reference_now - timedelta(days=range_value)
    if range_type == "weeks":
        return reference_now - timedelta(weeks=range_value)
    if range_type == "months":
        return reference_now - relativedelta(months=range_value)
    raise ValueError(f"range_type desconocido: {range_type}")


def resolve_eligibility_start(reference_now: datetime, range_start: datetime) -> datetime:
    """Define quien cuenta como miembro elegible para el ranking."""
    three_months_ago = reference_now - relativedelta(months=3)
    if range_start < three_months_ago:
        return range_start - relativedelta(months=3)
    return three_months_ago


def iter_days(range_start: datetime, range_end: datetime) -> list[date]:
    items: list[date] = []
    cursor = range_start.date()
    last_day = range_end.date()

    while cursor <= last_day:
        items.append(cursor)
        cursor += timedelta(days=1)

    return items


def build_daily_activity(messages: list[Message], range_start: datetime, range_end: datetime) -> list[DailyActivity]:
    days = iter_days(range_start, range_end)
    counts: dict[date, int] = {day: 0 for day in days}

    for message in messages:
        if range_start <= message.timestamp <= range_end:
            current_day = message.timestamp.date()
            counts[current_day] = counts.get(current_day, 0) + 1

    return [DailyActivity(day=day, count=counts[day]) for day in days]


def build_daily_snapshots(messages: list[Message], range_start: datetime, range_end: datetime) -> list[DailySnapshot]:
    days = iter_days(range_start, range_end)
    per_day: dict[date, dict[str, int]] = {day: {} for day in days}

    for message in messages:
        if range_start <= message.timestamp <= range_end:
            current_day = message.timestamp.date()
            per_day[current_day][message.author] = per_day[current_day].get(message.author, 0) + 1

    snapshots: list[DailySnapshot] = []
    for day in days:
        author_counts = per_day[day]
        if author_counts:
            top_author, top_count = max(author_counts.items(), key=lambda item: item[1])
        else:
            top_author, top_count = None, 0

        snapshots.append(
            DailySnapshot(
                day=day,
                message_count=sum(author_counts.values()),
                active_members=len(author_counts),
                top_author=top_author,
                top_author_messages=top_count,
            )
        )

    return snapshots


def build_hourly_heatmap(messages: list[Message], range_start: datetime, range_end: datetime) -> list[HeatmapCell]:
    counts: dict[tuple[int, int], int] = {(weekday, hour): 0 for weekday in range(7) for hour in range(24)}

    for message in messages:
        if range_start <= message.timestamp <= range_end:
            key = (message.timestamp.weekday(), message.timestamp.hour)
            counts[key] += 1

    return [
        HeatmapCell(weekday=weekday, hour=hour, count=counts[(weekday, hour)])
        for weekday in range(7)
        for hour in range(24)
    ]


def build_timeline_events(
    messages: list[Message],
    range_start: datetime,
    range_end: datetime,
    activity_by_day: list[DailyActivity],
) -> list[TimelineEvent]:
    in_range_messages = [message for message in messages if range_start <= message.timestamp <= range_end]

    events = [
        TimelineEvent(
            kind="range-start",
            at=range_start,
            title="Inicio del recorte",
            description="Comienza la ventana temporal elegida para el analisis.",
        )
    ]

    if not in_range_messages:
        events.append(
            TimelineEvent(
                kind="no-activity",
                at=range_end,
                title="Silencio total",
                description="No hubo mensajes dentro del periodo analizado.",
            )
        )
        return events

    peak_day = max(activity_by_day, key=lambda item: item.count)
    events.append(
        TimelineEvent(
            kind="peak-day",
            at=datetime.combine(peak_day.day, datetime.min.time()),
            title="Pico de actividad",
            description=f"{peak_day.count} mensajes en el dia mas intenso del periodo.",
        )
    )

    longest_gap_start = in_range_messages[0].timestamp
    longest_gap_end = in_range_messages[0].timestamp
    longest_gap = timedelta(0)

    for previous, current in zip(in_range_messages, in_range_messages[1:]):
        gap = current.timestamp - previous.timestamp
        if gap > longest_gap:
            longest_gap = gap
            longest_gap_start = previous.timestamp
            longest_gap_end = current.timestamp

    if longest_gap > timedelta(hours=12):
        gap_days = round(longest_gap.total_seconds() / 86400, 1)
        events.append(
            TimelineEvent(
                kind="longest-gap",
                at=longest_gap_end,
                title="Silencio prolongado",
                description=f"Pasaron {gap_days} dias entre {longest_gap_start.strftime('%d/%m')} y {longest_gap_end.strftime('%d/%m')}.",
            )
        )

    last_message = in_range_messages[-1]
    events.append(
        TimelineEvent(
            kind="last-message",
            at=last_message.timestamp,
            title="Ultimo mensaje del periodo",
            description=f"{last_message.author} fue la ultima persona en hablar dentro del recorte.",
        )
    )

    return sorted(events, key=lambda event: event.at)


def count_reactivation_attempts(daily_snapshots: list[DailySnapshot]) -> int:
    attempts = 0
    for previous, current in zip(daily_snapshots, daily_snapshots[1:]):
        if previous.message_count == 0 and current.message_count >= 3:
            attempts += 1
        elif previous.message_count <= 2 and current.message_count >= previous.message_count * 3 and current.message_count >= 6:
            attempts += 1
    return attempts


def build_reactivation_leaders(messages: list[Message], daily_snapshots: list[DailySnapshot]) -> list[ReactivationLeader]:
    first_author_by_day: dict[date, str] = {}
    for message in messages:
        current_day = message.timestamp.date()
        if current_day not in first_author_by_day:
            first_author_by_day[current_day] = message.author

    attempts_by_author: dict[str, int] = {}
    for previous, current in zip(daily_snapshots, daily_snapshots[1:]):
        is_reactivation = False
        if previous.message_count == 0 and current.message_count >= 3:
            is_reactivation = True
        elif previous.message_count <= 2 and current.message_count >= previous.message_count * 3 and current.message_count >= 6:
            is_reactivation = True

        if not is_reactivation:
            continue

        author = first_author_by_day.get(current.day)
        if author:
            attempts_by_author[author] = attempts_by_author.get(author, 0) + 1

    leaders = sorted(attempts_by_author.items(), key=lambda item: (-item[1], item[0]))
    return [ReactivationLeader(author=author, attempts=attempts) for author, attempts in leaders[:3]]


def detect_changepoints(counts: list[int]) -> list[int]:
    """Indices donde cambia el nivel medio de actividad (deteccion PELT, modelo l2).

    Devuelve los limites de segmento (excluye el 0 inicial, incluye len(counts) al final).
    """
    n = len(counts)
    if n < 4 or not any(counts):
        return [n]

    signal = np.array(counts, dtype=float)
    penalty = max(float(np.var(signal)) * np.log(n), 1.0)
    min_size = max(2, n // 15)
    algo = rpt.Pelt(model="l2", min_size=min_size).fit(signal.reshape(-1, 1))
    return algo.predict(pen=penalty)


def build_phase_summary(daily_snapshots: list[DailySnapshot]) -> list[PhaseSummary]:
    if not daily_snapshots:
        return []

    total = max(sum(item.message_count for item in daily_snapshots), 1)
    counts = [item.message_count for item in daily_snapshots]
    breakpoints = detect_changepoints(counts)

    phases: list[PhaseSummary] = []
    start = 0
    for end in breakpoints:
        chunk = daily_snapshots[start:end]
        start = end
        if not chunk:
            continue
        messages = sum(item.message_count for item in chunk)
        active_average = sum(item.active_members for item in chunk) / len(chunk)
        share = messages / total

        if messages == 0:
            label = "Silencio"
            description = "No hubo mensajes durante este tramo del periodo."
        elif share >= 0.45:
            label = "Pulso alto"
            description = f"Se concentro buena parte de la conversacion aqui, con {active_average:.1f} miembros activos en promedio."
        elif active_average <= 1.5:
            label = "Desgaste"
            description = "La conversacion quedo sostenida por muy pocas personas."
        else:
            label = "Transicion"
            description = "El grupo mantuvo algo de movimiento, pero sin la intensidad del tramo mas fuerte."

        phases.append(
            PhaseSummary(
                label=label,
                start_day=chunk[0].day,
                end_day=chunk[-1].day,
                description=description,
            )
        )

    return phases


def infer_conversation_pattern(members: list[MemberStats], daily_snapshots: list[DailySnapshot], reactivation_attempts: int) -> str:
    total_messages = sum(member.messages_in_range for member in members)
    if total_messages == 0:
        return "Muerto"

    total_members = max(len(members), 1)
    silent_members = sum(1 for member in members if member.messages_in_range == 0)
    silent_share = silent_members / total_members

    top_two = sorted(members, key=lambda member: member.messages_in_range, reverse=True)[:2]
    concentration = 0.0
    if total_messages > 0:
        concentration = sum(member.messages_in_range for member in top_two) / total_messages

    active_days = sum(1 for snapshot in daily_snapshots if snapshot.message_count > 0)
    active_ratio = active_days / max(len(daily_snapshots), 1)

    if concentration >= 0.75:
        return "Dependiente"
    if reactivation_attempts >= 2:
        return "Intermitente"
    if silent_share >= 0.6 or active_ratio <= 0.35:
        return "Fragil"
    if active_ratio >= 0.7 and silent_share <= 0.25:
        return "Estable"
    return "Desgastado"


def infer_probable_cause(
    members: list[MemberStats],
    daily_snapshots: list[DailySnapshot],
    reactivation_attempts: int,
    conversation_pattern: str,
) -> str:
    if not members:
        return "No hay suficientes datos para inferir una causa probable."

    total_members = len(members)
    silent_members = sum(1 for member in members if member.messages_in_range == 0)
    concentration = 0.0
    total_messages = sum(member.messages_in_range for member in members)
    if total_messages > 0:
        top_two = sorted(members, key=lambda member: member.messages_in_range, reverse=True)[:2]
        concentration = sum(member.messages_in_range for member in top_two) / total_messages

    if total_messages == 0:
        return "El grupo llego muerto al periodo analizado: no hubo actividad real en la ventana elegida."
    if conversation_pattern == "Dependiente" or concentration >= 0.75:
        return "La conversacion dependio demasiado de pocas personas. Cuando ese nucleo aflojo, el grupo perdio traccion."
    if silent_members / total_members >= 0.6:
        return "La causa probable es abandono colectivo: la mayoria de los miembros no participo en la ventana analizada."
    if reactivation_attempts >= 2:
        return "Hubo intentos de reactivacion, pero no lograron sostener continuidad. El problema parece ser falta de constancia."

    last_slice = daily_snapshots[-max(3, len(daily_snapshots) // 4):]
    if last_slice and sum(item.message_count for item in last_slice) <= max(3, len(last_slice)):
        return "La actividad se fue apagando de forma progresiva hasta quedar en un hilo muy fino."

    return "La causa probable es desgaste gradual: hubo actividad, pero sin suficiente continuidad para mantener vivo al grupo."


def analyze(
    messages: list[Message],
    range_type: RangeType,
    range_value: int | None,
    weight: float = 0.5,
) -> AnalysisResult:
    if not messages:
        raise ValueError("El chat no tiene mensajes para analizar.")

    messages_sorted = sorted(messages, key=lambda message: message.timestamp)
    reference_now = messages_sorted[-1].timestamp
    range_start = resolve_range_start(reference_now, range_type, range_value)
    eligibility_start = resolve_eligibility_start(reference_now, range_start)

    last_message_at: dict[str, datetime] = {}
    messages_in_range: dict[str, int] = {}

    for message in messages_sorted:
        if message.author not in last_message_at or message.timestamp > last_message_at[message.author]:
            last_message_at[message.author] = message.timestamp
        if range_start <= message.timestamp <= reference_now:
            messages_in_range[message.author] = messages_in_range.get(message.author, 0) + 1

    authors = sorted(author for author, timestamp in last_message_at.items() if timestamp >= eligibility_start)

    days_since_last = {
        author: (reference_now - last_message_at[author]).total_seconds() / 86400 for author in authors
    }
    counts = {author: messages_in_range.get(author, 0) for author in authors}

    max_count = max(counts.values(), default=0)
    max_days = max(days_since_last.values(), default=0)

    members: list[MemberStats] = []
    for author in authors:
        count = counts[author]
        days = days_since_last[author]

        msg_score = 1.0 if max_count == 0 else 1.0 - (count / max_count)
        recency_score = 0.0 if max_days == 0 else days / max_days
        score = weight * recency_score + (1 - weight) * msg_score

        members.append(
            MemberStats(
                author=author,
                messages_in_range=count,
                last_message_at=last_message_at[author],
                days_since_last_message=round(days, 2),
                inactivity_score=round(score, 4),
            )
        )

    members.sort(key=lambda member: (-member.inactivity_score, member.messages_in_range, -member.days_since_last_message))

    activity_by_day = build_daily_activity(messages_sorted, range_start, reference_now)
    daily_snapshots = build_daily_snapshots(messages_sorted, range_start, reference_now)
    hourly_heatmap = build_hourly_heatmap(messages_sorted, range_start, reference_now)
    timeline_events = build_timeline_events(messages_sorted, range_start, reference_now, activity_by_day)
    reactivation_attempts = count_reactivation_attempts(daily_snapshots)
    reactivation_leaders = build_reactivation_leaders(messages_sorted, daily_snapshots)
    phase_summary = build_phase_summary(daily_snapshots)
    conversation_pattern = infer_conversation_pattern(members, daily_snapshots, reactivation_attempts)
    probable_cause = infer_probable_cause(members, daily_snapshots, reactivation_attempts, conversation_pattern)

    return AnalysisResult(
        reference_date=reference_now,
        range_start=range_start,
        range_end=reference_now,
        total_members=len(members),
        total_messages_in_range=sum(counts.values()),
        members=members,
        top3=members[:3],
        activity_by_day=activity_by_day,
        daily_snapshots=daily_snapshots,
        hourly_heatmap=hourly_heatmap,
        timeline_events=timeline_events,
        probable_cause=probable_cause,
        conversation_pattern=conversation_pattern,
        reactivation_attempts=reactivation_attempts,
        reactivation_leaders=reactivation_leaders,
        phase_summary=phase_summary,
    )
