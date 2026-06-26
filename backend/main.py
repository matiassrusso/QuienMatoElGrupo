"""API de Quien Mato el Grupo; todo el procesamiento ocurre en memoria."""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analysis import analyze
from parser import extract_chat_text, extract_group_name, parse_messages
from schemas import AnalysisResultOut

app = FastAPI(title="Quien Mato el Grupo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/analizar", response_model=AnalysisResultOut)
async def analizar(
    file: UploadFile = File(...),
    range_type: Literal["24h", "days", "weeks", "months"] = Form(...),
    range_value: Optional[int] = Form(None),
    weight: float = Form(0.5),
):
    contents = await file.read()

    try:
        chat_text = extract_chat_text(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = parse_messages(chat_text)
    group_name = extract_group_name(chat_text)

    if not messages:
        raise HTTPException(status_code=422, detail="No se encontraron mensajes validos en el chat exportado.")

    try:
        result = analyze(messages, range_type, range_value, weight)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalysisResultOut(
        group_name=group_name,
        reference_date=result.reference_date,
        range_start=result.range_start,
        range_end=result.range_end,
        total_members=result.total_members,
        total_messages_in_range=result.total_messages_in_range,
        members=[asdict(member) for member in result.members],
        top3=[asdict(member) for member in result.top3],
        activity_by_day=[asdict(item) for item in result.activity_by_day],
        daily_snapshots=[asdict(item) for item in result.daily_snapshots],
        hourly_heatmap=[asdict(item) for item in result.hourly_heatmap],
        timeline_events=[asdict(item) for item in result.timeline_events],
        probable_cause=result.probable_cause,
        conversation_pattern=result.conversation_pattern,
        reactivation_attempts=result.reactivation_attempts,
        reactivation_leaders=[asdict(item) for item in result.reactivation_leaders],
        phase_summary=[asdict(item) for item in result.phase_summary],
    )
