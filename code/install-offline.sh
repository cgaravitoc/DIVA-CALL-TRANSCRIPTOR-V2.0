#!/usr/bin/env bash
set -euo pipefail

# Compatibility wrapper. The application no longer bundles Ollama.
# Use Docker Compose from the project root and provide Databricks credentials in .env.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  echo "Falta .env en $PROJECT_DIR" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no esta instalado" >&2
  exit 1
fi

docker compose up --build -d
docker compose ps
printf 'Aplicacion: http://localhost:8521\n'
