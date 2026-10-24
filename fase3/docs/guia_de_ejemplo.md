# Guía completa desde cero — Fase 3

Esta es la secuencia manual y lineal para borrar todo, reconstruir PostgreSQL, exportar los datos, migrarlos a MongoDB y probar cada etapa. Ejecute todos los comandos en **PowerShell desde la raíz del repositorio** `Bases2-grupo-1`.

## Requisitos previos

- Docker Desktop abierto.
- Python 3.8 o superior.
- Bash disponible mediante Git Bash o WSL.

Instale la única dependencia de Python:

```powershell
python -m pip install -r requirements.txt
```

## Paso 1: borrar completamente los entornos anteriores

PostgreSQL se elimina junto con su volumen; MongoDB se elimina junto con su contenedor y red:

```powershell
docker compose -f Fase1/docker-compose.yml down -v --remove-orphans
docker compose -f fase3/docker-compose.yml down --remove-orphans
```

Compruebe que ya no existen:

```powershell
docker ps -a --filter "name=proyecto-bases-db" --filter "name=proyecto_fase3"
```

No debe aparecer ninguno de esos dos contenedores.

## Paso 2: generar los CSV corregidos para Fase 3

Este paso corrige el alias `LBN → LIB` y evita mezclar personas cuando una fuente reutiliza el mismo ID para nombres diferentes. La salida es regenerable y no modifica los CSV históricos de Fase 1.

```powershell
python Fase1/etl/build_load.py --fase3-output fase3/src/output_fase1_corregido
```

Al final debe mostrar, entre otros:

```text
atleta:          244540
participacion:   693398
```

Compruebe que se generaron los diez archivos:

```powershell
Get-ChildItem fase3/src/output_fase1_corregido/*.csv | Select-Object Name, Length
```

## Paso 3: iniciar PostgreSQL y cargar la información corregida

```powershell
bash Fase1/etl/run_load.sh ../fase3/src/output_fase1_corregido
```

Este comando crea `proyecto-bases-db`, aplica el esquema, carga los CSV, deriva los equipos y crea los procedimientos almacenados.

## Paso 4: probar PostgreSQL

Verifique que el contenedor está activo:

```powershell
docker ps --filter "name=proyecto-bases-db"
```

Compruebe los conteos principales:

```powershell
docker exec -e PGPASSWORD=postgres proyecto-bases-db psql -U postgres -d olimpiadas -c "SELECT (SELECT count(*) FROM atleta) AS atletas, (SELECT count(*) FROM participacion) AS participaciones, (SELECT count(*) FROM equipo) AS equipos;"
```

Resultado esperado:

| atletas | participaciones | equipos |
|---:|---:|---:|
| 244540 | 693398 | 35880 |

Para entrar manualmente a PostgreSQL:

```powershell
docker exec -it -e PGPASSWORD=postgres proyecto-bases-db psql -U postgres -d olimpiadas
```

Para salir de `psql`, escriba `\q`.

## Paso 5: exportar las diez tablas de PostgreSQL

```powershell
bash fase3/src/exportar_tablas_postgres.sh
```

Los archivos quedan en `fase3/src/output_postgres/`.

## Paso 6: comprobar la exportación

```powershell
Get-ChildItem fase3/src/output_postgres/*.csv | Select-Object Name, Length
```

Deben aparecer exactamente estos diez archivos, todos con tamaño mayor que cero:

```text
atleta.csv
atleta_club.csv
club.csv
deporte.csv
edicion.csv
equipo.csv
evento.csv
pais.csv
participacion.csv
poblacion.csv
```

## Paso 7: iniciar MongoDB vacío

```powershell
docker compose -f fase3/docker-compose.yml up -d
Start-Sleep -Seconds 3
docker compose -f fase3/docker-compose.yml ps
```

El contenedor `proyecto_fase3` debe aparecer como `Up` con el puerto `27017` publicado.

Pruebe el servidor vacío:

```powershell
docker exec proyecto_fase3 mongosh --quiet --eval "db.adminCommand({ping:1})"
```

Debe responder con `ok: 1`.

## Paso 8: crear las colecciones, validadores e índices

Copie y ejecute el script de estructura:

```powershell
docker cp fase3/src/crear_colecciones_indices.js proyecto_fase3:/crear_colecciones_indices.js
docker exec proyecto_fase3 mongosh --quiet --file /crear_colecciones_indices.js
```

Debe informar la creación de:

- `paises`
- `ediciones`
- `atletas`

## Paso 9: ver las colecciones antes de cargar datos

```powershell
docker exec proyecto_fase3 mongosh olimpiadas_fase3 --quiet --eval "db.getCollectionNames()"
```

También puede revisar los índices:

```powershell
docker exec proyecto_fase3 mongosh olimpiadas_fase3 --quiet --eval "db.atletas.getIndexes().map(i => i.name)"
```

