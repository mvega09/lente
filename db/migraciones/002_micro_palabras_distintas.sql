-- =====================================================================
--  Migración 002 · La micro cuenta palabras cargadas distintas
--
--  El frontend marca palabra por palabra y la IA propone expresiones de varias
--  palabras. terminar_actividad() contaba cada MARCA que tocaba una expresión como
--  un acierto: tres palabras de una misma expresión sumaban tres, y la micro podía
--  llegar al 100 % (y dar "Ojo de águila") sin encontrar las demás. Ahora cuenta
--  las palabras cargadas distintas encontradas. Las actividades ya terminadas
--  conservan su nota.
--
--  En la VM-BD:
--     sudo -u postgres psql -d lente -v ON_ERROR_STOP=1 < 002_micro_palabras_distintas.sql
-- =====================================================================

\set ON_ERROR_STOP on
BEGIN;
SET search_path = lente, public;
SET ROLE lente_duenio;

CREATE OR REPLACE FUNCTION terminar_actividad(p_actividad bigint)
RETURNS TABLE (resultado_macro numeric, resultado_super numeric, resultado_micro numeric, puntos_ganados integer)
LANGUAGE plpgsql AS $$
#variable_conflict use_column
DECLARE
  a        lente.actividades;
  v_curso  bigint;
  x        int;
  bono     int;
  castigo  numeric;
  hoy      date    := (now() AT TIME ZONE 'America/Bogota')::date;
  v_estado_ia text; v_veredicto text;
  r_macro numeric; r_super numeric; r_micro numeric;
  aciertos int; neutras int; esperadas int; v_puntos int;
  e lente.estudiantes;
BEGIN
  SELECT * INTO a FROM lente.actividades WHERE id = p_actividad FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'La actividad % no existe', p_actividad; END IF;
  -- Reglas de puntos: las del curso del estudiante (o las generales)
  SELECT curso_id INTO v_curso FROM lente.estudiantes WHERE id = a.estudiante_id;
  x       := coalesce((lente.ajuste('puntos_por_acierto', v_curso))::int, 20);
  bono    := coalesce((lente.ajuste('puntos_por_terminar', v_curso))::int, 5);
  castigo := coalesce((lente.ajuste('descuento_palabra_neutra', v_curso))::numeric, 0.5);
  IF a.estado = 'terminada' THEN
    RETURN QUERY SELECT a.resultado_macro, a.resultado_super, a.resultado_micro, a.puntos_ganados;
    RETURN;
  END IF;

  -- Deben estar los tres pasos (RF-15)
  IF (SELECT count(DISTINCT nivel) FROM lente.respuestas WHERE actividad_id = p_actividad) < 3 THEN
    RAISE EXCEPTION 'Faltan pasos por responder en la actividad %', p_actividad;
  END IF;

  -- MACRO: según lo que dijo la IA
  SELECT estado_ia, veredicto_ia INTO v_estado_ia, v_veredicto
    FROM lente.respuestas WHERE actividad_id = p_actividad AND nivel = 'macro';
  IF v_estado_ia IN ('pendiente','procesando') THEN
    RAISE EXCEPTION 'La IA todavía está revisando la idea principal'
      USING ERRCODE = 'object_not_in_prerequisite_state';
  END IF;
  r_macro := CASE v_veredicto WHEN 'coincide' THEN 1 WHEN 'coincide_en_parte' THEN 0.5 ELSE 0 END;

  -- SUPER: preguntas acertadas / preguntas respondidas
  SELECT avg(CASE WHEN es_correcta THEN 1 ELSE 0 END) INTO r_super
    FROM lente.respuestas WHERE actividad_id = p_actividad AND nivel = 'super';

  -- MICRO: (palabras acertadas − 0,5 × palabras neutras) / palabras cargadas del texto
  --   Aciertos = palabras cargadas DISTINTAS encontradas. El estudiante marca palabra por
  --   palabra: varias marcas dentro de una misma expresión ("turbia y con olor a químicos")
  --   cuentan una sola vez. Antes se contaban marcas y la nota podía llegar al 100 %.
  SELECT count(DISTINCT p.id) INTO aciertos
    FROM lente.palabras_cargadas p
    JOIN lente.respuestas r ON r.actividad_id = p_actividad AND r.nivel = 'micro' AND r.es_correcta
   WHERE p.texto_id = a.texto_id
     AND (int4range(p.inicio, p.fin) && int4range(r.inicio, r.fin)
          OR lente.normalizar(p.palabra) = lente.normalizar(r.texto));
  SELECT count(*) INTO neutras
    FROM lente.respuestas WHERE actividad_id = p_actividad AND nivel = 'micro' AND NOT es_correcta;
  SELECT count(*) INTO esperadas FROM lente.palabras_cargadas WHERE texto_id = a.texto_id;
  r_micro := CASE WHEN esperadas = 0 THEN 0
                  ELSE greatest(0, least(1, (least(aciertos, esperadas) - castigo * neutras) / esperadas)) END;

  v_puntos := round(r_macro * x) + round(r_super * x) + round(r_micro * x) + bono;

  UPDATE lente.actividades
     SET estado = 'terminada', paso = 'resultado', terminada_en = now(),
         resultado_macro = round(r_macro, 2), resultado_super = round(r_super, 2),
         resultado_micro = round(r_micro, 2), puntos_ganados = v_puntos
   WHERE id = p_actividad;

  -- Puntos y racha del estudiante
  UPDATE lente.estudiantes s
     SET puntos = s.puntos + v_puntos,
         racha = CASE WHEN s.ultimo_dia = hoy THEN s.racha
                      WHEN s.ultimo_dia = hoy - 1 THEN s.racha + 1 ELSE 1 END,
         ultimo_dia = hoy
   WHERE s.id = a.estudiante_id;
  UPDATE lente.estudiantes s SET mejor_racha = greatest(s.mejor_racha, s.racha)
   WHERE s.id = a.estudiante_id RETURNING * INTO e;

  -- Logros
  INSERT INTO lente.logros_ganados(estudiante_id, logro_id)
  SELECT e.id, l.id FROM lente.logros l
   WHERE l.activo AND CASE l.regla
     WHEN 'actividades_terminadas' THEN
          (SELECT count(*) FROM lente.actividades WHERE estudiante_id = e.id AND estado = 'terminada') >= l.meta
     WHEN 'racha'          THEN e.racha >= l.meta
     WHEN 'micro_perfecto' THEN r_micro >= 1
     WHEN 'idea_correcta'  THEN v_veredicto = 'coincide'
     WHEN 'nivel'          THEN e.puntos / coalesce((lente.ajuste('puntos_por_nivel', v_curso))::int, 100) + 1 >= l.meta
   END
  ON CONFLICT DO NOTHING;

  -- Análisis de ánimo en segundo plano (RF-21)
  INSERT INTO lente.cola_ia(tarea, prioridad, actividad_id) VALUES ('analizar_animo', 9, p_actividad);

  RETURN QUERY SELECT round(r_macro,2), round(r_super,2), round(r_micro,2), v_puntos;
END $$;

RESET ROLE;
COMMIT;
