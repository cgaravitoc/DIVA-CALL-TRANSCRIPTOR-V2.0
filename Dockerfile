FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ARG WHISPER_MODEL_SIZE=large

# ffmpeg – required for audio decoding and preprocessing (loudnorm, resampling)
# curl   – used by the Docker healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY code/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Download the complete CTranslate2 model to a stable, explicit path. Runtime
# never resolves a Hugging Face model ID and therefore never needs a network.
RUN WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE} python -c "import os; from faster_whisper.utils import download_model; download_model(os.environ['WHISPER_MODEL_SIZE'], output_dir='/opt/whisper-model')" \
    && test -s /opt/whisper-model/model.bin

ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE} \
    WHISPER_MODEL_PATH=/opt/whisper-model \
    WHISPER_LOCAL_FILES_ONLY=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TRANSFORMERS_OFFLINE=1

# Copy every application module required by the web and CLI entry points.
COPY code/ ./

EXPOSE 8521

# Transcription runs locally via faster-whisper; model is baked into the image.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD curl -f http://localhost:8522/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8521", "--server.address=0.0.0.0", "--server.headless=true"]
