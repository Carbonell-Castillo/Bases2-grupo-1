# Informe Técnico

Integrantes del grupo

| Carnet    | Nombre                             | Rol                                    |
| --------- | ---------------------------------- | -------------------------------------- |
| 202203069 | Bruce Carbonell Castillo Cifuentes | coordinador                            |
| 202209714 | Angel Enrique Alvarado Ruiz        | el que hace lo que dice el coordinador |

## 1. Fuentes de datos y mapeo hacia el modelo

| Fuente                                                        | Archivo extraído     | Contenido principal                                                                      | Entidades que alimenta                                        |
| ------------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Olympics Dataset by KeithGalli                                | bios.csv             | Datos biográficos del atleta (nombre, nacimiento, medidas y afiliaciones)                | atleta, club, atleta_club y pais                              |
| Olympics Dataset by KeithGalli                                | results.csv          | Resultado por evento/atleta (posición, medalla, disciplina)                              | participacion, evento, deporte, edicion, equipo               |
| Olympics Dataset by KeithGalli                                | population.csv       | Valores de la población en base al país (NOC) y año                                      | poblacion                                                     |
| Olympics Dataset by KeithGalli                                | noc_regions.csv      | id de los paises (NOC), su nombre y región                                               | pais                                                          |
| 120 years of olympic history athletes and results by heesoo37 | athlete_events.csv   | Un renglón por atleta-evento con edad/altura/peso, equipo, año, ciudad, deporte, medalla | atleta, participacion, evento, edicion, deporte, equipo, pais |
| Summer Olympics Medals (1896-2024) by stefanydeoliveira       | olympics_dataset.csv | Registro histórico de Verano 1896–2024, deporte/evento/medalla                           | participacion, evento, deporte, edicion                       |
| datasets olympics by datacamp                                 | datalab_export.csv   | Dataset "Olympics" de R (ciudad, año, deporte, atleta, país, género, evento, medalla)    | participacion, evento, deporte, edicion, atleta               |

