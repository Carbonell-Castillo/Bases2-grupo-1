# Informe Técnico y Manual de Decisiones - Fase 3

## 1. Introducción
Este documento detalla la arquitectura, el modelado de datos y las decisiones técnicas tomadas para la migración de la base de datos de los Juegos Olímpicos desde un modelo relacional con PostgreSQL a un modelo NoSQL con MongoDB. El objetivo es optimizar el rendimiento de lectura y aprovechar las características de almacenamiento orientado a documentos.

## 2. Arquitectura de Migración y Flujo de Datos
**Decisión:** Se reutiliza el ETL de la Fase 1, pero en modo Fase 3 se regeneran los CSV en `fase3/src/output_fase1_corregido/` con las correcciones detectadas. PostgreSQL realiza la derivación de equipos y validación relacional; después se exportan sus diez tablas finales a CSV para construir los documentos de MongoDB. Los CSV entregados originalmente en Fase 1 no se sobrescriben.

**Justificación:**
1. **Preservación de la integridad ETL:** La formación de equipos (`derivar_equipos.sql`) ya está centralizada en Fase 1; reutilizarla evita dos implementaciones divergentes.
2. **Correcciones reproducibles:** El modo `--fase3-output` de `build_load.py` corrige códigos y colisiones de identidad antes de entrar a PostgreSQL, sin editar manualmente archivos generados.
3. **Fuente de verdad auditable:** MongoDB recibe exactamente lo que PostgreSQL validó y exportó en la misma corrida.

Flujo: fuentes de `Fase1/datasets/` → `build_load.py --fase3-output` → PostgreSQL (`run_load.sh`) → 10 CSV (`src/output_postgres/`) → `crear_colecciones_indices.js` → `script_de_carga.py` → `verificar_fase3.py` → MongoDB validado.

## 3. Modelo de Datos NoSQL: de 10 tablas a 3 colecciones
En el modelo relacional se utilizaron 10 tablas (`pais`, `poblacion`, `atleta`, `edicion`, `deporte`, `evento`, `equipo`, `club`, `atleta_club`, `participacion`) para evitar redundancia. En MongoDB las tablas se agruparon con un criterio: **se anida lo que siempre se consulta junto con su dueño y se mantiene separado lo que es un catálogo compartido o se consulta de forma independiente.** Quedaron **3 colecciones**.

| Tabla(s) relacional(es) | Destino en MongoDB | Cómo se relaciona |
|---|---|---|
| `pais` + `poblacion` | colección `paises` (población como arreglo `historico_poblacion`) | 1 a N con tope bajo (≈ 64 registros por país) |
| `edicion` | colección `ediciones` | referenciada por `pais_sede_id`; un resumen de la edición se copia dentro de cada participación |
| `atleta` + `atleta_club` + `club` + `participacion` + `evento` + `deporte` + `equipo` | colección `atletas` (`clubes[]` y `participaciones[]` embebidos; deporte, evento y equipo viajan dentro de cada participación) | 1 a N: cada atleta contiene todo su historial |

### Colección: `paises`
* **Estructura:** `_id` (código NOC), `nombre_pais`, `nombre_busqueda` (sin acentos, minúsculas), `region` y arreglo `historico_poblacion` (`{anio, poblacion}`).
* **Por qué se unió con `poblacion`:** la población pertenece a un solo país, está acotada (un valor por año) y siempre se lee junto al país. Anidarla elimina un `$lookup` y una colección extra.

### Colección: `ediciones`
* **Estructura:** `_id`, `nombre_edicion`, `anio`, `temporada`, `ciudad`, `pais_sede_id`.
* **Por qué sigue separada:** es un catálogo pequeño (64 documentos) y es la fuente de "¿qué países han sido sede?". Esa pregunta se responde con un índice sobre `pais_sede_id` sin recorrer a los atletas. Dentro de cada participación solo se copian los campos livianos de la edición (`edicion_id`, `anio`, `temporada`, `nombre_edicion`); duplicar la ciudad/sede en 534,950 participaciones no aporta valor.

