"""
Shared audio utilities for DIVA Call Transcriptor.

Provides: ffprobe-based metadata, audio preprocessing (loudnorm + silence strip,
16 kHz mono), stereo channel splitting, and local faster-whisper transcription.

ffmpeg/ffprobe must be available in PATH before calling any function.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Optional


# ─── Base prompt — domain vocabulary always injected into Whisper ────────────
#
# Edit this constant to add names, products, or terms that are always present
# in your call recordings.  The user's own prompt (entered in the UI or CLI)
# is appended after this text, so both are combined automatically.
#
# Whisper treats the initial_prompt as a "style/vocabulary hint" — keep it
# concise: ~50-150 tokens works best.  Avoid full sentences; prefer lists.

BASE_PROMPT: str = ('''

Eres un agente especializado en la transcripción literal de llamadas telefónicas utilizadas en procesos de monitoreo, validación, auditoría y control de calidad de Compensar.

Tu única función es convertir el contenido del audio a texto de manera fiel y objetiva, preservando el significado original de la conversación. Las llamadas están en español en un contexto colombiano. 

Principios obligatorios:

1. Transcribe únicamente aquello que exista en el audio.
2. Nunca inventes, completes, resumas o agregues contenido que no haya sido pronunciado.
3. Conserva nombres propios, apellidos, empresas, protocolos, números de identificación, extensiones, fechas, direcciones de correo, valores numéricos y términos de negocio exactamente como son mencionados.
4. Si una palabra no es completamente inteligible, utiliza la marca [inaudible] o [no comprendido] en lugar de inferir o reemplazar el contenido.
5. Mantén el idioma original de la conversación. Nunca traduzcas el contenido.
6. Identifica correctamente los turnos de conversación diferenciando asesor y usuario cuando sea posible.
7. No corrijas gramática, pronunciación, muletillas o errores de habla presentes en la grabación.
8. No elimines saludos, despedidas, validaciones de identidad, autorizaciones de tratamiento de datos, confirmaciones de transacciones o cualquier otro elemento del proceso.
9. Prioriza la precisión sobre la fluidez. Es preferible marcar una sección como incierta antes que generar una interpretación incorrecta.
10. Cuando existan números, fechas, montos o identificadores, verifica cuidadosamente su transcripción debido a su impacto en procesos de auditoría.

Errores que debes evitar:
- Cambiar palabras por otras similares fonéticamente.
- Omitir información relevante.
- Agregar frases inexistentes.
- Cambiar respuestas afirmativas por negativas o viceversa.
- Alterar nombres de personas.
- Alterar nombres de empresas o procesos.
- Inventar segmentos de conversación para completar silencios.

Formato de salida:

[ASESOR]:
texto transcrito...

[USUARIO]:
texto transcrito...

Mantén el orden cronológico exacto de la conversación y refleja fielmente cada intervención registrada en el audio.
''')

# ─── Ensure ffmpeg/ffprobe are discoverable on Windows ──────────────────────

def _ensure_ffmpeg_in_path() -> None:
    """Add a common Windows ffmpeg installation to PATH if not already present."""
    if shutil.which("ffmpeg"):
        return
    if os.name != "nt":
        return

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(
            Path(local_app_data).glob(
                r"Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin"
            )
        )
    for root in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
        if root:
            candidates.extend(Path(root).glob(r"ffmpeg*\bin"))
    for bin_dir in candidates:
        if (bin_dir / "ffmpeg.exe").exists():
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return


_ensure_ffmpeg_in_path()


# ─── Audio metadata ──────────────────────────────────────────────────────────

def get_audio_info(audio_path: str) -> dict:
    """
    Use ffprobe to read metadata for any audio format (wav, mp3, m4a, ogg, flac).

    Returns a dict with keys: duration (float, seconds), sample_rate (int, Hz),
    channels (int).  Any value is None when it cannot be determined.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a:0",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return {"duration": None, "sample_rate": None, "channels": None}
        s = streams[0]
        duration = float(s.get("duration") or 0) or None
        sample_rate = int(s.get("sample_rate") or 0) or None
        channels = int(s.get("channels") or 0) or None
        return {"duration": duration, "sample_rate": sample_rate, "channels": channels}
    except Exception:
        return {"duration": None, "sample_rate": None, "channels": None}


def get_audio_duration(audio_path: str) -> Optional[float]:
    """Return audio duration in seconds via ffprobe. Works for all formats."""
    return get_audio_info(audio_path)["duration"]


