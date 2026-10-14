\set ON_ERROR_STOP on

-- Evidencia reproducible: fecha/hora, COUNT(*) y muestra equivalente a SELECT *
-- para las diez tablas. Un fallo referencial detiene la ejecucion.
SELECT now() AS fecha_hora_servidor, current_database() AS base_datos, version();

SELECT 'pais' tabla, count(*) total FROM pais
UNION ALL SELECT 'poblacion', count(*) FROM poblacion
UNION ALL SELECT 'atleta', count(*) FROM atleta
UNION ALL SELECT 'edicion', count(*) FROM edicion
UNION ALL SELECT 'deporte', count(*) FROM deporte
UNION ALL SELECT 'evento', count(*) FROM evento
UNION ALL SELECT 'equipo', count(*) FROM equipo
UNION ALL SELECT 'club', count(*) FROM club
UNION ALL SELECT 'atleta_club', count(*) FROM atleta_club
UNION ALL SELECT 'participacion', count(*) FROM participacion
ORDER BY tabla;

SELECT * FROM pais ORDER BY pais_id LIMIT 5;
SELECT * FROM poblacion ORDER BY pais_id, anio LIMIT 5;
SELECT * FROM atleta ORDER BY atleta_id LIMIT 5;
SELECT * FROM edicion ORDER BY edicion_id LIMIT 5;
SELECT * FROM deporte ORDER BY deporte_id LIMIT 5;
SELECT * FROM evento ORDER BY evento_id LIMIT 5;
SELECT * FROM equipo ORDER BY equipo_id LIMIT 5;
SELECT * FROM club ORDER BY club_id LIMIT 5;
SELECT * FROM atleta_club ORDER BY atleta_id, club_id LIMIT 5;
SELECT * FROM participacion ORDER BY participacion_id LIMIT 5;

DO $$
DECLARE v_huerfanos bigint;
BEGIN
    SELECT count(*) INTO v_huerfanos
    FROM (
        SELECT 1 FROM poblacion x LEFT JOIN pais p ON p.pais_id=x.pais_id WHERE p.pais_id IS NULL
        UNION ALL SELECT 1 FROM atleta x LEFT JOIN pais p ON p.pais_id=x.pais_id WHERE x.pais_id IS NOT NULL AND p.pais_id IS NULL
        UNION ALL SELECT 1 FROM edicion x LEFT JOIN pais p ON p.pais_id=x.pais_sede_id WHERE x.pais_sede_id IS NOT NULL AND p.pais_id IS NULL
        UNION ALL SELECT 1 FROM evento x LEFT JOIN edicion e ON e.edicion_id=x.edicion_id WHERE e.edicion_id IS NULL
        UNION ALL SELECT 1 FROM evento x LEFT JOIN deporte d ON d.deporte_id=x.deporte_id WHERE d.deporte_id IS NULL
        UNION ALL SELECT 1 FROM equipo x LEFT JOIN evento e ON e.evento_id=x.evento_id WHERE e.evento_id IS NULL
        UNION ALL SELECT 1 FROM participacion x LEFT JOIN atleta a ON a.atleta_id=x.atleta_id WHERE a.atleta_id IS NULL
        UNION ALL SELECT 1 FROM participacion x LEFT JOIN evento e ON e.evento_id=x.evento_id WHERE e.evento_id IS NULL
        UNION ALL SELECT 1 FROM participacion x LEFT JOIN equipo e ON e.equipo_id=x.equipo_id WHERE x.equipo_id IS NOT NULL AND e.equipo_id IS NULL
    ) h;
    IF v_huerfanos <> 0 THEN
        RAISE EXCEPTION 'Integridad referencial invalida: % filas huerfanas', v_huerfanos;
    END IF;
END $$;

SELECT 'VALIDACION OK: 0 filas huerfanas' AS resultado;