### Colección: `atletas` (la colección principal)
* **Estructura:** biografía del atleta, `clubes[]` y `participaciones[]`. Cada participación incluye edición, deporte, evento, país representado, posición, medalla y `equipo` (`{equipo_id, nombre_equipo}` o `null`).
* **Por qué embeber las participaciones:** el caso de uso principal (inciso c) es "dame todo sobre este atleta". En PostgreSQL esto exigía JOIN entre `atleta`, `participacion`, `evento`, `edicion`, `deporte` y `equipo`; en MongoDB es la lectura de un documento por índice. El arreglo está acotado (decenas de eventos por atleta como máximo) y los 244,540 documentos quedan muy por debajo del límite de 16 MB por documento.
* **Por qué `deporte`, `evento` y `equipo` no son colecciones:** solo tienen sentido dentro de una participación (un evento pertenece a una edición y a un deporte; un equipo es un grupo de participaciones de un mismo país en un mismo evento). Como valores embebidos evitan 3 joins y no se consultan por separado. El inciso d (países) se resuelve con un `aggregate` sobre `participaciones.pais_representado_id`, apoyado en un índice multikey.
* **Por qué no se creó una cuarta colección `participaciones`:** habría reproducido el JOIN relacional (534,950 documentos con `$lookup` hacia atletas) y habría vuelto lenta la consulta más frecuente. El costo asumido es que las consultas globales por país requieren `$unwind`; se compensa con un índice multikey y con un `$match` previo.
* **Trade-off aceptado:** los datos de catálogo (nombre de deporte, edición) se repiten en cada participación, pero son históricos e inmutables.

### Correcciones aplicadas durante la carga (requisito: "corregir fallos previos")
1. **IDs locales reutilizados.** `olympics_dataset.csv` reutiliza 12,883 identificadores para nombres distintos. El ETL antiguo podía asignar una participación moderna al atleta histórico que compartía el número. En modo Fase 3 la identidad local es `(ID de fuente, nombre normalizado)`. Esto recuperó 2,519 atletas que antes estaban mezclados y dejó **244,540 atletas** correctamente separados; el caso Hala Fattouh se verifica automáticamente.
2. **Código de Líbano.** Olympedia usa `LBN`, pero el catálogo consolidado usa `LIB`. El alias se aplica antes de PostgreSQL; las 534,950 participaciones finales tienen país representado y no existen referencias huérfanas.
3. **Participaciones duplicadas entre fuentes.** `script_de_carga.py` calcula una clave canónica de evento y unifica por *(atleta, edición, evento)*, conservando posición y completando medalla/equipo. Se unificaron **158,448 duplicados (693,398 → 534,950 participaciones)**; Usain Bolt queda con 8 oros, no 16.
4. **Equipos duplicados.** Los IDs equivalentes se unifican con *union-find* y `nombre_equipo` usa el país representado.
5. **Medallas de equipo.** La consulta de país cuenta una medalla por equipo/evento, no una por integrante.
6. **Sedes faltantes.** Se completaron Pyeongchang 2018 y Beijing 2022.
7. **Búsqueda tolerante.** `nombre_busqueda` guarda minúsculas sin acentos y está indexado en atletas y países.

### Índices (ver `src/crear_colecciones_indices.js`)
| Colección | Índice | Para qué |
|---|---|---|
| `atletas` | `nombre_completo`, `nombre_usado`, `nombre_busqueda` | búsqueda por nombre (exacta y por prefijo) |
| `atletas` | `participaciones.pais_representado_id` | consulta de país (multikey) |
| `atletas` | `participaciones.edicion.anio`, `participaciones.deporte`, `participaciones.medalla` | filtros opcionales |
| `atletas` | `pais_origen_id` | atletas por país de origen |
| `paises` | `nombre_pais`, `nombre_busqueda` | búsqueda por nombre |
| `ediciones` | `pais_sede_id`, `(anio, temporada)` | países sede y orden cronológico |

El verificador confirma mediante `explain` que la búsqueda exacta de atleta usa `IXSCAN` y que la búsqueda por país usa el índice multikey `part_pais_1`. El tiempo total del comando incluye el arranque de Python, por lo que debe distinguirse del tiempo interno de MongoDB.

## 4. Infraestructura Docker
**Decisión:** Se implementó MongoDB en Docker **sin volúmenes persistentes** para que la ejecución esté automatizada.
**Justificación:** Dado que el script `exportar_fase1.sh` está diseñado para recrear todo el entorno desde cero (elimina contenedores previos para evitar conflictos de nombre), exportar y cargar los datos de forma automatizada en segundos, la persistencia de datos local genera conflictos si la estructura cambia. En un entorno de producción se agregarían volúmenes, pero para la evaluación del proyecto esto garantiza que la base de datos siempre arranque limpia y se cargue con el estado más reciente del script.

La ejecución comienza con `docker compose down -v --remove-orphans` para PostgreSQL y `docker compose down --remove-orphans` para MongoDB. Por tanto, la prueba no reutiliza datos de una corrida anterior. Con `PAUSA_ENTRE_PASOS=1`, el mismo orquestador se detiene después de borrar, cargar PostgreSQL, exportar los CSV y crear MongoDB para permitir comprobaciones manuales.