# ─── Quality validation ──────────────────────────────────────────────────────

# Below this mean volume (dBFS), Whisper tends to hallucinate rather than
# transcribe genuine speech, so callers should skip decoding entirely.
_SILENCE_DB_THRESHOLD = -45.0


def _mean_volume_db(audio_path: str) -> Optional[float]:
    """Return the mean volume (dBFS) of an audio file via ffmpeg's volumedetect, or None."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", proc.stderr)
        return float(match.group(1)) if match else None
    except Exception:
        return None


def validate_audio_quality(audio_path: str) -> list[str]:
    """
    Inspect an audio file and return human-readable Spanish warning strings for:
      - Very short duration (< 1 s)
      - Low sample rate (< 16 kHz, common in 8 kHz telephony)
      - Near-silent RMS level (< -45 dBFS mean volume)
    """
    warnings: list[str] = []
    info = get_audio_info(audio_path)

    if info["duration"] is not None and info["duration"] < 1.0:
        warnings.append(
            f"Audio muy corto ({info['duration']:.1f} s). "
            "La transcripción puede estar vacía."
        )

    if info["sample_rate"] is not None and info["sample_rate"] < 16000:
        warnings.append(
            f"Tasa de muestreo baja ({info['sample_rate']:,} Hz). "
            "Los audios de telefonía a 8 kHz pierden información vocal importante. "
            "Se recomienda ≥ 16 kHz para mejor precisión."
        )

    mean_vol = _mean_volume_db(audio_path)
    if mean_vol is not None and mean_vol < _SILENCE_DB_THRESHOLD:
        warnings.append(
            f"Audio casi silencioso (volumen medio: {mean_vol:.1f} dB). "
            "Whisper puede generar texto inventado en grabaciones silenciosas."
        )

    return warnings


# ─── Preprocessing ───────────────────────────────────────────────────────────

def preprocess_audio(
    audio_path: str,
    output_path: Optional[str] = None,
    trim_silence: bool = True,
) -> str:
    """
    Preprocess an audio file for optimal Whisper transcription:
      1. EBU R128 loudness normalisation (loudnorm).
    2. Strip leading/trailing silence (silenceremove), when enabled.
      3. Resample to 16 kHz mono PCM WAV.

    Args:
        audio_path:  Path to the source audio file.
        output_path: Destination WAV path.  A temp file is created when None.
        trim_silence: Remove leading/trailing silence. Disable this for stereo
                  channels so timestamps remain on the original timeline.

    Returns:
        Path to the preprocessed WAV file.  Caller is responsible for cleanup.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_pre.wav")
        output_path = tmp.name
        tmp.close()

    af = "loudnorm=I=-16:TP=-1.5:LRA=11"
    if trim_silence:
        af += (
            ",silenceremove=start_periods=1:start_silence=0.3:start_threshold=-50dB"
            ":stop_periods=-1:stop_silence=1:stop_threshold=-50dB"
        )

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-af", af,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output_path,
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    return output_path


# ─── Stereo channel handling ─────────────────────────────────────────────────

def split_stereo_channels(audio_path: str) -> tuple[str, str]:
    """
    Extract the left (ch 0) and right (ch 1) channels of a stereo audio file
    into separate mono 16 kHz WAV files.

    IMPORTANT: Call this on the *original* audio file, before any preprocessing
    that converts to mono (-ac 1).  Preprocessing on an already-mono file will
    fail with ffmpeg exit code 8 (channel map out of range).

    Intended for call recordings where the agent and customer are on different
    channels.

    Returns:
        (left_path, right_path) — caller is responsible for cleanup.

    Raises:
        ValueError: If the audio file has fewer than 2 channels.
        subprocess.CalledProcessError: If ffmpeg fails for another reason.
    """
    info = get_audio_info(audio_path)
    channels = info.get("channels") or 0
    if channels < 2:
        raise ValueError(
            f"El archivo '{Path(audio_path).name}' es mono ({channels} canal/es). "
            "La opción 'Separar canales estéreo' requiere una grabación estéreo "
            "donde el agente y el cliente estén en canales L/R independientes."
        )

    left_tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_ch0.wav")
    right_tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_ch1.wav")
    left_path, right_path = left_tmp.name, right_tmp.name
    left_tmp.close()
    right_tmp.close()

    # Use pan filter instead of -map_channel: more compatible across ffmpeg builds.
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-filter_complex",
            "pan=mono|c0=c0[left];[0:a]pan=mono|c0=c1[right]",
            "-map", "[left]",  "-ar", "16000", "-c:a", "pcm_s16le", left_path,
            "-map", "[right]", "-ar", "16000", "-c:a", "pcm_s16le", right_path,
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    return left_path, right_path


