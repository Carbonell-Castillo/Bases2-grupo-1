# Fase 2 — Respaldo y Restauración de Bases de Datos

Implementación de [`775_Proyecto_2_2S2026.md`](../775_Proyecto_2_2S2026.md):
3 rondas de carga (por año, por deporte, por deportista) sobre la base de
datos de Olimpiadas, con respaldo físico completo + incremental (Postgres 17,
`pg_basebackup` / `pg_combinebackup`) y restauración con medición de tiempos.

## Estructura

```
Fase2/
├── docker-compose.yml       Postgres 17 con summarize_wal=on y almacenamiento persistente
├── sql/                     Esquema, procedimientos, derivación y validaciones
├── carga/                   Generador de subconjuntos + script de carga incremental
├── backup/                  Scripts de respaldo full/incremental
├── restore/                 Scripts de restauración full y full+incremental
├── backups/                 Respaldos físicos (fuera del volumen de datos)
├── logs/                    backups.csv y restores.csv con tiempos reales
└── docs/                    Manual de usuario, informe técnico, análisis comparativo y evidencia
```

## Por qué Postgres 17

El enunciado pide una herramienta de respaldo **físico** (no dumps). Postgres
17 incorpora de forma nativa `pg_basebackup --incremental` (respaldo
incremental real, solo bloques modificados) y `pg_combinebackup` (reconstruye
el directorio de datos a partir de un full + su cadena de incrementales).
Esto evita depender de herramientas de terceros (xtrabackup, pgBackRest) y
sigue siendo "no dump": son copias físicas del directorio de datos, tomadas
vía el protocolo de replicación.

## Qué se reutilizó de Fase 1

- `sql/schema.sql` y `sql/stored_procedures.sql`: el mismo modelo e
  implementación de `sp_info_atleta` / `sp_info_pais`, sin cambios.
- `../Fase1/etl-csvs/*.csv`: fuente de datos para los 3 subconjuntos de carga
  (no se repitió el ETL de las 7 fuentes originales).
- `sql/derivar_equipos.sql`: adaptación del paso posterior a `load.sql` de
  Fase 1; se ejecuta después de cada delta para reconstruir y enlazar equipos.
- Los subconjuntos incluyen población, clubes y relaciones atleta–club para
  que las diez tablas del modelo participen en las validaciones.
- El enfoque de evidencia con capturas con fecha (`docs/evidencia.md`).

## Guía rápida

Ver [`docs/manual_usuario.md`](docs/manual_usuario.md) para el paso a paso
completo. Resultados y comparación de tiempos en
[`docs/analisis_comparativo.md`](docs/analisis_comparativo.md) y
[`docs/informe_tecnico.md`](docs/informe_tecnico.md).

Entregables listos para evaluación: [`docs/documentacion_tecnica.pdf`](docs/documentacion_tecnica.pdf)
y [`docs/manual_usuario.pdf`](docs/manual_usuario.pdf). Se regeneran con
`python docs/generar_pdfs.py`.
