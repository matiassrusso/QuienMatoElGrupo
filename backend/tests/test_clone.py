import asyncio
import io
import unittest
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

import clone
import main
from clone import (
    MAX_SAMPLE_CHARS,
    MAX_SAMPLE_MESSAGES,
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


class SampleStyleMessagesTests(unittest.TestCase):
    def test_general_mode_spreads_across_authors_and_time(self) -> None:
        base = datetime(2026, 1, 1)
        messages = [Message(author="Ana", timestamp=base + timedelta(hours=i), text=f"msj {i}") for i in range(400)]
        messages += [Message(author="Beto", timestamp=base + timedelta(hours=i * 20), text=f"msj {i}") for i in range(20)]
        messages.sort(key=lambda message: message.timestamp)

        sample = sample_style_messages(messages, None)
        counts = Counter(message.author for message in sample)

        self.assertLessEqual(len(sample), MAX_SAMPLE_MESSAGES)
        self.assertIn("Beto", counts)
        # Ana escribio 20x mas que Beto, pero no deberia dominar la muestra al punto
        # de dejar a Beto con una fraccion insignificante.
        self.assertGreater(counts["Beto"], len(sample) * 0.15)
        # La muestra cubre casi todo el rango temporal, no solo la cola final.
        total_span = (messages[-1].timestamp - messages[0].timestamp).total_seconds()
        sample_span = (sample[-1].timestamp - sample[0].timestamp).total_seconds()
        self.assertGreater(sample_span, total_span * 0.5)

    def test_hablar_como_filters_to_single_author_and_spreads_over_time(self) -> None:
        base = datetime(2026, 1, 1)
        messages = [Message(author="Ana", timestamp=base + timedelta(hours=i), text=f"msj {i}") for i in range(200)]
        messages += [Message(author="Beto", timestamp=base + timedelta(hours=i), text=f"msj {i}") for i in range(200)]
        messages.sort(key=lambda message: message.timestamp)

        sample = sample_style_messages(messages, "Ana")

        self.assertTrue(sample)
        self.assertTrue(all(message.author == "Ana" for message in sample))
        total_span = (messages[-1].timestamp - messages[0].timestamp).total_seconds()
        sample_span = (sample[-1].timestamp - sample[0].timestamp).total_seconds()
        self.assertGreater(sample_span, total_span * 0.5)

    def test_respects_char_budget_with_long_messages(self) -> None:
        base = datetime(2026, 1, 1)
        long_text = "palabra " * 200  # bien por encima del budget individual
        messages = [Message(author="Ana", timestamp=base + timedelta(hours=i), text=long_text) for i in range(100)]

        sample = sample_style_messages(messages, "Ana")

        total_chars = sum(len(message.text) for message in sample)
        self.assertLessEqual(total_chars, MAX_SAMPLE_CHARS + len(long_text))

    def test_empty_messages_returns_empty_sample(self) -> None:
        self.assertEqual(sample_style_messages([], None), [])
        self.assertEqual(sample_style_messages([], "Ana"), [])


class BuildCloneSystemPromptTests(unittest.TestCase):
    def test_general_mode_mentions_group_not_a_specific_person(self) -> None:
        sample = [Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]
        prompt = build_clone_system_prompt(sample, None, "Los Pibes")

        self.assertIn("Los Pibes", prompt)
        self.assertIn("estilo colectivo", prompt)

    def test_hablar_como_mode_names_the_member_and_disclaims_simulation(self) -> None:
        sample = [Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]
        prompt = build_clone_system_prompt(sample, "Ana", "Los Pibes")

        self.assertIn("Ana", prompt)
        self.assertIn("imitacion generada por IA", prompt)


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
