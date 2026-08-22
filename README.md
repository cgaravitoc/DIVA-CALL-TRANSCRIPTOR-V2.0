# DIVA Call Transcriptor v2.0

Aplicacion Streamlit para transcribir llamadas en espanol usando `faster-whisper` localmente. Permite preprocesar audio, separar canales estereo, ejecutar doble transcripcion y reconciliar resultados con un modelo servido en Databricks (opcional).

## Inicio rapido

### Ejecucion local

Requiere Python, `ffmpeg` y `ffprobe`. El modelo Whisper se descarga la primera vez y se almacena en la caché local.

```powershell
& ".\.transcriptor\Scripts\python.exe" -m pip install -r code\requirements.txt
& ".\.transcriptor\Scripts\python.exe" -m streamlit run code\app.py --server.port=8521
```

Abre `http://localhost:8521`.

### Docker

```bash
docker build -t diva-transcriptor:latest .
docker run --rm -p 8521:8522 --env-file .env diva-transcriptor:latest
```

### Docker Compose

Crea `.env` en la raiz del proyecto:

```dotenv
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Opcional: solo para "revision mejorada" (reconciliacion LLM)
DATABRICKS_TOKEN=tu-token
DATABRICKS_BASE_URL=https://<workspace>.azuredatabricks.net/serving-endpoints
DATABRICKS_MODEL=system.ai.claude-opus-4-8
```

Luego ejecuta:

```bash
docker compose up --build
```

La transcripcion base funciona localmente con Whisper y no requiere una clave de OpenAI. La "revision mejorada" (doble transcripcion + reconciliacion LLM) es opcional y requiere credenciales de Databricks.

## Componentes

- `code/app.py`: interfaz Streamlit y flujo de procesamiento.
- `code/audio_utils.py`: preprocesamiento, calidad de audio y orquestacion de transcripcion.
- `code/whisper_transcribe.py`: cliente de transcripcion local via `faster-whisper`.
- `code/llm_reviewer.py`: reconciliacion mediante el endpoint OpenAI-compatible de Databricks.
- `code/databricks_llm.py`: cliente de prueba para una consulta directa a Databricks.
- `code/transcript_service.py`: servicio/CLI programatico.
- `Dockerfile`: imagen reproducible con ffmpeg.
- `docker-compose.yml`: ejecucion del servicio con variables de Whisper/Databricks.
- `records/`: audios y transcripciones de ejemplo.

## Validacion

```powershell
& ".\.transcriptor\Scripts\python.exe" -m py_compile code\app.py code\audio_utils.py code\whisper_transcribe.py code\llm_reviewer.py code\databricks_llm.py
curl http://localhost:8521/_stcore/health
```

No guardes tokens en el codigo. `.env` esta excluido por `.gitignore`.