def merge_dual_channel_segments(
    segments_left: list[dict],
    segments_right: list[dict],
    label_left: str = "Agente",
    label_right: str = "Usuario",
) -> tuple[str, list[dict]]:
    """
    Interleave segments from two channels, sorted by start time, and add a
    'speaker' key to each segment. The text uses labels such as
    '[Agente] ...' and '[Usuario] ...'.

    Returns:
        (full_text_with_speaker_labels, merged_segment_list)
    """
    for seg in segments_left:
        seg["speaker"] = label_left
    for seg in segments_right:
        seg["speaker"] = label_right

    ordered = sorted(
        (seg for seg in segments_left + segments_right if seg.get("texto", "").strip()),
        key=lambda s: s["inicio"],
    )

    # Keep every Whisper segment: its start time is part of the conversation
    # timeline, even when two consecutive segments have the same speaker.
    merged = [{**segment, "texto": segment["texto"].strip()} for segment in ordered]

    lines = [
        f"{_format_timestamp(seg['inicio'])} [{seg['speaker']}] {seg['texto']}"
        for seg in merged
    ]
    return "\n".join(lines), merged


def _format_timestamp(seconds: float) -> str:
    """Format elapsed audio time as MM:SS:msms for transcript lines."""
    total_centiseconds = max(0, int(round(seconds * 100)))
    total_seconds, centiseconds = divmod(total_centiseconds, 100)
    minutes, remaining_seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}:{centiseconds:02d}"


# ─── Hallucination post-processing ──────────────────────────────────────────

_HALLUCINATION_PATTERNS: list[str] = [
    r"Subtítulos?\s+(?:realizados?\s+)?por\s+la\s+comunidad\s+de\s+Amara\.org",
    r"Subtítulos?\s+(?:en|al)\s+[Ee]spañol",
    r"Suscríbete\s+al\s+canal",
    r"Gracias\s+por\s+ver\s+(?:el\s+)?(?:vídeo|video)",
    r"Muchas?\s+gracias\s+por\s+(?:ver|tu\s+atención)",
    r"Dale\s+like\s+y\s+suscríbete",
    r"No\s+olvides\s+suscribirte",
    r"Deja\s+(?:tu\s+)?comentario",
    r"\[(?:Música|MÚSICA|música)\]",
    r"♪[^♪\n]*♪?",
]

_HALLUCINATION_RE = re.compile(
    "|".join(_HALLUCINATION_PATTERNS),
    re.IGNORECASE,
)


def _is_degenerate_text(text: str) -> bool:
    """
    Detect garbage decoder output typical of near-silent/noise-only audio:
    long runs of a single repeated character, text that is mostly punctuation
    with almost no letters, or the same word looping over and over.
    """
    if re.search(r"(.)\1{9,}", text):
        return True
    letters = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", text)
    if len(text) > 30 and len(letters) < len(text) * 0.2:
        return True
    words = re.findall(r"\w+", text.lower())
    if len(words) >= 8:
        most_common_count = max(Counter(words).values())
        if most_common_count / len(words) > 0.6:
            return True
    return False


def filter_hallucinations(text: str) -> str:
    """
    Remove known Spanish Whisper hallucination phrases and collapse consecutive
    repeated sentences (a common Whisper repetition-loop artifact).
    """
    text = _HALLUCINATION_RE.sub("", text)

    # Deduplicate consecutive repeated sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    deduped: list[str] = []
    for s in sentences:
        s = s.strip()
        if s and (not deduped or s.lower() != deduped[-1].lower()):
            deduped.append(s)
    text = " ".join(deduped)

    # Normalise whitespace
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ─── Local faster-whisper transcription core ─────────────────────────────────

def build_prompt(user_prompt: str = "") -> str:
    """
    Combine the fixed BASE_PROMPT with the user-supplied prompt.

    BASE_PROMPT always comes first (domain vocabulary, language context).
    The user's additions are appended after a separator so Whisper sees both.

    Returns an empty string only if both BASE_PROMPT and user_prompt are empty,
    which tells Whisper to use no initial prompt at all.
    """
    base = BASE_PROMPT.strip()
    user = user_prompt.strip()
    if base and user:
        return f"{base} {user}"
    return base or user


