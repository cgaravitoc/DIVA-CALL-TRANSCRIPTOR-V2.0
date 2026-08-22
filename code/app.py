"""
DIVA Call Transcriptor - Streamlit UI
Browser-based batch audio transcription with local faster-whisper.
"""

import streamlit as st
import tempfile
import io
import os
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from datetime import datetime
from audio_utils import (
    build_prompt,
    format_transcription_output,
    get_audio_duration,
    transcribe_audio_file,
    validate_audio_quality,
)


def configure_ffmpeg_path() -> str | None:
    """Make ffmpeg discoverable when Windows apps do not inherit the user PATH."""
    existing = shutil.which("ffmpeg")
    if existing:
        return existing

    if os.name != "nt":
        return None

    candidates = []
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
        ffmpeg = bin_dir / "ffmpeg.exe"
        if ffmpeg.exists():
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return str(ffmpeg)

    return None


FFMPEG_PATH = configure_ffmpeg_path()


# ─────────────────────────────────────────────
# Page config & global styles
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DIVA Call Transcriptor",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* ── Palette (Warm Stone + Teal) ─────────────────────────────────────────
       bg-warm:      #FAFAF9   surface: #FFFFFF   border: #E7E5E4
       primary:      #0D9488   hover:   #0F766E
       text-900:     #1C1917   text-600: #57534E  text-400: #A8A29E
       tag-bg:       #F0FDFA   tag-border: #99F6E4
    ── ──────────────────────────────────────────────────────────────────────── */

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: #FAFAF9;
        color: #1C1917;
    }

    .block-container {
        padding-top: 2rem;
        max-width: 1100px;
    }

    /* ── App header ──────────────────────────────────────────────────────── */
    .app-header {
        display: grid;
        grid-template-columns: 1.4fr .6fr;
        gap: 1.5rem;
        align-items: center;
        padding: 1.5rem 0 1.25rem;
        border-bottom: 1px solid #E7E5E4;
        margin-bottom: 1.5rem;
    }

    .app-header h1 {
        color: #1C1917;
        font-size: 2.25rem;
        font-weight: 700;
        letter-spacing: -.03em;
        margin: 0 0 .3rem;
    }

    .app-header p {
        color: #78716C;
        font-size: 1rem;
        margin: 0;
    }

    .header-aside {
        background: #F0FDFA;
        border: 1px solid #99F6E4;
        border-left: 3px solid #0D9488;
        border-radius: 10px;
        padding: .9rem 1rem;
        color: #0F766E;
        font-size: .875rem;
        line-height: 1.6;
    }

    /* ── Step cards ──────────────────────────────────────────────────────── */
    .step-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .75rem;
        margin-bottom: 1.25rem;
    }

    .step {
        background: #FFFFFF;
        border: 1px solid #E7E5E4;
        border-left: 3px solid #0D9488;
        border-radius: 10px;
        padding: 1rem 1.1rem;
        transition: box-shadow .15s;
    }

    .step:hover {
        box-shadow: 0 4px 18px rgba(13, 148, 136, .10);
    }

    .step strong {
        display: block;
        color: #1C1917;
        font-size: .95rem;
        font-weight: 600;
        margin-bottom: .25rem;
    }

    .step span {
        color: #78716C;
        font-size: .875rem;
        line-height: 1.5;
    }

    /* ── Hint text ───────────────────────────────────────────────────────── */
    .hint {
        color: #78716C;
        font-size: .875rem;
        line-height: 1.55;
        margin-top: .4rem;
    }

    .hint code {
        background: #F0FDFA;
        color: #0D9488;
        padding: .1em .35em;
        border-radius: 4px;
        font-size: .82rem;
        font-family: 'Menlo', 'Consolas', monospace;
    }

    /* ── Primary action button ───────────────────────────────────────────── */
    .stButton > button {
        background: #0D9488;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: .6rem 1.5rem;
        font-weight: 600;
        font-size: .95rem;
        box-shadow: 0 1px 4px rgba(13, 148, 136, .25);
        transition: background .18s, box-shadow .18s, transform .12s;
    }
    .stButton > button:hover {
        background: #0F766E;
        box-shadow: 0 4px 14px rgba(13, 148, 136, .30);
        transform: translateY(-1px);
    }
    .stButton > button:active  { transform: translateY(0); }
    .stButton > button:disabled {
        background: #E7E5E4;
        color: #57534E !important;
        box-shadow: none;
        transform: none;
        cursor: not-allowed;
    }

    /* ── Download button (outlined teal — visually distinct from CTA) ────── */
    .stDownloadButton > button {
        background: #FFFFFF;
        border: 1.5px solid #0D9488;
        color: #0D9488;
        border-radius: 8px;
        font-weight: 600;
        transition: background .18s, color .18s, box-shadow .18s;
    }
    .stDownloadButton > button:hover {
        background: #0D9488;
        color: #FFFFFF;
        box-shadow: 0 3px 10px rgba(13, 148, 136, .25);
    }

    /* ── Form labels ─────────────────────────────────────────────────────── */
    .stSelectbox label,
    .stFileUploader label,
    .stTextInput label,
    .stTextArea label,
    .stCheckbox label {
        color: #44403C !important;
        font-weight: 500;
        font-size: .9rem;
    }
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] label span {
        color: #1C1917 !important;
        opacity: 1 !important;
    }

    /* ── File uploader drop zone ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] section {
        background: #FAFAF9;
        border: 1.5px dashed #D6D3D1;
        border-radius: 10px;
        transition: border-color .18s, background .18s;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #0D9488;
        background: #F0FDFA;
    }
    /* "Browse files" button only — not the per-file delete buttons */
    [data-testid="stFileUploader"] section button {
        background: #0D9488 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: background .18s !important;
    }
    [data-testid="stFileUploader"] section button:hover {
        background: #0F766E !important;
    }
    [data-testid="stFileUploader"] [title] {
        color: #1C1917 !important;
        opacity: 1 !important;
    }

    /* ── Metric cards ────────────────────────────────────────────────────── */
    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: 1px solid #E7E5E4;
        border-radius: 10px;
        padding: .9rem 1.2rem;
    }

    /* ── Expander ────────────────────────────────────────────────────────── */
    [data-testid="stExpander"] summary {
        color: #44403C;
        font-weight: 500;
    }

    /* ── Scrollbar ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(13, 148, 136, .22);
        border-radius: 3px;
    }

    /* ── Responsive ──────────────────────────────────────────────────────── */
    @media (max-width: 820px) {
        .app-header { grid-template-columns: 1fr; }
        .step-grid  { grid-template-columns: 1fr; }
        .app-header h1 { font-size: 1.85rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────
st.markdown(
    """
    <div class="app-header">
        <div>
            <h1>DIVA Call Transcriptor</h1>
            <p>Transcribe llamadas de audio en lote y descarga cada resultado como archivo de texto.</p>
        </div>
        <div class="header-aside">
            Motor de transcripción: <strong>faster-whisper local</strong>. El audio se normaliza, limpia y preprocesa automáticamente. Los resultados se entregan en un ZIP.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def fmt_seconds(s: float) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


def fmt_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def get_audio_duration_seconds(audio_path: Path) -> float | None:
    """Return audio duration in seconds via ffprobe (works for all formats)."""
    return get_audio_duration(str(audio_path))


def estimate_transcription_seconds(audio_path: Path) -> float:
    """Estimate local Whisper transcription time from the audio duration."""
    duration = get_audio_duration_seconds(audio_path)
    api_factor = 0.5

    if duration:
        return max(8.0, duration * api_factor)

    size_mb = max(audio_path.stat().st_size / (1024 * 1024), 1.0)
    return max(8.0, size_mb * api_factor * 1.8)


def run_with_file_progress(work, audio_path: Path, progress_slot, label: str):
    """Run blocking transcription work while keeping Streamlit progress moving."""
    started = time.monotonic()
    estimate = estimate_transcription_seconds(audio_path)

    progress_slot.progress(0.02, text=f"{label} - iniciando")
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(work)
        while True:
            try:
                result = future.result(timeout=0.5)
                progress_slot.progress(1.0, text=f"{label} - listo")
                return result
            except TimeoutError:
                elapsed = time.monotonic() - started
                pct = min(0.95, max(0.03, elapsed / estimate))
                progress_slot.progress(
                    pct,
                    text=f"{label} - transcribiendo... {int(pct * 100)}% estimado",
                )


def build_transcriptions_zip(results: list[dict]) -> bytes:
    zip_buffer = io.BytesIO()
    used_names = set()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for result in results:
            if "texto" not in result:
                continue

            txt_path = Path(result["archivo_txt"]) if result.get("archivo_txt") else None
            if txt_path and txt_path.exists():
                file_name = txt_path.name
                data = txt_path.read_bytes()
            else:
                file_name = f"{Path(result['archivo']).stem}_transcript.txt"
                data = result["texto"].encode("utf-8")

            unique_name = file_name
            counter = 2
            while unique_name.lower() in used_names:
                stem = Path(file_name).stem
                suffix = Path(file_name).suffix
                unique_name = f"{stem}_{counter}{suffix}"
                counter += 1

            used_names.add(unique_name.lower())
            zip_file.writestr(unique_name, data)

    return zip_buffer.getvalue()


def show_transcript_download(result: dict, key_prefix: str = "main"):
    """Render only the per-file TXT download action."""
    texto = result.get("texto", "")
    st.download_button(
        label="Descargar .txt",
        data=texto.encode("utf-8"),
        file_name=f"{Path(result['archivo']).stem}_transcript.txt",
        mime="text/plain",
        key=f"dl_txt_{key_prefix}",
    )


st.markdown(
    """
    <div class="step-grid">
        <div class="step"><strong>1. Selecciona audios</strong><span>Sube uno o varios archivos desde tu equipo.</span></div>
        <div class="step"><strong>2. Transcribe</strong><span>La app procesa cada archivo y muestra avance general e individual.</span></div>
        <div class="step"><strong>3. Descarga</strong><span>Obtén un ZIP con un archivo de texto por cada transcripción exitosa.</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown("### Cargar archivos de audio")
    st.markdown(
        '<p class="hint">Formatos compatibles: <code>.wav</code>, <code>.mp3</code>, <code>.m4a</code>, <code>.ogg</code>, <code>.flac</code>. Para mejores resultados, usa audios claros y evita subir archivos duplicados.</p>',
        unsafe_allow_html=True,
    )

    uploaded_batch = st.file_uploader(
        "Selecciona archivos de audio",
        type=["wav", "mp3", "m4a", "ogg", "flac"],
        accept_multiple_files=True,
        help="Puedes seleccionar varios archivos al mismo tiempo.",
        key="main_batch_files",
    )

    separar_canales = st.checkbox(
        "Separar canales estéreo (Agente / Usuario)",
        value=True,
        help="Usa el canal izquierdo para el agente y el derecho para el usuario. "
        "Desactívalo si el audio es mono o si ambos hablan mezclados.",
    )

    run_batch = st.button("Transcribir archivos", key="btn_main_batch", disabled=not uploaded_batch)
if run_batch and uploaded_batch:
    st.markdown("---")
    st.markdown("### Progreso")
    overall_progress = st.progress(0, text=f"Progreso general: 0/{len(uploaded_batch)} archivos completados")
    current_progress = st.progress(0, text="Archivo actual: en espera")
    results = []

    # Vocabulario del dominio fijo (BASE_PROMPT), sin entrada adicional del usuario.
    effective_prompt = build_prompt()

    if not FFMPEG_PATH:
        st.error(
            "No se encontró ffmpeg. Es necesario para preprocesar y leer archivos de audio. "
            "Instala ffmpeg y asegúrate de que esté disponible en el PATH del sistema."
        )
        st.stop()

    uploaded_payloads = [
        {
            "name": uploaded_audio.name,
            "suffix": Path(uploaded_audio.name).suffix,
            "data": uploaded_audio.getvalue(),
        }
        for uploaded_audio in uploaded_batch
    ]

    for idx, uploaded_audio in enumerate(uploaded_payloads, 1):
        completed = idx - 1
        overall_progress.progress(
            completed / len(uploaded_payloads),
            text=f"Progreso general: {completed}/{len(uploaded_payloads)} archivos completados",
        )
        current_progress.progress(0, text=f"Archivo actual [{idx}/{len(uploaded_payloads)}]: {uploaded_audio['name']}")

        suffix = uploaded_audio["suffix"]
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_audio["data"])
                tmp_path = tmp.name

            # Show quality warnings before transcription starts
            for w in validate_audio_quality(tmp_path):
                st.warning(f"⚠️ {uploaded_audio['name']}: {w}")

            raw = run_with_file_progress(
                lambda p=tmp_path: transcribe_audio_file(
                    p,
                    initial_prompt=effective_prompt,
                    handle_stereo=separar_canales,
                ),
                Path(tmp_path),
                current_progress,
                f"Archivo actual [{idx}/{len(uploaded_payloads)}]: {uploaded_audio['name']}",
            )
            texto = format_transcription_output(uploaded_audio["name"], raw["text"])
            for w in raw.get("channel_warnings", []):
                st.warning(f"⚠️ {uploaded_audio['name']}: {w}")

            results.append(
                {
                    "archivo": uploaded_audio["name"],
                    "ruta": uploaded_audio["name"],
                    "texto": texto,
                    "segmentos": raw["segments"],
                    "idioma_detectado": raw["language"],
                    "fecha_transcripcion": datetime.now().isoformat(),
                }
            )
        except Exception as exc:
            results.append({"archivo": uploaded_audio["name"], "ruta": uploaded_audio["name"], "error": str(exc)})
            current_progress.progress(
                1.0,
                text=f"Archivo actual [{idx}/{len(uploaded_payloads)}]: {uploaded_audio['name']} - error",
            )
        finally:
            if tmp_path:
                os.unlink(tmp_path)

        overall_progress.progress(
            idx / len(uploaded_payloads),
            text=f"Progreso general: {idx}/{len(uploaded_payloads)} archivos completados",
        )

    current_progress.progress(1.0, text="Archivo actual: finalizado")
    overall_progress.progress(1.0, text="Todos los archivos fueron procesados")
    st.session_state["main_upload_results"] = results

if st.session_state.get("main_upload_results"):
    results = st.session_state["main_upload_results"]
    ok = [r for r in results if "texto" in r]
    err = [r for r in results if "error" in r]

    st.markdown("---")
    st.markdown("### Resultados")
    c1, c2, c3 = st.columns(3)
    c1.metric("Procesados", len(results))
    c2.metric("Exitosos", len(ok))
    c3.metric("Con error", len(err))

    if ok:
        col_dl_txt, _ = st.columns([1, 3])
        with col_dl_txt:
            st.download_button(
                label="Descargar ZIP",
                data=build_transcriptions_zip(ok),
                file_name=f"transcriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                key="dl_main_upload_zip",
            )
        st.caption("El ZIP incluye un archivo `.txt` por cada transcripción exitosa.")

    if err:
        st.warning("Algunos archivos no se pudieron transcribir.")

    st.markdown("---")
    for idx_r, res in enumerate(results):
        col_file, col_action = st.columns([3, 1])
        with col_file:
            if "error" in res:
                st.error(f"Error · {res['archivo']}: {res['error']}")
            else:
                st.write(f"Listo · {res['archivo']}")
        with col_action:
            if "texto" in res:
                show_transcript_download(res, key_prefix=f"main_upload_{idx_r}")

st.markdown(
    """
    <div style='text-align:center; color:#A8A29E; font-size:.8rem; padding: 2rem 0 1rem;'>
        DIVA Call Transcriptor &nbsp;·&nbsp; faster-whisper local &nbsp;·&nbsp; Built with Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
st.stop()
