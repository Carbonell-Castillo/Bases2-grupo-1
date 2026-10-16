#!/usr/bin/env bash
# Levanta Postgres en Docker desde cero, aplica src/schema.sql, carga los
# CSVs, deriva los equipos de eventos de conjunto, crea los stored procedures
# y deja abierta una sesión interactiva de psql para hacer consultas.

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

echo "Derivando equipos de eventos de conjunto (etl/derivar_equipos.sql)..."
docker cp etl/derivar_equipos.sql "$CONTAINER":/derivar_equipos.sql
docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /derivar_equipos.sql

echo "Creando stored procedures (src/stored_procedures.sql)..."
docker cp src/stored_procedures.sql "$CONTAINER":/stored_procedures.sql
docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -v ON_ERROR_STOP=1 -f /stored_procedures.sql

docker exec -it -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas
