import asyncio
import unittest

import httpx

from llm import DEFAULT_MODELS, LLMError, _extract_error_message, call_llm


class CallLlmDispatchTests(unittest.TestCase):
    def test_raises_for_unknown_provider(self) -> None:
        with self.assertRaises(LLMError):
            asyncio.run(call_llm("unknown", "key", None, "sys", "user"))

    def test_known_providers_have_default_models(self) -> None:
        for provider in ("anthropic", "openai", "gemini", "groq"):
            self.assertIn(provider, DEFAULT_MODELS)


class ExtractErrorMessageTests(unittest.TestCase):
    def test_extracts_nested_error_message(self) -> None:
        response = httpx.Response(429, json={"error": {"message": "You exceeded your current quota."}})
        self.assertEqual(_extract_error_message(response), "You exceeded your current quota.")

    def test_returns_none_when_body_is_not_json(self) -> None:
        response = httpx.Response(500, content=b"not json")
        self.assertIsNone(_extract_error_message(response))

    def test_returns_none_when_error_key_is_missing(self) -> None:
        response = httpx.Response(429, json={"detail": "rate limited"})
        self.assertIsNone(_extract_error_message(response))


if __name__ == "__main__":
    unittest.main()
