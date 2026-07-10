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

# TPM/TPD reales de cada provider en su tier gratuito/inicial (investigado
# sesion 6, fuentes de terceros -- no doc oficial, puede necesitar ajuste).
# Determinan cuanto se puede "leer" de una sola vez en la pasada de
# comprension inicial (ver build_reading_pass_prompt) sin que el pedido
# falle o se coma el dia entero de cuota. Groq es por lejos el mas ajustado:
# 12k tokens/minuto y apenas 100k tokens/dia en el free tier -- una lectura
# de 30-40k tokens ahi ni siquiera entraria en un solo pedido. Gemini tiene
# 250k TPM compartidos y ventana de 1M, mucho mas margen.

# Los valores dejan margen real bajo el limite: la heuristica de 4
# caracteres/token es aproximada (texto informal con acentos/emojis/marcas
# invisibles de WhatsApp suele tokenizar mas denso que eso en la practica),
# y al presupuesto hay que sumarle el prompt del "analista" y la respuesta
# del modelo, no solo la muestra. Groq en particular no tiene margen para
# errores de estimacion: 5000 tokens de entrada deja ~7000 de colchon sobre
# el limite real de 12000 TPM.
READING_PASS_TOKEN_BUDGET = {
    "groq": 5000,
    "gemini": 60000,
    "anthropic": 20000,
    "openai": 15000,
    # NVIDIA build.nvidia.com no publica TPM, solo ~40 req/min por key -- pero
    # el default (mixtral-8x7b, elegido por ser el mas grande que responde
    # rapido en el free tier, ver DEFAULT_MODELS en llm.py) tiene ventana de
    # ~32k tokens, asi que el limite real ahi es el contexto del modelo.
    "nvidia": 20000,
}
DEFAULT_READING_PASS_TOKEN_BUDGET = 5000  # provider desconocido: el mas conservador


@dataclass
class CloneSession:
    messages: list[Message]
    authors: list[str]
    group_name: str | None
    created_at: datetime
    expires_at: datetime
    chat_history: list[dict[str, str]] = field(default_factory=list)
    message_count: int = 0
    # Ficha de estilo generada una vez por modo (None = tono general, o el
    # nombre de la persona en modo "hablar como X") -- ver
    # build_reading_pass_prompt. Evita rehacer la lectura completa en cada
    # mensaje.
    persona_briefs: dict[str | None, str] = field(default_factory=dict)
    persona_brief_failed: set[str | None] = field(default_factory=set)


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


