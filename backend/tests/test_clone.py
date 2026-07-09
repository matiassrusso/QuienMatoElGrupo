import asyncio
import io
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

import clone
import main
from clone import (
    MAX_SAMPLE_CHARS,
    MAX_SAMPLE_MESSAGES,
    WINDOW_SIZE,
    build_clone_system_prompt,
    create_session,
    get_session,
    record_exchange,
    sample_style_messages,
)
from parser import Message
from schemas import ClonMensajeRequest


def make_chat_zip(chat_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("_chat.txt", chat_text)
    return buffer.getvalue()


class SessionStoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        clone._sessions.clear()

    def test_create_and_get_session_roundtrip(self) -> None:
        messages = [Message(author="Ana", timestamp=datetime(2026, 1, 1), text="hola")]

        token = create_session(messages, "Los Pibes")
        session = get_session(token)

        self.assertIsNotNone(session)
        self.assertEqual(session.authors, ["Ana"])
        self.assertEqual(session.group_name, "Los Pibes")
        self.assertEqual(session.message_count, 0)

    def test_expired_session_returns_none_and_is_purged(self) -> None:
        token = create_session([Message(author="Ana", timestamp=datetime(2026, 1, 1), text="hola")], None)
        clone._sessions[token].expires_at = datetime.now() - timedelta(seconds=1)

        self.assertIsNone(get_session(token))
        self.assertNotIn(token, clone._sessions)

    def test_new_session_lazily_purges_other_expired_sessions(self) -> None:
        stale_token = create_session([Message(author="Ana", timestamp=datetime(2026, 1, 1), text="hola")], None)
        clone._sessions[stale_token].expires_at = datetime.now() - timedelta(seconds=1)

        create_session([Message(author="Beto", timestamp=datetime(2026, 1, 1), text="hola")], None)

        self.assertNotIn(stale_token, clone._sessions)

    def test_record_exchange_appends_history_and_increments_count(self) -> None:
        token = create_session([Message(author="Ana", timestamp=datetime(2026, 1, 1), text="hola")], None)

        record_exchange(token, "hola clon", "hola como va")

        session = get_session(token)
        self.assertEqual(session.message_count, 1)
        self.assertEqual(
            session.chat_history,
            [{"role": "user", "content": "hola clon"}, {"role": "assistant", "content": "hola como va"}],
        )


def make_conversation(base: datetime, authors: list[str], count: int, start_offset_hours: float = 0) -> list[Message]:
    """Una racha de mensajes alternando autores cada uno, simulando un
    intercambio real (no un monologo)."""
    return [
        Message(
            author=authors[index % len(authors)],
            timestamp=base + timedelta(hours=start_offset_hours, minutes=index),
            text=f"mensaje {index}",
        )
        for index in range(count)
    ]


class SampleStyleMessagesTests(unittest.TestCase):
    def test_general_mode_returns_windows_with_real_exchanges(self) -> None:
        base = datetime(2026, 1, 1)
        # Varias franjas temporales separadas, cada una con un intercambio real
        # entre Ana y Beto -- simula conversaciones reales, no lineas sueltas.
        messages: list[Message] = []
        for week in range(8):
            messages += make_conversation(base, ["Ana", "Beto"], 20, start_offset_hours=week * 24 * 7)

        sample = sample_style_messages(messages, None)

        self.assertTrue(sample)
        total_messages = sum(len(window) for window in sample)
        # El corte respeta ventanas completas (no trunca a mitad de un
        # intercambio), asi que puede pasarse por hasta una ventana entera.
        self.assertLessEqual(total_messages, MAX_SAMPLE_MESSAGES + WINDOW_SIZE)
        # Cada ventana devuelta tiene que ser un intercambio real (mas de un
        # autor), no una racha de una sola persona -- es el bug que se arreglo.
        multi_author_windows = [window for window in sample if len({m.author for m in window}) > 1]
        self.assertGreater(len(multi_author_windows), 0)
        # La muestra cubre varias franjas del rango temporal, no solo una.
        distinct_days = {window[0].timestamp.date() for window in sample}
        self.assertGreater(len(distinct_days), 1)

    def test_hablar_como_windows_all_contain_that_author(self) -> None:
        base = datetime(2026, 1, 1)
        messages: list[Message] = []
        for week in range(8):
            messages += make_conversation(base, ["Ana", "Beto"], 20, start_offset_hours=week * 24 * 7)

        sample = sample_style_messages(messages, "Ana")

        self.assertTrue(sample)
        for window in sample:
            self.assertIn("Ana", {message.author for message in window})

    def test_filters_out_attachment_placeholders(self) -> None:
        base = datetime(2026, 1, 1)
        messages = [
            Message(author="Ana", timestamp=base, text="che mira esto"),
            Message(author="Beto", timestamp=base + timedelta(minutes=1), text="‎image omitted"),
            Message(author="Ana", timestamp=base + timedelta(minutes=2), text="‎audio omitted"),
            Message(author="Beto", timestamp=base + timedelta(minutes=3), text="jajaja que es eso"),
        ]

        sample = sample_style_messages(messages, None)

        sampled_texts = [message.text for window in sample for message in window]
        self.assertNotIn("‎image omitted", sampled_texts)
        self.assertNotIn("‎audio omitted", sampled_texts)

    def test_respects_message_and_char_budget_with_long_messages(self) -> None:
        base = datetime(2026, 1, 1)
        long_text = "palabra " * 200  # bien por encima del budget individual
        messages: list[Message] = []
        for week in range(20):
            messages += [
                Message(author="Ana", timestamp=base + timedelta(hours=week * 24 * 7, minutes=i), text=long_text)
                for i in range(10)
            ]

        sample = sample_style_messages(messages, "Ana")

        total_chars = sum(len(message.text) for window in sample for message in window)
        total_messages = sum(len(window) for window in sample)
        self.assertLessEqual(total_messages, MAX_SAMPLE_MESSAGES + WINDOW_SIZE)
        self.assertLessEqual(total_chars, MAX_SAMPLE_CHARS + WINDOW_SIZE * len(long_text))

    def test_empty_messages_returns_empty_sample(self) -> None:
        self.assertEqual(sample_style_messages([], None), [])
        self.assertEqual(sample_style_messages([], "Ana"), [])


class BuildCloneSystemPromptTests(unittest.TestCase):
    def test_general_mode_mentions_group_and_conversation_rule(self) -> None:
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]
        prompt = build_clone_system_prompt(sample, None, "Los Pibes")

        self.assertIn("Los Pibes", prompt)
        self.assertIn("dinamica colectiva", prompt)
        self.assertIn("Respondele de forma directa y coherente", prompt)

    def test_prompt_refuses_to_act_as_general_assistant(self) -> None:
        # Bug real: le pidieron resolver un ejercicio de Python y el clon
        # actuo como asistente generico, rompiendo el personaje.
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]

        general_prompt = build_clone_system_prompt(sample, None, "Los Pibes")
        hablar_como_prompt = build_clone_system_prompt(sample, "Ana", "Los Pibes")

        for prompt in (general_prompt, hablar_como_prompt):
            self.assertIn("no sos un asistente de proposito general", prompt)
            self.assertIn("NO lo hagas", prompt)

    def test_hablar_como_mode_names_the_member_and_disclaims_simulation(self) -> None:
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]
        prompt = build_clone_system_prompt(sample, "Ana", "Los Pibes")

        self.assertIn("Ana", prompt)
        self.assertIn("imitacion generada por IA", prompt)

    def test_multiple_windows_are_separated_in_the_prompt(self) -> None:
        sample = [
            [Message(author="Ana", timestamp=datetime(2026, 1, 1), text="hola")],
            [Message(author="Beto", timestamp=datetime(2026, 2, 1), text="q onda")],
        ]
        prompt = build_clone_system_prompt(sample, None, "Los Pibes")

        self.assertIn("---", prompt)


