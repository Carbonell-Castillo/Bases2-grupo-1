# Pruebas paso a paso — comandos listos para copiar y pegar

Esta guía reproduce los tres escenarios: carga por año, por deporte y por
deportista. Incluye cargas, respaldo full, dos incrementales, eliminación de
la base, restauración y validación.

> **Advertencia:** `docker compose down -v` elimina la base principal para
> simular una pérdida total. No elimina los respaldos de `Fase2/backups/`.

## 0. Entrar a la carpeta correcta

El error `'.\backup\respaldo_full.ps1' no se reconoce` ocurrió porque
PowerShell estaba en `D:\bccas\USAC\ProyectoBases`, pero los scripts están en
`D:\bccas\USAC\ProyectoBases\Fase2`.

Copiar y pegar:

```powershell
Set-Location 'D:\bccas\USAC\ProyectoBases\Fase2'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Get-Location
Test-Path .\backup\respaldo_full.ps1
Test-Path .\sql\validar_integridad.sql
```

Los dos `Test-Path` deben devolver `True`.

## 1. Preparación — imagen, limpieza y funciones

### 1.1 Aclaración sobre las imágenes

El proyecto no contiene un `Dockerfile` propio. Tanto la base principal
`fase2-pg` como la base restaurada `fase2-prueba` utilizan la misma imagen
oficial `postgres:17-alpine`. Por eso no se ejecuta `docker build`; se descarga
o actualiza con:

```powershell
docker compose pull db
docker pull postgres:17-alpine
```

### 1.2 Borrar los contenedores y comenzar con una base principal vacía

Este bloque elimina el contenedor y volumen principal, elimina el contenedor
de restauración si existe y vuelve a levantar PostgreSQL. **Conserva** las
carpetas de `Fase2/backups/`.

Ejecutar cada bloque por separado:

```powershell
docker compose down -v
```

```powershell
$ContenedorRestore = docker ps -aq --filter "name=^/fase2-prueba$"
if ($ContenedorRestore) { docker rm -f fase2-prueba }
```

```powershell
docker compose pull db
```

```powershell
docker compose up -d db
```

```powershell
$Limite = (Get-Date).AddSeconds(90)
do {
    docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -At -c "SELECT 1" *> $null
    $Listo = $LASTEXITCODE -eq 0
    if (-not $Listo) { Start-Sleep -Milliseconds 500 }
    if ((Get-Date) -gt $Limite) { throw 'PostgreSQL no inició en 90 segundos.' }
} until ($Listo)
```

Crear las tablas y procedimientos en la base vacía:

```powershell
docker cp .\sql\schema.sql fase2-pg:/tmp/schema.sql
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/schema.sql
```

```powershell
docker cp .\sql\stored_procedures.sql fase2-pg:/tmp/stored_procedures.sql
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/stored_procedures.sql
```

### 1.3 Limpieza total opcional, incluyendo respaldos

> **PELIGRO:** ejecutar esta sección solamente si se desea eliminar todos los
> respaldos full, incrementales y carpetas restauradas. Para probar una
> restauración se deben conservar los respaldos y omitir esta sección.

El bloque verifica la ruta exacta antes de borrar su contenido y conserva
únicamente `.gitkeep`:

```powershell
$RutaBackupsEsperada = 'D:\bccas\USAC\ProyectoBases\Fase2\backups'
$RutaBackupsActual = (Resolve-Path .\backups).Path
if ($RutaBackupsActual -ne $RutaBackupsEsperada) { throw "Ruta inesperada: $RutaBackupsActual" }
Get-ChildItem -LiteralPath $RutaBackupsActual -Force |
    Where-Object { $_.Name -ne '.gitkeep' } |
    Remove-Item -Recurse -Force
```

Comprobar que quedó vacía:

```powershell
Get-ChildItem .\backups -Force
```

### 1.4 Renovar también la imagen local, opcional

La imagen solo se puede eliminar cuando ningún contenedor la está utilizando.
Después se vuelve a descargar; esta operación no crea dos imágenes diferentes:

```powershell
docker compose down -v
$ContenedorRestore = docker ps -aq --filter "name=^/fase2-prueba$"
if ($ContenedorRestore) { docker rm -f fase2-prueba }
docker image rm postgres:17-alpine
docker pull postgres:17-alpine
```

