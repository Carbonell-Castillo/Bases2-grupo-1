#!/usr/bin/env bash

set -euo pipefail

# Nos aseguramos de estar situados en la carpeta fase3
cd "$(dirname "$0")"

echo "=================================================="
echo " 1. Ejecutando el pipeline de Fase 1 "
echo "=================================================="
# Ejecutamos el script de la fase 1 (que levanta docker, carga CSVs y deriva equipos)
bash ../fase1/etl/run_load.sh

echo "=================================================="
echo " 2. Exportando tablas luego de derivar equipos "
echo "=================================================="
# Creamos la carpeta de salida dentro de fase3
mkdir -p ./output_postgres

CONTAINER="proyecto-fase3"

# Lista de tablas a exportar
TABLAS=(
    "pais" "poblacion" "atleta" "edicion" "deporte" 
    "evento" "equipo" "club" "atleta_club" "participacion"
)

for tabla in "${TABLAS[@]}"; do
    echo "  -> Exportando $tabla..."
    docker exec -e PGPASSWORD=postgres "$CONTAINER" psql -U postgres -d olimpiadas -c "\copy $tabla TO STDOUT WITH (FORMAT CSV, HEADER TRUE)" > "./output_postgres/${tabla}.csv"
done

echo " Archivos CSV generados en ./fase3/output_postgres/"

echo "=================================================="
echo " 3. Levantando MongoDB y cargando datos "
echo "=================================================="

# Levantamos el contenedor de MongoDB (proyecto-fase3) sin volúmenes persistentes
docker compose up -d

# Retrasamos unos segundos para asegurar que el puerto 27017 esté recibiendo conexiones
echo "Esperando a que MongoDB inicie..."
sleep 5

# Ejecutamos el script de Python que lee los CSVs exportados y los inserta en MongoDB
echo "Ejecutando script de carga en Python..."
python script_de_carga.py

echo "=================================================="
echo " 4. Abriendo terminal interactiva de MongoDB "
echo "=================================================="
MONGO_CONTAINER="proyecto-fase3"

# Abre mongosh apuntando directamente a la base de datos 'olimpiadas_fase3'
docker exec -it "$MONGO_CONTAINER" mongosh olimpiadas_fase3
