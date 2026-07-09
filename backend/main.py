"""API de Quien Mato el Grupo; todo el procesamiento ocurre en memoria."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from analysis import analyze
from clone import (
    MAX_MESSAGES_PER_SESSION,
    build_clone_system_prompt,
    create_session,
    get_session,
    record_exchange,
    sample_style_messages,
)
from llm import LLMError, call_llm, stream_llm_chat
from parser import extract_chat_text, extract_group_name, parse_messages
from schemas import (
    AnalysisResultOut,
    ClonIniciarResponse,
    ClonMensajeRequest,
    VeredictoIARequest,
    VeredictoIAResponse,
)

app = FastAPI(title="Quien Mato el Grupo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

TONE_INSTRUCTIONS = {
    "forense": "Tono forense/serio, como un peritaje.",
    "neutral": "Tono neutral y descriptivo.",
    "bardero": "Tono con humor y sana argentina, sin dejar de ser preciso con los datos.",
}


def build_verdict_prompt(payload: VeredictoIARequest) -> tuple[str, str]:
    system_prompt = (
        "Sos un investigador que analiza la actividad de grupos de WhatsApp a partir de metricas agregadas "
        "(nunca recibis el contenido real de los mensajes). Escribi un veredicto breve (3 a 5 frases) en "
        "espanol rioplatense explicando quien parece responsable del enfriamiento del grupo y por que, "
        "basandote unicamente en los datos que se te dan. No inventes datos ni nombres que no aparezcan en el "
        "contexto. " + TONE_INSTRUCTIONS[payload.tone]
    )

    top3_lines = "\n".join(
        f"- {member.author}: {member.messages_in_range} mensajes en el periodo, "
        f"{member.days_since_last_message:.1f} dias sin escribir, {round(member.inactivity_score * 100)}% de inactividad"
        for member in payload.top3
    )
    reactivadores = ", ".join(f"{leader.author} ({leader.attempts})" for leader in payload.reactivation_leaders) or "ninguno detectado"
    fases = "\n".join(f"- {phase.label} ({phase.start_day} a {phase.end_day}): {phase.description}" for phase in payload.phase_summary)

    user_prompt = (
        f"Grupo: {payload.group_name or 'sin nombre'}\n"
        f"Miembros totales: {payload.total_members}\n"
        f"Mensajes totales en el periodo: {payload.total_messages_in_range}\n"
        f"Patron de conversacion detectado: {payload.conversation_pattern}\n"
        f"Intentos de reactivacion: {payload.reactivation_attempts}\n"
        f"Lideres de reactivacion: {reactivadores}\n"
        f"Top 3 por inactividad:\n{top3_lines}\n"
        f"Fases del periodo:\n{fases}\n"
        f"Causa probable calculada por reglas (como referencia, podes reformularla): {payload.rule_based_cause}"
    )

    return system_prompt, user_prompt


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
        interaction_graph=asdict(result.interaction_graph),
    )


@app.post("/veredicto-ia", response_model=VeredictoIAResponse)
async def veredicto_ia(payload: VeredictoIARequest):
    system_prompt, user_prompt = build_verdict_prompt(payload)

    try:
        verdict = await call_llm(payload.provider, payload.api_key, payload.model, system_prompt, user_prompt)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return VeredictoIAResponse(verdict=verdict)


@app.post("/clon-chat/iniciar", response_model=ClonIniciarResponse)
async def clon_chat_iniciar(file: UploadFile = File(...)):
    contents = await file.read()

    try:
        chat_text = extract_chat_text(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = parse_messages(chat_text)
    group_name = extract_group_name(chat_text)

    if not messages:
        raise HTTPException(status_code=422, detail="No se encontraron mensajes validos en el chat exportado.")

    token = create_session(messages, group_name)
    session = get_session(token)
    assert session is not None  # recien creada, no puede haber expirado

    return ClonIniciarResponse(
        token=token,
        authors=session.authors,
        group_name=group_name,
        message_count=len(messages),
    )


@app.post("/clon-chat/mensaje")
async def clon_chat_mensaje(payload: ClonMensajeRequest):
    session = get_session(payload.token)
    if session is None:
        raise HTTPException(status_code=404, detail="Tu sesion expiro. Volve a subir el chat para seguir charlando.")

    if session.message_count >= MAX_MESSAGES_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail=f"Llegaste al limite de {MAX_MESSAGES_PER_SESSION} mensajes para esta sesion. Volve a subir el chat para seguir.",
        )

    if payload.hablar_como is not None and payload.hablar_como not in session.authors:
        raise HTTPException(status_code=400, detail="Ese miembro no aparece en el chat subido.")

    sample = sample_style_messages(session.messages, payload.hablar_como)
    system_prompt = build_clone_system_prompt(sample, payload.hablar_como, session.group_name)
    history = session.chat_history + [{"role": "user", "content": payload.mensaje}]

    async def event_stream():
        collected: list[str] = []
        try:
            async for chunk in stream_llm_chat(payload.provider, payload.api_key, payload.model, system_prompt, history):
                collected.append(chunk)
                yield f"event: chunk\ndata: {json.dumps(chunk)}\n\n"
        except LLMError as exc:
            yield f"event: error\ndata: {json.dumps(str(exc))}\n\n"
            return

        record_exchange(payload.token, payload.mensaje, "".join(collected))
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
