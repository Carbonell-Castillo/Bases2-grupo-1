-- script para meter los datos a postgres

BEGIN;

COPY pais (pais_id, nombre_pais, region)
    FROM '/data/pais.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY poblacion (pais_id, anio, poblacion)
    FROM '/data/poblacion.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY atleta (atleta_id, nombre_completo, nombre_usado, sexo, fecha_nacimiento,
             lugar_nacimiento, fecha_fallecimiento, lugar_fallecimiento,
             estatura_cm, peso_kg, pais_id)
    FROM '/data/atleta.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY edicion (edicion_id, nombre_edicion, anio, temporada, ciudad, pais_sede_id)
    FROM '/data/edicion.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY deporte (deporte_id, nombre_deporte)
    FROM '/data/deporte.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY evento (evento_id, edicion_id, deporte_id, nombre_evento)
    FROM '/data/evento.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY equipo (equipo_id, evento_id, pais_id, nombre_equipo)
    FROM '/data/equipo.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY club (club_id, nombre_club, pais_id)
    FROM '/data/club.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY atleta_club (atleta_id, club_id)
    FROM '/data/atleta_club.csv' WITH (FORMAT csv, HEADER true, NULL '');

COPY participacion (participacion_id, atleta_id, evento_id, equipo_id,
                     pais_representado_id, nombre_en_competencia, posicion, medalla)
    FROM '/data/participacion.csv' WITH (FORMAT csv, HEADER true, NULL '');

-- actualizar los auto increment porque si no truena con los stored procedures
SELECT setval(pg_get_serial_sequence('atleta', 'atleta_id'), COALESCE((SELECT MAX(atleta_id) FROM atleta), 1));
SELECT setval(pg_get_serial_sequence('edicion', 'edicion_id'), COALESCE((SELECT MAX(edicion_id) FROM edicion), 1));
SELECT setval(pg_get_serial_sequence('deporte', 'deporte_id'), COALESCE((SELECT MAX(deporte_id) FROM deporte), 1));
SELECT setval(pg_get_serial_sequence('evento', 'evento_id'), COALESCE((SELECT MAX(evento_id) FROM evento), 1));
SELECT setval(pg_get_serial_sequence('equipo', 'equipo_id'), COALESCE((SELECT MAX(equipo_id) FROM equipo), 1));
SELECT setval(pg_get_serial_sequence('club', 'club_id'), COALESCE((SELECT MAX(club_id) FROM club), 1));
SELECT setval(pg_get_serial_sequence('participacion', 'participacion_id'), COALESCE((SELECT MAX(participacion_id) FROM participacion), 1));

COMMIT;
