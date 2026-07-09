"""Clon conversacional del grupo: sesion efimera en memoria + muestreo de
estilo (few-shot) para el prompt. Unica pieza del proyecto que expone texto
real de los mensajes y que mantiene estado entre requests -- ver disclaimer
de privacidad en el frontend (GroupClone.tsx) y en el README.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from parser import Message

# Placeholders que WhatsApp deja cuando el mensaje es un adjunto sin texto
# ("audio omitted", "image omitted", etc, a veces con un "@Autor " adelante
# por una mencion). En un chat real llegan a ser 1 de cada 6 mensajes -- puro
# ruido para el tono, asi que se descartan del muestreo de estilo.
_OMITTED_ATTACHMENT_RE = re.compile(r"\bomitted$", re.IGNORECASE)

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

# Tamano de cada "ventana" de contexto conversacional (ver sample_style_messages).
WINDOW_SIZE = 8
# Mensajes de contexto antes/despues de la primera aparicion de la persona
# elegida en el modo "hablar como X", para mostrar a que le esta respondiendo.
CONTEXT_PADDING = 2


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


def _distinct_authors(window: list[Message]) -> int:
    return len({message.author for message in window})


def _best_window(bucket: list[Message]) -> list[Message]:
    """Dentro de una franja temporal, elige la ventana de WINDOW_SIZE
    mensajes consecutivos con mas autores distintos -- un intercambio real,
    no una racha de un solo autor."""
    if not bucket:
        return []
    if len(bucket) <= WINDOW_SIZE:
        return bucket
    offsets = sorted({0, len(bucket) // 4, len(bucket) // 2, (3 * len(bucket)) // 4})
    candidates = [bucket[offset : offset + WINDOW_SIZE] for offset in offsets]
    return max(candidates, key=_distinct_authors)


def _general_windows(candidates: list[Message], bucket_count: int) -> list[list[Message]]:
    buckets = _split_into_buckets(candidates, bucket_count)
    return [window for bucket in buckets if (window := _best_window(bucket))]


def _author_windows(candidates: list[Message], author: str, bucket_count: int) -> list[list[Message]]:
    """Para el modo 'hablar como X': ventanas centradas en apariciones de esa
    persona, con un poco de contexto de quien le hablaba -- no solo sus
    lineas sueltas, sino a que estaba respondiendo de verdad."""
    buckets = _split_into_buckets(candidates, bucket_count)
    windows: list[list[Message]] = []
    for bucket in buckets:
        first_index = next((index for index, message in enumerate(bucket) if message.author == author), None)
        if first_index is None:
            continue
        start = max(0, first_index - CONTEXT_PADDING)
        end = min(len(bucket), first_index + CONTEXT_PADDING + 1)
        window = bucket[start:end]
        if window:
            windows.append(window)
    return windows


def sample_style_messages(messages: list[Message], hablar_como: str | None) -> list[list[Message]]:
    """Fragmentos de conversacion real (few-shot) para el prompt del clon.

    Devuelve ventanas de varios mensajes consecutivos -- no lineas sueltas de
    distintos puntos del historial. Esto es deliberado: en un chat largo
    (años de historia), muestrear mensajes individuales aislados produce una
    "muestra" sin ninguna coherencia conversacional (ej: una linea de 2022
    seguida de una de 2024, sin relacion entre si), y el modelo termina
    citando fragmentos sueltos de la muestra en vez de responder de verdad a
    lo que le dicen. Mostrarle intercambios reales (alguien dice algo, otro
    responde) es lo que le da ritmo y coherencia a la imitacion.

    No se manda el chat completo: caro y probablemente excede el contexto en
    grupos grandes. Tamano acotado por MAX_SAMPLE_MESSAGES / MAX_SAMPLE_CHARS,
    lo que se cumpla primero corta el muestreo.
    """
    candidates = [
        message
        for message in messages
        if message.text.strip() and not _OMITTED_ATTACHMENT_RE.search(message.text.strip())
    ]
    if not candidates:
        return []

    bucket_count = min(10, max(1, len(candidates) // 20))

    if hablar_como is not None:
        windows = _author_windows(candidates, hablar_como, bucket_count)
    else:
        windows = _general_windows(candidates, bucket_count)

    sample: list[list[Message]] = []
    total_chars = 0
    total_messages = 0
    for window in windows:
        sample.append(window)
        total_chars += sum(len(message.text) for message in window)
        total_messages += len(window)
        if total_chars >= MAX_SAMPLE_CHARS or total_messages >= MAX_SAMPLE_MESSAGES:
            break

    return sample


def _format_sample(sample: list[list[Message]]) -> str:
    if not sample:
        return "(sin mensajes de muestra)"
    blocks = [
        "\n".join(f"{message.author}: {_excerpt(message.text)}" for message in window) for window in sample
    ]
    return "\n---\n".join(blocks)


# Instruccion reforzada tras un bug real detectado con un grupo grande: con
# la muestra vieja (lineas sueltas de años distintos, sin conversacion real)
# el modelo respondia con frases inconexas, a veces citando casi textual una
# linea de la muestra sin relacion con lo que se le preguntaba. Ahora la
# muestra son fragmentos de charla real (ver sample_style_messages) y ademas
# se le deja explicito que tiene que sostener una conversacion de verdad, no
# recitar la muestra.
_CONVERSATION_RULE = (
    "A partir de aca vas a charlar en vivo con una persona real. Respondele de forma directa y coherente a lo que "
    "te dice -- no ignores el mensaje ni sueltes frases sacadas de los fragmentos de arriba sin relacion con lo "
    "que te preguntan. Usa mensajes cortos, estilo WhatsApp (1-3 lineas), con el tono/vocabulario/muletillas que "
    "se ven en esos fragmentos, pero conversando de verdad sobre lo que te dicen."
)

# Bug real detectado por el usuario: le pidio que le resuelva un ejercicio de
# Python y el clon actuo como asistente generico (le escribio el codigo
# completo), rompiendo el personaje por completo. El prompt de arriba nunca
# decia explicitamente que NO es un asistente -- se agrega la prohibicion
# directa.
_NOT_AN_ASSISTANT_RULE = (
    "Importante: no sos un asistente de proposito general (no ChatGPT, no un tutor, no una IA que ayuda con "
    "tareas). Si te piden algo que claramente no es una charla de WhatsApp con amigos -- resolver ejercicios, "
    "escribir codigo, ayuda con la facultad o el laburo, actuar como asistente -- NO lo hagas ni des la solucion. "
    "Respondele como responderia alguien real del grupo que no tiene ganas de hacer de profesor: cortala con "
    "humor, mandala a buscarlo en Google, cambiale el tema -- pero nunca cumplas el pedido literal."
)

# Otro bug real: el clon respondia coherente pero con jerga "argentina de
# manual" inventada (ej. dijo "chimarrao", que ni siquiera es jerga
# argentina) en vez del vocabulario especifico de ESE grupo. La instruccion
# vieja pedia "imitar el tono" en abstracto, sin pedir explicitamente que
# reuse palabras/frases textuales de la muestra -- un modelo mediocre cae en
# el registro generico mas probable en vez de anclarse en el ejemplo real.
_VOCABULARY_RULE = (
    "Fijate bien en las palabras, apodos, frases hechas y jerga EXACTA que aparecen en los fragmentos de arriba, y "
    "reusalas cuando tengan sentido en tu respuesta. No inventes jerga generica de otro lado que no salga de los "
    "fragmentos (nada de modismos random tipo 'che boludo' de manual si el grupo no habla asi) -- el objetivo es "
    "sonar como ESTE grupo especifico, no como un arquetipo generico de chat argentino."
)


def build_clone_system_prompt(sample: list[list[Message]], hablar_como: str | None, group_name: str | None) -> str:
    label = group_name or "el grupo"
    sample_block = _format_sample(sample)
    rules = f"{_CONVERSATION_RULE}\n\n{_VOCABULARY_RULE}\n\n{_NOT_AN_ASSISTANT_RULE}"

    if hablar_como:
        intro = (
            f'Sos una simulacion de estilo de como escribe "{hablar_como}" en el chat de WhatsApp "{label}". Abajo '
            f'hay fragmentos reales de conversaciones donde {hablar_como} participa (separados por "---"), para '
            "que aprendas su tono, vocabulario y muletillas -- son solo referencia de estilo, no la charla actual."
        )
        disclaimer = (
            f"Dejá siempre claro, si el contexto lo amerita, que sos una imitacion generada por IA y no la persona "
            f"real -- no inventes hechos, opiniones ni datos personales de {hablar_como} que no se desprendan del "
            f"tono de los fragmentos."
        )
        return (
            f"{intro}\n\nFragmentos reales con mensajes de {hablar_como}:\n{sample_block}\n\n{rules}\n\n{disclaimer}"
        )

    intro = (
        f'Sos una simulacion de estilo del chat de WhatsApp grupal "{label}". Abajo hay fragmentos reales de '
        'conversaciones del grupo (separados por "---"), para que aprendas su tono, vocabulario y dinamica '
        "colectiva -- son solo referencia de estilo, no la charla actual."
    )
    disclaimer = "No inventes hechos ni opiniones reales de nadie del grupo mas alla de lo que el tono de los fragmentos sugiere."
    return f"{intro}\n\nFragmentos reales de conversaciones del grupo:\n{sample_block}\n\n{rules}\n\n{disclaimer}"