## 5. Scripts y entregables
| Archivo | Función |
|---|---|
| `src/exportar_fase1.sh` | Orquesta todo: Fase 1 → CSV → Mongo → índices → carga (con fecha/hora en cada paso) |
| `src/exportar_tablas_postgres.sh` | Paso manual: exporta y valida las diez tablas de PostgreSQL sin ejecutar las demás etapas |
| `src/crear_colecciones_indices.js` | Script de BD: colecciones, validadores `$jsonSchema` e índices |
| `src/script_de_carga.py` | Script de carga: lee `src/output_postgres/*.csv`, corrige/unifica y carga. Escribe `logs/carga_*.log` |
| `src/script_de_consultas.py` | Inciso c (`atleta`) e inciso d (`pais`), con filtros opcionales y salida texto/JSON |
| `src/verificar_fase3.py` | 26 pruebas automáticas de conexión, estructura, integridad, resultados, CLI e índices; termina con código distinto de cero si algo falla |
| `docker-compose.yml` | MongoDB 6.0 en `localhost:27017` sin autenticación |
| `docs/guia_de_ejemplo.md` | Guía desde cero, conexión con Compass/mongosh y consultas MongoDB para pruebas en vivo |
| `docs/ejemplos_y_validaciones.md` | Consultas de ejemplo y validaciones |
| `logs/` | Bitácoras con fecha y hora de las ejecuciones |

**Archivos fuente:** los datos originales están en `Fase1/datasets/` y `Fase1/etl-csvs/`; los CSV que consume Mongo (`src/output_postgres/`) se regeneran con `exportar_fase1.sh` desde PostgreSQL (están en `.gitignore`).

**Cumplimiento del enunciado de la Fase 3:** (a) carga completa en MongoDB y corrección de IDs/NOC previos; (b) scripts de colecciones, validadores, índices, carga, prueba y bitácoras fechadas; (c) `script_de_consultas.py atleta` con datos personales, participaciones, resultados, medallas y filtros; (d) `script_de_consultas.py pais` con población, sedes, años, resultados, historial de medallas y filtros; rendimiento respaldado por índices comprobados con `explain`.

## 6. Bitácora de ejecución (fecha y hora)
Corrida limpia de `bash src/exportar_fase1.sh` el **2026-10-23** (hora local de Guatemala, UTC-6). Log completo: `logs/ejecucion_pipeline_completa.log`; pruebas: `logs/verificacion_fase3.log`.

| Hora | Proceso |
|---|---|
| 21:54:47–21:54:50 | Paso 0: `compose down`; PostgreSQL, MongoDB, redes y volumen anterior eliminados |
| 21:54:50 | Paso 1: regeneración corregida (244,540 atletas; 693,398 participaciones) y arranque limpio de PostgreSQL |
| 21:56:02 | Prueba de las 10 tablas PostgreSQL; todos los conteos correctos |
| 21:56:03–21:56:19 | Paso 2: exportación y validación de 10/10 CSV no vacíos |
| 21:56:19–21:56:23 | Paso 3: creación de MongoDB, 3 colecciones, validadores e índices |
| 21:56:23 | Inicio de carga; 234 países y 64 ediciones insertados |
| 21:56:32 | 693,398 filas → 534,950 participaciones únicas (158,448 unificadas) |
| 21:56:53 | 244,540 atletas insertados; carga finalizada en 29.2 s |
| 21:56:55–21:57:04 | Verificación integral: **26 correctas, 0 fallidas; APROBADO** |

Resultados de referencia comprobados: Usain Bolt 8 oros; Michael Phelps 23/3/2; Simone Biles 2016, 4 oros + 1 bronce; Jamaica 37/48/36; Guatemala 2024, 1 oro + 1 bronce; Estados Unidos fue sede en 8 ediciones.

Ejecuciones anteriores de desarrollo (también en `logs/`): `carga_20261023_211220.log` y `carga_20261023_211331.log`.

## 7. Limitaciones conocidas
* Hay 232 atletas biográficos sin participación en los archivos de resultados; se conservan porque son registros válidos de la fuente. No hay participaciones finales sin país representado.
* La detección de eventos de equipo (`derivar_equipos.sql`) usa expresiones regulares; un evento por equipos que no coincida se cuenta por integrante.
* Se incluyen también los Juegos Olímpicos de la Juventud y otras ediciones no oficiales presentes en las fuentes; no tienen país sede asignado.
* La columna `region` de `pais` viene vacía desde la Fase 1 (el archivo `noc_regions.csv` usa `region` como nombre del país).