Si Docker informa que otro contenedor utiliza la imagen, no se debe forzar su
eliminación; `docker pull postgres:17-alpine` es suficiente para actualizarla.

### 1.5 Funciones auxiliares — ejecutar una vez por ventana

Copiar y pegar este bloque completo. Define las funciones utilizadas en los
tres escenarios:

```powershell
Set-Location 'D:\bccas\USAC\ProyectoBases\Fase2'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

function Reset-Fase2Database {
    docker compose down -v
    docker compose up -d db
    Start-Sleep -Seconds 5

    $limite = (Get-Date).AddSeconds(90)
    do {
        $errorActionAnterior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -At -c 'SELECT 1' *> $null
        $listo = $LASTEXITCODE -eq 0
        $ErrorActionPreference = $errorActionAnterior
        if (-not $listo) { Start-Sleep -Milliseconds 500 }
        if ((Get-Date) -gt $limite) { throw 'PostgreSQL no inicio en 90 segundos.' }
    } until ($listo)

    docker cp .\sql\schema.sql fase2-pg:/tmp/schema.sql
    docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/schema.sql

    docker cp .\sql\stored_procedures.sql fase2-pg:/tmp/stored_procedures.sql
    docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/stored_procedures.sql
}

function Test-Fase2Integrity {
    param([string]$Contenedor)
    docker cp .\sql\validar_integridad.sql "${Contenedor}:/tmp/validar_integridad.sql"
    docker exec $Contenedor psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/validar_integridad.sql
    if ($LASTEXITCODE -ne 0) { throw "Fallo la integridad en $Contenedor" }
}

function Assert-ParticipacionCount {
    param([string]$Contenedor, [int]$Esperado)
    $actual = [int](docker exec $Contenedor psql -U postgres -d olimpiadas_fase2 -At -c 'SELECT COUNT(*) FROM participacion;')
    if ($actual -ne $Esperado) { throw "Conteo incorrecto en ${Contenedor}: esperado=$Esperado, actual=$actual" }
    Write-Host "OK ${Contenedor}: participacion=$actual" -ForegroundColor Green
}

python .\carga\generar_subconjuntos.py
```

No cierres esta ventana de PowerShell hasta terminar las pruebas.

---

# Conexiones en DBeaver

Un respaldo almacenado en `Fase2/backups/` no es un servidor al que DBeaver
pueda conectarse. Primero se restaura en un contenedor PostgreSQL; después se
conecta DBeaver a ese contenedor.

## Base principal

Usar esta conexión mientras está activo el contenedor `fase2-pg`:

| Campo | Valor |
|---|---|
| Tipo | PostgreSQL |
| Host | `localhost` |
| Puerto | `5433` |
| Base de datos | `olimpiadas_fase2` |
| Usuario | `postgres` |
| Contraseña | `postgres` |

Comprobar que está levantada:

```powershell
docker ps --filter "name=fase2-pg"
```

## Base restaurada desde un respaldo

Usar esta segunda conexión cuando esté activo el contenedor `fase2-prueba`:

| Campo | Valor |
|---|---|
| Tipo | PostgreSQL |
| Host | `localhost` |
| Puerto | `5544` |
| Base de datos | `olimpiadas_fase2` |
| Usuario | `postgres` |
| Contraseña | `postgres` |

Comprobar que está levantada:

```powershell
docker ps --filter "name=fase2-prueba"
```

En el editor SQL de cualquiera de las dos conexiones se pueden ejecutar estas
consultas de comprobación:

```sql
SELECT COUNT(*) AS participaciones
FROM participacion;

SELECT ed.anio, COUNT(*) AS participaciones
FROM participacion p
JOIN evento e ON e.evento_id = p.evento_id
JOIN edicion ed ON ed.edicion_id = e.edicion_id
GROUP BY ed.anio
ORDER BY ed.anio;
```

Cuando se ejecuta `docker compose down -v`, la conexión principal deja de
funcionar porque se elimina `fase2-pg` y su volumen. Después de restaurar se
debe usar la segunda conexión, puerto `5544`.

---

# Escenario 1 — carga por año

Datos: París 2024, Tokio 2020 y Río 2016.

