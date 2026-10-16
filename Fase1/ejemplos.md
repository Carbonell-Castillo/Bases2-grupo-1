# Ejemplos de consultas y verificación

Estas consultas se ejecutan dentro de la consola que abre `etl/run_load.sh`.
Si se cerró, se puede volver a entrar con:

```bash
docker exec -it proyecto-bases-db psql -U postgres -d olimpiadas
```

Los ejemplos usan valores presentes en los CSV generados:

- Atleta: `Usain St. Leo Bolt` (`atleta_id = 103192`).
- País representado: `JAM`.
- Deporte: `Athletics`.
- Años disponibles para ese atleta: `2004`, `2008`, `2012` y `2016`.
- Medallas almacenadas: `Oro`, `Plata` y `Bronce`.

`etl-csvs/equipo.csv` se genera vacío porque los equipos se detectan después
de cargar las participaciones. Los equipos finales se encuentran en la tabla
`equipo`, después de ejecutar `etl/derivar_equipos.sql`.

## 1. Verificar que existen equipos

La primera consulta muestra cuántos equipos fueron creados por el proceso de
derivación.

```sql
SELECT count(*) AS equipos_creados
FROM equipo;
```

La segunda consulta lista los equipos con más atletas enlazados y muestra el
evento, deporte, país y año al que pertenecen.

```sql
SELECT
    e.equipo_id,
    e.nombre_equipo,
    e.pais_id,
    p.nombre_pais,
    ev.anio,
    d.nombre_deporte,
    evn.nombre_evento,
    count(pa.participacion_id) AS atletas_enlazados
FROM equipo e
JOIN pais p ON p.pais_id = e.pais_id
JOIN evento evn ON evn.evento_id = e.evento_id
JOIN edicion ev ON ev.edicion_id = evn.edicion_id
JOIN deporte d ON d.deporte_id = evn.deporte_id
LEFT JOIN participacion pa ON pa.equipo_id = e.equipo_id
GROUP BY e.equipo_id, e.nombre_equipo, e.pais_id, p.nombre_pais,
         ev.anio, d.nombre_deporte, evn.nombre_evento
ORDER BY atletas_enlazados DESC
LIMIT 10;
```

Esta consulta filtra los equipos de relevos de Jamaica para comprobar un caso
concreto relacionado con las participaciones de Usain Bolt.

```sql
SELECT
    e.equipo_id,
    e.nombre_equipo,
    p.nombre_pais,
    ed.anio,
    d.nombre_deporte,
    ev.nombre_evento,
    count(pa.participacion_id) AS atletas_enlazados
FROM equipo e
JOIN pais p ON p.pais_id = e.pais_id
JOIN evento ev ON ev.evento_id = e.evento_id
JOIN edicion ed ON ed.edicion_id = ev.edicion_id
JOIN deporte d ON d.deporte_id = ev.deporte_id
LEFT JOIN participacion pa ON pa.equipo_id = e.equipo_id
WHERE e.pais_id = 'JAM'
  AND ev.nombre_evento ILIKE '%Relay%'
GROUP BY e.equipo_id, e.nombre_equipo, p.nombre_pais, ed.anio,
         d.nombre_deporte, ev.nombre_evento
ORDER BY ed.anio, ev.nombre_evento;
```

## 2. Verificar integridad de las relaciones

Esta consulta comprueba que no existan participaciones apuntando a un equipo
que no existe. El resultado esperado es `0`.

```sql
SELECT count(*) AS referencias_huerfanas
FROM participacion pa
LEFT JOIN equipo e ON e.equipo_id = pa.equipo_id
WHERE pa.equipo_id IS NOT NULL
  AND e.equipo_id IS NULL;
```

También se puede revisar cuántas participaciones quedaron enlazadas:
Esta consulta compara cuántas participaciones tienen equipo y cuántas
permanecen sin equipo porque corresponden a pruebas individuales.

