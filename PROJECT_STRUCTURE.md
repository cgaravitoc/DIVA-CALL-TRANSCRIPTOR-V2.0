# Estructura del proyecto

```text
DIVA CALL TRANSCRIPTOR V2.0/
├── code/
│   ├── app.py
│   ├── audio_utils.py
│   ├── databricks_llm.py
│   ├── whisper_transcribe.py
│   ├── llm_reviewer.py
│   ├── transcript_service.py
│   ├── requirements.txt
│   └── (sin scripts de instalacion alternativos)
├── docs/
│   ├── DEPLOYMENT.md
│   └── NOTAS.md
├── records/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── README.md
```

La carpeta `code/` es la unica fuente de codigo. El `Dockerfile` se ejecuta desde la raiz y copia sus dependencias desde `code/`.

Los archivos de `records/` son datos de ejemplo. Los artefactos Docker y las caches Python son generados y no forman parte del runtime.
