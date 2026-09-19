CREATE OR REPLACE PROCEDURE sp_info_atleta(
    p_nombre text,
    p_deporte text DEFAULT NULL,
    p_pais text DEFAULT NULL,
    p_anio integer DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    DROP TABLE IF EXISTS resultado_sp_info_atleta;

    CREATE TEMP TABLE resultado_sp_info_atleta ON COMMIT PRESERVE ROWS AS
    SELECT
        a.atleta_id,
        a.nombre_completo,
        a.nombre_usado,
        a.sexo,
        a.fecha_nacimiento,
        a.lugar_nacimiento,
        a.estatura_cm,
        a.peso_kg,
        ev.anio,
        ev.temporada,
        ev.ciudad,
        d.nombre_deporte,
        e.nombre_evento,
        p.pais_representado_id,
        pais.nombre_pais AS pais_representado,
        p.nombre_en_competencia,
        p.posicion,
        p.medalla,
        p.equipo_id
    FROM atleta a
    LEFT JOIN participacion p ON p.atleta_id = a.atleta_id
    LEFT JOIN evento e ON e.evento_id = p.evento_id
    LEFT JOIN edicion ev ON ev.edicion_id = e.edicion_id
    LEFT JOIN deporte d ON d.deporte_id = e.deporte_id
    LEFT JOIN pais ON pais.pais_id = p.pais_representado_id
    WHERE a.nombre_completo ILIKE '%' || p_nombre || '%'
      AND (p_deporte IS NULL OR d.nombre_deporte ILIKE '%' || p_deporte || '%')
      AND (p_pais IS NULL OR p.pais_representado_id ILIKE p_pais
           OR pais.nombre_pais ILIKE '%' || p_pais || '%')
      AND (p_anio IS NULL OR ev.anio = p_anio)
    ORDER BY a.atleta_id, ev.anio, d.nombre_deporte, e.nombre_evento;

    RAISE NOTICE 'Resultado disponible en resultado_sp_info_atleta: % filas',
        (SELECT count(*) FROM resultado_sp_info_atleta);
END;
$$;

CREATE OR REPLACE PROCEDURE sp_info_pais(
    p_pais text,
    p_anio integer DEFAULT NULL,
    p_deporte text DEFAULT NULL,
    p_medalla text DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pais_id varchar(3);
BEGIN
    SELECT pa.pais_id
    INTO v_pais_id
    FROM pais pa
    WHERE pa.pais_id ILIKE p_pais
       OR pa.nombre_pais ILIKE '%' || p_pais || '%'
    ORDER BY CASE WHEN pa.pais_id ILIKE p_pais THEN 0 ELSE 1 END, pa.pais_id
    LIMIT 1;

    IF v_pais_id IS NULL THEN
        RAISE EXCEPTION 'No se encontró el país: %', p_pais;
    END IF;

    DROP TABLE IF EXISTS resultado_sp_info_pais;

    CREATE TEMP TABLE resultado_sp_info_pais ON COMMIT PRESERVE ROWS AS
    SELECT
        pa.pais_id,
        pa.nombre_pais,
        p.anio AS anio_poblacion,
        p.poblacion,
        sede.anio AS anio_sede,
        sede.nombre_edicion AS edicion_sede,
        ev.anio,
        ev.temporada,
        ev.ciudad,
        d.nombre_deporte,
        e.nombre_evento,
        a.atleta_id,
        a.nombre_completo AS atleta,
        part.nombre_en_competencia,
        part.posicion,
        part.medalla,
        part.equipo_id
    FROM pais pa
    LEFT JOIN LATERAL (
        SELECT po.anio, po.poblacion
        FROM poblacion po
        WHERE po.pais_id = pa.pais_id
        ORDER BY po.anio DESC
        LIMIT 1
    ) p ON true
    LEFT JOIN edicion sede ON sede.pais_sede_id = pa.pais_id
    LEFT JOIN participacion part ON part.pais_representado_id = pa.pais_id
    LEFT JOIN atleta a ON a.atleta_id = part.atleta_id
    LEFT JOIN evento e ON e.evento_id = part.evento_id
    LEFT JOIN edicion ev ON ev.edicion_id = e.edicion_id
    LEFT JOIN deporte d ON d.deporte_id = e.deporte_id
    WHERE pa.pais_id = v_pais_id
      AND (p_anio IS NULL OR ev.anio = p_anio)
      AND (p_deporte IS NULL OR d.nombre_deporte ILIKE '%' || p_deporte || '%')
      AND (p_medalla IS NULL OR part.medalla ILIKE p_medalla);

    RAISE NOTICE 'Resultado disponible en resultado_sp_info_pais: % filas',
        (SELECT count(*) FROM resultado_sp_info_pais);
END;
$$;
