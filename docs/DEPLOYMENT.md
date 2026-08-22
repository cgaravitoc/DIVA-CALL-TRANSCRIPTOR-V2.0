# Despliegue offline

Esta guía crea y despliega una imagen Docker autocontenida. El servidor de
destino puede permanecer completamente sin acceso a internet.

## Arquitectura

La imagen contiene todos los recursos de ejecución:

- Aplicación Streamlit.
- Dependencias Python.
- `ffmpeg` y `ffprobe`.
- Modelo CTranslate2 de Whisper en `/opt/whisper-model`.

El contenedor fuerza `HF_HUB_OFFLINE=1` y
`WHISPER_LOCAL_FILES_ONLY=1`. Whisper carga el directorio interno y no intenta
resolver ni descargar un modelo desde Hugging Face.

La imagen generada con los comandos de esta guía es para Linux `amd64`. Si el
servidor usa ARM64, debe reconstruirse con la plataforma correspondiente y
validarse en esa arquitectura.

## Requisitos

### Máquina de construcción

- Docker Engine o Docker Desktop.
- Acceso a internet durante el build.
- Espacio suficiente para la imagen y el TAR exportado.

### Servidor de destino

- Linux `amd64` con Docker Engine.
- Espacio en disco y memoria suficientes para Whisper `large`.
- No necesita Python, FFmpeg ni acceso a internet instalados en el host.

## 1. Construir la imagen

Desde la raíz del proyecto:

```bash
docker build --platform linux/amd64 \
  --build-arg WHISPER_MODEL_SIZE=large \
  -t diva-transcriptor:latest .
```

`WHISPER_MODEL_SIZE` es una decisión de build. Cambiar esta variable al
arrancar el contenedor no reemplaza el modelo incorporado. Para usar otro
modelo, reconstruye la imagen:

```bash
docker build --platform linux/amd64 \
  --build-arg WHISPER_MODEL_SIZE=medium \
  -t diva-transcriptor:medium .
```

## 2. Validar la imagen sin red

Comprueba que FFmpeg y el modelo puedan cargarse con la red deshabilitada:

```bash
docker run --rm --network none \
  --entrypoint python \
  diva-transcriptor:latest \
  -c "import shutil; assert shutil.which('ffmpeg'); assert shutil.which('ffprobe'); from whisper_transcribe import ensure_model_loaded; ensure_model_loaded(); print('offline: ok')"
```

La salida esperada termina en `offline: ok`.

## 3. Exportar y verificar el artefacto

```bash
docker save -o diva-transcriptor-offline-large.tar diva-transcriptor:latest
sha256sum diva-transcriptor-offline-large.tar
```

En Windows PowerShell:

```powershell
docker save -o diva-transcriptor-offline-large.tar diva-transcriptor:latest
Get-FileHash .\diva-transcriptor-offline-large.tar -Algorithm SHA256
```

Registra el hash y copia el TAR al servidor mediante el mecanismo autorizado.
En el servidor, calcula nuevamente el SHA-256 antes de cargarlo. Los valores
deben coincidir.

## 4. Cargar la imagen en el servidor

```bash
docker load -i diva-transcriptor-offline-large.tar
docker image inspect diva-transcriptor:latest \
  --format 'OS={{.Os}} ARCH={{.Architecture}} SIZE={{.Size}}'
```

## 5. Iniciar el contenedor

```bash
docker run -d \
  --name diva-transcriptor \
  --restart unless-stopped \
  -p 8521:8522 \
  diva-transcriptor:latest
```

No se requiere `.env` para la configuración predeterminada de CPU. La imagen
ya define:

```text
WHISPER_MODEL_PATH=/opt/whisper-model
WHISPER_MODEL_SIZE=large
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LOCAL_FILES_ONLY=1
HF_HUB_OFFLINE=1
```

No cambies `WHISPER_MODEL_PATH`: apunta al modelo incorporado en la imagen.

## 6. Verificar el servicio

```bash
docker ps --filter name=diva-transcriptor
curl http://localhost:8521/_stcore/health
docker exec diva-transcriptor \
  sh -c 'test -s /opt/whisper-model/model.bin && echo "modelo: presente"'
```

La respuesta de salud debe ser `ok`.

Desde otra máquina, abre `http://IP_DEL_SERVIDOR:8521`. El firewall del
servidor debe permitir conexiones entrantes al puerto 8521.

## Operación

Ver logs:

```bash
docker logs -f diva-transcriptor
```

Reiniciar:

```bash
docker restart diva-transcriptor
```

Detener e iniciar:

```bash
docker stop diva-transcriptor
docker start diva-transcriptor
```

Eliminar el contenedor sin borrar la imagen:

```bash
docker rm -f diva-transcriptor
```

## Actualizar la aplicación

Una actualización requiere una imagen y un TAR nuevos:

```bash
docker build --platform linux/amd64 \
  --build-arg WHISPER_MODEL_SIZE=large \
  -t diva-transcriptor:latest .
docker save -o diva-transcriptor-offline-large.tar diva-transcriptor:latest
```

Después de transferir y cargar la nueva imagen en el servidor:

```bash
docker rm -f diva-transcriptor
docker run -d \
  --name diva-transcriptor \
  --restart unless-stopped \
  -p 8521:8522 \
  diva-transcriptor:latest
```

## Docker Compose

Docker Compose no es requerido y este proyecto no incluye actualmente
`docker-compose.yml`. Para el único servicio de la aplicación, `docker run`
ofrece el flujo más directo y evita depender de archivos adicionales en el
servidor offline.

## Solución de problemas

### El puerto 8521 está ocupado

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Detén el servicio que usa el puerto o publica otro puerto:

```bash
docker run -d --name diva-transcriptor -p 8523:8522 diva-transcriptor:latest
```

### No se encuentra el modelo

```bash
docker run --rm --entrypoint sh diva-transcriptor:latest \
  -c 'ls -lh /opt/whisper-model && test -s /opt/whisper-model/model.bin'
```

Si `model.bin` no existe, la imagen o su transferencia están incompletas.
Verifica el SHA-256 del TAR y vuelve a ejecutar `docker load`.

### Comprobar FFmpeg

```bash
docker run --rm --entrypoint sh diva-transcriptor:latest \
  -c 'ffmpeg -version | head -n 1; ffprobe -version | head -n 1'
```
