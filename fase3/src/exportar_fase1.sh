#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python -c 'import pymongo' >/dev/null 2>&1; then
    echo "Error: pymongo no está instalado. Ejecuta: python -m pip install pymongo" >&2
    exit 1
fi

echo "=================================================="
echo " 1. Ejecutando el pipeline de Fase 1 "
echo "=================================================="
# Ejecutamos el script de la fase 1 (que levanta docker, carga CSVs y deriva equipos)
bash ../../fase1/etl/run_load.sh

echo "=================================================="
echo " 2. Exportando tablas luego de derivar equipos "
echo "=================================================="
# Creamos la carpeta de salida junto a este script
mkdir -p ./output_postgres

CONTAINER="proyecto-bases-db"

# Lista de tablas a exportar
TABLAS=(
    "pais" "poblacion" "atleta" "edicion" "deporte" 
    "evento" "equipo" "club" "atleta_club" "participacion"
)

for tabla in "${TABLAS[@]}"; do
    echo "  -> Exportando $tabla..."
    docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -c "\copy $tabla TO STDOUT WITH (FORMAT CSV, HEADER TRUE)" > "./output_postgres/${tabla}.csv"
done

echo " Archivos CSV generados en ./output_postgres/"

echo "=================================================="
echo " 3. Levantando MongoDB y cargando datos "
echo "=================================================="

# Levantamos el contenedor de MongoDB sin volúmenes persistentes
docker compose -f ../docker-compose.yml up -d

MONGO_CONTAINER="proyecto_fase3"
echo "Esperando a que MongoDB acepte conexiones..."
MONGO_READY=false
for intento in {1..60}; do
    if docker exec "$MONGO_CONTAINER" mongosh --quiet --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
        MONGO_READY=true
        break
    fi
    sleep 1
done
if [[ "$MONGO_READY" != true ]]; then
    echo "Error: MongoDB no aceptó conexiones después de 60 segundos." >&2
    docker logs "$MONGO_CONTAINER" >&2
    exit 1
fi

# Ejecutamos el script de Python que lee los CSVs exportados y los inserta en MongoDB
echo "Ejecutando script de carga en Python..."
python "$SCRIPT_DIR/script_de_carga.py"

echo "=================================================="
echo " 4. Abriendo terminal interactiva de MongoDB "
echo "=================================================="

# Abre mongosh apuntando directamente a la base de datos 'olimpiadas_fase3'
if [[ -t 0 && -t 1 ]]; then
    docker exec -it "$MONGO_CONTAINER" mongosh olimpiadas_fase3
else
    echo "Sin terminal interactiva; MongoDB sigue ejecutándose en segundo plano."
    echo "Conéctate con: docker exec -it $MONGO_CONTAINER mongosh olimpiadas_fase3"
fi
