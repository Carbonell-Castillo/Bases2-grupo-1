#!/usr/bin/env bash
# Levanta Postgres en Docker, aplica src/schema.sql y carga los CSVs

set -euo pipefail

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

cd "$(dirname "$0")/.."

CONTAINER=proyecto-bases-db

echo "Recreando el contenedor desde cero..."
docker compose down -v --remove-orphans
docker compose up -d db

echo "Esperando a que Postgres acepte conexiones..."
until docker exec "$CONTAINER" pg_isready -U postgres -d olimpiadas >/dev/null 2>&1; do
    sleep 1
done

echo "Aplicando esquema (src/schema.sql)..."
docker cp src/schema.sql "$CONTAINER":/schema.sql
docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /schema.sql

echo "Copiando CSVs al contenedor..."
docker exec "$CONTAINER" mkdir -p /data
docker cp etl-csvs/. "$CONTAINER":/data

echo "Cargando datos (etl/load.sql)..."
docker cp etl/load.sql "$CONTAINER":/load.sql
docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /load.sql

echo "Listo."
