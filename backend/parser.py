"""Parseo de exports de chat de WhatsApp (.zip -> mensajes reales en memoria)."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime

LRM_RLM = "\u200e\u200f"

# Soporta variantes Android ("DD/MM/YY, HH:MM - Autor: msg") e iOS
# ("[DD/MM/YYYY, HH:MM:SS] Autor: msg"), con o sin segundos, 12h/24h
# y con marcas invisibles LRM/RLM. Se evita dateutil para bajar bastante
# el costo de parseo en chats largos.
LINE_RE = re.compile(
    r"^[{lrm}]?"
    r"(?:\[(?P<ts_b>\d{{1,2}}/\d{{1,2}}/\d{{2,4}},\s*\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:\s*[ap]\.?\s*m\.?)?)\]"
    r"|(?P<ts_d>\d{{1,2}}/\d{{1,2}}/\d{{2,4}},\s*\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:\s*[ap]\.?\s*m\.?)?)\s*-)"
    r"\s*(?P<rest>.*)$".format(lrm=LRM_RLM),
    re.IGNORECASE,
)

TIMESTAMP_RE = re.compile(
    r"^\s*(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{2,4}),\s*"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2}))?"
    r"(?:\s*(?P<ampm>[ap]\.?\s*m\.?))?\s*$",
    re.IGNORECASE,
)

# Frases de notificaciones de sistema (ingles + espanol). Se matchean contra
# el texto del mensaje, no contra el autor.
SYSTEM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"end-to-end encrypted",
        r"created (this|the) group",
        r"cre[oó] (este|el) grupo",
        r"\badded you$",
        r"\bte a[ñn]adi[oó]$",
        r"\bte agreg[oó]$",
        r"^[^:]+ added [^:]+$",
        r"^[^:]+ a[ñn]adi[oó] a [^:]+$",
        r"^[^:]+ agreg[oó] a [^:]+$",
        r"\bleft$",
        r"sali[oó] del grupo$",
        r"^[^:]+ sali[oó]$",
        r"removed [^:]+$",
        r"elimin[oó] a [^:]+$",
        r"quit[oó] a [^:]+$",
        r"changed the subject",
        r"cambi[oó] el asunto",
        r"changed this group.s icon",
        r"cambi[oó] el [ií]cono de este grupo",
        r"changed the group (description|name)",
        r"cambi[oó] (la descripci[oó]n|el nombre) del grupo",
        r"security code (with|changed)",
        r"c[oó]digo de seguridad",
        r"joined using this group.s invite link",
        r"se uni[oó] usando el enlace",
        r"pinned a message$",
        r"fij[oó] un mensaje$",
        r"changed their phone number",
        r"cambi[oó] su n[uú]mero",
        r"no longer an admin",
        r"now an admin",
        r"ya no (es|son) administrador",
        r"ahora (es|son) administrador",
        r"changed (this|the) group.s settings",
        r"changed the settings so",
        r"^[^:]+ updated .+$",
        r"^only messages that mention or .*meta ai",
    ]
]

BOT_AUTHORS = {"Meta AI"}


@dataclass
class Message:
    author: str
    timestamp: datetime
    text: str


def _is_system_text(text: str) -> bool:
    stripped = text.lstrip(LRM_RLM)
    return any(pattern.search(stripped) for pattern in SYSTEM_PATTERNS)


def _normalize_ampm(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw.lower().replace(".", "").replace(" ", "")


def _parse_timestamp(raw: str) -> datetime | None:
    match = TIMESTAMP_RE.match(raw.replace("\u202f", " "))
    if match is None:
        return None

    try:
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        second = int(match.group("second") or 0)
    except ValueError:
        return None

    if year < 100:
        year += 2000

    ampm = _normalize_ampm(match.group("ampm"))
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def _find_chat_txt(zf: zipfile.ZipFile) -> str | None:
    candidates = [name for name in zf.namelist() if name.lower().endswith(".txt")]
    return candidates[0] if candidates else None


def extract_chat_text(zip_bytes: bytes) -> str:
    """Encuentra y decodifica el .txt del chat dentro del .zip, sin tocar disco."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = _find_chat_txt(zf)
        if name is None:
            raise ValueError("El .zip no contiene ningun archivo .txt de chat de WhatsApp.")
        raw = zf.read(name)
    return raw.decode("utf-8-sig", errors="replace")


def parse_messages(chat_text: str) -> list[Message]:
    """Parsea el texto del chat a una lista de mensajes reales (filtra sistema y bots)."""
    messages: list[Message] = []

    for line in chat_text.splitlines():
        match = LINE_RE.match(line)
        if match is None:
            if messages:
                messages[-1].text += "\n" + line
            continue

        ts_raw = match.group("ts_b") or match.group("ts_d")
        rest = match.group("rest")
        timestamp = _parse_timestamp(ts_raw)
        if timestamp is None:
            if messages:
                messages[-1].text += "\n" + line
            continue

        author, separator, text = rest.partition(": ")
        if separator == "":
            continue
        if _is_system_text(text):
            continue
        if author in BOT_AUTHORS:
            continue

        messages.append(Message(author=author, timestamp=timestamp, text=text))

    return messages


RENAME_RE = re.compile(
    r'changed the group name to\s*["“](?P<name>.+?)["”]\s*$'
    r'|cambi[oó] el nombre del grupo a\s*["“](?P<name_es>.+?)["”]\s*$',
    re.IGNORECASE,
)


def extract_group_name(chat_text: str) -> str | None:
    """Detecta el nombre del grupo o contacto a partir del export."""
    last_rename: str | None = None

    for line in chat_text.splitlines():
        match = LINE_RE.match(line)
        if match is None:
            continue

        rest = match.group("rest")
        author, separator, text = rest.partition(": ")
        if separator == "":
            continue

        stripped = text.lstrip(LRM_RLM)
        if re.search(r"end-to-end encrypted", stripped, re.IGNORECASE):
            return author

        rename_match = RENAME_RE.search(stripped)
        if rename_match:
            last_rename = rename_match.group("name") or rename_match.group("name_es")

    return last_rename


def parse_zip(zip_bytes: bytes) -> list[Message]:
    chat_text = extract_chat_text(zip_bytes)
    return parse_messages(chat_text)