## ¿Hay que cargar cada tabla manualmente?

No. Cada vez que se ejecuta `cargar_paso.ps1`, el script revisa todos los CSV
de la carpeta indicada y los carga automáticamente respetando las llaves
foráneas, en este orden:

```text
País -> población/edición/atleta/club -> deporte/evento
     -> atleta_club -> participación -> derivación de equipos
```

Por ejemplo, `carga1_paris2024` contiene los CSV relacionados de `pais`,
`poblacion`, `edicion`, `deporte`, `evento`, `atleta`, `club`,
`atleta_club` y `participacion`. Un solo comando carga todo; no se debe
ejecutar un `COPY` manual para cada tabla.

El `equipo.csv` original de Fase 1 está vacío porque `run_load.sh` crea los
equipos después de importar los CSV. Fase 2 reproduce automáticamente ese
paso con `sql/derivar_equipos.sql` después de cada carga y antes del respaldo.
Por eso no se debe ejecutar `run_load.sh` de Fase 1: usaría otro contenedor,
otra base de datos y rompería la secuencia incremental.

Que `equipo` quede en cero puede ser válido para un subconjunto estrictamente
individual, como 100 metros femeninos o un único deportista; en la carga por
año sí se derivan equipos. En la validación real final por año se obtuvieron
`5108` equipos y `28647` participaciones enlazadas a ellos.

Después de cada carga se puede revisar el estado de las diez tablas con:

```powershell
docker cp .\sql\validar_integridad.sql fase2-pg:/tmp/validar_integridad.sql
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/validar_integridad.sql
```

La validación muestra el conteo de todas las tablas, una muestra de sus datos y
confirma que no existan filas huérfanas.

## 2.1 Crear una base nueva

```powershell
Reset-Fase2Database
```

Crear identificadores únicos para que los nuevos respaldos no sobrescriban ni
se mezclen con ejecuciones anteriores:

```powershell
Reset-Fase2Database
$RunId = 'demostracion_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$BackupRoot = "pruebas/$RunId"
New-Item -ItemType Directory -Path .\logs\pruebas -Force | Out-Null
```

## 2.2 Carga 1 — París 2024

Ejecutar la primera carga:

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga1_paris2024 -DirectorioEvidencia ".\logs\pruebas\$RunId"
```

Consultar el estado después de la carga:

```powershell
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

El resultado esperado es `14891`. Validarlo automáticamente:

```powershell
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 14891
```

Crear el respaldo completo. El comando crea automáticamente la carpeta
`Fase2/backups/<BackupRoot>/full_carga1` y copia allí el estado completo:

```powershell
.\backup\respaldo_full.ps1 -Destino "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

Comprobar que el respaldo existe y tiene manifiesto:

```powershell
Test-Path ".\backups\$BackupRoot\full_carga1\backup_manifest"
Get-ChildItem ".\backups\$BackupRoot\full_carga1"
```

## 2.3 Carga 2 — Tokio 2020

Agregar la segunda carga:

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga2_tokio2020 -DirectorioEvidencia ".\logs\pruebas\$RunId"
```

Consultar el nuevo estado:

```powershell
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

El resultado esperado es `43890`. Validarlo automáticamente:

```powershell
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 43890
```

Crear el primer incremental usando el FULL como base:

```powershell
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr1_carga2" -ManifestBase "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

Comprobar la nueva carpeta:

```powershell
Test-Path ".\backups\$BackupRoot\incr1_carga2\backup_manifest"
Get-ChildItem ".\backups\$BackupRoot"
```

## 2.4 Carga 3 — Río 2016

Agregar la tercera carga:

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga3_rio2016 -DirectorioEvidencia ".\logs\pruebas\$RunId"
```

Consultar el estado final:

```powershell
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

El resultado esperado es `75533`. Validarlo automáticamente:

```powershell
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 75533
```

Crear el segundo incremental usando el incremental anterior como base:

```powershell
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr2_carga3" -ManifestBase "$BackupRoot/incr1_carga2" -LogCsv $BackupLog
```

Comprobar que ya existen las tres partes de la cadena:

```powershell
Test-Path ".\backups\$BackupRoot\incr2_carga3\backup_manifest"
Get-ChildItem ".\backups\$BackupRoot"
```