```sql
SELECT
    count(*) FILTER (WHERE equipo_id IS NOT NULL) AS con_equipo,
    count(*) FILTER (WHERE equipo_id IS NULL) AS individuales_o_sin_equipo
FROM participacion;
```

## 3. Probar `sp_info_atleta`

El procedimiento crea la tabla temporal `resultado_sp_info_atleta`. La
consulta posterior muestra el resultado detallado.

El procedimiento busca al atleta y crea el resultado detallado en la tabla
temporal `resultado_sp_info_atleta`. La consulta siguiente muestra todas sus
participaciones ordenadas cronológicamente.

```sql
CALL sp_info_atleta('Usain St. Leo Bolt');
SELECT *
FROM resultado_sp_info_atleta
ORDER BY anio, nombre_deporte, nombre_evento;
```

Con filtros:

Aquí se prueba el mismo procedimiento aplicando simultáneamente filtros de
deporte, país representado y año.

```sql
CALL sp_info_atleta('Usain St. Leo Bolt', 'Athletics', 'JAM', 2012);
SELECT *
FROM resultado_sp_info_atleta;
```

Para probar la búsqueda parcial:

Esta variante comprueba que la búsqueda del procedimiento funciona con una
parte del nombre y permite identificar los atletas encontrados.

```sql
CALL sp_info_atleta('Bolt');
SELECT DISTINCT atleta_id, nombre_completo, sexo, pais_representado
FROM resultado_sp_info_atleta
ORDER BY atleta_id;
```

## 4. Probar `sp_info_pais`

El procedimiento busca el país por su código NOC y deja sus sedes,
participaciones y datos relacionados en `resultado_sp_info_pais`.

```sql
CALL sp_info_pais('JAM');
SELECT *
FROM resultado_sp_info_pais
ORDER BY anio, nombre_deporte, atleta;
```

La búsqueda también acepta el nombre del país. En este dataset el catálogo
usa `Jamaica` como nombre:

Esta consulta comprueba que el procedimiento también acepta el nombre
completo del país en lugar del código `JAM`.

```sql
CALL sp_info_pais('Jamaica');
SELECT *
FROM resultado_sp_info_pais;
```

Con filtros por año, deporte y medalla:

Aquí se filtran las participaciones de Jamaica por año, deporte y medalla de
oro.

```sql
CALL sp_info_pais('JAM', 2012, 'Athletics', 'Oro');
SELECT *
FROM resultado_sp_info_pais;
```

## 5. Consultas rápidas de resumen

Esta consulta resume cuántas medallas de cada tipo existen en toda la base de
datos.

```sql
SELECT medalla, count(*)
FROM participacion
WHERE medalla IS NOT NULL
GROUP BY medalla
ORDER BY count(*) DESC;
```

Esta consulta muestra los diez países con más participaciones registradas.

```sql
SELECT p.nombre_pais, count(*) AS participaciones
FROM participacion pa
JOIN pais p ON p.pais_id = pa.pais_representado_id
GROUP BY p.nombre_pais
ORDER BY participaciones DESC
LIMIT 10;
```

### 5.1. Conteo de registros principales

Esta consulta permite verificar rápidamente que las tablas principales fueron
cargadas y comparar sus cantidades con el resumen producido por el ETL.

```sql
SELECT 'paises' AS entidad, count(*) AS registros FROM pais
UNION ALL
SELECT 'atletas', count(*) FROM atleta
UNION ALL
SELECT 'ediciones', count(*) FROM edicion
UNION ALL
SELECT 'deportes', count(*) FROM deporte
UNION ALL
SELECT 'eventos', count(*) FROM evento
UNION ALL
SELECT 'participaciones', count(*) FROM participacion;
```

### 5.2. Medallas por deporte

Esta consulta identifica qué deportes concentran más medallas y separa los
resultados por tipo de medalla.

