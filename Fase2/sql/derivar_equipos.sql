\set ON_ERROR_STOP on

BEGIN;

-- Replica etl/derivar_equipos.sql de Fase 1 sobre el estado acumulado de
-- Fase 2. La reconstruccion completa permite repetir el paso sin duplicados.
UPDATE participacion
SET equipo_id = NULL
WHERE equipo_id IS NOT NULL;

DELETE FROM equipo;

CREATE TEMP TABLE deportes_equipo AS
SELECT deporte_id
FROM deporte
WHERE nombre_deporte ~* '(football|soccer|basketball|volleyball|beach volleyball|handball|hockey|rugby|baseball|softball|water polo|curling)';

CREATE TEMP TABLE eventos_equipo AS
SELECT ev.evento_id
FROM evento ev
WHERE ev.deporte_id IN (SELECT deporte_id FROM deportes_equipo)
   OR ev.nombre_evento ~* '(relay|relevo|double|doubles|dobles|pair|pairs|parejas|team|equipo|4x|synchroni[sz]ed)';

CREATE TEMP TABLE equipos_candidatos AS
SELECT
    p.evento_id,
    p.pais_representado_id,
    count(*) AS num_atletas,
    max(p.nombre_en_competencia) AS nombre_en_competencia_frecuente
FROM participacion p
WHERE p.evento_id IN (SELECT evento_id FROM eventos_equipo)
  AND p.pais_representado_id IS NOT NULL
GROUP BY p.evento_id, p.pais_representado_id
HAVING count(*) >= 2;

INSERT INTO equipo (evento_id, pais_id, nombre_equipo)
SELECT
    ec.evento_id,
    ec.pais_representado_id,
    COALESCE(ec.nombre_en_competencia_frecuente, pa.nombre_pais)
FROM equipos_candidatos ec
JOIN pais pa ON pa.pais_id = ec.pais_representado_id;

UPDATE participacion p
SET equipo_id = eq.equipo_id
FROM equipo eq
WHERE eq.evento_id = p.evento_id
  AND eq.pais_id = p.pais_representado_id
  AND p.evento_id IN (SELECT evento_id FROM eventos_equipo);

DO $$
DECLARE
    v_equipos bigint;
    v_participaciones bigint;
BEGIN
    SELECT count(*) INTO v_equipos FROM equipo;
    SELECT count(*) INTO v_participaciones
    FROM participacion
    WHERE equipo_id IS NOT NULL;

    RAISE NOTICE 'Equipos creados: %', v_equipos;
    RAISE NOTICE 'Participaciones enlazadas a un equipo: %', v_participaciones;
END
$$;

COMMIT;
