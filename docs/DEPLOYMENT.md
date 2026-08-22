# Despliegue

## Requisitos

- Docker Engine y Docker Compose.
- `ffmpeg` solo para ejecucion fuera de Docker.
- Python 3.12 o superior, `ffmpeg` y `ffprobe` para ejecucion local.
- Acceso de red para descargar el modelo Whisper la primera vez.
- Acceso al endpoint Databricks, solo si se usa la revision mejorada (opcional).

## Docker Compose

Configura `.env` en la raiz:

```dotenv
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Opcional: solo para revision mejorada
DATABRICKS_TOKEN=tu-token
DATABRICKS_BASE_URL=https://<workspace>.azuredatabricks.net/serving-endpoints
DATABRICKS_MODEL=system.ai.claude-opus-4-8
```

Arranca la aplicacion:

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8521/_stcore/health
```

Logs:

```bash
docker compose logs -f diva
```

Detener:

```bash
docker compose down
```

## Imagen independiente

```bash
docker build -t diva-transcriptor:latest .
docker run --rm -p 8521:8522 --env-file .env diva-transcriptor:latest
```

## Ejecucion local

En Windows, usando el entorno del proyecto:

```powershell
& ".\.transcriptor\Scripts\python.exe" -m pip install -r code\requirements.txt
& ".\.transcriptor\Scripts\python.exe" -m streamlit run code\app.py --server.port=8521
```

La transcripcion funciona localmente despues de descargar el modelo Whisper. La revision mejorada sigue requiriendo acceso al endpoint Databricks.
