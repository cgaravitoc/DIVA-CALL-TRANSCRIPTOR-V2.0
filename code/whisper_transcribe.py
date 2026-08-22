"""Local Whisper transcription for the offline project variant."""

import os
from functools import lru_cache

# Store the multi-gigabyte model on the data drive by default on Windows.
if os.name == "nt":
    os.environ.setdefault("HF_HOME", r"D:\huggingface-cache")

from faster_whisper import WhisperModel

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    """Load the local model once per process."""
    return WhisperModel(
        WHISPER_MODEL_SIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )


def ensure_model_loaded() -> None:
    """Download and load the configured model before transcription starts."""
    _get_model()


def is_available() -> tuple[bool, str]:
    """Report that the local Whisper dependency is available."""
    return True, (
        f"Whisper local configurado — modelo '{WHISPER_MODEL_SIZE}', "
        f"dispositivo '{WHISPER_DEVICE}'."
    )


def transcribe_with_whisper(
    audio_path: str,
    *,
    initial_prompt: str = "",
    language: str = "es",
    temperature: float = 0.0,
) -> dict:
    """Transcribe locally and return text plus timestamped segments."""
    segments_generator, info = _get_model().transcribe(
        audio_path,
        language=language,
        beam_size=5,
        initial_prompt=initial_prompt or None,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.2,
        vad_filter=False,
        word_timestamps=True,
        temperature=temperature,
    )
    segments = list(segments_generator)
    segments.sort(key=lambda segment: (segment.start, segment.end))
    return {
        "text": " ".join(segment.text.strip() for segment in segments if segment.text.strip()),
        "segments": [
            {
                "inicio": segment.start,
                "fin": segment.end,
                "texto": segment.text.strip(),
            }
            for segment in segments
            if segment.text.strip()
        ],
        "language": info.language,
    }