**Nota sobre bios.csv y results.csv:** según el propio repositorio de KeithGalli, ambos
archivos provienen de [olympedia.org](https://www.olympedia.org/) y se relacionan
entre sí por `athlete_id`. Esa llave es la que se preserva como `atleta_id` (litearlmente
lo pasamos a español) en el modelo unificado (con reasignación de IDs al momento de la carga,
ya que cada fuente trae su propio identificador).

Como las cuatro fuentes describen el mismo dominio con columnas distintas
(`Sport` vs. `Discipline`, `Team` vs. `NOC`, `Pos` vs. `Rank`, etc.).

## 2. Entidades

### 2.1 pais

Representa un Comité Olímpico Nacional (NOC) o país participante (una sede).

| Atributo    | Tipo         | Descripción            | Llave |
| ----------- | ------------ | ---------------------- | ----- |
| pais_id     | varchar(3)   | Código NOC             | PK    |
| nombre_pais | varchar(100) | Nombre del NOC         | -     |
| region      | varchar(100) | Agrupación continental | -     |

### 2.2 poblacion

Represnta a la cantidad de personas que habitan el pais durante la edición y evento en base a un anio y un pais.

| Atributo  | Tipo       | Descripción                                    | Llave |
| --------- | ---------- | ---------------------------------------------- | ----- |
| pais_id   | varchar(3) | identificador pais (NOC)                       | PK    |
| anio      | int        | nombre del club/affiliations                   | PK    |
| poblacion | int        | total de habitantes de un pais en base al anio | -     |

### 2.3 atleta

Un deportista individual, con sus datos biográficos.

| Atributo            | Tipo         | Descripción                                          | Llave |
| ------------------- | ------------ | ---------------------------------------------------- | ----- |
| atleta_id           | int          | Identificador interno del atleta                     | PK    |
| nombre_completo     | varchar(255) | Nombre completo (bios.csv: Full name)                | -     |
| nombre_usado        | varchar(255) | Nombre con el que se le conoce (bios.csv: Used name) | -     |
| sexo                | varchar(1)   | M / F                                                | -     |
| fecha_nacimiento    | date         | fecha                                                | -     |
| lugar_nacimiento    | varchar(255) | dirección de nacimiento                              | -     |
| fecha_fallecimiento | date         | Nulo si aplica                                       | -     |
| lugar_fallecimiento | varchar(255) | Nulo si aplica                                       | -     |
| estatura_cm         | int          | De Measurements en bios.csv                          | -     |
| peso_kg             | int          | De Measurements en bios.csv                          | -     |
| pais_id             | varchar(3)   | Nacionalidad principal declarada                     | FK    |

### 2.4 edicion

Una edición específica de los Juegos Olímpicos.

| Atributo       | Tipo         | Descripción              | Llave |
| -------------- | ------------ | ------------------------ | ----- |
| edicion_id     | int          | identificador            | PK    |
| nombre_edicion | varchar(100) | Ej. 1924 Summer Olympics | -     |
| anio           | int          | Año de celebración       | -     |
| temporada      | varchar(10)  | Verano / Invierno        | -     |
| ciudad         | varchar(100) | Ciudad sede              | -     |
| pais_sede_id   | varchar(3)   | País sede de esa edición | FK    |

### 2.5 deporte

Catálogo de deportes/disciplinas (unifica `Sport` y `Discipline` de las fuentes).

| Atributo       | Tipo         | Descripción                    | Llave |
| -------------- | ------------ | ------------------------------ | ----- |
| deporte_id     | int          | identificador                  | PK    |
| nombre_deporte | varchar(100) | Nombre normalizado del deporte | -     |

### 2.6 evento

Una prueba específica dentro de un deporte, en una edición determinada, por ejemplo: "Singles, Men" de Tenis en 1924.

| Atributo      | Tipo         | Descripción                | Llave |
| ------------- | ------------ | -------------------------- | ----- |
| evento_id     | int          | Identificador del evento   | PK    |
| edicion_id    | int          | Edición a la que pertenece | FK    |
| deporte_id    | int          | Deporte al que pertenece   | FK    |
| nombre_evento | varchar(255) | Nombre de la prueba/evento | -     |

### 2.7 equipo

Agrupa a los atletas que compitieron como escuadra/selección/dupla en un
evento puntual (relevos, dobles, deportes de equipo). Permite modelar
resultados grupales sin duplicar el resultado por cada atleta.

| Atributo      | Tipo         | Descripción                                                  | Llave |
| ------------- | ------------ | ------------------------------------------------------------ | ----- |
| equipo_id     | int          | identificador del equipo                                     | PK    |
| evento_id     | int          | Evento en el que compitió ese equipo                         | FK    |
| pais_id       | varchar(3)   | País/selección que representa (nulo si es equipo mixto/club) | FK    |
| nombre_equipo | varchar(150) | Nombre del equipo tal como aparece en la fuente              | -     |

### 2.8 club

Club o institución a la que estuvo afiliado un atleta (bios.csv: `Affiliations`).

| Atributo    | Tipo         | Descripción                        | Llave |
| ----------- | ------------ | ---------------------------------- | ----- |
| club_id     | int          | identificador del club/affliations | PK    |
| nombre_club | varchar(255) | nombre del club/affiliations       | -     |
| pais_id     | varchar(3)   | País del club, si se conoce        | FK    |

### 2.9 atleta_club

Tabla puente ya que un atleta puede haber pertenecido a varios clubes a lo largo
de su carrera, y un club tiene varios atletas afiliados.

| Atributo  | Tipo | Descripción                         | Llave     |
| --------- | ---- | ----------------------------------- | --------- |
| atleta_id | int  | identificador de atleta             | Compuesta |
| club_id   | int  | identificador del club/affiliations | Compuesta |

### 2.10 participacion

Cada renglón es la participación de un atleta en un evento (equivalente a un
renglón de `results.csv` o `athlete_events.csv`).

| Atributo              | Tipo         | Descripción                                                 | Llave     |
| --------------------- | ------------ | ----------------------------------------------------------- | --------- |
| participacion_id      | int          | identificador                                               | PK        |
| atleta_id             | int          | Atleta que participó                                        | FK        |
| evento_id             | int          | Evento en el que participó                                  | FK        |
| equipo_id             | int          | Equipo/escuadra, si aplica                                  | FK o nulo |
| pais_representado_id  | varchar(3)   | NOC bajo el cual compitió en esa participación              | FK        |
| nombre_en_competencia | varchar(255) | Nombre bajo el que compitió (results.csv: As)               | -         |
| posicion              | varchar(20)  | Posición final, admite valores no numéricos (=17, DNS, DNF) | -         |
| medalla               | varchar(10)  | Oro / Plata / Bronce / nulo si no hubo medalla              | -         |

**Nota:** en `pais_representado_id` puede diferir de `atleta.pais_id` si cambió de nacionalidad deportiva, por eso se hace énfasis sobre a participación.

## 3. Relaciones y cardinalidad

| Entidad A | Entidad B     | Cardinalidad | Descripción                                                                                                                 |
| --------- | ------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| pais      | atleta        | 1:N          | Un país es la nacionalidad de muchos atletas, un atleta tiene un país de nacionalidad principal                             |
| pais      | edicion       | 1:N          | Un país puede haber sido sede de varias ediciones, una edición tiene un único país sede                                     |
| pais      | poblacion     | 1:N          | la población de un país depende del país y del año en específico.                                                           |
| pais      | equipo        | 1:N          | Un país puede tener muchos equipos (uno por evento en el que compitió), un equipo representa a un solo país                 |
| pais      | club          | 1:N          | Un país puede tener muchos clubes registrados, un club pertenece a un país                                                  |
| pais      | participacion | 1:N          | Un país es representado en muchas participaciones, cada participación se hace bajo un solo país                             |
| edicion   | evento        | 1:N          | Una edición agrupa muchos eventos, un evento pertenece a una sola edición                                                   |
| deporte   | evento        | 1:N          | Un deporte agrupa muchos eventos, un evento pertenece a un solo deporte                                                     |
| evento    | equipo        | 1:N          | Un evento puede tener varios equipos inscritos, un equipo compite en un solo evento                                         |
| evento    | participacion | 1:N          | Un evento tiene muchas participaciones (una por atleta), una participación ocurre en un solo evento                         |
| equipo    | participacion | 1:N          | Un equipo agrupa las participaciones de varios atletas, una participación pertenece a lo sumo a un equipo (individual nulo) |
| atleta    | participacion | 1:N          | Un atleta tiene muchas participaciones a lo largo de su carrera, una participación corresponde a un solo atleta             |
| atleta    | club          | N:M          | Un atleta puede pertenecer a varios clubes, un club tiene varios atletas afiliados                                          |

## 4. Diagrama ER

El siguiente es el código utilizado para modelar la base de datos en [dbdiagram](https://dbdiagram.io/)

```
Table pais {
  pais_id varchar(3) [pk]
  nombre_pais varchar(100) [not null]
  region varchar(100)
}

Table poblacion {
  pais_id varchar(3) [ref: > pais.pais_id]
  anio int
  poblacion bigint

  indexes {
    (pais_id, anio) [pk]
  }
}

Table atleta {
  atleta_id int [pk, increment]
  nombre_completo varchar(255) [not null]
  nombre_usado varchar(255)
  sexo varchar(1)
  fecha_nacimiento date
  lugar_nacimiento varchar(255)
  fecha_fallecimiento date
  lugar_fallecimiento varchar(255)
  estatura_cm int
  peso_kg int
  pais_id varchar(3) [ref: > pais.pais_id]
}

Table edicion {
  edicion_id int [pk, increment]
  nombre_edicion varchar(100) [not null]
  anio int [not null]
  temporada varchar(10) [not null]
  ciudad varchar(100)
  pais_sede_id varchar(3) [ref: > pais.pais_id]
}

Table deporte {
  deporte_id int [pk, increment]
  nombre_deporte varchar(100) [not null, unique]
}

Table evento {
  evento_id int [pk, increment]
  edicion_id int [not null, ref: > edicion.edicion_id]
  deporte_id int [not null, ref: > deporte.deporte_id]
  nombre_evento varchar(255) [not null]
}

Table equipo {
  equipo_id int [pk, increment]
  evento_id int [not null, ref: > evento.evento_id]
  pais_id varchar(3) [ref: > pais.pais_id]
  nombre_equipo varchar(150)
}

Table club {
  club_id int [pk, increment]
  nombre_club varchar(255) [not null]
  pais_id varchar(3) [ref: > pais.pais_id]
}

Table atleta_club {
  atleta_id int [ref: > atleta.atleta_id]
  club_id int [ref: > club.club_id]

  indexes {
    (atleta_id, club_id) [pk]
  }
}

Table participacion {
  participacion_id int [pk, increment]
  atleta_id int [not null, ref: > atleta.atleta_id]
  evento_id int [not null, ref: > evento.evento_id]
  equipo_id int [ref: > equipo.equipo_id]
  pais_representado_id varchar(3) [ref: > pais.pais_id]
  nombre_en_competencia varchar(255)
  posicion varchar(20)
  medalla varchar(10)
}
```

![Diagrama ER](./img/ER.png)

**Nota:** El sitio web permite exportar hacia: PostgresSQL, MySQL, Oracle o SQL server. Por fines prácticos fue exportado a PostgresSQL.

## 5. Decisiones de diseño y supuestos

- **`deporte` unifica `Sport` y `Discipline`.** Las fuentes usan ambos términos
  de forma inconsistente; se normalizan a un único catálogo durante el ETL.
- **`equipo` es opcional.** En eventos individuales, `participacion.equipo_id`
  queda nulo; solo se usa en relevos, dobles y deportes de equipo, evitando así
  una tabla `equipo` vacía o forzada para la mayoría de los registros.
- **`pais_representado_id` vs. `atleta.pais_id`.** Se separan porque un atleta
  puede competir por más de un país a lo largo de su carrera (cambios de
  nacionalidad deportiva); `atleta.pais_id` guarda la nacionalidad de
  referencia y `participacion.pais_representado_id` la usada en cada
  participación puntual, esto también resuelve el requerimiento e) de listar
  participaciones por país.
- **`posicion` como texto, no numérico.** Los datasets incluyen valores no
  numéricos como `DNS`, `DNF`, `=17`, por lo que se modela como `varchar`.
- **`club`/`atleta_club` es una extensión opcional** alimentada solo por
  `bios.csv` (columna `Affiliations`, que trae varias afiliaciones separadas
  por `/`).

## 6. Carga de datos (ETL)

El script [`etl/build_load.py`](../etl/build_load.py) lee las 7 fuentes de la sección 1,
resuelve el mapeo de columnas repetidas entre fuentes (`Sport`/`Discipline`/`sport`,
`Team`/`NOC`/`noc`, `Pos`, etc.) y genera un CSV por tabla en `etl-csvs/`
(archivos auxiliares versionados en el repositorio; se regeneran con el script
si hace falta). `etl/load.sql` carga
esos CSVs a PostgreSQL respetando el orden de llaves foráneas y sincroniza
las secuencias de los `IDENTITY` para que los próximos `INSERT` (p. ej. desde
los stored procedures) no choquen con los ids ya cargados.

Para levantar todo en Docker:

```bash
python3 etl/build_load.py   # genera etl-csvs/*.csv
bash etl/run_load.sh        # levanta docker-compose (postgres:16), aplica src/schema.sql y carga los CSVs
```

### 6.1 Regla de deduplicación de atletas

Un atleta se identifica por su nombre. Al procesar un nuevo renglón:

- Si ya existe un atleta con ese nombre y **ningún** atributo comparable
  (sexo, país) difiere del nuevo registro, es el mismo atleta: se reutiliza
  su `atleta_id` y se completan los campos que le faltaban (fecha de
  nacimiento, medidas, etc.) con los datos de la fuente nueva.
- Si algún atributo comparable varía, aunque sea solo el país de origen,
  no es el mismo atleta: se crea un registro nuevo con el mismo nombre
  (homónimo legítimo).
- Los nombres se comparan sin distinguir mayúsculas/minúsculas ni
  acentos/diacríticos (p. ej. "Cenk İldem" y "Cenk Ildem", transliterado en
  una de las fuentes, resuelven al mismo `atleta_id`).

`bios.csv` y `results.csv` comparten `athlete_id` (ambos vienen de
olympedia.org), así que para `results.csv` no se vuelve a resolver
identidad: sus participaciones se enlazan directamente al `atleta_id` ya
creado a partir de `bios.csv`.

Con esta regla, sobre las ~950 mil filas de las 7 fuentes se obtuvieron
**242,021 atletas** (0 duplicados exactos por nombre+sexo+país, verificado
en la base ya cargada) y **693,327 participaciones**, también deduplicadas
por la llave natural (atleta, evento, país representado): si la misma
participación aparece en más de una fuente, se conserva un solo renglón y
se completan `posición`/`medalla` con lo que aporte cada fuente.

### 6.2 Supuestos adicionales de la carga

- **`equipo` se deriva después de la carga base.** La carga inicial deja
  `participacion.equipo_id` nulo; posteriormente
  `etl/derivar_equipos.sql` detecta eventos colectivos y enlaza las
  participaciones cuando existen al menos dos atletas del mismo país en el
  evento. La heurística y sus validaciones se explican en la sección 8.
- **Sede de la edición (`edicion.pais_sede_id`)** se resuelve con un
  diccionario ciudad-país de las sedes olímpicas conocidas; ediciones que
  solo llegan por `results.csv` (sin ciudad) usan un diccionario equivalente
  por nombre de edición. Juegos Olímpicos de la Juventud, Intercalados, etc.
  quedan sin sede si no están en ese diccionario.
- **`poblacion`** mapea el código ISO-3166 de `populations.csv` al código
  NOC/IOC del catálogo de `pais` (difieren en ~20 países, por ejemplo `DEU`-`GER`,
  `CHE`-`SUI`); los códigos que son agregados regionales del Banco Mundial
  (`AFE`, `ARB`, `OED`, etc.) no tienen país real y se descartan (127 de los
  ~267 códigos de la fuente).
- **Nacionalidad en `bios.csv`.** La columna `NOC` de esa fuente trae texto
  libre (a veces varios países concatenados) y no un código; se usa en su
  lugar el código entre paréntesis al final de `Born` (p. ej. "... (FRA)").

## 7. Stored procedures

El archivo [`src/stored_procedures.sql`](./src/stored_procedures.sql) crea
dos procedimientos. Cada uno deja el resultado detallado en una tabla
temporal para consultarlo desde `psql` y muestra por `NOTICE` cuántas filas
produjo.

### 7.1. `sp_info_atleta`

Recibe el nombre completo o una parte del nombre del atleta y deja su
información biográfica, edición, deporte, evento, país representado,
posición, medalla y equipo en `resultado_sp_info_atleta`.

Filtros opcionales:

- `p_deporte`: nombre o parte del deporte.
- `p_pais`: código NOC o nombre del país representado.
- `p_anio`: año de la edición.

### 7.2. `sp_info_pais`

Recibe un código NOC o una parte del nombre del país y deja en
`resultado_sp_info_pais` la población más reciente, sus ediciones como
sede y sus participaciones con atleta, deporte, evento, posición, medalla
y equipo.

Filtros opcionales:

- `p_anio`: año de la edición.
- `p_deporte`: nombre o parte del deporte.
- `p_medalla`: medalla exacta, por ejemplo `Oro`.

Las consultas completas para probar ambos procedimientos están en
[`ejemplos.md`](./ejemplos.md).

## 8. Derivación y verificación de equipos

El archivo [`etl/derivar_equipos.sql`](./etl/derivar_equipos.sql) se ejecuta
automáticamente desde [`etl/run_load.sh`](./etl/run_load.sh), después de
[`etl/load.sql`](./etl/load.sql) y antes de
[`src/stored_procedures.sql`](./src/stored_procedures.sql).

La detección considera deportes inherentemente colectivos (fútbol,
baloncesto, voleibol, hockey, rugby, béisbol, entre otros) y eventos cuyo
nombre contiene términos como `relay`, `relevo`, `double`, `pair`, `team` o
`4x`. Dentro de esos eventos se agrupan las participaciones por
`(evento_id, pais_representado_id)`. Solo se crea un equipo cuando el grupo
tiene al menos dos atletas.

El script es idempotente: desvincula las participaciones existentes,
elimina los equipos derivados con `DELETE` para conservar la FK sin borrar
participaciones, vuelve a insertar los equipos y enlaza nuevamente sus
participaciones. Las consultas de [`ejemplos.md`](./ejemplos.md) verifican
la cantidad de equipos y que no existan referencias huérfanas.

## 9. Evidencia de ejecución

Capturas con fecha de una corrida completa del pipeline (esquema, carga,
derivación de equipos y los dos stored procedures) en
[`docs/evidencia.md`](./docs/evidencia.md).