def sample_style_messages(
    messages: list[Message],
    hablar_como: str | None,
    max_messages: int = MAX_SAMPLE_MESSAGES,
    max_chars: int = MAX_SAMPLE_CHARS,
) -> list[list[Message]]:
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
    grupos grandes. Tamano acotado por max_messages/max_chars (default: la
    muestra chica de cada mensaje: MAX_SAMPLE_MESSAGES/MAX_SAMPLE_CHARS;
    sample_for_reading_pass pasa un budget mucho mas grande para la lectura
    inicial), lo que se cumpla primero corta el muestreo.
    """
    candidates = [
        message
        for message in messages
        if message.text.strip() and not _OMITTED_ATTACHMENT_RE.search(message.text.strip())
    ]
    if not candidates:
        return []

    desired_windows = max(1, max_messages // WINDOW_SIZE)
    available_windows = max(1, len(candidates) // WINDOW_SIZE)
    bucket_count = min(desired_windows, available_windows)

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
        if total_chars >= max_chars or total_messages >= max_messages:
            break

    return sample


def sample_for_reading_pass(messages: list[Message], hablar_como: str | None, token_budget: int) -> list[list[Message]]:
    """Muestra mucho mas grande que la de cada mensaje, para la pasada unica
    de 'lectura' de la conversacion (ver build_reading_pass_prompt). El tope
    sale del presupuesto de tokens del provider elegido (READING_PASS_TOKEN_BUDGET),
    no de una constante fija -- asi se adapta a Groq (muy ajustado) o Gemini
    (mucho mas margen) sin romper ninguno de los dos."""
    # Antes se asumian ~4 caracteres/token (generico para texto en ingles).
    # Con datos reales (chat de WhatsApp en castellano, emojis/acentos/jerga)
    # se midio ~1.75 char/token -- mas del doble de denso. Causaba que la
    # pasada de lectura mandara ~2x mas tokens de los presupuestados y
    # rompiera el limite real del provider (confirmado con NVIDIA: request
    # de 45666 tokens contra un limite de 32768, con budget nominal de solo
    # 20000). 2 char/token deja margen real sobre el valor medido.
    max_chars = token_budget * 2
    max_messages = max(WINDOW_SIZE, token_budget // 6)  # ~6 tokens promedio por mensaje corto
    return sample_style_messages(messages, hablar_como, max_messages=max_messages, max_chars=max_chars)


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
    "te dice -- no ignores el mensaje ni sueltes frases sacadas de lo de arriba sin relacion con lo que te "
    "preguntan. Usa mensajes cortos, estilo WhatsApp (1-3 lineas), con el tono/vocabulario/muletillas que se ven "
    "arriba, pero conversando de verdad sobre lo que te dicen. Respondes SIEMPRE en castellano rioplatense (el "
    "idioma del chat de arriba), nunca en ingles."
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


_VOCABULARY_RULE_FROM_BRIEF = (
    "Usa la jerga, apodos y frases especificas que menciona la ficha de arriba. No inventes modismos genericos que "
    "no salgan de ahi -- el objetivo es sonar como ESTE grupo especifico, no como un arquetipo generico de chat."
)


def build_reading_pass_prompt(
    sample: list[list[Message]], hablar_como: str | None, group_name: str | None
) -> tuple[str, str]:
    """System+user prompt para la pasada unica de "lectura" que resume una
    muestra grande del chat en una ficha de estilo compacta (ver
    CloneSession.persona_briefs). Se llama una sola vez por sesion y por
    modo (no en cada mensaje) -- pedido explicito del usuario de que el
    clon "se tome su tiempo y entienda la conversacion" antes de charlar,
    en vez de solo pattern-matchear fragmentos sueltos en cada turno.
    """
    label = group_name or "el grupo"
    sample_block = _format_sample(sample)

    system_prompt = (
        "Sos un analista de estilo conversacional. Te van a dar fragmentos reales de un chat de WhatsApp y tenes "
        "que resumir, en un texto corto (maximo ~200 palabras), como habla ese grupo: jerga y palabras especificas "
        "que usan, apodos, chistes internos o referencias que se repiten, muletillas, tono general (formal/informal, "
        "que tipo de humor). Se concreto y especifico de ESTE grupo -- nada de generalidades tipo 'usan jerga "
        "informal', dame ejemplos reales de palabras/frases que aparecen en los fragmentos. No resumas de que "
        "hablan (el contenido), solo COMO hablan (el estilo). Escribi la ficha en castellano rioplatense, "
        "nunca en ingles, sin importar en que idioma este el resto de estas instrucciones."
    )

    if hablar_como:
        user_prompt = (
            f'Fragmentos reales de "{label}" donde participa {hablar_como} (separados por "---"):\n\n{sample_block}'
            f"\n\nResumime especificamente el estilo de {hablar_como}: su vocabulario, muletillas, tono particular."
        )
    else:
        user_prompt = (
            f'Fragmentos reales del chat grupal "{label}" (separados por "---"):\n\n{sample_block}\n\nResumime el '
            "estilo colectivo del grupo (no el de una persona en particular)."
        )

    return system_prompt, user_prompt


def build_clone_system_prompt_from_brief(persona_brief: str, hablar_como: str | None, group_name: str | None) -> str:
    """Prompt por-mensaje una vez que ya existe la ficha de estilo (mas
    barato que reenviar los fragmentos crudos en cada turno de la charla)."""
    label = group_name or "el grupo"
    rules = f"{_CONVERSATION_RULE}\n\n{_VOCABULARY_RULE_FROM_BRIEF}\n\n{_NOT_AN_ASSISTANT_RULE}"

    if hablar_como:
        intro = (
            f'Sos una simulacion de estilo de como escribe "{hablar_como}" en el chat de WhatsApp "{label}". Esta '
            f"es la ficha de estilo de {hablar_como}, generada a partir de mensajes reales suyos:\n\n{persona_brief}"
            f"\n\nDejá siempre claro, si el contexto lo amerita, que sos una imitacion generada por IA y no la "
            f"persona real -- no inventes hechos, opiniones ni datos personales de {hablar_como} que no se "
            "desprendan de la ficha."
        )
    else:
        intro = (
            f'Sos una simulacion de estilo del chat de WhatsApp grupal "{label}". Esta es la ficha de estilo del '
            f"grupo, generada a partir de mensajes reales:\n\n{persona_brief}\n\nNo inventes hechos ni opiniones "
            "reales de nadie del grupo mas alla de lo que la ficha sugiere."
        )

    return f"{intro}\n\n{rules}"


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
