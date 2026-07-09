import asyncio
import io
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

import clone
import main
from clone import (
    MAX_SAMPLE_CHARS,
    MAX_SAMPLE_MESSAGES,
    READING_PASS_TOKEN_BUDGET,
    WINDOW_SIZE,
    build_clone_system_prompt,
    build_reading_pass_prompt,
    create_session,
    get_session,
    record_exchange,
    sample_for_reading_pass,
    sample_style_messages,
)
from llm import LLMError
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


class SampleForReadingPassTests(unittest.TestCase):
    def test_bigger_budget_yields_a_bigger_sample(self) -> None:
        base = datetime(2026, 1, 1)
        messages: list[Message] = []
        # Suficientes mensajes como para que ni siquiera el budget mas chico
        # (groq) se quede corto de datos -- si no, ambos terminan usando
        # "todo lo que hay" y el test no puede distinguir los dos budgets.
        for week in range(250):
            messages += make_conversation(base, ["Ana", "Beto", "Caro"], 20, start_offset_hours=week * 24 * 7)

        small = sample_for_reading_pass(messages, None, READING_PASS_TOKEN_BUDGET["groq"])
        big = sample_for_reading_pass(messages, None, READING_PASS_TOKEN_BUDGET["gemini"])

        small_messages = sum(len(window) for window in small)
        big_messages = sum(len(window) for window in big)
        # Groq (5000 tokens) tiene un presupuesto mucho mas ajustado que
        # Gemini (60000) -- el mismo chat tiene que darle una muestra
        # bastante mas chica, sin romper (ni superar el propio budget de Groq).
        self.assertGreater(big_messages, small_messages)
        self.assertLessEqual(small_messages, READING_PASS_TOKEN_BUDGET["groq"] // 6 + WINDOW_SIZE)

    def test_uses_full_conversation_not_just_the_small_per_message_budget(self) -> None:
        base = datetime(2026, 1, 1)
        messages: list[Message] = []
        for week in range(30):
            messages += make_conversation(base, ["Ana", "Beto"], 20, start_offset_hours=week * 24 * 7)

        reading_sample = sample_for_reading_pass(messages, None, READING_PASS_TOKEN_BUDGET["gemini"])
        default_sample = sample_style_messages(messages, None)

        reading_total = sum(len(window) for window in reading_sample)
        default_total = sum(len(window) for window in default_sample)
        self.assertGreater(reading_total, default_total)


class BuildReadingPassPromptTests(unittest.TestCase):
    def test_general_mode_asks_for_collective_style_summary(self) -> None:
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]
        system_prompt, user_prompt = build_reading_pass_prompt(sample, None, "Los Pibes")

        self.assertIn("analista de estilo", system_prompt)
        self.assertIn("Los Pibes", user_prompt)
        self.assertIn("estilo colectivo", user_prompt)

    def test_hablar_como_mode_asks_for_that_persons_style(self) -> None:
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]
        _system_prompt, user_prompt = build_reading_pass_prompt(sample, "Ana", "Los Pibes")

        self.assertIn("estilo de Ana", user_prompt)


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

    def test_prompt_demands_literal_vocabulary_from_sample(self) -> None:
        # Bug real: el clon sonaba coherente pero con jerga argentina
        # generica inventada, no la del grupo real.
        sample = [[Message(author="Ana", timestamp=datetime(2026, 1, 1), text="dale")]]

        prompt = build_clone_system_prompt(sample, None, "Los Pibes")

        self.assertIn("jerga EXACTA", prompt)
        self.assertIn("No inventes jerga generica", prompt)

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
    raise LLMError("La API key no es valida.")
    yield ""  # pragma: no cover -- fuerza que sea un async generator


def _patched_call_and_stream(call_llm_result="Ficha: hablan informal.", call_llm_side_effect=None, stream=_fake_stream_ok):
    """Contexto combinado que mockea call_llm (usado por la pasada de
    lectura) y stream_llm_chat (usado por la respuesta en si), para no
    pegarle a la red real en los tests del endpoint."""
    call_mock = AsyncMock(return_value=call_llm_result, side_effect=call_llm_side_effect)
    return patch.object(main, "call_llm", new=call_mock), patch.object(main, "stream_llm_chat", new=stream), call_mock


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
            call_patch, stream_patch, _ = _patched_call_and_stream()
            with call_patch, stream_patch:
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
            call_patch, stream_patch, _ = _patched_call_and_stream(stream=_fake_stream_error)
            with call_patch, stream_patch:
                streaming_response = await main.clon_chat_mensaje(payload)
                return [chunk async for chunk in streaming_response.body_iterator]

        frames = asyncio.run(run())

        self.assertEqual(frames[-1], 'event: error\ndata: "La API key no es valida."\n\n')
        # No se registra el intercambio si el proveedor fallo.
        session = get_session(session_response.token)
        self.assertEqual(session.message_count, 0)

    def test_mensaje_emits_reading_event_and_caches_persona_brief(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia\n19/06/26, 10:00 - Ana: Otra vez yo")
        payload = ClonMensajeRequest(token=session_response.token, mensaje="hola", provider="groq", api_key="fake")

        async def send():
            call_patch, stream_patch, call_mock = _patched_call_and_stream()
            with call_patch, stream_patch:
                streaming_response = await main.clon_chat_mensaje(payload)
                frames = [chunk async for chunk in streaming_response.body_iterator]
            return frames, call_mock

        first_frames, first_call_mock = asyncio.run(send())
        self.assertEqual(first_frames[0], "event: reading\ndata: {}\n\n")
        first_call_mock.assert_awaited_once()

        session = get_session(session_response.token)
        self.assertEqual(session.persona_briefs[None], "Ficha: hablan informal.")

        # Segundo mensaje: la ficha ya esta cacheada, no se vuelve a leer.
        second_frames, second_call_mock = asyncio.run(send())
        self.assertNotIn("event: reading\ndata: {}\n\n", second_frames)
        second_call_mock.assert_not_awaited()

    def test_reading_pass_failure_falls_back_to_default_sample(self) -> None:
        session_response = make_session_with_zip("18/06/26, 09:00 - Ana: Buen dia\n19/06/26, 10:00 - Ana: Otra vez yo")
        payload = ClonMensajeRequest(token=session_response.token, mensaje="hola", provider="groq", api_key="fake")

        async def send():
            call_patch, stream_patch, _ = _patched_call_and_stream(call_llm_side_effect=LLMError("rate limited"))
            with call_patch, stream_patch:
                streaming_response = await main.clon_chat_mensaje(payload)
                return [chunk async for chunk in streaming_response.body_iterator]

        frames = asyncio.run(send())

        # La charla sigue funcionando (fallback), no se corta por el error de lectura.
        self.assertIn('event: chunk\ndata: "Hola "\n\n', frames)
        session = get_session(session_response.token)
        self.assertEqual(session.persona_briefs, {})
        self.assertIn(None, session.persona_brief_failed)
        self.assertEqual(session.message_count, 1)

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
