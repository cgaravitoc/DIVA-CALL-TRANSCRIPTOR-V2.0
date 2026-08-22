# DIVA Call Transcriptor v2.0

Aplicación Streamlit para transcribir llamadas en español con
`faster-whisper`. Preprocesa audio con FFmpeg, permite separar canales
estéreo e identifica cada intervención con timestamp y hablante.

## Ejecución local

Requiere Python, `ffmpeg` y `ffprobe`. El modelo Whisper se descarga en el
primer uso y queda almacenado en `.whisper-cache/` dentro del proyecto. Esta
carpeta está excluida de Git y del contexto de construcción de Docker.

```powershell
& ".\.transcriptor\Scripts\python.exe" -m pip install -r code\requirements.txt
& ".\.transcriptor\Scripts\python.exe" -m streamlit run code\app.py --server.port=8521
```

Abre `http://localhost:8521`.

## Imagen Docker autocontenida

El build incluye:

- Python y todas las dependencias de `code/requirements.txt`.
- `ffmpeg` y `ffprobe`.
- El modelo Whisper en `/opt/whisper-model`.
- La aplicación Streamlit y sus módulos.

La máquina que construye la imagen necesita internet para descargar estos
recursos. El servidor que ejecuta la imagen no necesita acceso a internet.

```bash
docker build --platform linux/amd64 \
  --build-arg WHISPER_MODEL_SIZE=large \
  -t diva-transcriptor:latest .
```

El modelo se selecciona durante el build. Para usar `medium` o `small`, hay
que reconstruir la imagen con el valor correspondiente.

### Ejecutar el contenedor

```bash
docker run -d \
  --name diva-transcriptor \
  --restart unless-stopped \
  -p 8521:8522 \
  diva-transcriptor:latest
```

Comprobación:

```bash
curl http://localhost:8521/_stcore/health
docker logs -f diva-transcriptor
```

La aplicación queda disponible en `http://localhost:8521`.

### Exportar para un servidor sin internet

```bash
docker save -o diva-transcriptor-offline-large.tar diva-transcriptor:latest
sha256sum diva-transcriptor-offline-large.tar
```

En PowerShell, el hash se calcula con:

```powershell
Get-FileHash .\diva-transcriptor-offline-large.tar -Algorithm SHA256
```

Copia el TAR al servidor Linux y verifica que el SHA-256 sea el mismo. Después:

```bash
docker load -i diva-transcriptor-offline-large.tar

docker run -d \
  --name diva-transcriptor \
  --restart unless-stopped \
  -p 8521:8522 \
  diva-transcriptor:latest
```

El archivo `*.tar` está excluido de Git.


## Funcionamiento

La transcripción se realiza localmente y no requiere credenciales de servicios
externos. En grabaciones estéreo, el canal izquierdo se identifica como
`Agente` y el derecho como `Usuario`.

```text
00:00:00 [Agente] Buenas tardes, ¿hablo con el señor Luis?
00:13:04 [Usuario] Sí señor, con él habla. ¿Qué necesita?
```

## Componentes

- `code/app.py`: interfaz Streamlit y flujo de procesamiento.
- `code/audio_utils.py`: preprocesamiento y orquestación de transcripción.
- `code/whisper_transcribe.py`: carga local de `faster-whisper`.
- `code/transcript_service.py`: servicio/CLI programático.
- `Dockerfile`: imagen Linux autocontenida con FFmpeg y Whisper.
- `records/`: audios y transcripciones de ejemplo.

## Validación

```powershell
& ".\.transcriptor\Scripts\python.exe" -m py_compile code\app.py code\audio_utils.py code\whisper_transcribe.py code\transcript_service.py
curl http://localhost:8521/_stcore/health
```

Consulta [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) para el procedimiento completo
de despliegue y operación offline.