En este momento las colecciones existen, pero todavía están vacías:

```powershell
docker exec proyecto_fase3 mongosh olimpiadas_fase3 --quiet --eval "db.atletas.countDocuments()"
```

Resultado esperado: `0`.

## Paso 10: ejecutar la migración hacia MongoDB

```powershell
python fase3/src/script_de_carga.py
```

El proceso debe terminar mostrando:

```text
paises: 234
ediciones: 64
atletas: 244540
```

También consolida `693398` filas en `534950` participaciones únicas.

## Paso 11: ver las colecciones y documentos cargados

Entrar a MongoDB:

```powershell
docker exec -it proyecto_fase3 mongosh olimpiadas_fase3
```

Dentro de `mongosh`, ejecute:

```javascript
show dbs
use olimpiadas_fase3
show collections

db.paises.countDocuments()
db.ediciones.countDocuments()
db.atletas.countDocuments()

db.atletas.findOne({ nombre_usado: "Usain Bolt" })
db.paises.findOne({ _id: "GUA" })
db.atletas.getIndexes()
```

Resultados esperados:

- `paises`: 234
- `ediciones`: 64
- `atletas`: 244540

### Consultas MongoDB importantes para pruebas en vivo

Las siguientes consultas se pegan directamente dentro de `mongosh`. Antes de
ejecutarlas confirme que esta usando la base correcta:

```javascript
use olimpiadas_fase3
```

**1. Ver un atleta con sus datos personales y todo su historial:**

```javascript
db.atletas.findOne(
  { nombre_usado: "Usain Bolt" },
  { nombre_completo: 1, sexo: 1, fecha_nacimiento: 1, pais_origen_id: 1, clubes: 1, participaciones: 1 }
)
```

**2. Ver solamente las medallas de un atleta:**

```javascript
db.atletas.aggregate([
  { $match: { nombre_usado: "Usain Bolt" } },
  { $unwind: "$participaciones" },
  { $match: { "participaciones.medalla": { $in: ["Oro", "Plata", "Bronce"] } } },
  { $project: {
      _id: 0,
      anio: "$participaciones.edicion.anio",
      deporte: "$participaciones.deporte",
      evento: "$participaciones.evento",
      medalla: "$participaciones.medalla"
  } },
  { $sort: { anio: 1, evento: 1 } }
])
```

Para Usain Bolt deben aparecer `8` documentos, todos con medalla `Oro`.

**3. Buscar participaciones usando varios filtros:**

```javascript
db.atletas.aggregate([
  { $match: { participaciones: { $elemMatch: {
      pais_representado_id: "USA",
      "edicion.anio": 2016,
      deporte: "Gymnastics",
      medalla: "Oro"
  } } } },
  { $unwind: "$participaciones" },
  { $match: {
      "participaciones.pais_representado_id": "USA",
      "participaciones.edicion.anio": 2016,
      "participaciones.deporte": "Gymnastics",
      "participaciones.medalla": "Oro"
  } },
  { $project: {
      _id: 0,
      atleta: "$nombre_completo",
      evento: "$participaciones.evento",
      medalla: "$participaciones.medalla"
  } },
  { $sort: { atleta: 1, evento: 1 } },
  { $limit: 20 }
])
```

**4. Ver la informacion y el historial de poblacion de un pais:**

```javascript
db.paises.findOne({ _id: "GUA" })
```

**5. Consultar en que ediciones un pais fue sede:**

```javascript
db.ediciones.find(
  { pais_sede_id: "USA" },
  { _id: 0, anio: 1, temporada: 1, ciudad: 1, nombre_edicion: 1 }
).sort({ anio: 1 })
```

Para `USA` deben aparecer `8` ediciones sede.

**6. Obtener los anos en que participo Guatemala:**

```javascript
db.atletas.distinct(
  "participaciones.edicion.anio",
  { "participaciones.pais_representado_id": "GUA" }
).sort((a, b) => a - b)
```

**7. Resumen correcto de medallas de un pais:**

Esta consulta cuenta una medalla de equipo una sola vez, aunque el equipo tenga
varios integrantes. Cambie `GUA` por el codigo del pais que desee probar.

```javascript
db.atletas.aggregate([
  { $match: { "participaciones.pais_representado_id": "GUA" } },
  { $unwind: "$participaciones" },
  { $match: {
      "participaciones.pais_representado_id": "GUA",
      "participaciones.medalla": { $in: ["Oro", "Plata", "Bronce"] }
  } },
  { $group: {
      _id: {
        anio: "$participaciones.edicion.anio",
        medalla: "$participaciones.medalla",
        equipo: "$participaciones.equipo.equipo_id",
        individual: {
          $cond: [
            { $ifNull: ["$participaciones.equipo", false] },
            0,
            "$participaciones.participacion_id"
          ]
        }
      }
  } },
  { $group: { _id: "$_id.medalla", total: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])
```

