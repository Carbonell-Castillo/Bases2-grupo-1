param([switch]$OmitirBaseActiva)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$errores = [System.Collections.Generic.List[string]]::new()

function Confirmar($condicion, [string]$mensaje) {
    if ($condicion) { Write-Host "OK  $mensaje" -ForegroundColor Green }
    else { Write-Host "ERROR  $mensaje" -ForegroundColor Red; $errores.Add($mensaje) }
}

$requeridos = @(
    "docker-compose.yml", "sql\schema.sql", "sql\stored_procedures.sql",
    "sql\derivar_equipos.sql", "sql\validar_integridad.sql",
    "carga\generar_subconjuntos.py", "carga\cargar_paso.ps1",
    "backup\respaldo_full.ps1", "backup\respaldo_incremental.ps1",
    "restore\restaurar_full.ps1", "restore\restaurar_incremental.ps1",
    "docs\manual_usuario.md", "docs\informe_tecnico.md",
    "docs\analisis_comparativo.md", "docs\evidencia.md", "docs\test.md",
    "docs\manual_usuario.pdf", "docs\documentacion_tecnica.pdf"
)
foreach ($archivo in $requeridos) {
    Confirmar (Test-Path -LiteralPath (Join-Path $raiz $archivo) -PathType Leaf) $archivo
}

foreach ($script in Get-ChildItem $raiz -Recurse -Filter *.ps1 -File) {
    $tokens = $null; $fallos = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$tokens, [ref]$fallos)
    Confirmar ($fallos.Count -eq 0) "Sintaxis PowerShell: $($script.Name)"
}

python -m py_compile (Join-Path $raiz "carga\generar_subconjuntos.py") (Join-Path $raiz "docs\generar_pdfs.py")
Confirmar ($LASTEXITCODE -eq 0) "Sintaxis Python"

foreach ($ronda in "por_anio", "por_deporte", "por_deportista") {
    foreach ($backup in "full_carga1", "incr1_carga2", "incr2_carga3") {
        $manifest = Join-Path $raiz "backups\$ronda\$backup\backup_manifest"
        Confirmar (Test-Path -LiteralPath $manifest -PathType Leaf) "Manifest: $ronda/$backup"
    }
}

$backups = Import-Csv (Join-Path $raiz "logs\backups.csv")
$restores = Import-Csv (Join-Path $raiz "logs\restores.csv")
Confirmar ($backups.Count -eq 9) "Nueve operaciones de respaldo registradas"
Confirmar ((@($restores | Where-Object tipo -eq "RESTORE_FULL")).Count -ge 3) "Tres restauraciones FULL registradas"
Confirmar ((@($restores | Where-Object tipo -eq "RESTORE_INCREMENTAL")).Count -ge 3) "Tres restauraciones incrementales registradas"

if (-not $OmitirBaseActiva) {
    docker inspect fase2-pg *> $null
    Confirmar ($LASTEXITCODE -eq 0) "Contenedor fase2-pg activo"
    if ($LASTEXITCODE -eq 0) {
        $conteo = docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -At -c "SELECT count(*) FROM participacion;"
        Confirmar ([int]$conteo -eq 75533) "Base principal con 75,533 participaciones"
    }
}

if ($errores.Count -gt 0) {
    throw "Verificación fallida: $($errores.Count) problema(s)."
}
Write-Host "ENTREGA VALIDADA" -ForegroundColor Cyan
