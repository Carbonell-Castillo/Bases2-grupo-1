#!/usr/bin/env bash
# Levanta Postgres en Docker desde cero, aplica src/schema.sql, carga los
# CSVs, deriva los equipos de eventos de conjunto, crea los stored procedures
# y deja abierta una sesión interactiva de psql para hacer consultas.

set -euo pipefail

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

DOCKER_CMD=""
for candidato in docker docker.exe; do
    if command -v "$candidato" >/dev/null 2>&1 \
        && "$candidato" version --format '{{.Server.Version}}' >/dev/null 2>&1; then
        DOCKER_CMD="$candidato"
        break
    fi
done
if [[ -z "$DOCKER_CMD" ]]; then
    echo "Error: Docker Desktop no está disponible desde esta terminal." >&2
    exit 1
fi

cd "$(dirname "$0")/.."

CONTAINER=proyecto-bases-db
# Puede recibirse una carpeta de CSV como primer argumento. Si se omite, se
# conserva el comportamiento original de Fase 1.
CSV_DIR="${1:-${ETL_CSV_DIR:-etl-csvs}}"

echo "Recreando el contenedor desde cero..."
"$DOCKER_CMD" compose down -v --remove-orphans
"$DOCKER_CMD" compose up -d db

echo "Esperando a que Postgres acepte conexiones..."
until "$DOCKER_CMD" exec "$CONTAINER" pg_isready -U postgres -d olimpiadas >/dev/null 2>&1; do
    sleep 1
done

echo "Aplicando esquema (src/schema.sql)..."
"$DOCKER_CMD" cp src/schema.sql "$CONTAINER":/schema.sql
"$DOCKER_CMD" exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /schema.sql

echo "Copiando CSVs al contenedor..."
"$DOCKER_CMD" exec "$CONTAINER" mkdir -p /data
"$DOCKER_CMD" cp "$CSV_DIR"/. "$CONTAINER":/data

echo "Cargando datos (etl/load.sql)..."
"$DOCKER_CMD" cp etl/load.sql "$CONTAINER":/load.sql
"$DOCKER_CMD" exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /load.sql

echo "Derivando equipos de eventos de conjunto (etl/derivar_equipos.sql)..."
"$DOCKER_CMD" cp etl/derivar_equipos.sql "$CONTAINER":/derivar_equipos.sql
"$DOCKER_CMD" exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /derivar_equipos.sql

echo "Creando stored procedures (src/stored_procedures.sql)..."
"$DOCKER_CMD" cp src/stored_procedures.sql "$CONTAINER":/stored_procedures.sql
"$DOCKER_CMD" exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /stored_procedures.sql

# docker exec -it -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas
