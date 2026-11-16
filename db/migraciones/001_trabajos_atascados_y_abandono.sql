-- =====================================================================
--  Migración 001 · Trabajos de IA atascados y actividades abandonadas
--
--  Aplica a una base YA CREADA los cambios de schema.sql del 16-nov-2026,
--  sin borrar datos. Todo va en una transacción: si algo falla, no cambia nada.
--
--  En la VM-BD:
--     sudo -u postgres psql -d lente -v ON_ERROR_STOP=1 -f 001_trabajos_atascados_y_abandono.sql
--
--  Qué cambia:
--   1. cola_ia.tomado_en y tomar_trabajo_ia(): un trabajo que quedó en
--      "procesando" porque el worker se detuvo se reintenta (3 min; 20 min si
--      es preparar un texto) o se marca fallido si no le quedan intentos.
--   2. marcar_abandonadas(): actividades sin respuestas durante
--      horas_para_abandono (3 h por defecto) pasan a "abandonada" y, si el
--      estudiante respondió algo, se pide el análisis de ánimo (RF-21).
--   3. ia_animo incluye si la actividad se abandonó y en qué paso.
--   4. Nuevo ajuste general horas_para_abandono = 3.
-- =====================================================================

\set ON_ERROR_STOP on
BEGIN;
SET search_path = lente, public;
SET ROLE lente_duenio;

ALTER TABLE cola_ia ADD COLUMN IF NOT EXISTS tomado_en timestamptz;
COMMENT ON COLUMN cola_ia.tomado_en IS 'Cuándo lo tomó el programa de IA (para recuperar trabajos interrumpidos).';

CREATE OR REPLACE FUNCTION tomar_trabajo_ia() RETURNS SETOF cola_ia
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
DECLARE v_id bigint;
BEGIN
  FOR v_id IN
    SELECT id FROM cola_ia
     WHERE estado = 'procesando'
       AND coalesce(tomado_en, creada_en) < now() - CASE tarea WHEN 'preparar_texto'
                                                   THEN interval '20 minutes' ELSE interval '3 minutes' END
     FOR UPDATE SKIP LOCKED
  LOOP
    PERFORM reportar_error_ia(v_id, 'Trabajo interrumpido: el programa de IA se detuvo antes de terminar');
  END LOOP;

  RETURN QUERY
  UPDATE cola_ia c SET estado = 'procesando', intentos = c.intentos + 1, tomado_en = now()
   WHERE c.id = (SELECT id FROM cola_ia
                  WHERE estado = 'pendiente' AND disponible_desde <= now()
                  ORDER BY prioridad, disponible_desde, id
                  FOR UPDATE SKIP LOCKED LIMIT 1)
  RETURNING c.*;
END $$;

CREATE OR REPLACE FUNCTION marcar_abandonadas() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
DECLARE r record; n int := 0;
BEGIN
  FOR r IN
    SELECT a.id, (SELECT max(x.recibida_en) FROM respuestas x WHERE x.actividad_id = a.id) AS ultima,
           a.iniciada_en, s.curso_id
      FROM actividades a JOIN estudiantes s ON s.id = a.estudiante_id
     WHERE a.estado = 'en_curso'
     FOR UPDATE OF a SKIP LOCKED
  LOOP
    CONTINUE WHEN coalesce(r.ultima, r.iniciada_en)
                  >= now() - make_interval(hours => coalesce((ajuste('horas_para_abandono', r.curso_id))::int, 3));
    UPDATE actividades SET estado = 'abandonada', terminada_en = coalesce(r.ultima, r.iniciada_en)
     WHERE id = r.id;
    IF r.ultima IS NOT NULL THEN
      INSERT INTO cola_ia(tarea, prioridad, actividad_id) VALUES ('analizar_animo', 9, r.id);
    END IF;
    n := n + 1;
  END LOOP;
  RETURN n;
END $$;

CREATE OR REPLACE VIEW ia_animo AS
SELECT c.id AS trabajo_id,
       (SELECT r.texto FROM respuestas r WHERE r.actividad_id = a.id AND r.nivel = 'macro') AS respuesta_abierta,
       a.resultado_macro, a.resultado_super, a.resultado_micro,
       extract(epoch FROM a.terminada_en - a.iniciada_en)::int AS segundos,
       a.estado = 'abandonada' AS abandonada,
       a.paso
  FROM cola_ia c JOIN actividades a ON a.id = c.actividad_id
 WHERE c.tarea = 'analizar_animo' AND c.estado = 'procesando';

INSERT INTO ajustes(clave, valor, descripcion)
VALUES ('horas_para_abandono', '3', 'Horas sin respuestas para dar una actividad por abandonada')
ON CONFLICT (clave) WHERE curso_id IS NULL DO NOTHING;

RESET ROLE;
REVOKE EXECUTE ON FUNCTION marcar_abandonadas() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION marcar_abandonadas() TO lente_ia, lente_app;
GRANT SELECT ON ia_animo TO lente_ia;

COMMIT;