Validar la integridad:

```powershell
Test-Fase2Integrity -Contenedor fase2-pg
```

## 2.5 Probar fragmentación

```powershell
docker cp .\sql\verificar_fragmentacion.sql fase2-pg:/tmp/verificar_fragmentacion.sql
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -v ON_ERROR_STOP=1 -f /tmp/verificar_fragmentacion.sql
```

## 2.6 Eliminar la base y restaurar solo el full

Antes de eliminarla, en DBeaver la conexión principal debe mostrar `75533`.
El siguiente comando simula una pérdida total: elimina el contenedor principal
y el volumen de la base, pero conserva los respaldos del directorio
`Fase2/backups/`.

```powershell
docker compose down -v
docker ps -a --filter "name=fase2-pg"
```

Confirmar que los respaldos continúan en disco:

```powershell
Get-ChildItem ".\backups\$BackupRoot"
```

Crear la base restaurada desde el FULL. El script descarga/utiliza
`postgres:17-alpine`, crea `fase2-prueba` y publica el puerto `5544`:

```powershell
.\restore\restaurar_full.ps1 -BackupDir "$BackupRoot/full_carga1" -CarpetaRestaurada "restore_${RunId}_full" -Puerto 5544 -NombreContenedor fase2-prueba -LogCsv $RestoreLog
```

Consultar el estado recuperado:

```powershell
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

Validarlo automáticamente:

```powershell
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 14891
Test-Fase2Integrity -Contenedor fase2-prueba
```

Abrir la conexión restaurada de DBeaver, en el puerto `5544`. El conteo debe
ser `14891`, porque el full corresponde al estado después de París 2024.

## 2.7 Restaurar full más incremental 1

Esta restauración reconstruye el segundo punto de la cadena. El script elimina
el contenedor de prueba anterior, combina el full con el primer incremental y
crea nuevamente `fase2-prueba`.

```powershell
.\restore\restaurar_incremental.ps1 -Cadena "$BackupRoot/full_carga1","$BackupRoot/incr1_carga2" -CarpetaRestaurada "restore_${RunId}_incr1" -Puerto 5544 -NombreContenedorDestino fase2-prueba -LogCsv $RestoreLog
```

Consultar el punto recuperado:

```powershell
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

Validar que corresponde a París más Tokio:

```powershell
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 43890
Test-Fase2Integrity -Contenedor fase2-prueba
```

Actualizar la conexión restaurada en DBeaver. Ahora debe mostrar `43890`, que
corresponde a París 2024 más Tokio 2020.

## 2.8 Restaurar full más los dos incrementales

```powershell
.\restore\restaurar_incremental.ps1 -Cadena "$BackupRoot/full_carga1","$BackupRoot/incr1_carga2","$BackupRoot/incr2_carga3" -CarpetaRestaurada "restore_${RunId}_incremental" -Puerto 5544 -NombreContenedorDestino fase2-prueba -LogCsv $RestoreLog
```

Consultar el estado final recuperado:

```powershell
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) AS participaciones FROM participacion;"
```

Validar el conteo y la integridad:

```powershell
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 75533
Test-Fase2Integrity -Contenedor fase2-prueba
```

Consultar la distribución por año:

```powershell
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT ed.anio, COUNT(*) FROM participacion p JOIN evento e ON e.evento_id=p.evento_id JOIN edicion ed ON ed.edicion_id=e.edicion_id GROUP BY ed.anio ORDER BY ed.anio;"
```

Resultado esperado:

```text
2016 | 31643
2020 | 28999
2024 | 14891
```

Este último resultado demuestra que la cadena completa recuperó el estado que
existía antes de borrar la base principal.

## 2.9 Finalizar el escenario

```powershell
docker rm -f fase2-prueba
Get-Content $BackupLog
Get-Content $RestoreLog
```

---

# Escenario 2 — carga por deporte

Datos: 100 metros femeninos en París 2024, Tokio 2020 y Río 2016.

## 3.1 Crear una base nueva

