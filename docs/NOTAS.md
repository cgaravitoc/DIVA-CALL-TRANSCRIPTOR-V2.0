# Notas

## Reconstruir la imagen Docker desde cero

Cuando los cambios de código no se reflejan en el contenedor, reconstruye ignorando el cache:

```bash
# 1) Reconstruir sin caché, jalando la imagen base más reciente
docker build --no-cache --pull -t diva-transcriptor:latest .

# 2) (Opcional) eliminar la imagen anterior con el mismo tag antes de reconstruir,
#    si quieres forzar que no quede ningún rastro previo
docker rmi diva-transcriptor:latest

# 3) Levantar el contenedor con las credenciales de Databricks
docker run --rm -p 8521:8521 --env-file .env diva-transcriptor:latest
# o con Compose:
docker compose up --build -d
```

`--no-cache` ignora todas las capas cacheadas (por eso reinstala todo desde cero) y `--pull` refresca la imagen base `python:3.12-slim`. Por eso tarda más de lo normal.
