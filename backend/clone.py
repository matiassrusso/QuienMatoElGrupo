"""Clon conversacional del grupo: sesion efimera en memoria + muestreo de
estilo (few-shot) para el prompt. Unica pieza del proyecto que expone texto
real de los mensajes y que mantiene estado entre requests -- ver disclaimer
de privacidad en el frontend (GroupClone.tsx) y en el README.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from parser import Message

# Vive solo en RAM del proceso: no sobrevive un restart ni escala a multiples
# instancias/workers (no hay store compartido tipo Redis). Aceptable para el
# alcance actual del proyecto -- si en algun momento se despliega con mas de
# un worker o necesita sobrevivir restarts, hay que migrar a un store externo.
SESSION_TTL_MINUTES = 45

# Tope de intercambios (ida y vuelta) por sesion, para que un loop accidental
# o una pestaña olvidada no gaste la key del usuario sin limite. La sesion ya
# expira sola por TTL, pero eso protege el tiempo, no la cantidad de llamadas.
MAX_MESSAGES_PER_SESSION = 30

MAX_SAMPLE_MESSAGES = 50
MAX_SAMPLE_CHARS = 6000
MAX_EXCERPT_CHARS = 220


@dataclass
class CloneSession:
    messages: list[Message]
    authors: list[str]
    group_name: str | None
    created_at: datetime
    expires_at: datetime
    chat_history: list[dict[str, str]] = field(default_factory=list)
    message_count: int = 0


_sessions: dict[str, CloneSession] = {}


def _purge_expired() -> None:
    """Barrido perezoso: corre en cada sesion nueva, asi no hace falta un
    scheduler/background task solo para limpiar sesiones que nunca se
    vuelven a consultar (y que igual expirarian al accederlas via
    get_session)."""
    now = datetime.now()
    expired = [token for token, session in _sessions.items() if session.expires_at <= now]
    for token in expired:
        del _sessions[token]


def create_session(messages: list[Message], group_name: str | None) -> str:
    _purge_expired()
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    _sessions[token] = CloneSession(
        messages=messages,
        authors=sorted({message.author for message in messages}),
        group_name=group_name,
        created_at=now,
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    return token


def get_session(token: str) -> CloneSession | None:
    session = _sessions.get(token)
    if session is None:
        return None
    if session.expires_at <= datetime.now():
        del _sessions[token]
        return None
    return session


def record_exchange(token: str, user_message: str, assistant_message: str) -> None:
    session = _sessions.get(token)
    if session is None:
        return
    session.chat_history.append({"role": "user", "content": user_message})
    session.chat_history.append({"role": "assistant", "content": assistant_message})
    session.message_count += 1


def _excerpt(text: str) -> str:
    flat = text.strip().replace("\n", " ")
    if len(flat) <= MAX_EXCERPT_CHARS:
        return flat
    return flat[:MAX_EXCERPT_CHARS].rstrip() + "…"


def _split_into_buckets(messages: list[Message], bucket_count: int) -> list[list[Message]]:
    size = max(1, len(messages) // bucket_count)
    return [messages[i : i + size] for i in range(0, len(messages), size)]


def sample_style_messages(messages: list[Message], hablar_como: str | None) -> list[Message]:
    """Muestra representativa de tono para el few-shot del clon.

    No se manda el chat completo en cada request: es caro y probablemente
    excede el contexto en grupos grandes. El tamano de la muestra esta
    acotado por MAX_SAMPLE_MESSAGES (~50 mensajes, en linea con "few-shot",
    no "historial completo") y MAX_SAMPLE_CHARS (~6000 caracteres, ~1500
    tokens) -- lo que se cumpla primero corta el muestreo.
    """
    candidates = [message for message in messages if message.text.strip()]

    if hablar_como is not None:
        author_messages = [message for message in candidates if message.author == hablar_como]
        return _sample_spread(author_messages)

    # Modo general: reparte la muestra en franjas temporales iguales y, dentro
    # de cada franja, alterna autores round-robin -- asi ni quien mas
    # escribio ni el tramo final del chat dominan la muestra de tono.
    if not candidates:
        return []

    bucket_count = min(10, max(1, len(candidates) // 5))
    buckets = _split_into_buckets(candidates, bucket_count)
    per_bucket_quota = max(1, MAX_SAMPLE_MESSAGES // len(buckets))

    sample: list[Message] = []
    total_chars = 0

    for bucket in buckets:
        by_author: dict[str, list[Message]] = {}
        for message in bucket:
            by_author.setdefault(message.author, []).append(message)

        authors_cycle = list(by_author.keys())
        taken_in_bucket = 0
        while authors_cycle and taken_in_bucket < per_bucket_quota:
            for author in list(authors_cycle):
                queue = by_author[author]
                if not queue:
                    authors_cycle.remove(author)
                    continue
                message = queue.pop(0)
                sample.append(message)
                total_chars += len(message.text)
                taken_in_bucket += 1
                if taken_in_bucket >= per_bucket_quota or len(sample) >= MAX_SAMPLE_MESSAGES:
                    break
            if total_chars >= MAX_SAMPLE_CHARS or len(sample) >= MAX_SAMPLE_MESSAGES:
                break
        if total_chars >= MAX_SAMPLE_CHARS or len(sample) >= MAX_SAMPLE_MESSAGES:
            break

    sample.sort(key=lambda message: message.timestamp)
    return sample


def _sample_spread(messages: list[Message]) -> list[Message]:
    """Muestreo espaciado a lo largo del tiempo (no solo los ultimos
    mensajes) -- usado para el modo 'hablar como X'."""
    if not messages:
        return []

    step = max(1, len(messages) // MAX_SAMPLE_MESSAGES)
    spread = messages[::step][:MAX_SAMPLE_MESSAGES]

    result: list[Message] = []
    total_chars = 0
    for message in spread:
        total_chars += len(message.text)
        result.append(message)
        if total_chars >= MAX_SAMPLE_CHARS:
            break
    return result


def build_clone_system_prompt(sample: list[Message], hablar_como: str | None, group_name: str | None) -> str:
    label = group_name or "el grupo"
    sample_block = "\n".join(f"{message.author}: {_excerpt(message.text)}" for message in sample) or "(sin mensajes de muestra)"

    if hablar_como:
        return (
            f'Sos una simulacion de estilo de como escribe "{hablar_como}" en el chat de WhatsApp "{label}", basada '
            "unicamente en el tono, vocabulario y muletillas que se ven en la siguiente muestra real de sus "
            f"mensajes. Imita ese estilo al responder. Dejá siempre claro, si el contexto lo amerita, que sos una "
            f"imitacion generada por IA y no la persona real -- no inventes hechos, opiniones ni datos personales "
            f"de {hablar_como} que no se desprendan del tono de la muestra.\n\n"
            f"Muestra de mensajes reales de {hablar_como}:\n{sample_block}"
        )

    return (
        f'Sos una simulacion de estilo del chat de WhatsApp grupal "{label}", basada unicamente en el tono, '
        "vocabulario y dinamica que se ven en la siguiente muestra real de mensajes de varios miembros. Imita ese "
        "estilo colectivo al responder (no el de una persona en particular) -- no inventes hechos ni opiniones "
        "reales de nadie del grupo mas alla de lo que el tono de la muestra sugiere.\n\n"
        f"Muestra de mensajes reales del grupo:\n{sample_block}"
    )