```powershell
Reset-Fase2Database
$RunId = 'deporte_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$BackupRoot = "pruebas/$RunId"
New-Item -ItemType Directory -Path .\logs\pruebas -Force | Out-Null
$BackupLog = ".\logs\pruebas\test_backups_$RunId.csv"
$RestoreLog = ".\logs\pruebas\test_restores_$RunId.csv"
'backup,tipo,base,inicio,fin,duracion_s' | Set-Content $BackupLog -Encoding utf8
'backup,tipo,inicio,fin,duracion_s' | Set-Content $RestoreLog -Encoding utf8
```

## 3.2 Carga 1 y full

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deporte\carga1_paris2024 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 91
.\backup\respaldo_full.ps1 -Destino "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

## 3.3 Carga 2 e incremental 1

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deporte\carga2_tokio2020 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 232
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr1_carga2" -ManifestBase "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

## 3.4 Carga 3 e incremental 2

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deporte\carga3_rio2016 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 410
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr2_carga3" -ManifestBase "$BackupRoot/incr1_carga2" -LogCsv $BackupLog
Test-Fase2Integrity -Contenedor fase2-pg
```

## 3.5 Eliminar y restaurar solo el full

```powershell
docker compose down -v
.\restore\restaurar_full.ps1 -BackupDir "$BackupRoot/full_carga1" -CarpetaRestaurada "restore_${RunId}_full" -Puerto 5544 -NombreContenedor fase2-prueba -LogCsv $RestoreLog
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 91
Test-Fase2Integrity -Contenedor fase2-prueba
```

## 3.6 Restaurar full más incrementales

```powershell
.\restore\restaurar_incremental.ps1 -Cadena "$BackupRoot/full_carga1","$BackupRoot/incr1_carga2","$BackupRoot/incr2_carga3" -CarpetaRestaurada "restore_${RunId}_incremental" -Puerto 5544 -NombreContenedorDestino fase2-prueba -LogCsv $RestoreLog
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 410
Test-Fase2Integrity -Contenedor fase2-prueba
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT ed.anio, COUNT(*) FROM participacion p JOIN evento e ON e.evento_id=p.evento_id JOIN edicion ed ON ed.edicion_id=e.edicion_id GROUP BY ed.anio ORDER BY ed.anio;"
```

Resultado esperado:

```text
2016 | 178
2020 | 141
2024 | 91
```

## 3.7 Finalizar el escenario

```powershell
docker rm -f fase2-prueba
Get-Content $BackupLog
Get-Content $RestoreLog
```

---

# Escenario 3 — carga por deportista

Datos: Usain Bolt en Atenas 2004, Pekín 2008 y Londres 2012.

## 4.1 Crear una base nueva

```powershell
Reset-Fase2Database
$RunId = 'deportista_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$BackupRoot = "pruebas/$RunId"
New-Item -ItemType Directory -Path .\logs\pruebas -Force | Out-Null
$BackupLog = ".\logs\pruebas\test_backups_$RunId.csv"
$RestoreLog = ".\logs\pruebas\test_restores_$RunId.csv"
'backup,tipo,base,inicio,fin,duracion_s' | Set-Content $BackupLog -Encoding utf8
'backup,tipo,inicio,fin,duracion_s' | Set-Content $RestoreLog -Encoding utf8
```

## 4.2 Carga 1 y full

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deportista\carga1_atenas2004 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 2
.\backup\respaldo_full.ps1 -Destino "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

## 4.3 Carga 2 e incremental 1

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deportista\carga2_pekin2008 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 8
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr1_carga2" -ManifestBase "$BackupRoot/full_carga1" -LogCsv $BackupLog
```

## 4.4 Carga 3 e incremental 2

```powershell
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_deportista\carga3_londres2012 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 14
.\backup\respaldo_incremental.ps1 -Destino "$BackupRoot/incr2_carga3" -ManifestBase "$BackupRoot/incr1_carga2" -LogCsv $BackupLog
Test-Fase2Integrity -Contenedor fase2-pg
```

## 4.5 Eliminar y restaurar solo el full

```powershell
docker compose down -v
.\restore\restaurar_full.ps1 -BackupDir "$BackupRoot/full_carga1" -CarpetaRestaurada "restore_${RunId}_full" -Puerto 5544 -NombreContenedor fase2-prueba -LogCsv $RestoreLog
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 2
Test-Fase2Integrity -Contenedor fase2-prueba
```

