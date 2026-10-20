# Informe Técnico y Manual de Decisiones - Fase 3

## 1. Introducción
Este documento detalla la arquitectura, el modelado de datos y las decisiones técnicas tomadas para la migración de la base de datos de los Juegos Olímpicos desde un modelo relacional (PostgreSQL - Fase 1) a un modelo NoSQL (MongoDB - Fase 3). El objetivo es optimizar el rendimiento de lectura y aprovechar las características de almacenamiento orientado a documentos.

## 2. Arquitectura de Migración y Flujo de Datos
**Decisión:** En lugar de procesar los archivos CSV originales nuevamente con Python, se decidió ejecutar el entorno de la Fase 1, permitir que PostgreSQL realice la derivación compleja de equipos y limpieza de datos, y luego exportar las tablas finales a archivos CSV.
**Justificación:** 
1. **Preservación de la Integridad ETL:** La lógica de deduplicación de atletas y la formación de deportes de equipo (`derivar_equipos.sql`) es compleja y ya está validada en la Fase 1. Replicar esto en Python introduciría riesgos innecesarios.
2. **Fuente de la Verdad:** Al exportar desde PostgreSQL, garantizamos que MongoDB tenga exactamente los mismos datos finales evaluados en la primera fase.

## 3. Modelo de Datos NoSQL
En un modelo relacional se utilizaron 10 tablas para evitar la redundancia. En MongoDB, el diseño prioriza las lecturas rápidas mediante la denormalización. Se definieron **3 colecciones principales**:

### Colección: `paises`
* **Estructura:** Contiene `_id` (código del país), `nombre_pais`, `region` y un arreglo anidado `historico_poblacion`.
* **Justificación:** La población histórica es un dato intrínseco del país que rara vez se actualiza. Anidarlo evita tener una colección separada de "Población" que requería un `$lookup` costoso en cada consulta geográfica.

### Colección: `ediciones`
* **Estructura:** Contiene los metadatos de cada juego olímpico (año, temporada, ciudad, sede).
* **Justificación:** Se mantiene como colección independiente porque funciona como un catálogo ligero. Anidar esta información repetidamente dentro de millones de participaciones aumentaría drásticamente el tamaño de almacenamiento sin aportar valor, ya que los metadatos de la edición rara vez cambian.

### Colección: `atletas` (La colección principal)
* **Estructura:** Agrupa la biografía del atleta, un arreglo de `clubes` a los que pertenece, y un arreglo complejo de `participaciones` (que incluye el evento, edición, medalla, país representado y el equipo).
* **Justificación:** En PostgreSQL, consultar todo el historial de un atleta (el requerimiento principal C) requería hacer un JOIN entre `atleta`, `participacion`, `evento`, `edicion`, `deporte` y `equipo`. Al embeber las participaciones dentro del documento del atleta, la base de datos puede devolver el perfil completo del atleta con una sola operación de lectura `find()`, lo que representa una mejora de rendimiento de magnitud exponencial (O(1) en lectura).

## 4. Infraestructura Docker
**Decisión:** Se implementó MongoDB en Docker **sin volúmenes persistentes** en esta iteración de prueba automatizada.
**Justificación:** Dado que el script `exportar_fase1.sh` está diseñado para recrear todo el entorno desde cero, exportar y cargar los datos de forma automatizada en segundos, la persistencia de datos local genera conflictos si la estructura cambia. En un entorno de producción, se agregarían volúmenes, pero para la evaluación del proyecto, esto garantiza que la base de datos siempre arranque limpia y se cargue con el estado más reciente del script.
