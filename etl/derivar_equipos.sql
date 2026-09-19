BEGIN;
-- Limpieza de corridas previas de este script (idempotencia)
UPDATE
    participacion
SET
    equipo_id = NULL
WHERE
    equipo_id IS NOT NULL;
-- La FK desde participacion impide TRUNCATE aunque equipo_id ya sea NULL.
-- DELETE conserva la restricción y no elimina las participaciones.
DELETE FROM equipo;
-- Deportes que SIEMPRE son de conjunto, sin importar el nombre
-- exacto del evento. Ajusta el patrón si tu ETL normalizó los
-- nombres distinto.
CREATE TEMP TABLE deportes_equipo AS
SELECT
    deporte_id
FROM
    deporte
WHERE
    nombre_deporte ~* '(football|soccer|basketball|volleyball|beach volleyball|handball|hockey|rugby|baseball|softball|water polo|curling)';
-- Eventos "de conjunto": deporte de equipo del paso 1, o el
-- nombre del evento sugiere relevo/dobles/parejas/equipo.
CREATE TEMP TABLE eventos_equipo AS
SELECT
    ev.evento_id
FROM
    evento ev
WHERE
    ev.deporte_id IN (
        SELECT
            deporte_id
        FROM
            deportes_equipo)
    OR ev.nombre_evento ~* '(relay|relevo|double|doubles|dobles|pair|pairs|parejas|team|equipo|4x|synchroni[sz]ed)';
-- Candidatos a equipo: agrupar participaciones de esos eventos
-- por (evento, país representado). Solo cuenta como "equipo" si
-- hay 2 o más atletas del mismo país en el mismo evento.
CREATE TEMP TABLE equipos_candidatos AS
SELECT
    p.evento_id,
    p.pais_representado_id,
    count(*) AS num_atletas,
    max(p.nombre_en_competencia) AS nombre_en_competencia_frecuente
FROM
    participacion p
WHERE
    p.evento_id IN (
        SELECT
            evento_id
        FROM
            eventos_equipo)
    AND p.pais_representado_id IS NOT NULL
GROUP BY
    p.evento_id,
    p.pais_representado_id
HAVING
    count(*) >= 2;
-- Insertar un registro de equipo por cada grupo detectado
INSERT INTO equipo (evento_id, pais_id, nombre_equipo)
SELECT
    ec.evento_id,
    ec.pais_representado_id,
    COALESCE(ec.nombre_en_competencia_frecuente, pa.nombre_pais)
FROM
    equipos_candidatos ec
    JOIN pais pa ON pa.pais_id = ec.pais_representado_id;
-- Enlazar cada participación al equipo_id recién creado
UPDATE
    participacion p
SET
    equipo_id = eq.equipo_id
FROM
    equipo eq
WHERE
    eq.evento_id = p.evento_id
    AND eq.pais_id = p.pais_representado_id
    AND p.evento_id IN (
        SELECT
            evento_id
        FROM
            eventos_equipo);
-- Resumen para verificar el resultado de la corrida
DO $$
DECLARE
    v_equipos int;
    v_participaciones int;
BEGIN
    SELECT
        count(*)
    INTO
        v_equipos
    FROM
        equipo;
    SELECT
        count(*)
    INTO
        v_participaciones
    FROM
        participacion
    WHERE
        equipo_id IS NOT NULL;
    RAISE NOTICE 'Equipos creados: %', v_equipos;
    RAISE NOTICE 'Participaciones enlazadas a un equipo: %', v_participaciones;
END
$$;
DROP TABLE deportes_equipo;
DROP TABLE eventos_equipo;
DROP TABLE equipos_candidatos;
COMMIT;
