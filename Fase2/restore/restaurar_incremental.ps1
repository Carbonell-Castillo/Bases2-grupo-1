# Combina el respaldo full + la cadena de incrementales con pg_combinebackup y
# arranca un contenedor nuevo con el resultado, midiendo el tiempo total.
# No depende del contenedor original (pudo haber sido eliminado junto con la BD).
# Uso: .\restaurar_incremental.ps1 -Cadena por_anio/full_carga1,por_anio/incr1_carga2,por_anio/incr2_carga3 -Puerto 5434
param(
    [Parameter(Mandatory = $true)][string[]]$Cadena,
    [string]$CarpetaRestaurada = "restore_tmp",
    [int]$Puerto = 5434,
    [string]$NombreContenedorDestino = "fase2-restore",
    [string]$LogCsv = "$PSScriptRoot\..\logs\restores.csv",
    [int]$TimeoutSegundos = 90
)

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path "$PSScriptRoot\.."
if ($Cadena.Count -lt 2) { throw "La cadena debe incluir un full y al menos un incremental." }
foreach ($elemento in $Cadena) {
    if (-not (Test-Path "$raiz\backups\$elemento\backup_manifest")) {
        throw "No existe el respaldo o su backup_manifest: $elemento"
    }
}
$existente = docker ps -aq --filter "name=^/$NombreContenedorDestino$"
if ($existente) { docker rm -f $NombreContenedorDestino | Out-Null }
Remove-Item -Recurse -Force "$raiz\backups\$CarpetaRestaurada" -ErrorAction SilentlyContinue

# Se implemento la restauracion incremental: pg_combinebackup reconstruye el directorio completo,
# usando un contenedor efimero que solo necesita el binario de postgres y el bind-mount de /backups
$inicio = Get-Date
$montajeBackups = "$raiz\backups" + ":/backups"
$rutas = $Cadena | ForEach-Object { "/backups/$_" }
docker run --rm -v $montajeBackups postgres:17-alpine pg_combinebackup @rutas -o "/backups/$CarpetaRestaurada"
if ($LASTEXITCODE -ne 0) { throw "pg_combinebackup no pudo reconstruir la cadena." }
docker run --rm -v $montajeBackups postgres:17-alpine chown -R postgres:postgres "/backups/$CarpetaRestaurada"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron ajustar los permisos del respaldo combinado." }

$montajeDestino = "$raiz\backups\$CarpetaRestaurada" + ":/var/lib/postgresql/data"
docker run -d --name $NombreContenedorDestino -e POSTGRES_PASSWORD=postgres `
    -v $montajeDestino -p "${Puerto}:5432" postgres:17-alpine | Out-Null
if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar el contenedor restaurado." }

$limite = (Get-Date).AddSeconds($TimeoutSegundos)
do {
    $corriendo = docker ps -q --filter "name=^/$NombreContenedorDestino$"
    if (-not $corriendo) {
        docker logs $NombreContenedorDestino
        throw "El contenedor restaurado termino antes de aceptar conexiones."
    }
    docker exec $NombreContenedorDestino pg_isready -U postgres *> $null
    $ready = $LASTEXITCODE -eq 0
    if (-not $ready) { Start-Sleep -Milliseconds 500 }
    if ((Get-Date) -gt $limite) {
        docker logs $NombreContenedorDestino
        throw "La restauracion no estuvo lista en $TimeoutSegundos segundos."
    }
} until ($ready)
$fin = Get-Date
$dur = [math]::Round(($fin - $inicio).TotalSeconds, 2)

$cadenaTxt = $Cadena -join " + "
Write-Output "Restauracion INCREMENTAL ($cadenaTxt) lista en $dur s ($fin) -> contenedor $NombreContenedorDestino puerto $Puerto"
"$cadenaTxt,RESTORE_INCREMENTAL,$($inicio.ToString('o')),$($fin.ToString('o')),$dur" | Out-File -Append -FilePath $LogCsv -Encoding utf8