Para Guatemala deben obtenerse `1 Oro`, `3 Platas` y `1 Bronce` en todo su
historial. Si se agrega el filtro
`"participaciones.edicion.anio": 2024` en ambos `$match`, el resultado debe ser
`1 Oro` y `1 Bronce`.

**8. Ver los diez atletas con mas registros de medalla:**

```javascript
db.atletas.aggregate([
  { $unwind: "$participaciones" },
  { $match: { "participaciones.medalla": { $in: ["Oro", "Plata", "Bronce"] } } },
  { $group: {
      _id: "$_id",
      atleta: { $first: "$nombre_completo" },
      total: { $sum: 1 },
      oros: { $sum: { $cond: [{ $eq: ["$participaciones.medalla", "Oro"] }, 1, 0] } },
      platas: { $sum: { $cond: [{ $eq: ["$participaciones.medalla", "Plata"] }, 1, 0] } },
      bronces: { $sum: { $cond: [{ $eq: ["$participaciones.medalla", "Bronce"] }, 1, 0] } }
  } },
  { $sort: { total: -1 } },
  { $limit: 10 }
])
```

**9. Validar conteos e integridad basica:**

```javascript
db.paises.countDocuments()                                      // 234
db.ediciones.countDocuments()                                   // 64
db.atletas.countDocuments()                                     // 244540
db.atletas.countDocuments({ participaciones: { $size: 0 } })    // 232

db.atletas.aggregate([
  { $project: { cantidad: { $size: "$participaciones" } } },
  { $group: { _id: null, total: { $sum: "$cantidad" } } }
])                                                              // total: 534950

db.atletas.countDocuments({
  participaciones: { $elemMatch: { pais_representado_id: null } }
})                                                              // 0
```

**10. Comprobar que una consulta utiliza un indice:**

```javascript
db.atletas.find({
  "participaciones.pais_representado_id": "JAM"
}).explain("executionStats")
```

En el plan debe aparecer `IXSCAN` y el indice `part_pais_1`; no debe aparecer
un recorrido completo `COLLSCAN` como etapa principal.

Para salir, escriba `exit`.

## Paso 12: ejecutar la verificación integral

```powershell
python fase3/src/verificar_fase3.py
```

El resultado correcto es:

```text
26 pruebas correctas, 0 fallidas
RESULTADO FINAL: APROBADO
```

Esta prueba comprueba conteos, validadores, índices, duplicados, referencias, resultados conocidos, consultas por país/atleta y planes `IXSCAN`.

## Paso 13: probar los scripts solicitados por el enunciado

Consulta de atleta:

```powershell
python fase3/src/script_de_consultas.py atleta "Usain Bolt"
python fase3/src/script_de_consultas.py atleta "Usain Bolt" --anio 2012 --medalla oro
python fase3/src/script_de_consultas.py atleta "Simone Biles" --pais USA --anio 2016
```

Consulta de país:

```powershell
python fase3/src/script_de_consultas.py pais Guatemala --anio 2024
python fase3/src/script_de_consultas.py pais JAM
python fase3/src/script_de_consultas.py pais USA --deporte Swimming --medalla oro
```

Agregue `--json` a cualquiera para recibir JSON y `--detalle` a la consulta de país para listar cada medalla.

## Paso 14: conectarse desde DBeaver o Compass

La siguiente cadena es una URI de MongoDB, no una página web:

```text
mongodb://localhost:27017/olimpiadas_fase3
```

No la pegue en Chrome o Edge porque el navegador la convertirá en una búsqueda de Google.

### DBeaver

MongoDB requiere DBeaver Lite, Enterprise o Ultimate; Community no incluye este controlador. Cree una conexión MongoDB con:

- Host: `localhost`
- Port: `27017`
- Database: `olimpiadas_fase3`
- Authentication: `None`
- Usuario y contraseña: vacíos

También puede seleccionar conexión por URL y pegar la URI anterior. Pulse **Test Connection** y luego expanda `olimpiadas_fase3 → Collections`.

### MongoDB Compass

Seleccione **New Connection** y pegue:

```text
mongodb://localhost:27017/olimpiadas_fase3
```

### Comprobar únicamente el puerto

```powershell
Test-NetConnection localhost -Port 27017
```

`TcpTestSucceeded` debe ser `True`.

## Ejecución automática opcional

Después de comprender los pasos anteriores, todo el flujo puede repetirse con un único comando desde `fase3`:

```powershell
cd fase3
bash src/exportar_fase1.sh
```

Este comando ejecuta el mismo `down`, reconstrucción, exportación, migración y verificación, dejando evidencia en `fase3/logs/`.
