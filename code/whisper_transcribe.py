"""Local Whisper transcription for the offline project variant."""

import os
from functools import lru_cache
from pathlib import Path

# Keep the multi-gigabyte model inside the project by default. An explicit
# HF_HOME (for example, the Docker volume configured by docker-compose) still
# takes precedence.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WHISPER_CACHE = PROJECT_ROOT / ".whisper-cache"
os.environ.setdefault("HF_HOME", str(DEFAULT_WHISPER_CACHE))

from faster_whisper import WhisperModel

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large")
WHISPER_MODEL_PATH = os.environ.get("WHISPER_MODEL_PATH", "").strip()
WHISPER_LOCAL_FILES_ONLY = os.environ.get(
    "WHISPER_LOCAL_FILES_ONLY", "0"
).lower() in {"1", "true", "yes"}
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    """Load the local model once per process."""
    model_source = WHISPER_MODEL_PATH or WHISPER_MODEL_SIZE
    if WHISPER_MODEL_PATH and not Path(WHISPER_MODEL_PATH).is_dir():
        raise FileNotFoundError(
            f"No se encontro el modelo Whisper incluido en: {WHISPER_MODEL_PATH}"
        )
    return WhisperModel(
        model_source,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        local_files_only=WHISPER_LOCAL_FILES_ONLY,
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
