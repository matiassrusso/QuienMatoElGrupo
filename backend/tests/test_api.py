import io
import asyncio
import unittest
import zipfile
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

import main
from llm import LLMError
from main import analizar
from schemas import VeredictoIARequest


def make_chat_zip(chat_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("_chat.txt", chat_text)
    return buffer.getvalue()


class AnalyzeApiTests(unittest.TestCase):
    def run_analizar(self, zip_bytes: bytes, range_type: str = "days", range_value: int | None = 7):
        upload = UploadFile(filename="chat.zip", file=io.BytesIO(zip_bytes))
        return asyncio.run(analizar(file=upload, range_type=range_type, range_value=range_value, weight=0.5))

    def test_analizar_returns_summary_payload(self) -> None:
        chat_text = "\n".join(
            [
                "18/06/26, 09:00 - Ana: Buen dia",
                "19/06/26, 10:00 - Juan: Todo bien",
                "21/06/26, 11:00 - Ana: Reactivemos esto",
                "21/06/26, 11:10 - Pedro: Banco",
                "21/06/26, 11:15 - Ana: Entonces seguimos",
            ]
        )
        zip_bytes = make_chat_zip(chat_text)

        payload = self.run_analizar(zip_bytes)

        self.assertEqual(payload.group_name, None)
        self.assertEqual(payload.total_members, 3)
        self.assertEqual(payload.total_messages_in_range, 5)
        self.assertEqual(len(payload.top3), 3)
        self.assertEqual(len(payload.hourly_heatmap), 168)
        self.assertTrue(payload.timeline_events)
        self.assertTrue(payload.conversation_pattern)
        self.assertTrue(payload.probable_cause)

    def test_analizar_rejects_zip_without_chat_txt(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nota.md", "sin chat")

        with self.assertRaises(HTTPException) as context:
            self.run_analizar(buffer.getvalue())

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("no contiene ningun archivo .txt", context.exception.detail)

    def test_analizar_rejects_non_zip_file(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.run_analizar(b"esto no es un zip")

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("no es un .zip valido", context.exception.detail)

    def test_analizar_requires_positive_range_value_for_days(self) -> None:
        zip_bytes = make_chat_zip("21/06/26, 22:00 - Ana: Hola")

        with self.assertRaises(HTTPException) as context:
            self.run_analizar(zip_bytes, range_value=0)

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("range_value debe ser un entero positivo", context.exception.detail)


def make_veredicto_request(**overrides) -> VeredictoIARequest:
    defaults = dict(
        provider="anthropic",
        api_key="fake-key",
        tone="forense",
        group_name="Los Pibes",
        total_members=5,
        total_messages_in_range=170,
        conversation_pattern="Desgastado",
        reactivation_attempts=1,
        top3=[],
        reactivation_leaders=[],
        phase_summary=[],
        rule_based_cause="La causa probable es desgaste gradual.",
    )
    defaults.update(overrides)
    return VeredictoIARequest(**defaults)


class VeredictoIAApiTests(unittest.TestCase):
    def test_veredicto_ia_returns_llm_output(self) -> None:
        payload = make_veredicto_request()

        with patch.object(main, "call_llm", new=AsyncMock(return_value="Texto generado por la IA.")) as mocked:
            response = asyncio.run(main.veredicto_ia(payload))

        self.assertEqual(response.verdict, "Texto generado por la IA.")
        mocked.assert_awaited_once()
        called_provider = mocked.await_args.args[0]
        self.assertEqual(called_provider, "anthropic")

    def test_veredicto_ia_wraps_llm_error_as_502(self) -> None:
        payload = make_veredicto_request()

        with patch.object(main, "call_llm", new=AsyncMock(side_effect=LLMError("La API key no es valida."))):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(main.veredicto_ia(payload))

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("no es valida", context.exception.detail)
