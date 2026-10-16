# Restaura UNICAMENTE el respaldo completo en un contenedor nuevo y mide el tiempo.
# Uso: .\restaurar_full.ps1 -BackupDir por_anio/full_carga1 -Puerto 5434
param(
    [Parameter(Mandatory = $true)][string]$BackupDir,
    [string]$CarpetaRestaurada = "restore_tmp",
    [int]$Puerto = 5434,
    [string]$NombreContenedor = "fase2-restore",
    [string]$LogCsv = "$PSScriptRoot\..\logs\restores.csv",
    [int]$TimeoutSegundos = 90
)

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path "$PSScriptRoot\.."
if (-not (Test-Path "$raiz\backups\$BackupDir\backup_manifest")) {
    throw "No existe el respaldo o su backup_manifest: $BackupDir"
}
$existente = docker ps -aq --filter "name=^/$NombreContenedor$"
if ($existente) { docker rm -f $NombreContenedor | Out-Null }
Remove-Item -Recurse -Force "$raiz\backups\$CarpetaRestaurada" -ErrorAction SilentlyContinue

# Se implemento la restauracion completa: copiar el respaldo y arrancar Postgres apuntando a esa carpeta
$inicio = Get-Date
Copy-Item -Recurse "$raiz\backups\$BackupDir" "$raiz\backups\$CarpetaRestaurada"
$montaje = "$raiz\backups\$CarpetaRestaurada" + ":/var/lib/postgresql/data"
docker run -d --name $NombreContenedor -e POSTGRES_PASSWORD=postgres `
    -v $montaje -p "${Puerto}:5432" postgres:17-alpine | Out-Null
if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar el contenedor restaurado." }

$limite = (Get-Date).AddSeconds($TimeoutSegundos)
do {
    $corriendo = docker ps -q --filter "name=^/$NombreContenedor$"
    if (-not $corriendo) {
        docker logs $NombreContenedor
        throw "El contenedor restaurado termino antes de aceptar conexiones."
    }
    docker exec $NombreContenedor pg_isready -U postgres *> $null
    $ready = $LASTEXITCODE -eq 0
    if (-not $ready) { Start-Sleep -Milliseconds 500 }
    if ((Get-Date) -gt $limite) {
        docker logs $NombreContenedor
        throw "La restauracion no estuvo lista en $TimeoutSegundos segundos."
    }
} until ($ready)
$fin = Get-Date
$dur = [math]::Round(($fin - $inicio).TotalSeconds, 2)

Write-Output "Restauracion FULL de '$BackupDir' lista en $dur s ($fin) -> contenedor $NombreContenedor puerto $Puerto"
"$BackupDir,RESTORE_FULL,$($inicio.ToString('o')),$($fin.ToString('o')),$dur" | Out-File -Append -FilePath $LogCsv -Encoding utf8
