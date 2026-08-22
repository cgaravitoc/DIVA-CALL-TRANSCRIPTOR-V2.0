FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg – required for audio decoding and preprocessing (loudnorm, resampling)
# curl   – used by the Docker healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY code/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application source; all modules are required at runtime
COPY code/app.py code/audio_utils.py code/gpt_transcribe.py code/llm_reviewer.py ./

EXPOSE 8522

# Transcription runs via OpenAI's gpt-4o-transcribe API — requires OPENAI_API_KEY at runtime.
# Revisión mejorada (opcional) requires Databricks credentials.
ENV DATABRICKS_BASE_URL=https://adb-2549848299256377.17.azuredatabricks.net/serving-endpoints \
    DATABRICKS_MODEL=system.ai.claude-opus-4-8

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD curl -f http://localhost:8522/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8522", "--server.address=0.0.0.0", "--server.headless=true"]
