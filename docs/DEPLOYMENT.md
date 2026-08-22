# Despliegue

## Requisitos

- Docker Engine y Docker Compose.
- `ffmpeg` solo para ejecucion fuera de Docker.
- Python 3.12 o superior, `ffmpeg` y `ffprobe` para ejecucion local.
- Acceso de red para descargar el modelo Whisper la primera vez.

## Docker Compose

Configura `.env` en la raiz:

```dotenv
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

`large-v3` ofrece mayor precision, pero requiere mas memoria y tarda mas en
CPU. Sobrescribe `WHISPER_MODEL_SIZE` con `medium` o `small` si es necesario.

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

La transcripcion funciona localmente despues de descargar el modelo Whisper.
