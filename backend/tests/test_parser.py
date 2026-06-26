import io
import unittest
import zipfile
from datetime import datetime

from parser import extract_chat_text, extract_group_name, parse_messages


def make_zip_with_chat(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


class ParserTests(unittest.TestCase):
    def test_extract_chat_text_reads_txt_from_zip(self) -> None:
        zip_bytes = make_zip_with_chat("_chat.txt", "hola")

        chat_text = extract_chat_text(zip_bytes)

        self.assertEqual(chat_text, "hola")

    def test_extract_chat_text_requires_txt_file(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("foto.jpg", "binary")

        with self.assertRaisesRegex(ValueError, "no contiene ningun archivo .txt"):
            extract_chat_text(buffer.getvalue())

    def test_parse_messages_filters_system_and_bot_messages_and_keeps_multiline(self) -> None:
        chat_text = "\n".join(
            [
                "21/06/26, 22:00 - Juan: Primer mensaje",
                "continuacion del mensaje",
                "21/06/26, 22:05 - Meta AI: respuesta automatica",
                "21/06/26, 22:10 - Ana: Hola grupo",
                "21/06/26, 22:11 - Juan changed the group name to \"Nuevo nombre\"",
                "21/06/26, 22:12 - Pedro: Cierro aca",
            ]
        )

        messages = parse_messages(chat_text)

        self.assertEqual([message.author for message in messages], ["Juan", "Ana", "Pedro"])
        self.assertEqual(messages[0].text, "Primer mensaje\ncontinuacion del mensaje")
        self.assertEqual(messages[0].timestamp, datetime(2026, 6, 21, 22, 0))

    def test_extract_group_name_uses_last_rename_event(self) -> None:
        chat_text = "\n".join(
            [
                "21/06/26, 20:00 - Juan: arrancamos",
                "21/06/26, 20:01 - Ana: cambi\u00f3 el nombre del grupo a \"Asado viernes\"",
                "21/06/26, 20:02 - Pedro: ok",
            ]
        )

        group_name = extract_group_name(chat_text)

        self.assertEqual(group_name, "Asado viernes")
