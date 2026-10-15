# Respaldo fisico completo con pg_basebackup (formato plano + WAL en streaming).
# Uso: .\respaldo_full.ps1 -Destino por_anio/full_carga1
param(
    [string]$Contenedor = "fase2-pg",
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$LogCsv = "$PSScriptRoot\..\logs\backups.csv"
)

$ErrorActionPreference = "Stop"

docker inspect $Contenedor *> $null
if ($LASTEXITCODE -ne 0) { throw "No existe el contenedor '$Contenedor'." }

docker exec $Contenedor test ! -e "/backups/$Destino"
if ($LASTEXITCODE -ne 0) {
    throw "El destino /backups/$Destino ya existe. Use un destino nuevo para no mezclar respaldos."
}
docker exec $Contenedor mkdir -p "/backups/$Destino"
if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el destino /backups/$Destino." }

# Se implemento el respaldo completo (no dump) via el protocolo de replicacion
$inicio = Get-Date
docker exec $Contenedor pg_basebackup -h 127.0.0.1 -U postgres -D "/backups/$Destino" -Fp -X stream -c fast -P
if ($LASTEXITCODE -ne 0) { throw "pg_basebackup fallo; no se registro el respaldo." }
$fin = Get-Date
$dur = [math]::Round(($fin - $inicio).TotalSeconds, 2)

$tam = docker exec $Contenedor du -sh "/backups/$Destino" 2>$null
Write-Output "Respaldo FULL '$Destino' completado en $dur s ($fin) - tamano: $tam"
"$Destino,FULL,,$($inicio.ToString('o')),$($fin.ToString('o')),$dur" | Out-File -Append -FilePath $LogCsv -Encoding utf8