```sql
SELECT
    d.nombre_deporte,
    p.medalla,
    count(*) AS total_medallas
FROM participacion p
JOIN evento e ON e.evento_id = p.evento_id
JOIN deporte d ON d.deporte_id = e.deporte_id
WHERE p.medalla IS NOT NULL
GROUP BY d.nombre_deporte, p.medalla
ORDER BY total_medallas DESC, d.nombre_deporte, p.medalla
LIMIT 20;
```

### 5.3. Países sede de los Juegos

Esta consulta lista las ediciones olímpicas y el país que fue sede en cada
una, usando la relación entre `edicion` y `pais`.

```sql
SELECT
    e.anio,
    e.nombre_edicion,
    e.ciudad,
    p.pais_id,
    p.nombre_pais
FROM edicion e
LEFT JOIN pais p ON p.pais_id = e.pais_sede_id
WHERE e.pais_sede_id IS NOT NULL
ORDER BY e.anio;
```

### 5.4. Atletas por edición

Esta consulta cuenta atletas distintos que participaron en cada edición y
permite comparar el tamaño de las competencias a través del tiempo.

```sql
SELECT
    e.anio,
    e.nombre_edicion,
    count(DISTINCT p.atleta_id) AS atletas_distintos,
    count(*) AS participaciones
FROM edicion e
JOIN evento ev ON ev.edicion_id = e.edicion_id
JOIN participacion p ON p.evento_id = ev.evento_id
GROUP BY e.anio, e.nombre_edicion
ORDER BY e.anio;
```

### 5.5. Países con más medallas

Esta consulta obtiene un ranking de países representados con más medallas,
sin distinguir entre oro, plata y bronce.

```sql
SELECT
    pa.nombre_pais,
    count(*) AS medallas
FROM participacion p
JOIN pais pa ON pa.pais_id = p.pais_representado_id
WHERE p.medalla IS NOT NULL
GROUP BY pa.nombre_pais
ORDER BY medallas DESC, pa.nombre_pais
LIMIT 10;
```

### 5.6. Tamaño de los equipos derivados

Esta consulta muestra cuántos atletas quedaron enlazados a cada equipo y
permite detectar equipos con una cantidad inesperada de integrantes.

```sql
SELECT
    e.equipo_id,
    e.nombre_equipo,
    e.pais_id,
    count(p.participacion_id) AS integrantes
FROM equipo e
LEFT JOIN participacion p ON p.equipo_id = e.equipo_id
GROUP BY e.equipo_id, e.nombre_equipo, e.pais_id
ORDER BY integrantes DESC, e.equipo_id
LIMIT 20;
```

### 5.7. Atletas con más medallas

Esta consulta muestra los atletas que acumulan más medallas y el detalle de
oro, plata y bronce que obtuvo cada uno.

```sql
SELECT
    a.nombre_completo,
    count(*) AS total_medallas,
    count(*) FILTER (WHERE p.medalla = 'Oro') AS oros,
    count(*) FILTER (WHERE p.medalla = 'Plata') AS platas,
    count(*) FILTER (WHERE p.medalla = 'Bronce') AS bronces
FROM atleta a
JOIN participacion p ON p.atleta_id = a.atleta_id
WHERE p.medalla IS NOT NULL
GROUP BY a.atleta_id, a.nombre_completo
ORDER BY total_medallas DESC, a.nombre_completo
LIMIT 10;
```

### 5.8. Eventos con más países representados

Esta consulta identifica eventos internacionales con mayor diversidad de
países participantes.

```sql
SELECT
    e.anio,
    d.nombre_deporte,
    ev.nombre_evento,
    count(DISTINCT p.pais_representado_id) AS paises,
    count(*) AS participaciones
FROM evento ev
JOIN edicion e ON e.edicion_id = ev.edicion_id
JOIN deporte d ON d.deporte_id = ev.deporte_id
JOIN participacion p ON p.evento_id = ev.evento_id
WHERE p.pais_representado_id IS NOT NULL
GROUP BY e.anio, d.nombre_deporte, ev.nombre_evento
ORDER BY paises DESC, participaciones DESC
LIMIT 20;
```