def make_session_with_zip(chat_text: str):
    zip_bytes = make_chat_zip(chat_text)
    upload = UploadFile(filename="chat.zip", file=io.BytesIO(zip_bytes))
    return asyncio.run(main.clon_chat_iniciar(file=upload))


async def _fake_stream_ok(*_args, **_kwargs):
    for chunk in ["Hola ", "como ", "va"]:
        yield chunk


async def _fake_stream_error(*_args, **_kwargs):
    from llm import LLMError

    raise LLMError("La API key no es valida.")
    yield ""  # pragma: no cover -- fuerza que sea un async generator


class ClonChatEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        clone._sessions.clear()

    def test_iniciar_returns_token_and_authors(self) -> None:
        response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia\n19/06/26, 10:00 - Juan: Todo bien")

        self.assertTrue(response.token)
        self.assertEqual(response.authors, ["Ana", "Juan"])

    def test_mensaje_streams_chunks_and_records_exchange(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia")
        payload = ClonMensajeRequest(token=session_response.token, mensaje="hola clon", provider="anthropic", api_key="fake")

        async def run():
            with patch.object(main, "stream_llm_chat", new=_fake_stream_ok):
                streaming_response = await main.clon_chat_mensaje(payload)
                return [chunk async for chunk in streaming_response.body_iterator]

        frames = asyncio.run(run())

        self.assertIn('event: chunk\ndata: "Hola "\n\n', frames)
        self.assertEqual(frames[-1], "event: done\ndata: {}\n\n")

        session = get_session(session_response.token)
        self.assertEqual(session.message_count, 1)
        self.assertEqual(session.chat_history[-1], {"role": "assistant", "content": "Hola como va"})

    def test_mensaje_yields_error_frame_on_llm_error(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia")
        payload = ClonMensajeRequest(token=session_response.token, mensaje="hola clon", provider="anthropic", api_key="fake")

        async def run():
            with patch.object(main, "stream_llm_chat", new=_fake_stream_error):
                streaming_response = await main.clon_chat_mensaje(payload)
                return [chunk async for chunk in streaming_response.body_iterator]

        frames = asyncio.run(run())

        self.assertEqual(frames, ['event: error\ndata: "La API key no es valida."\n\n'])
        # No se registra el intercambio si el proveedor fallo.
        session = get_session(session_response.token)
        self.assertEqual(session.message_count, 0)

    def test_mensaje_with_missing_token_raises_404(self) -> None:
        payload = ClonMensajeRequest(token="no-existe", mensaje="hola", provider="anthropic", api_key="fake")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(main.clon_chat_mensaje(payload))

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("expiro", context.exception.detail)

    def test_mensaje_rejects_unknown_hablar_como(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia")
        payload = ClonMensajeRequest(
            token=session_response.token, mensaje="hola", provider="anthropic", api_key="fake", hablar_como="Fantasma"
        )

        with self.assertRaises(HTTPException) as context:
            asyncio.run(main.clon_chat_mensaje(payload))

        self.assertEqual(context.exception.status_code, 400)

    def test_mensaje_enforces_session_message_cap(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia")
        session = get_session(session_response.token)
        session.message_count = clone.MAX_MESSAGES_PER_SESSION
        payload = ClonMensajeRequest(token=session_response.token, mensaje="hola", provider="anthropic", api_key="fake")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(main.clon_chat_mensaje(payload))

        self.assertEqual(context.exception.status_code, 429)
        self.assertIn("limite", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
