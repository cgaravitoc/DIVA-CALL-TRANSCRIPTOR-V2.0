# DIVA Call Transcriptor v2.0

Aplicacion Streamlit para transcribir llamadas en espanol usando `faster-whisper` localmente. Permite preprocesar audio y separar canales estereo, identificando cada intervencion con timestamp y hablante.

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
```

Luego ejecuta:

```bash
docker compose up --build
```

La transcripcion funciona localmente con Whisper y no requiere credenciales de servicios externos.

En grabaciones estereo, el canal izquierdo se identifica como `Agente` y el
canal derecho como `Usuario`. Las transiciones se exportan con este formato:

```text
00:00:00 [Agente] Buenas tardes, ¿hablo con el señor Luis?
00:13:04 [Usuario] Sí señor, con él habla. ¿Qué necesita?
```

## Componentes

- `code/app.py`: interfaz Streamlit y flujo de procesamiento.
- `code/audio_utils.py`: preprocesamiento, calidad de audio y orquestacion de transcripcion.
- `code/whisper_transcribe.py`: cliente de transcripcion local via `faster-whisper`.
- `code/transcript_service.py`: servicio/CLI programatico.
- `Dockerfile`: imagen reproducible con ffmpeg.
- `docker-compose.yml`: ejecucion del servicio con variables de Whisper/Databricks.
- `records/`: audios y transcripciones de ejemplo.

## Validacion

```powershell
& ".\.transcriptor\Scripts\python.exe" -m py_compile code\app.py code\audio_utils.py code\whisper_transcribe.py code\transcript_service.py
curl http://localhost:8521/_stcore/health
```

No guardes tokens en el codigo. `.env` esta excluido por `.gitignore`.
