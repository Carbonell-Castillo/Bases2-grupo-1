#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export MSYS_NO_PATHCONV=1

ts() { date '+%Y-%m-%d %H:%M:%S'; }
paso() {
    echo "=================================================="
    echo "[$(ts)] $1"
    echo "=================================================="
}

pausa() {
    if [[ "${PAUSA_ENTRE_PASOS:-0}" == "1" && -t 0 ]]; then
        read -r -p "Presiona Enter para continuar con el siguiente paso..."
    fi
}

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

# Git Bash, WSL y Linux no siempre exponen Python con el mismo nombre. Se
# selecciona el primer intérprete que realmente pueda importar PyMongo.
PYTHON_CMD=""
for candidato in python python.exe py py.exe python3; do
    if command -v "$candidato" >/dev/null 2>&1 \
        && "$candidato" -c 'import pymongo' >/dev/null 2>&1; then
        PYTHON_CMD="$candidato"
        break
    fi
done
if [[ -z "$PYTHON_CMD" ]]; then
    echo "Error: no se encontró un Python con pymongo instalado." >&2
    echo "Instálalo con: python -m pip install -r ../requirements.txt" >&2
    exit 1
fi
echo "[$(ts)] Python seleccionado: $PYTHON_CMD"

paso "0. Eliminando los entornos anteriores con Docker Compose down"
pushd ../../Fase1 >/dev/null
"$DOCKER_CMD" compose down -v --remove-orphans
popd >/dev/null
"$DOCKER_CMD" compose -f ../docker-compose.yml down --remove-orphans
echo "[$(ts)] Contenedores anteriores de Fase 1 y Fase 3 eliminados"
pausa

paso "1. Regenerando datos corregidos y ejecutando el pipeline de Fase 1"
# La salida se genera dentro de fase3 (ignorada por Git), sin alterar los CSV
# entregados en Fase 1. Aquí se aplica, entre otras, la corrección LBN -> LIB.
pushd ../../Fase1 >/dev/null
"$PYTHON_CMD" etl/build_load.py --fase3-output ../fase3/src/output_fase1_corregido
bash etl/run_load.sh ../fase3/src/output_fase1_corregido
popd >/dev/null

echo "[$(ts)] Prueba de PostgreSQL: conteos de las 10 tablas"
"$DOCKER_CMD" exec -e PGPASSWORD=postgres proyecto-bases-db psql -U postgres -d olimpiadas -At -c \
    "SELECT 'pais='||count(*) FROM pais UNION ALL SELECT 'poblacion='||count(*) FROM poblacion UNION ALL SELECT 'atleta='||count(*) FROM atleta UNION ALL SELECT 'edicion='||count(*) FROM edicion UNION ALL SELECT 'deporte='||count(*) FROM deporte UNION ALL SELECT 'evento='||count(*) FROM evento UNION ALL SELECT 'equipo='||count(*) FROM equipo UNION ALL SELECT 'club='||count(*) FROM club UNION ALL SELECT 'atleta_club='||count(*) FROM atleta_club UNION ALL SELECT 'participacion='||count(*) FROM participacion;"
pausa

paso "2. Exportando tablas luego de derivar equipos"
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
    "$DOCKER_CMD" exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -c "\copy $tabla TO STDOUT WITH (FORMAT CSV, HEADER TRUE)" > "./output_postgres/${tabla}.csv"
done

echo " Archivos CSV generados en ./output_postgres/"
for tabla in "${TABLAS[@]}"; do
    if [[ ! -s "./output_postgres/${tabla}.csv" ]]; then
        echo "Error: la exportación de ${tabla}.csv está vacía o no existe." >&2
        exit 1
    fi
done
echo "[$(ts)] Prueba de exportación: 10 de 10 CSV existen y no están vacíos"
pausa

paso "3. Levantando MongoDB y cargando datos"

# Levantamos MongoDB desde cero; el paso 0 ya eliminó el contenedor anterior.
"$DOCKER_CMD" compose -f ../docker-compose.yml up -d

MONGO_CONTAINER="proyecto_fase3"
echo "Esperando a que MongoDB acepte conexiones..."
MONGO_READY=false
for intento in {1..60}; do
    if "$DOCKER_CMD" exec "$MONGO_CONTAINER" mongosh --quiet --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
        MONGO_READY=true
        break
    fi
    sleep 1
done
if [[ "$MONGO_READY" != true ]]; then
    echo "Error: MongoDB no aceptó conexiones después de 60 segundos." >&2
    "$DOCKER_CMD" logs "$MONGO_CONTAINER" >&2
    exit 1
fi

echo "[$(ts)] Creando colecciones, validadores e índices (crear_colecciones_indices.js)..."
"$DOCKER_CMD" cp crear_colecciones_indices.js "$MONGO_CONTAINER":/crear_colecciones_indices.js
"$DOCKER_CMD" exec "$MONGO_CONTAINER" mongosh --quiet --file /crear_colecciones_indices.js
echo "[$(ts)] Prueba de MongoDB: ping, colecciones e índices creados correctamente"
pausa

# Ejecutamos el script de Python que lee los CSVs exportados y los inserta en MongoDB
echo "Ejecutando script de carga en Python..."
"$PYTHON_CMD" script_de_carga.py

paso "4. Ejecutando verificación integral"
"$PYTHON_CMD" verificar_fase3.py

paso "5. Abriendo terminal interactiva de MongoDB"

# Abre mongosh apuntando directamente a la base de datos 'olimpiadas_fase3'
if [[ -t 0 && -t 1 ]]; then
    "$DOCKER_CMD" exec -it "$MONGO_CONTAINER" mongosh olimpiadas_fase3
else
    echo "Sin terminal interactiva; MongoDB sigue ejecutándose en segundo plano."
    echo "Conéctate con: docker exec -it $MONGO_CONTAINER mongosh olimpiadas_fase3"
fi