def _transcribe_via_whisper(
    audio_path: str,
    initial_prompt: str,
    language: str,
    *,
    temperature: float = 0.0,
) -> dict:
    """
    Transcribe locally with faster-whisper, then drop degenerate
    (garbage/repeated-word) output typical of near-silent audio.

    Returns dict with keys: text (str), segments (list[dict] with timestamps),
    language (str).
    """
    from whisper_transcribe import transcribe_with_whisper

    result = transcribe_with_whisper(
        audio_path, initial_prompt=initial_prompt, language=language, temperature=temperature,
    )
    text = result["text"]
    if _is_degenerate_text(text):
        text = ""
    return {"text": text, "segments": result["segments"], "language": result["language"]}


def transcribe_audio_file(
    audio_path: str,
    *,
    initial_prompt: str = "",
    enable_preprocess: bool = True,
    handle_stereo: bool = False,
    language: str = "es",
) -> dict:
    """
    Full transcription pipeline for a single audio file.

    Steps:
      1. Optional stereo channel split (agent L / customer R).
      2. Optional preprocessing: loudnorm → silence strip → 16 kHz mono WAV.
    3. Transcription via the local faster-whisper model.
      4. Hallucination post-processing.

    Args:
        audio_path:       Path to the source audio file.
        initial_prompt:   Domain vocabulary hint (e.g. product/agent names).
        enable_preprocess: Run the ffmpeg preprocessing pipeline before transcription.
        handle_stereo:    If True and audio is stereo, split channels and transcribe
                          each separately with AGENTE/CLIENTE speaker labels.
        language:         BCP-47 language code passed to Whisper.

    Returns:
        dict with keys: text (str), segments (list[dict]), language (str).
        When handle_stereo produces dual-channel output, segments also carry a
        'speaker' key ('AGENTE' or 'CLIENTE'), and 'channel_warnings' (list[str])
        reports channels skipped for being near-silent.
    """
    temp_files: list[str] = []
    try:
        is_stereo = False
        if handle_stereo:
            info = get_audio_info(audio_path)
            is_stereo = (info.get("channels") or 1) >= 2

        if is_stereo:
            left_path, right_path = split_stereo_channels(audio_path)
            temp_files.extend([left_path, right_path])

            if enable_preprocess:
                try:
                    left_prep = preprocess_audio(left_path, trim_silence=False)
                    temp_files.append(left_prep)
                except subprocess.CalledProcessError:
                    left_prep = left_path
                try:
                    right_prep = preprocess_audio(right_path, trim_silence=False)
                    temp_files.append(right_prep)
                except subprocess.CalledProcessError:
                    right_prep = right_path
            else:
                left_prep, right_prep = left_path, right_path

            channel_warnings: list[str] = []

            def _transcribe_channel(path: str, label: str) -> dict:
                mean_db = _mean_volume_db(path)
                if mean_db is not None and mean_db < _SILENCE_DB_THRESHOLD:
                    channel_warnings.append(
                        f"Canal {label} sin voz detectada (volumen medio: {mean_db:.1f} dB). "
                        "Se omitió la transcripción de ese canal para evitar texto inventado."
                    )
                    return {"segments": [], "language": language}
                result = _transcribe_via_whisper(path, initial_prompt, language)
                duration = get_audio_duration(path) or 0.0
                segments = result["segments"]
                if not segments and result["text"].strip():
                    segments = [{"inicio": 0.0, "fin": duration, "texto": result["text"]}]
                return {"segments": segments, "language": result["language"]}

            result_l = _transcribe_channel(left_prep, "Agente")
            result_r = _transcribe_channel(right_prep, "Usuario")
            for channel_result in (result_l, result_r):
                for segment in channel_result["segments"]:
                    segment["texto"] = filter_hallucinations(segment["texto"])
            text, merged_segs = merge_dual_channel_segments(
                result_l["segments"], result_r["segments"]
            )
            return {
                "text": text,
                "segments": merged_segs,
                "language": result_l["language"] or result_r["language"],
                "channel_warnings": channel_warnings,
            }

        # ── Single-channel path ──────────────────────────────────────────────
        if enable_preprocess:
            try:
                prep_path = preprocess_audio(audio_path)
                temp_files.append(prep_path)
            except subprocess.CalledProcessError:
                prep_path = audio_path  # Fall back gracefully on preprocessing failure
        else:
            prep_path = audio_path

        result = _transcribe_via_whisper(prep_path, initial_prompt, language)
        result["text"] = filter_hallucinations(result["text"])
        return result

    finally:
        for p in temp_files:
            if p and p != audio_path and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass
