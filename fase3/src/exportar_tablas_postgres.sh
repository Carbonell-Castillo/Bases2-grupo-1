#!/usr/bin/env bash
# Exporta exclusivamente las diez tablas ya cargadas en PostgreSQL.
# Debe ejecutarse después de Fase1/etl/run_load.sh.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export MSYS_NO_PATHCONV=1

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

if ! "$DOCKER_CMD" exec proyecto-bases-db pg_isready -U postgres -d olimpiadas >/dev/null 2>&1; then
    echo "Error: PostgreSQL no está listo. Ejecuta primero el paso de carga de Fase 1." >&2
    exit 1
fi

TABLAS=(
    "pais" "poblacion" "atleta" "edicion" "deporte"
    "evento" "equipo" "club" "atleta_club" "participacion"
)

mkdir -p output_postgres
for tabla in "${TABLAS[@]}"; do
    echo "Exportando ${tabla}.csv..."
    "$DOCKER_CMD" exec -e PGPASSWORD=postgres proyecto-bases-db \
        psql -U postgres -d olimpiadas \
        -c "\copy $tabla TO STDOUT WITH (FORMAT CSV, HEADER TRUE)" \
        > "output_postgres/${tabla}.csv"
    if [[ ! -s "output_postgres/${tabla}.csv" ]]; then
        echo "Error: output_postgres/${tabla}.csv quedó vacío." >&2
        exit 1
    fi
done

echo "Exportación terminada: 10 de 10 CSV no vacíos en fase3/src/output_postgres/."
