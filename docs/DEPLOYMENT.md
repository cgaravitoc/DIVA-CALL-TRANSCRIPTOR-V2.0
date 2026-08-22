# Despliegue

## Requisitos

- Docker Engine y Docker Compose.
- `ffmpeg` solo para ejecucion fuera de Docker.
- Acceso de red a la API de OpenAI (`OPENAI_API_KEY`), requerido para transcribir.
- Acceso de red al endpoint Databricks, solo si se usa la revision mejorada (opcional).

## Docker Compose

Configura `.env` en la raiz:

```dotenv
OPENAI_API_KEY=tu-clave-openai
GPT_TRANSCRIBE_MODEL=gpt-4o-transcribe

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
docker run --rm -p 8521:8521 --env-file .env diva-transcriptor:latest
```

## Nota sobre modo offline

La transcripcion depende de la API de OpenAI (`gpt-4o-transcribe`) y la revision mejorada de Databricks. Ninguna de las dos funciona sin conectividad a internet/red hacia esos servicios; no hay modo totalmente offline.
