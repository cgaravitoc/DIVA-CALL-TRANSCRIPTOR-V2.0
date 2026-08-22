"""
GPT Transcribe — audio transcription via OpenAI's gpt-4o-transcribe model.

Replaces the local faster-whisper engine. Requires OPENAI_API_KEY.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GPT_TRANSCRIBE_MODEL = os.environ.get("GPT_TRANSCRIBE_MODEL", "gpt-4o-transcribe")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY no está configurado. Añádelo a tu archivo .env."
            )
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def is_available() -> tuple[bool, str]:
    """Check whether the OpenAI transcription client is configured."""
    if not OPENAI_API_KEY:
        return False, "Falta OPENAI_API_KEY. Configúralo como variable de entorno."
    return True, f"OpenAI configurado — modelo '{GPT_TRANSCRIBE_MODEL}' listo para transcribir."


def transcribe_with_gpt(
    audio_path: str,
    *,
    initial_prompt: str = "",
    language: str = "es",
    temperature: float = 0.0,
) -> dict:
    """
    Transcribe an audio file with OpenAI's gpt-4o-transcribe model.

    Returns dict with keys:
      text (str), segments (list — always empty, this model returns no
      per-segment timestamps), language (str).
    """
    client = _get_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=GPT_TRANSCRIBE_MODEL,
            file=f,
            language=language,
            prompt=initial_prompt or None,
            temperature=temperature,
            response_format="text",
        )
    text = response if isinstance(response, str) else getattr(response, "text", str(response))
    return {"text": text.strip(), "segments": [], "language": language}
