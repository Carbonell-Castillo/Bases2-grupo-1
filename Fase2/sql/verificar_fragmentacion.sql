-- Se implemento la verificacion de fragmentacion pedida en la metodologia (seccion 6, Fase 2)
CREATE EXTENSION IF NOT EXISTS pgstattuple;

SELECT relname AS tabla,
       n_live_tup AS filas_vivas,
       n_dead_tup AS filas_muertas,
       round(100.0 * n_dead_tup / GREATEST(n_live_tup + n_dead_tup, 1), 2) AS pct_fragmentacion,
       last_vacuum,
       last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

SELECT * FROM pgstattuple('participacion');
