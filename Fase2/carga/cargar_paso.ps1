# Carga (via COPY) los CSV nuevos de un paso de una ronda hacia la base de datos.
# Uso: .\cargar_paso.ps1 -CarpetaCSV ..\carga\subconjuntos\por_anio\carga1_paris2024
param(
    [string]$Contenedor = "fase2-pg",
    [string]$BaseDatos = "olimpiadas_fase2",
    [Parameter(Mandatory = $true)][string]$CarpetaCSV,
    [bool]$Validar = $true,
    [string]$DirectorioEvidencia = "$PSScriptRoot\..\logs\cargas"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $CarpetaCSV -PathType Container)) {
    throw "No existe la carpeta de carga: $CarpetaCSV"
}
docker inspect $Contenedor *> $null
if ($LASTEXITCODE -ne 0) { throw "No existe el contenedor '$Contenedor'." }

# Se implemento el orden de carga respetando las FKs del esquema (pais -> edicion/atleta -> evento -> equipo -> participacion)
$orden = @("pais", "edicion", "deporte", "evento", "atleta", "equipo", "participacion")

foreach ($tabla in $orden) {
    $archivo = Join-Path $CarpetaCSV "$tabla.csv"
    if (-not (Test-Path $archivo)) { continue }
    $lineas = (Get-Content $archivo | Measure-Object -Line).Lines
    if ($lineas -le 1) { continue }

    docker cp $archivo "${Contenedor}:/tmp/$tabla.csv" | Out-Null
    docker exec $Contenedor psql -U postgres -d $BaseDatos -v ON_ERROR_STOP=1 -c "COPY $tabla FROM '/tmp/$tabla.csv' WITH (FORMAT csv, HEADER true, NULL '')"
    if ($LASTEXITCODE -ne 0) { throw "Fallo la carga de $archivo en $tabla." }
}

# Se implemento la sincronizacion de secuencias IDENTITY tras la carga
docker exec $Contenedor psql -U postgres -d $BaseDatos -c "
SELECT setval(pg_get_serial_sequence('atleta','atleta_id'), COALESCE((SELECT MAX(atleta_id) FROM atleta), 1));
SELECT setval(pg_get_serial_sequence('edicion','edicion_id'), COALESCE((SELECT MAX(edicion_id) FROM edicion), 1));
SELECT setval(pg_get_serial_sequence('deporte','deporte_id'), COALESCE((SELECT MAX(deporte_id) FROM deporte), 1));
SELECT setval(pg_get_serial_sequence('evento','evento_id'), COALESCE((SELECT MAX(evento_id) FROM evento), 1));
SELECT setval(pg_get_serial_sequence('equipo','equipo_id'), COALESCE((SELECT MAX(equipo_id) FROM equipo), 1));
SELECT setval(pg_get_serial_sequence('participacion','participacion_id'), COALESCE((SELECT MAX(participacion_id) FROM participacion), 1));
" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "No se pudieron sincronizar las secuencias IDENTITY." }

if ($Validar) {
    $sqlValidacion = Join-Path $PSScriptRoot "..\sql\validar_integridad.sql"
    if (-not (Test-Path -LiteralPath $sqlValidacion)) {
        throw "No existe el script de validacion: $sqlValidacion"
    }
    New-Item -ItemType Directory -Path $DirectorioEvidencia -Force | Out-Null
    $paso = Split-Path $CarpetaCSV -Leaf
    $ronda = Split-Path (Split-Path $CarpetaCSV -Parent) -Leaf
    $nombreLog = (($ronda + "_" + $paso) -replace '[^a-zA-Z0-9_-]', '_') + ".txt"
    $log = Join-Path $DirectorioEvidencia $nombreLog

    docker cp $sqlValidacion "${Contenedor}:/tmp/validar_integridad.sql" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar validar_integridad.sql al contenedor." }
    "Evidencia generada: $(Get-Date -Format o)" | Out-File -FilePath $log -Encoding utf8
    # psql envia los NOTICE exitosos por stderr. Se captura toda la salida sin
    # permitir que PowerShell convierta esos NOTICE en excepciones.
    $errorActionAnterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $salidaValidacion = docker exec $Contenedor psql -U postgres -d $BaseDatos -v ON_ERROR_STOP=1 -f /tmp/validar_integridad.sql 2>&1
    $codigoValidacion = $LASTEXITCODE
    $ErrorActionPreference = $errorActionAnterior
    $salidaValidacion | Out-File -FilePath $log -Append -Encoding utf8
    $salidaValidacion | Write-Output
    if ($codigoValidacion -ne 0) { throw "La validacion posterior a la carga fallo. Revise $log" }
    Write-Output "Evidencia de COUNT/SELECT e integridad: $log"
}

Write-Output "Carga completa: $CarpetaCSV"
