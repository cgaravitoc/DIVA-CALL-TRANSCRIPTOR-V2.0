FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/data/huggingface

ARG WHISPER_MODEL_SIZE=large

# ffmpeg – required for audio decoding and preprocessing (loudnorm, resampling)
# curl   – used by the Docker healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /data/huggingface

COPY code/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model during build so runtime can work offline.
RUN WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE} python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ.get('WHISPER_MODEL_SIZE', 'large'), device='cpu', compute_type='int8')"

# Copy application source; all modules are required at runtime
COPY code/app.py code/audio_utils.py code/whisper_transcribe.py ./

EXPOSE 8522

# Transcription runs locally via faster-whisper; model is baked at build time.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD curl -f http://localhost:8522/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8522", "--server.address=0.0.0.0", "--server.headless=true"]