## 4.6 Restaurar full más incrementales

```powershell
.\restore\restaurar_incremental.ps1 -Cadena "$BackupRoot/full_carga1","$BackupRoot/incr1_carga2","$BackupRoot/incr2_carga3" -CarpetaRestaurada "restore_${RunId}_incremental" -Puerto 5544 -NombreContenedorDestino fase2-prueba -LogCsv $RestoreLog
Assert-ParticipacionCount -Contenedor fase2-prueba -Esperado 14
Test-Fase2Integrity -Contenedor fase2-prueba
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c "SELECT ed.anio, COUNT(*) FROM participacion p JOIN evento e ON e.evento_id=p.evento_id JOIN edicion ed ON ed.edicion_id=e.edicion_id GROUP BY ed.anio ORDER BY ed.anio;"
```

Resultado esperado:

```text
2004 | 2
2008 | 6
2012 | 6
```

## 4.7 Probar el stored procedure

```powershell
$sql = "CALL sp_info_atleta('Usain Bolt'); SELECT * FROM resultado_sp_info_atleta ORDER BY anio;"
docker exec fase2-prueba psql -U postgres -d olimpiadas_fase2 -c $sql
```

## 4.8 Finalizar el escenario

```powershell
docker rm -f fase2-prueba
Get-Content $BackupLog
Get-Content $RestoreLog
```

---

# 5. Dejar el proyecto levantado al terminar

Los escenarios eliminan la base principal antes de probar la restauración en
`fase2-prueba`. Para dejar `fase2-pg` activo nuevamente con las 75,533
participaciones finales:

```powershell
$RunId = 'estado_final_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Reset-Fase2Database
New-Item -ItemType Directory -Path .\logs\pruebas -Force | Out-Null
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga1_paris2024 -DirectorioEvidencia ".\logs\pruebas\$RunId"
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga2_tokio2020 -DirectorioEvidencia ".\logs\pruebas\$RunId"
.\carga\cargar_paso.ps1 -CarpetaCSV .\carga\subconjuntos\por_anio\carga3_rio2016 -DirectorioEvidencia ".\logs\pruebas\$RunId"
Assert-ParticipacionCount -Contenedor fase2-pg -Esperado 75533
Test-Fase2Integrity -Contenedor fase2-pg
```

# 6. Verificación rápida

```powershell
docker ps --filter "name=fase2-pg"
docker exec fase2-pg psql -U postgres -d olimpiadas_fase2 -c "SELECT COUNT(*) FROM participacion;"
```

El conteo debe ser `75533`.

# 7. Errores comunes

## ¿Un respaldo nuevo elimina el anterior?

No. Ni el respaldo full ni el incremental eliminan respaldos anteriores. Cada
uno se almacena en su propia carpeta dentro de `Fase2/backups/`.

Los scripts incluso rechazan un destino que ya exista para evitar sobrescribir
un respaldo accidentalmente. Por eso se genera un identificador diferente en
cada prueba:

```powershell
$RunId = 'manual_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$BackupRoot = "pruebas/$RunId"
```

La cadena se conserva de esta forma:

```text
full_carga1
    -> incr1_carga2 (depende de full_carga1)
        -> incr2_carga3 (depende de incr1_carga2)
```

`docker compose down -v` elimina la base principal, no esas carpetas de
respaldo. Los scripts de restauración sí reemplazan el contenedor
`fase2-prueba` y su carpeta temporal reconstruida, pero no eliminan las carpetas
fuente `full_carga1`, `incr1_carga2` o `incr2_carga3`.

## El script no se reconoce

```powershell
Set-Location 'D:\bccas\USAC\ProyectoBases\Fase2'
```

## Docker no encuentra `sql/`

```powershell
Set-Location 'D:\bccas\USAC\ProyectoBases\Fase2'
docker cp .\sql\validar_integridad.sql fase2-pg:/tmp/validar_integridad.sql
```

## El destino del respaldo ya existe

Los scripts no sobrescriben respaldos. Crear otro identificador:

```powershell
$RunId = 'manual_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$BackupRoot = "pruebas/$RunId"
```

## El puerto 5544 está ocupado

```powershell
docker rm -f fase2-prueba
```
