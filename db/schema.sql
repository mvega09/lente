-- COPIA DE REFERENCIA de Info_bd/schema.sql para las pruebas del backend.
-- Las contraseñas se reemplazaron por CAMBIE_ESTA_CLAVE. La fuente oficial sigue siendo Info_bd/schema.sql.

-- =====================================================================
--  LENTE · Base de datos (PostgreSQL 16)
--  Semillero · Universidad de Manizales
--
--  Versión 4: 15 tablas (varios cursos por profesor; ajustes por curso).
--
--  Cómo ejecutarlo en el servidor (VM-BD), por SSH:
--     sudo -u postgres createdb lente
--     sudo -u postgres psql -d lente -v ON_ERROR_STOP=1 -f schema.sql
--
--  ¡CUIDADO! El script borra y vuelve a crear todo el esquema "lente".
--  Úselo solo la primera vez o en pruebas.
--  Antes de usarlo de verdad:
--     Contraseña de los usuarios de la base y del administrador: CAMBIE_ESTA_CLAVE

--
--  La base queda vacía: solo trae lo necesario para funcionar
--  (ajustes, logros y el primer administrador). No trae datos de prueba.
-- =====================================================================

\set ON_ERROR_STOP on
SET client_min_messages = warning;
SET check_function_bodies = off;

-- ---------------------------------------------------------------------
-- PASO 0. USUARIOS DE LA BASE DE DATOS
-- ---------------------------------------------------------------------
--  lente_duenio : dueño de las tablas. Nadie se conecta con él.
--  lente_app    : lo usa la aplicación web.
--  lente_ia     : lo usa el programa que habla con la IA (Ollama).
--                 No puede ver los nombres de los estudiantes.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lente_duenio') THEN
    CREATE ROLE lente_duenio NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lente_app') THEN
    CREATE ROLE lente_app LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lente_ia') THEN
    CREATE ROLE lente_ia LOGIN;
  END IF;
  ALTER ROLE lente_app LOGIN PASSWORD 'CAMBIE_ESTA_CLAVE' CONNECTION LIMIT 30;
  ALTER ROLE lente_ia  LOGIN PASSWORD 'CAMBIE_ESTA_CLAVE' CONNECTION LIMIT 5;
END $$;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- para guardar contraseñas cifradas
CREATE EXTENSION IF NOT EXISTS unaccent;   -- para comparar palabras sin tildes

DROP SCHEMA IF EXISTS lente CASCADE;
CREATE SCHEMA lente AUTHORIZATION lente_duenio;
SET search_path = lente, public;
SET ROLE lente_duenio;

-- ---------------------------------------------------------------------
-- PASO 1. TABLAS
-- ---------------------------------------------------------------------

-- 1. USUARIOS: administradores y profesores (los únicos que inician sesión)
CREATE TABLE usuarios (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  rol               varchar(15) NOT NULL CHECK (rol IN ('administrador','profesor')),
  nombre            varchar(120) NOT NULL,
  usuario           varchar(40) NOT NULL CHECK (usuario ~ '^[a-z0-9._-]{3,40}$'),
  clave_cifrada     text        NOT NULL,
  activo            boolean     NOT NULL DEFAULT true,
  debe_cambiar_clave boolean    NOT NULL DEFAULT true,
  intentos_fallidos smallint    NOT NULL DEFAULT 0,
  ultimo_ingreso    timestamptz,
  creado_en         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX usuarios_usuario_unico ON usuarios (lower(usuario));

-- 2. CURSOS: los cursos de cada profesor (un profesor puede tener varios)
CREATE TABLE cursos (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  profesor_id  bigint      NOT NULL REFERENCES usuarios(id),
  nombre       varchar(80) NOT NULL,            -- por ejemplo "7°B" o "Grupo de la tarde"
  institucion  varchar(120),
  anio         smallint    NOT NULL DEFAULT extract(year FROM now())::smallint,
  activo       boolean     NOT NULL DEFAULT true,
  creado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (profesor_id, nombre, anio)
);
CREATE INDEX cursos_por_profesor ON cursos(profesor_id);

-- 3. ESTUDIANTES: solo el nombre. No inician sesión.
--    También guarda sus puntos y su racha.
CREATE TABLE estudiantes (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  curso_id        bigint      NOT NULL REFERENCES cursos(id),
  nombre          varchar(80) NOT NULL CHECK (length(trim(nombre)) > 0),
  grado           smallint    CHECK (grado BETWEEN 3 AND 11),   -- vacío = "Sin grado"
  activo          boolean     NOT NULL DEFAULT true,
  puntos          integer     NOT NULL DEFAULT 0 CHECK (puntos >= 0),
  racha           smallint    NOT NULL DEFAULT 0,   -- días seguidos con actividad
  mejor_racha     smallint    NOT NULL DEFAULT 0,
  ultimo_dia      date,                              -- último día que hizo una actividad
  creado_en       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX estudiantes_por_curso ON estudiantes(curso_id);

-- 4. TEXTOS: la biblioteca de noticias y publicaciones de cada profesor.
--    Aquí también queda lo que preparó la IA y aprobó el profesor.
CREATE TABLE textos (
  id                 bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  profesor_id        bigint      NOT NULL REFERENCES usuarios(id),
  tipo               varchar(20) NOT NULL DEFAULT 'noticia'
                     CHECK (tipo IN ('noticia','publicacion','video','aportado_en_clase')),
  titulo             varchar(250) NOT NULL,
  cuerpo             text,              -- el texto original. Nunca se modifica.
  enlace             text,
  fuente             varchar(120),
  nota               varchar(300),      -- nota que se ve en la tarjeta
  estado             varchar(15) NOT NULL DEFAULT 'borrador'
                     CHECK (estado IN ('borrador','preparando','en_revision','aprobado','archivado')),
  -- Lo que prepara la IA y revisa el profesor:
  idea_principal     text,              -- respuesta esperada de macroestructura
  elementos_clave    text[] NOT NULL DEFAULT '{}',  -- lo que debe mencionar la idea principal
  consejo_macro      text,              -- "Para mejorar" de macroestructura
  consejo_super      text,              -- explicación del orden y lo que se omite
  consejo_micro      text,              -- "Para mejorar" de microestructura
  preparado_por_ia   boolean     NOT NULL DEFAULT false,
  aprobado_en        timestamptz,
  creado_en          timestamptz NOT NULL DEFAULT now(),
  CHECK (cuerpo IS NOT NULL OR enlace IS NOT NULL),
  -- Regla del SRS: ningún texto se aprueba sin idea principal
  CONSTRAINT aprobar_requiere_idea_principal CHECK (
    estado <> 'aprobado'
    OR (idea_principal IS NOT NULL AND length(trim(idea_principal)) > 0
        AND aprobado_en IS NOT NULL AND cuerpo IS NOT NULL))
);
CREATE INDEX textos_por_profesor ON textos(profesor_id, estado);

-- 5. TEXTOS DEL CURSO: qué textos están activos en cada curso.
--    Un mismo texto puede usarse en varios cursos del profesor.
CREATE TABLE textos_del_curso (
  curso_id     bigint      NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
  texto_id     bigint      NOT NULL REFERENCES textos(id) ON DELETE CASCADE,
  activo       boolean     NOT NULL DEFAULT true,
  activado_en  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (curso_id, texto_id)
);

-- 6. PREGUNTAS de superestructura de cada texto (con sus opciones)
CREATE TABLE preguntas (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  texto_id     bigint      NOT NULL REFERENCES textos(id) ON DELETE CASCADE,
  orden        smallint    NOT NULL,
  pregunta     varchar(300) NOT NULL,
  opciones     text[]      NOT NULL CHECK (array_length(opciones, 1) BETWEEN 2 AND 6),
  correcta     smallint    NOT NULL,      -- número de la opción correcta (1, 2, 3…)
  dificultad   smallint    NOT NULL DEFAULT 1 CHECK (dificultad BETWEEN 1 AND 3),
  CHECK (correcta BETWEEN 1 AND array_length(opciones, 1)),
  UNIQUE (texto_id, orden)
);

-- 7. PALABRAS CARGADAS: palabras con carga emocional de cada texto (microestructura)
CREATE TABLE palabras_cargadas (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  texto_id     bigint      NOT NULL REFERENCES textos(id) ON DELETE CASCADE,
  palabra      varchar(120) NOT NULL,
  tipo         varchar(20) NOT NULL CHECK (tipo IN ('adjetivo','verbo','expresion')),
  inicio       integer     NOT NULL CHECK (inicio >= 0),   -- posición en el texto
  fin          integer     NOT NULL,
  explicacion  text,
  CHECK (fin > inicio),
  UNIQUE (texto_id, inicio)
);

-- 8. RESALTADOS que hace el profesor en el modo explicación (videobeam)
CREATE TABLE resaltados (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  texto_id          bigint      NOT NULL REFERENCES textos(id) ON DELETE CASCADE,
  nivel             varchar(5)  NOT NULL CHECK (nivel IN ('macro','super','micro')),
  inicio            integer     NOT NULL CHECK (inicio >= 0),
  fin               integer     NOT NULL,
  fragmento         text        NOT NULL,
  explicacion       text,
  es_idea_principal boolean     NOT NULL DEFAULT false,
  creado_en         timestamptz NOT NULL DEFAULT now(),
  CHECK (fin > inicio)
);

-- 9. ACTIVIDADES: un estudiante analizando un texto.
--    Guarda en qué paso va, el resultado de cada nivel y los puntos.
CREATE TABLE actividades (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  estudiante_id    bigint      NOT NULL REFERENCES estudiantes(id),
  texto_id         bigint      NOT NULL REFERENCES textos(id),
  numero           smallint    NOT NULL DEFAULT 1,           -- 1, 2… si la repite
  estado           varchar(12) NOT NULL DEFAULT 'en_curso'
                   CHECK (estado IN ('en_curso','terminada','abandonada')),
  paso             varchar(10) NOT NULL DEFAULT 'macro'
                   CHECK (paso IN ('macro','super','micro','resultado')),
  grado            smallint,                                 -- grado que tenía al hacerla
  resultado_macro  numeric(3,2) CHECK (resultado_macro BETWEEN 0 AND 1),   -- 0 a 1
  resultado_super  numeric(3,2) CHECK (resultado_super BETWEEN 0 AND 1),
  resultado_micro  numeric(3,2) CHECK (resultado_micro BETWEEN 0 AND 1),
  puntos_ganados   integer     NOT NULL DEFAULT 0,
  animo            varchar(20) CHECK (animo IN ('motivacion_alta','neutral','requiere_apoyo')),
  iniciada_en      timestamptz NOT NULL DEFAULT now(),
  terminada_en     timestamptz,
  UNIQUE (estudiante_id, texto_id, numero)
);
CREATE INDEX actividades_por_estudiante ON actividades(estudiante_id, iniciada_en DESC);

-- 10. RESPUESTAS: todo lo que el estudiante envía.
--    macro : una fila con la idea principal que escribió (+ revisión de la IA)
--    super : una fila por pregunta
--    micro : una fila por cada palabra que marcó
CREATE TABLE respuestas (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actividad_id    bigint      NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
  nivel           varchar(5)  NOT NULL CHECK (nivel IN ('macro','super','micro')),
  codigo_envio    uuid        NOT NULL UNIQUE,   -- lo crea el navegador: evita duplicados sin conexión
  texto           text,                          -- macro: lo que escribió · micro: la palabra
  pregunta_id     bigint      REFERENCES preguntas(id),   -- super
  opcion_elegida  smallint,                               -- super
  inicio          integer,                                -- micro: posición de la palabra
  fin             integer,
  tipo_palabra    varchar(20) CHECK (tipo_palabra IN ('adjetivo','verbo','expresion')),
  es_correcta     boolean,
  -- Revisión de la IA (solo macro):
  estado_ia       varchar(12) CHECK (estado_ia IN ('pendiente','procesando','lista','fallida')),
  veredicto_ia    varchar(20) CHECK (veredicto_ia IN ('coincide','coincide_en_parte','por_mejorar')),
  faltantes_ia    text,
  explicacion_ia  text,
  cita_ia         text,
  cita_valida     boolean,       -- ¿la cita existe de verdad en el texto?
  tiempo_ia_ms    integer,
  enviada_en      timestamptz NOT NULL,          -- hora del celular / computador
  recibida_en     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT forma_de_la_respuesta CHECK (
       (nivel = 'macro' AND texto IS NOT NULL)
    OR (nivel = 'super' AND pregunta_id IS NOT NULL AND opcion_elegida IS NOT NULL)
    OR (nivel = 'micro' AND texto IS NOT NULL AND inicio IS NOT NULL AND fin > inicio))
);
CREATE INDEX respuestas_por_actividad ON respuestas(actividad_id, nivel);
CREATE UNIQUE INDEX una_idea_principal_por_actividad ON respuestas(actividad_id) WHERE nivel = 'macro';
CREATE UNIQUE INDEX una_respuesta_por_pregunta ON respuestas(actividad_id, pregunta_id) WHERE nivel = 'super';
CREATE UNIQUE INDEX una_marca_por_palabra ON respuestas(actividad_id, inicio) WHERE nivel = 'micro';

-- 11. COLA DE LA IA: trabajos pendientes para la IA.
--     La app deja el trabajo aquí y el programa de IA lo recoge.
CREATE TABLE cola_ia (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tarea            varchar(20) NOT NULL CHECK (tarea IN ('preparar_texto','revisar_idea','analizar_animo')),
  estado           varchar(12) NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente','procesando','lista','fallida')),
  prioridad        smallint    NOT NULL DEFAULT 5,   -- 1 = un estudiante está esperando
  texto_id         bigint      REFERENCES textos(id) ON DELETE CASCADE,
  respuesta_id     bigint      REFERENCES respuestas(id) ON DELETE CASCADE,
  actividad_id     bigint      REFERENCES actividades(id) ON DELETE CASCADE,
  intentos         smallint    NOT NULL DEFAULT 0,
  max_intentos     smallint    NOT NULL DEFAULT 3,
  disponible_desde timestamptz NOT NULL DEFAULT now(),
  tomado_en        timestamptz,          -- cuándo lo tomó el programa de IA
  ultimo_error     text,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  terminada_en     timestamptz,
  CHECK ((tarea = 'preparar_texto' AND texto_id IS NOT NULL)
      OR (tarea = 'revisar_idea'   AND respuesta_id IS NOT NULL)
      OR (tarea = 'analizar_animo' AND actividad_id IS NOT NULL))
);
CREATE INDEX cola_ia_pendientes ON cola_ia(prioridad, disponible_desde) WHERE estado = 'pendiente';

-- 12. ALERTAS de acompañamiento para el profesor (análisis de sentimientos)
CREATE TABLE alertas (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  estudiante_id  bigint      NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
  motivo         text        NOT NULL,
  atendida       boolean     NOT NULL DEFAULT false,
  nota_profesor  text,
  creada_en      timestamptz NOT NULL DEFAULT now(),
  atendida_en    timestamptz
);
CREATE UNIQUE INDEX una_alerta_abierta_por_estudiante ON alertas(estudiante_id) WHERE NOT atendida;

-- 13. LOGROS que se pueden ganar
CREATE TABLE logros (
  id           smallint    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre       varchar(60) NOT NULL UNIQUE,
  descripcion  varchar(160) NOT NULL,
  regla        varchar(25) NOT NULL
               CHECK (regla IN ('actividades_terminadas','racha','micro_perfecto','idea_correcta','nivel')),
  meta         smallint    NOT NULL DEFAULT 1,
  activo       boolean     NOT NULL DEFAULT true
);

-- 14. LOGROS GANADOS por cada estudiante
CREATE TABLE logros_ganados (
  estudiante_id bigint     NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
  logro_id     smallint    NOT NULL REFERENCES logros(id),
  ganado_en    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (estudiante_id, logro_id)
);

-- 15. AJUSTES: reglas que se cambian sin tocar código.
--     Si curso_id está vacío, es el valor GENERAL (para todos los cursos).
--     Si tiene un curso, es un valor PROPIO de ese curso y reemplaza al general.
CREATE TABLE ajustes (
  id              integer     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clave           varchar(60) NOT NULL,
  curso_id        bigint      REFERENCES cursos(id) ON DELETE CASCADE,  -- vacío = general
  valor           jsonb       NOT NULL,
  descripcion     text        NOT NULL,
  actualizado_por bigint      REFERENCES usuarios(id),                  -- quién lo cambió
  actualizado_en  timestamptz NOT NULL DEFAULT now()
);
-- Un solo valor general por clave, y un solo valor por clave en cada curso
-- (dos índices para que funcione también en PostgreSQL 14)
CREATE UNIQUE INDEX un_valor_general_por_clave ON ajustes(clave) WHERE curso_id IS NULL;
CREATE UNIQUE INDEX un_valor_por_clave_y_curso ON ajustes(clave, curso_id) WHERE curso_id IS NOT NULL;

-- Un valor propio de un curso solo puede existir si hay un valor general con esa clave
CREATE FUNCTION al_guardar_ajuste() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.actualizado_en := now();
  IF NEW.curso_id IS NOT NULL AND NOT EXISTS
     (SELECT 1 FROM lente.ajustes WHERE clave = NEW.clave AND curso_id IS NULL) THEN
    RAISE EXCEPTION 'No existe el ajuste general "%"', NEW.clave;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ajuste_guardar BEFORE INSERT OR UPDATE ON ajustes
  FOR EACH ROW EXECUTE FUNCTION al_guardar_ajuste();

-- ---------------------------------------------------------------------
-- PASO 2. FUNCIONES DE APOYO
-- ---------------------------------------------------------------------

-- Lee un ajuste: el valor propio del curso si existe; si no, el general
CREATE FUNCTION ajuste(p_clave text, p_curso bigint DEFAULT NULL) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = lente, public AS $$
  SELECT valor FROM ajustes
   WHERE clave = p_clave AND (curso_id = p_curso OR curso_id IS NULL)
   ORDER BY curso_id NULLS LAST LIMIT 1
$$;

-- Quita tildes, mayúsculas y signos para comparar palabras
CREATE FUNCTION normalizar(p text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(public.unaccent('public.unaccent', p), '[«»"“”.,;:()¿?¡!]', '', 'g'))
$$;

-- Primaria (3° a 5°), secundaria (6° a 9°) o media (10° y 11°)
CREATE FUNCTION nivel_escolar(p_grado smallint) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN p_grado IS NULL THEN 'media'
              WHEN p_grado <= 5 THEN 'primaria'
              WHEN p_grado <= 9 THEN 'secundaria' ELSE 'media' END
$$;

-- Hasta qué dificultad de pregunta ve cada nivel escolar
CREATE FUNCTION dificultad_maxima(p_grado smallint) RETURNS smallint LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE lente.nivel_escolar(p_grado) WHEN 'primaria' THEN 1 WHEN 'secundaria' THEN 2 ELSE 3 END::smallint
$$;

-- ---------------------------------------------------------------------
-- PASO 3. REGLAS AUTOMÁTICAS (triggers)
-- ---------------------------------------------------------------------

-- 3.1 Al pedir que la IA prepare un texto, se deja el trabajo en la cola
CREATE FUNCTION al_cambiar_texto() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado = 'preparando' AND (TG_OP = 'INSERT' OR OLD.estado <> 'preparando') THEN
    IF NEW.cuerpo IS NULL THEN
      RAISE EXCEPTION 'El texto % no tiene cuerpo: no se puede preparar con IA', NEW.id;
    END IF;
    INSERT INTO lente.cola_ia(tarea, prioridad, texto_id) VALUES ('preparar_texto', 5, NEW.id);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER texto_preparar AFTER INSERT OR UPDATE OF estado ON textos
  FOR EACH ROW EXECUTE FUNCTION al_cambiar_texto();

-- 3.2a Solo se activa en un curso un texto APROBADO del mismo profesor
CREATE FUNCTION al_activar_texto() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_prof_curso bigint; v_prof_txt bigint; v_estado text;
BEGIN
  SELECT profesor_id INTO v_prof_curso FROM lente.cursos WHERE id = NEW.curso_id;
  SELECT profesor_id, estado INTO v_prof_txt, v_estado FROM lente.textos WHERE id = NEW.texto_id;
  IF v_estado IS DISTINCT FROM 'aprobado' THEN
    RAISE EXCEPTION 'El texto % no está aprobado: no se puede activar', NEW.texto_id;
  END IF;
  IF v_prof_curso IS DISTINCT FROM v_prof_txt THEN
    RAISE EXCEPTION 'El texto % no es del profesor de este curso', NEW.texto_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER texto_activar BEFORE INSERT OR UPDATE ON textos_del_curso
  FOR EACH ROW EXECUTE FUNCTION al_activar_texto();

-- 3.2b Una actividad solo se abre con un texto ACTIVO en el curso del estudiante
CREATE FUNCTION al_abrir_actividad() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_curso bigint; v_activo boolean; v_grado smallint;
BEGIN
  SELECT curso_id, activo, grado INTO v_curso, v_activo, v_grado
    FROM lente.estudiantes WHERE id = NEW.estudiante_id;
  IF NOT v_activo THEN
    RAISE EXCEPTION 'El estudiante % está desactivado', NEW.estudiante_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM lente.textos_del_curso
                  WHERE curso_id = v_curso AND texto_id = NEW.texto_id AND activo) THEN
    RAISE EXCEPTION 'El texto % no está activo en el curso del estudiante', NEW.texto_id;
  END IF;
  NEW.grado := v_grado;
  SELECT coalesce(max(numero), 0) + 1 INTO NEW.numero FROM lente.actividades
   WHERE estudiante_id = NEW.estudiante_id AND texto_id = NEW.texto_id;
  RETURN NEW;
END $$;
CREATE TRIGGER actividad_abrir BEFORE INSERT ON actividades
  FOR EACH ROW EXECUTE FUNCTION al_abrir_actividad();

-- 3.3 Al recibir una respuesta:
--     super → se califica con la opción correcta (sin IA)
--     micro → se compara con las palabras cargadas (sin IA)
--     macro → queda pendiente y se manda a la IA
CREATE FUNCTION al_recibir_respuesta() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_texto bigint; v_correcta smallint; v_texto_preg bigint;
BEGIN
  SELECT texto_id INTO v_texto FROM lente.actividades WHERE id = NEW.actividad_id;
  IF NEW.nivel = 'super' THEN
    SELECT correcta, texto_id INTO v_correcta, v_texto_preg FROM lente.preguntas WHERE id = NEW.pregunta_id;
    IF v_texto_preg IS DISTINCT FROM v_texto THEN
      RAISE EXCEPTION 'La pregunta % no es de este texto', NEW.pregunta_id;
    END IF;
    NEW.es_correcta := (NEW.opcion_elegida = v_correcta);
  ELSIF NEW.nivel = 'micro' THEN
    NEW.es_correcta := EXISTS (
      SELECT 1 FROM lente.palabras_cargadas p
       WHERE p.texto_id = v_texto
         AND (int4range(p.inicio, p.fin) && int4range(NEW.inicio, NEW.fin)
              OR lente.normalizar(p.palabra) = lente.normalizar(NEW.texto)));
  ELSE
    NEW.estado_ia := 'pendiente';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER respuesta_calificar BEFORE INSERT ON respuestas
  FOR EACH ROW EXECUTE FUNCTION al_recibir_respuesta();

CREATE FUNCTION despues_de_respuesta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.nivel = 'macro' THEN
    INSERT INTO lente.cola_ia(tarea, prioridad, respuesta_id, max_intentos)
    VALUES ('revisar_idea', 1, NEW.id, 2);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER respuesta_a_la_ia AFTER INSERT ON respuestas
  FOR EACH ROW EXECUTE FUNCTION despues_de_respuesta();

-- 3.4 Cuando la IA guarda el ánimo de una actividad, se revisa si hay
--     que avisar al profesor (N veces seguidas "requiere apoyo")
CREATE FUNCTION al_guardar_animo() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
DECLARE v_umbral int; v_seguidas int;
BEGIN
  v_umbral := coalesce((ajuste('alerta_veces_seguidas',
                (SELECT curso_id FROM estudiantes WHERE id = NEW.estudiante_id)))::int, 3);
  IF NEW.animo IS DISTINCT FROM 'requiere_apoyo' THEN RETURN NEW; END IF;
  -- cuenta las últimas actividades seguidas con "requiere_apoyo"
  SELECT count(*) INTO v_seguidas FROM (
    SELECT animo, count(*) FILTER (WHERE animo <> 'requiere_apoyo')
                  OVER (ORDER BY terminada_en DESC, id DESC) AS cortes
      FROM actividades WHERE estudiante_id = NEW.estudiante_id AND animo IS NOT NULL) x
   WHERE cortes = 0;
  IF v_seguidas >= v_umbral
     AND NOT EXISTS (SELECT 1 FROM alertas WHERE estudiante_id = NEW.estudiante_id AND NOT atendida) THEN
    INSERT INTO alertas(estudiante_id, motivo)
    VALUES (NEW.estudiante_id, v_seguidas || ' actividades seguidas con señales de que podría necesitar acompañamiento.');
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER actividad_animo AFTER UPDATE OF animo ON actividades
  FOR EACH ROW EXECUTE FUNCTION al_guardar_animo();

-- ---------------------------------------------------------------------
-- PASO 4. FUNCIONES QUE LLAMA LA APLICACIÓN
-- ---------------------------------------------------------------------

-- 4.1 Iniciar sesión. Devuelve el usuario si la clave es correcta.
CREATE FUNCTION iniciar_sesion(p_usuario text, p_clave text)
RETURNS TABLE (id bigint, rol varchar, nombre varchar, debe_cambiar_clave boolean)
LANGUAGE plpgsql AS $$
#variable_conflict use_column
DECLARE u lente.usuarios;
BEGIN
  SELECT * INTO u FROM lente.usuarios x WHERE lower(x.usuario) = lower(trim(p_usuario));
  IF NOT FOUND OR NOT u.activo OR u.intentos_fallidos >= 5 THEN RETURN; END IF;
  IF u.clave_cifrada = public.crypt(p_clave, u.clave_cifrada) THEN
    UPDATE lente.usuarios x SET ultimo_ingreso = now(), intentos_fallidos = 0 WHERE x.id = u.id;
    RETURN QUERY SELECT u.id, u.rol, u.nombre, u.debe_cambiar_clave;
  ELSE
    UPDATE lente.usuarios x SET intentos_fallidos = x.intentos_fallidos + 1 WHERE x.id = u.id;
  END IF;
END $$;

-- 4.2 Terminar la actividad: calcula resultados, puntos, racha y logros,
--     y deja el análisis de ánimo en la cola de la IA.
--     Se llama cuando el estudiante pulsa "Ver mi resultado".
CREATE FUNCTION terminar_actividad(p_actividad bigint)
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

-- ---------------------------------------------------------------------
-- PASO 5. FUNCIONES QUE USA EL PROGRAMA DE IA
--         (corren con permisos del dueño: así el programa de IA no
--          necesita ver la tabla de estudiantes)
-- ---------------------------------------------------------------------

-- 5.1 Tomar el siguiente trabajo de la cola (el más urgente primero).
--     Si hay varios programas de IA, nunca toman el mismo trabajo.
--     Antes, recupera los trabajos que quedaron en "procesando" porque el
--     programa de IA se detuvo a mitad (reinicio, corte de luz): se tratan
--     como un error, así que se reintentan o, sin intentos, se marcan fallidos.
CREATE FUNCTION tomar_trabajo_ia() RETURNS SETOF cola_ia
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

-- 5.2 Guardar la revisión de la idea principal.
--     Se comprueba que la cita exista en el texto; si no, no se muestra.
CREATE FUNCTION guardar_revision_idea(p_trabajo bigint, p_veredicto text, p_faltantes text,
                                      p_explicacion text, p_cita text, p_tiempo_ms int)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
DECLARE v_resp bigint; v_cuerpo text; v_ok boolean;
BEGIN
  SELECT respuesta_id INTO v_resp FROM cola_ia WHERE id = p_trabajo AND tarea = 'revisar_idea';
  IF v_resp IS NULL THEN RAISE EXCEPTION 'El trabajo % no es una revisión de idea', p_trabajo; END IF;
  SELECT t.cuerpo INTO v_cuerpo FROM respuestas r
    JOIN actividades a ON a.id = r.actividad_id JOIN textos t ON t.id = a.texto_id
   WHERE r.id = v_resp;
  v_ok := coalesce(length(trim(p_cita)) > 0, false)
          AND position(normalizar(trim(p_cita)) IN normalizar(v_cuerpo)) > 0;
  UPDATE respuestas SET estado_ia = 'lista', veredicto_ia = p_veredicto, faltantes_ia = p_faltantes,
         explicacion_ia = CASE WHEN v_ok THEN p_explicacion END,
         cita_ia = CASE WHEN v_ok THEN p_cita END, cita_valida = v_ok,
         es_correcta = (p_veredicto = 'coincide'), tiempo_ia_ms = p_tiempo_ms
   WHERE id = v_resp;
  UPDATE cola_ia SET estado = 'lista', terminada_en = now() WHERE id = p_trabajo;
  RETURN v_ok;
END $$;

-- 5.3 Guardar el ánimo de una actividad (clasificador de sentimientos)
CREATE FUNCTION guardar_animo(p_trabajo bigint, p_animo text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
BEGIN
  UPDATE actividades SET animo = p_animo
   WHERE id = (SELECT actividad_id FROM cola_ia WHERE id = p_trabajo AND tarea = 'analizar_animo');
  UPDATE cola_ia SET estado = 'lista', terminada_en = now() WHERE id = p_trabajo;
END $$;

-- 5.4 Marcar el texto como preparado (después de guardar preguntas y palabras)
CREATE FUNCTION terminar_preparacion(p_trabajo bigint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
BEGIN
  UPDATE textos SET estado = 'en_revision', preparado_por_ia = true
   WHERE id = (SELECT texto_id FROM cola_ia WHERE id = p_trabajo AND tarea = 'preparar_texto');
  UPDATE cola_ia SET estado = 'lista', terminada_en = now() WHERE id = p_trabajo;
END $$;

-- 5.5 Reportar un error. Se reintenta más tarde; si se acaban los intentos:
--     · revisar_idea   → se muestra solo la idea principal aprobada
--     · preparar_texto → el texto vuelve a borrador para hacerlo a mano
CREATE FUNCTION reportar_error_ia(p_trabajo bigint, p_error text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = lente, public AS $$
DECLARE c cola_ia;
BEGIN
  SELECT * INTO c FROM cola_ia WHERE id = p_trabajo FOR UPDATE;
  IF c.intentos < c.max_intentos THEN
    UPDATE cola_ia SET estado = 'pendiente', ultimo_error = p_error,
           disponible_desde = now() + make_interval(secs => 5 * c.intentos) WHERE id = p_trabajo;
    RETURN;
  END IF;
  UPDATE cola_ia SET estado = 'fallida', ultimo_error = p_error, terminada_en = now() WHERE id = p_trabajo;
  IF c.tarea = 'revisar_idea' THEN
    UPDATE respuestas SET estado_ia = 'fallida', veredicto_ia = 'por_mejorar' WHERE id = c.respuesta_id;
  ELSIF c.tarea = 'preparar_texto' THEN
    UPDATE textos SET estado = 'borrador', nota = 'La IA no pudo prepararlo. Complételo a mano.'
     WHERE id = c.texto_id;
  END IF;
END $$;

-- 5.6 Marcar como abandonadas las actividades sin movimiento (RF-21: "abandono
--     anticipado"). Cuenta desde la última respuesta; el plazo es el ajuste
--     horas_para_abandono del curso. Si el estudiante alcanzó a responder algo,
--     se pide el análisis de ánimo con esa señal. Lo llama el programa de IA.
CREATE FUNCTION marcar_abandonadas() RETURNS integer
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

-- ---------------------------------------------------------------------
-- PASO 6. VISTAS (consultas listas para cada pantalla)
-- ---------------------------------------------------------------------

-- "Mi curso" y lista del administrador
CREATE VIEW vista_estudiantes AS
SELECT s.id, s.nombre, s.curso_id, c.nombre AS curso, c.profesor_id, p.nombre AS profesor,
       s.grado, CASE WHEN s.grado IS NULL THEN 'Sin grado' ELSE s.grado || '°' END AS grado_texto,
       nivel_escolar(s.grado) AS nivel_escolar,
       CASE WHEN NOT s.activo THEN 'Inactivo' WHEN s.grado IS NULL THEN 'Sin grado' ELSE 'Activo' END AS estado,
       s.puntos,
       s.puntos / coalesce((ajuste('puntos_por_nivel', s.curso_id))::int, 100) + 1 AS nivel,
       s.racha, s.mejor_racha
  FROM estudiantes s JOIN cursos c ON c.id = s.curso_id JOIN usuarios p ON p.id = c.profesor_id;

-- Indicadores del administrador y su tabla de profesores
CREATE VIEW vista_profesores AS
SELECT u.id, u.nombre, u.usuario, u.activo, u.ultimo_ingreso,
       (SELECT count(*) FROM cursos c WHERE c.profesor_id = u.id AND c.activo) AS cursos,
       (SELECT count(*) FROM estudiantes s JOIN cursos c ON c.id = s.curso_id
         WHERE c.profesor_id = u.id AND s.activo) AS estudiantes
  FROM usuarios u WHERE u.rol = 'profesor';

-- Historial de respuestas (una fila por pregunta)
CREATE VIEW vista_historial AS
SELECT a.estudiante_id, a.id AS actividad_id, t.titulo, r.recibida_en AS fecha, r.nivel,
       CASE r.nivel WHEN 'macro' THEN '¿Cuál es la idea principal?'
                    WHEN 'super' THEN q.pregunta
                    ELSE 'Palabras con carga emocional' END AS pregunta,
       CASE r.nivel WHEN 'super' THEN q.opciones[r.opcion_elegida] ELSE r.texto END AS respuesta,
       CASE r.nivel WHEN 'macro' THEN t.idea_principal
                    WHEN 'super' THEN q.opciones[q.correcta]
                    ELSE (SELECT string_agg(p.palabra, ', ' ORDER BY p.inicio)
                            FROM palabras_cargadas p WHERE p.texto_id = t.id) END AS respuesta_esperada,
       CASE r.nivel WHEN 'macro' THEN coalesce(r.veredicto_ia, r.estado_ia)
                    ELSE CASE WHEN r.es_correcta THEN 'correcta' ELSE 'incorrecta' END END AS resultado,
       r.es_correcta
  FROM respuestas r JOIN actividades a ON a.id = r.actividad_id
  JOIN textos t ON t.id = a.texto_id LEFT JOIN preguntas q ON q.id = r.pregunta_id;

-- Progreso individual: totales y porcentaje por nivel
CREATE VIEW vista_progreso AS
SELECT s.id AS estudiante_id,
       (SELECT count(*) FROM actividades a WHERE a.estudiante_id = s.id AND a.estado = 'terminada') AS actividades_hechas,
       (SELECT count(*) FROM textos_del_curso tc WHERE tc.curso_id = s.curso_id AND tc.activo
          AND NOT EXISTS (SELECT 1 FROM actividades a WHERE a.texto_id = tc.texto_id
                            AND a.estudiante_id = s.id AND a.estado = 'terminada')) AS actividades_pendientes,
       count(h.*)                                       AS preguntas_respondidas,
       count(h.*) FILTER (WHERE h.es_correcta)          AS correctas,
       count(h.*) FILTER (WHERE h.es_correcta IS FALSE) AS incorrectas,
       round(100.0 * count(h.*) FILTER (WHERE h.es_correcta) / nullif(count(h.*), 0)) AS porcentaje_acierto,
       (SELECT round(100 * avg(resultado_macro)) FROM actividades a WHERE a.estudiante_id = s.id) AS porcentaje_macro,
       (SELECT round(100 * avg(resultado_super)) FROM actividades a WHERE a.estudiante_id = s.id) AS porcentaje_super,
       (SELECT round(100 * avg(resultado_micro)) FROM actividades a WHERE a.estudiante_id = s.id) AS porcentaje_micro
  FROM estudiantes s LEFT JOIN vista_historial h ON h.estudiante_id = s.id
 GROUP BY s.id, s.curso_id;

-- Último ánimo registrado de un estudiante (para el clima del curso)
CREATE FUNCTION ultimo_animo(p_estudiante bigint) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = lente, public AS $$
  SELECT animo FROM lente.actividades WHERE estudiante_id = p_estudiante AND animo IS NOT NULL
   ORDER BY terminada_en DESC LIMIT 1
$$;

-- Panel del docente (un panel por curso)
CREATE VIEW vista_panel AS
SELECT c.id AS curso_id, c.nombre AS curso, c.profesor_id,
       count(s.id) FILTER (WHERE s.activo)                                  AS estudiantes_activos,
       count(s.id) FILTER (WHERE s.activo AND s.ultimo_dia IS NOT NULL)     AS participaron,
       (SELECT round(avg(p.porcentaje_acierto)) FROM vista_progreso p
          JOIN estudiantes x ON x.id = p.estudiante_id WHERE x.curso_id = c.id) AS acierto_promedio,
       coalesce(sum(s.puntos) FILTER (WHERE s.activo), 0)                   AS puntos_del_curso,
       coalesce(max(s.mejor_racha), 0)                                      AS racha_mas_larga,
       count(s.id) FILTER (WHERE s.activo AND ultimo_animo(s.id) = 'motivacion_alta') AS animo_alto,
       count(s.id) FILTER (WHERE s.activo AND ultimo_animo(s.id) = 'neutral')         AS animo_neutral,
       count(s.id) FILTER (WHERE s.activo AND ultimo_animo(s.id) = 'requiere_apoyo')  AS animo_requiere_apoyo
  FROM cursos c LEFT JOIN estudiantes s ON s.curso_id = c.id
 GROUP BY c.id, c.nombre, c.profesor_id;

-- Lo que ve el programa de IA. NUNCA incluye el nombre del estudiante.
CREATE VIEW ia_textos AS
SELECT c.id AS trabajo_id, t.id AS texto_id, t.titulo, t.cuerpo
  FROM cola_ia c JOIN textos t ON t.id = c.texto_id
 WHERE c.tarea = 'preparar_texto' AND c.estado = 'procesando';

CREATE VIEW ia_ideas AS
SELECT c.id AS trabajo_id, t.cuerpo AS texto, t.idea_principal, t.elementos_clave,
       r.texto AS respuesta_estudiante, nivel_escolar(a.grado) AS nivel_escolar
  FROM cola_ia c JOIN respuestas r ON r.id = c.respuesta_id
  JOIN actividades a ON a.id = r.actividad_id JOIN textos t ON t.id = a.texto_id
 WHERE c.tarea = 'revisar_idea' AND c.estado = 'procesando';

CREATE VIEW ia_animo AS
SELECT c.id AS trabajo_id,
       (SELECT r.texto FROM respuestas r WHERE r.actividad_id = a.id AND r.nivel = 'macro') AS respuesta_abierta,
       a.resultado_macro, a.resultado_super, a.resultado_micro,
       extract(epoch FROM a.terminada_en - a.iniciada_en)::int AS segundos,
       a.estado = 'abandonada' AS abandonada,
       a.paso
  FROM cola_ia c JOIN actividades a ON a.id = c.actividad_id
 WHERE c.tarea = 'analizar_animo' AND c.estado = 'procesando';

-- ---------------------------------------------------------------------
-- PASO 6B. PERMISOS
-- ---------------------------------------------------------------------
RESET ROLE;
GRANT USAGE ON SCHEMA lente TO lente_app, lente_ia;

-- La aplicación: lee y escribe datos, pero no puede cambiar la estructura
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA lente TO lente_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lente TO lente_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA lente TO lente_app;

-- El programa de IA: solo las vistas ia_* y lo que necesita escribir
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA lente FROM PUBLIC;
-- Las funciones de solo lectura que usan las vistas sí quedan para todos
GRANT EXECUTE ON FUNCTION ajuste(text, bigint), normalizar(text), nivel_escolar(smallint),
      dificultad_maxima(smallint), ultimo_animo(bigint) TO PUBLIC;
GRANT EXECUTE ON FUNCTION ajuste(text, bigint), normalizar(text), nivel_escolar(smallint),
      tomar_trabajo_ia(), guardar_revision_idea(bigint,text,text,text,text,int),
      guardar_animo(bigint,text), terminar_preparacion(bigint), reportar_error_ia(bigint,text),
      marcar_abandonadas()
      TO lente_ia;
GRANT SELECT ON ia_textos, ia_ideas, ia_animo, ajustes TO lente_ia;
GRANT SELECT, INSERT, UPDATE, DELETE ON preguntas, palabras_cargadas TO lente_ia;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lente TO lente_ia;
GRANT UPDATE (idea_principal, elementos_clave, consejo_macro, consejo_super, consejo_micro) ON textos TO lente_ia;
GRANT SELECT (id) ON textos TO lente_ia;

ALTER ROLE lente_app SET search_path = lente, public;
ALTER ROLE lente_ia  SET search_path = lente, public;
SET ROLE lente_duenio;

-- ---------------------------------------------------------------------
-- PASO 6C. AJUSTES Y LOGROS INICIALES (necesarios para que la app funcione)
-- ---------------------------------------------------------------------
INSERT INTO ajustes(clave, valor, descripcion) VALUES
 ('puntos_por_acierto',       '20',  'Puntos por cada nivel hecho al 100 % (el control deslizante del panel)'),
 ('puntos_por_terminar',      '5',   'Puntos extra por terminar la actividad'),
 ('puntos_por_nivel',         '100', 'Puntos necesarios para subir de nivel'),
 ('nombres_de_niveles',       '["Curioso","Lector","Lector atento","Analista","Analista crítico","Maestro del discurso"]', 'Nombre de cada nivel'),
 ('minimo_para_logrado',      '0.6', 'Desde qué resultado (0 a 1) un nivel se muestra como "Logrado"'),
 ('descuento_palabra_neutra', '0.5', 'Cuánto resta marcar una palabra que no es cargada'),
 ('alerta_veces_seguidas',    '3',   'Veces seguidas con "requiere apoyo" para avisar al profesor (por validar)'),
 ('horas_para_abandono',      '3',   'Horas sin respuestas para dar una actividad por abandonada'),
 ('ia_modelo',                '"qwen3:14b"', 'Modelo de lenguaje en Ollama'),
 ('ia_direccion',             '"http://VM-IA:11434/api/chat"', 'Dirección interna de Ollama'),
 ('ia_tiempo_maximo_seg',     '15',  'Tiempo máximo para revisar la idea principal'),
 ('ia_instrucciones_preparar', to_jsonb('Analiza SOLO el texto según van Dijk. Devuelve JSON con: idea_principal, elementos_clave, palabras (texto literal, tipo adjetivo|verbo|expresion, explicacion), preguntas (pregunta, opciones, correcta, dificultad 1-3), consejo_macro, consejo_super, consejo_micro. No inventes información.'::text), 'Instrucciones (prompt) para preparar un texto'),
 ('ia_instrucciones_revisar',  to_jsonb('Compara la respuesta del estudiante con la idea principal aprobada. Usa SOLO el texto. Devuelve JSON: veredicto (coincide|coincide_en_parte|por_mejorar), faltantes, explicacion, cita (fragmento LITERAL del texto).'::text), 'Instrucciones (prompt) para revisar la idea principal');

INSERT INTO logros(nombre, descripcion, regla, meta) VALUES
 ('Primer análisis',  'Completa tu primera actividad', 'actividades_terminadas', 1),
 ('Racha de 3 días',  'Participa tres días seguidos',  'racha', 3),
 ('Ojo de águila',    '100 % en lenguaje',             'micro_perfecto', 1),
 ('Detective',        'Idea principal correcta',       'idea_correcta', 1),
 ('Constante',        'Cinco actividades',             'actividades_terminadas', 5),
 ('Analista',         'Llega al nivel 5',              'nivel', 5);

-- =====================================================================
-- PASO 7. PRIMER ADMINISTRADOR (necesario para poder entrar a la app)
-- ---------------------------------------------------------------------
--  Sin al menos un administrador nadie podría iniciar sesión ni crear
--  las cuentas de los profesores. Cambie la contraseña temporal antes de
--  ejecutar el script: la app le pedirá cambiarla al primer ingreso.
-- =====================================================================
INSERT INTO usuarios(rol, nombre, usuario, clave_cifrada, debe_cambiar_clave)
VALUES ('administrador', 'Administrador', 'admin',
        public.crypt('CAMBIE_ESTA_CLAVE', public.gen_salt('bf', 10)), true);

RESET ROLE;

-- ---------------------------------------------------------------------
-- PASO 8. DICCIONARIO DE DATOS DENTRO DE LA BASE (\d+ lente.textos lo muestra)
-- ---------------------------------------------------------------------
SET ROLE lente_duenio;
COMMENT ON TABLE usuarios IS 'Las personas que inician sesión: administradores y profesores.';
COMMENT ON COLUMN usuarios.id IS 'Número que identifica al usuario.';
COMMENT ON COLUMN usuarios.rol IS '"administrador" o "profesor".';
COMMENT ON COLUMN usuarios.nombre IS 'Nombre completo.';
COMMENT ON COLUMN usuarios.usuario IS 'Nombre para iniciar sesión.';
COMMENT ON COLUMN usuarios.clave_cifrada IS 'La contraseña cifrada. Nunca se guarda la contraseña real.';
COMMENT ON COLUMN usuarios.activo IS 'Si la cuenta está activa o desactivada.';
COMMENT ON COLUMN usuarios.debe_cambiar_clave IS 'Sí, cuando tiene una contraseña temporal.';
COMMENT ON COLUMN usuarios.intentos_fallidos IS 'Intentos fallidos seguidos; con 5 se bloquea.';
COMMENT ON COLUMN usuarios.ultimo_ingreso IS 'Última vez que entró.';
COMMENT ON COLUMN usuarios.creado_en IS 'Cuándo se creó la cuenta.';
COMMENT ON TABLE cursos IS 'Los cursos de cada profesor. Un profesor puede tener varios.';
COMMENT ON COLUMN cursos.id IS 'Número que identifica el curso.';
COMMENT ON COLUMN cursos.profesor_id IS 'Profesor del curso. Cada profesor solo ve sus cursos.';
COMMENT ON COLUMN cursos.nombre IS 'Nombre del curso (por ejemplo, 7°B).';
COMMENT ON COLUMN cursos.institucion IS 'Colegio.';
COMMENT ON COLUMN cursos.anio IS 'Año escolar.';
COMMENT ON COLUMN cursos.activo IS 'Si el curso está activo.';
COMMENT ON COLUMN cursos.creado_en IS 'Cuándo se creó.';
COMMENT ON TABLE estudiantes IS 'Los estudiantes de cada curso. Solo se guarda el nombre; no inician sesión. Aquí van también sus puntos y su racha.';
COMMENT ON COLUMN estudiantes.id IS 'Número que identifica al estudiante.';
COMMENT ON COLUMN estudiantes.curso_id IS 'Su curso (y por el curso, su profesor). Cada profesor solo ve a los suyos.';
COMMENT ON COLUMN estudiantes.nombre IS 'Nombre del estudiante (único dato personal).';
COMMENT ON COLUMN estudiantes.grado IS 'Grado de 3 a 11. Vacío = "Sin grado". Cambia cómo ve la actividad.';
COMMENT ON COLUMN estudiantes.activo IS 'Si está activo o desactivado.';
COMMENT ON COLUMN estudiantes.puntos IS 'Puntos acumulados. El nivel sale de aquí (un nivel cada 100 puntos).';
COMMENT ON COLUMN estudiantes.racha IS 'Días seguidos con actividad.';
COMMENT ON COLUMN estudiantes.mejor_racha IS 'La racha más larga que ha tenido.';
COMMENT ON COLUMN estudiantes.ultimo_dia IS 'Último día en que hizo una actividad.';
COMMENT ON COLUMN estudiantes.creado_en IS 'Cuándo se registró.';
COMMENT ON TABLE textos IS 'La biblioteca de noticias y publicaciones de cada profesor, junto con lo que preparó la IA y aprobó el profesor.';
COMMENT ON COLUMN textos.id IS 'Número que identifica el texto.';
COMMENT ON COLUMN textos.profesor_id IS 'Profesor que lo subió.';
COMMENT ON COLUMN textos.tipo IS 'noticia, publicacion, video o aportado_en_clase.';
COMMENT ON COLUMN textos.titulo IS 'Titular.';
COMMENT ON COLUMN textos.cuerpo IS 'El texto completo. Nunca se modifica.';
COMMENT ON COLUMN textos.enlace IS 'Enlace, si se aportó como link.';
COMMENT ON COLUMN textos.fuente IS 'Medio que lo publicó.';
COMMENT ON COLUMN textos.nota IS 'Nota que se ve en la tarjeta del texto.';
COMMENT ON COLUMN textos.estado IS 'borrador → preparando (IA) → en_revision (profesor) → aprobado → archivado. Se activa por curso en textos_del_curso.';
COMMENT ON COLUMN textos.idea_principal IS 'Respuesta esperada de la idea principal. Sin ella el texto no se puede aprobar.';
COMMENT ON COLUMN textos.elementos_clave IS 'Lo que debe mencionar una buena idea principal.';
COMMENT ON COLUMN textos.consejo_macro IS 'Consejo "Para mejorar" de la idea principal.';
COMMENT ON COLUMN textos.consejo_super IS 'Explicación de cómo se ordena la información y qué se omite.';
COMMENT ON COLUMN textos.consejo_micro IS 'Consejo "Para mejorar" de las palabras.';
COMMENT ON COLUMN textos.preparado_por_ia IS 'Sí, si lo preparó la IA.';
COMMENT ON COLUMN textos.aprobado_en IS 'Cuándo lo aprobó el profesor.';
COMMENT ON COLUMN textos.creado_en IS 'Cuándo se subió.';
COMMENT ON TABLE textos_del_curso IS 'Qué textos están activos en cada curso. Un mismo texto puede usarse en varios cursos.';
COMMENT ON COLUMN textos_del_curso.curso_id IS 'Curso.';
COMMENT ON COLUMN textos_del_curso.texto_id IS 'Texto activado en ese curso (debe estar aprobado).';
COMMENT ON COLUMN textos_del_curso.activo IS 'Si sigue disponible para los estudiantes del curso.';
COMMENT ON COLUMN textos_del_curso.activado_en IS 'Cuándo se activó.';
COMMENT ON TABLE preguntas IS 'Las preguntas de superestructura de cada texto, con sus opciones.';
COMMENT ON COLUMN preguntas.id IS 'Número de la pregunta.';
COMMENT ON COLUMN preguntas.texto_id IS 'Texto al que pertenece.';
COMMENT ON COLUMN preguntas.orden IS 'Orden en que aparece.';
COMMENT ON COLUMN preguntas.pregunta IS 'La pregunta.';
COMMENT ON COLUMN preguntas.opciones IS 'Lista de opciones de respuesta.';
COMMENT ON COLUMN preguntas.correcta IS 'Cuál opción es la correcta (1, 2, 3…).';
COMMENT ON COLUMN preguntas.dificultad IS '1, 2 o 3. Primaria ve la 1; secundaria, hasta la 2; media, todas.';
COMMENT ON TABLE palabras_cargadas IS 'Las palabras con carga emocional de cada texto (microestructura).';
COMMENT ON COLUMN palabras_cargadas.id IS 'Número de la palabra.';
COMMENT ON COLUMN palabras_cargadas.texto_id IS 'Texto al que pertenece.';
COMMENT ON COLUMN palabras_cargadas.palabra IS 'La palabra tal como aparece.';
COMMENT ON COLUMN palabras_cargadas.tipo IS 'adjetivo, verbo o expresion.';
COMMENT ON COLUMN palabras_cargadas.inicio IS 'Dónde empieza la palabra dentro del texto.';
COMMENT ON COLUMN palabras_cargadas.fin IS 'Dónde termina.';
COMMENT ON COLUMN palabras_cargadas.explicacion IS 'Por qué carga emocionalmente el texto.';
COMMENT ON TABLE resaltados IS 'Lo que el profesor resalta en el modo explicación (videobeam).';
COMMENT ON COLUMN resaltados.id IS 'Número del resaltado.';
COMMENT ON COLUMN resaltados.texto_id IS 'Texto resaltado.';
COMMENT ON COLUMN resaltados.nivel IS 'macro, super o micro (define el color).';
COMMENT ON COLUMN resaltados.inicio IS 'Dónde empieza el fragmento.';
COMMENT ON COLUMN resaltados.fin IS 'Dónde termina.';
COMMENT ON COLUMN resaltados.fragmento IS 'El fragmento resaltado.';
COMMENT ON COLUMN resaltados.explicacion IS 'La explicación del profesor.';
COMMENT ON COLUMN resaltados.es_idea_principal IS 'Sí, si es "Señalar idea principal".';
COMMENT ON COLUMN resaltados.creado_en IS 'Cuándo se hizo.';
COMMENT ON TABLE actividades IS 'Cada vez que un estudiante analiza un texto: en qué paso va, cómo le fue en cada nivel, sus puntos y su ánimo.';
COMMENT ON COLUMN actividades.id IS 'Número de la actividad.';
COMMENT ON COLUMN actividades.estudiante_id IS 'Estudiante que la hace.';
COMMENT ON COLUMN actividades.texto_id IS 'Texto que analiza.';
COMMENT ON COLUMN actividades.numero IS '1, 2… si repite el mismo texto.';
COMMENT ON COLUMN actividades.estado IS 'en_curso, terminada o abandonada.';
COMMENT ON COLUMN actividades.paso IS 'macro → super → micro → resultado.';
COMMENT ON COLUMN actividades.grado IS 'Grado que tenía al hacerla.';
COMMENT ON COLUMN actividades.resultado_macro IS 'Resultado en idea principal, de 0 a 1.';
COMMENT ON COLUMN actividades.resultado_super IS 'Resultado en organización, de 0 a 1.';
COMMENT ON COLUMN actividades.resultado_micro IS 'Resultado en palabras, de 0 a 1.';
COMMENT ON COLUMN actividades.puntos_ganados IS 'Puntos que ganó en esta actividad.';
COMMENT ON COLUMN actividades.animo IS 'motivacion_alta, neutral o requiere_apoyo. Solo apoyo pedagógico; solo lo ve su profesor.';
COMMENT ON COLUMN actividades.iniciada_en IS 'Cuándo empezó.';
COMMENT ON COLUMN actividades.terminada_en IS 'Cuándo terminó.';
COMMENT ON TABLE respuestas IS 'Todo lo que envía el estudiante: su idea principal, sus respuestas a las preguntas y cada palabra que marcó.';
COMMENT ON COLUMN respuestas.id IS 'Número de la respuesta.';
COMMENT ON COLUMN respuestas.actividad_id IS 'Actividad a la que pertenece.';
COMMENT ON COLUMN respuestas.nivel IS 'macro, super o micro.';
COMMENT ON COLUMN respuestas.codigo_envio IS 'Código que crea el navegador. Si se cae el internet y reenvía, no se duplica.';
COMMENT ON COLUMN respuestas.texto IS 'macro: la idea que escribió · micro: la palabra que marcó.';
COMMENT ON COLUMN respuestas.pregunta_id IS 'super: la pregunta respondida.';
COMMENT ON COLUMN respuestas.opcion_elegida IS 'super: la opción que eligió.';
COMMENT ON COLUMN respuestas.inicio IS 'micro: dónde empieza la palabra.';
COMMENT ON COLUMN respuestas.fin IS 'micro: dónde termina.';
COMMENT ON COLUMN respuestas.tipo_palabra IS 'micro: el tipo que eligió (en primaria va vacío).';
COMMENT ON COLUMN respuestas.es_correcta IS 'Si acertó. Lo calcula la base (super y micro) o la IA (macro).';
COMMENT ON COLUMN respuestas.estado_ia IS 'macro: pendiente, procesando, lista o fallida.';
COMMENT ON COLUMN respuestas.veredicto_ia IS 'macro: coincide, coincide_en_parte o por_mejorar.';
COMMENT ON COLUMN respuestas.faltantes_ia IS 'macro: lo que le faltó.';
COMMENT ON COLUMN respuestas.explicacion_ia IS 'macro: explicación de la IA (solo si la cita es real).';
COMMENT ON COLUMN respuestas.cita_ia IS 'macro: frase del texto que respalda la explicación.';
COMMENT ON COLUMN respuestas.cita_valida IS 'macro: si la cita existe de verdad en el texto.';
COMMENT ON COLUMN respuestas.tiempo_ia_ms IS 'macro: cuánto tardó la IA (meta: 15 segundos o menos).';
COMMENT ON COLUMN respuestas.enviada_en IS 'Hora en que la envió desde su dispositivo.';
COMMENT ON COLUMN respuestas.recibida_en IS 'Hora en que llegó al servidor.';
COMMENT ON TABLE cola_ia IS 'La lista de trabajos pendientes para la IA. La app deja el trabajo aquí y el programa de IA lo recoge.';
COMMENT ON COLUMN cola_ia.id IS 'Número del trabajo.';
COMMENT ON COLUMN cola_ia.tarea IS 'preparar_texto, revisar_idea o analizar_animo.';
COMMENT ON COLUMN cola_ia.estado IS 'pendiente, procesando, lista o fallida.';
COMMENT ON COLUMN cola_ia.prioridad IS '1 = un estudiante está esperando; 9 = puede esperar.';
COMMENT ON COLUMN cola_ia.texto_id IS 'Texto a preparar.';
COMMENT ON COLUMN cola_ia.respuesta_id IS 'Idea principal a revisar.';
COMMENT ON COLUMN cola_ia.actividad_id IS 'Actividad para analizar el ánimo.';
COMMENT ON COLUMN cola_ia.intentos IS 'Cuántas veces se ha intentado.';
COMMENT ON COLUMN cola_ia.max_intentos IS 'Máximo de intentos.';
COMMENT ON COLUMN cola_ia.disponible_desde IS 'Desde cuándo se puede volver a intentar.';
COMMENT ON COLUMN cola_ia.tomado_en IS 'Cuándo lo tomó el programa de IA (para recuperar trabajos interrumpidos).';
COMMENT ON COLUMN cola_ia.ultimo_error IS 'Último error (por ejemplo, tiempo agotado).';
COMMENT ON COLUMN cola_ia.creada_en IS 'Cuándo se pidió.';
COMMENT ON COLUMN cola_ia.terminada_en IS 'Cuándo terminó.';
COMMENT ON TABLE alertas IS 'Avisos al profesor cuando un estudiante muestra varias veces seguidas que podría necesitar apoyo.';
COMMENT ON COLUMN alertas.id IS 'Número de la alerta.';
COMMENT ON COLUMN alertas.estudiante_id IS 'Estudiante.';
COMMENT ON COLUMN alertas.motivo IS 'Texto que ve el profesor.';
COMMENT ON COLUMN alertas.atendida IS 'Si el profesor ya la atendió.';
COMMENT ON COLUMN alertas.nota_profesor IS 'Nota del profesor.';
COMMENT ON COLUMN alertas.creada_en IS 'Cuándo se creó.';
COMMENT ON COLUMN alertas.atendida_en IS 'Cuándo se atendió.';
COMMENT ON TABLE logros IS 'Los logros que se pueden ganar.';
COMMENT ON COLUMN logros.id IS 'Número del logro.';
COMMENT ON COLUMN logros.nombre IS 'Nombre (por ejemplo, Ojo de águila).';
COMMENT ON COLUMN logros.descripcion IS 'Lo que hay que hacer para ganarlo.';
COMMENT ON COLUMN logros.regla IS 'Cómo se gana: actividades_terminadas, racha, micro_perfecto, idea_correcta o nivel.';
COMMENT ON COLUMN logros.meta IS 'Cuánto hace falta (por ejemplo, 3 días).';
COMMENT ON COLUMN logros.activo IS 'Si está disponible.';
COMMENT ON TABLE logros_ganados IS 'Qué logros ha ganado cada estudiante.';
COMMENT ON COLUMN logros_ganados.estudiante_id IS 'Estudiante.';
COMMENT ON COLUMN logros_ganados.logro_id IS 'Logro ganado.';
COMMENT ON COLUMN logros_ganados.ganado_en IS 'Cuándo lo ganó.';
COMMENT ON TABLE ajustes IS 'Las reglas que se pueden cambiar sin tocar el código: puntos, umbrales, modelo de IA e instrucciones para la IA. Cada regla tiene un valor general y, si se quiere, un valor propio para un curso.';
COMMENT ON COLUMN ajustes.id IS 'Número del ajuste.';
COMMENT ON COLUMN ajustes.clave IS 'Nombre del ajuste (por ejemplo, puntos_por_acierto).';
COMMENT ON COLUMN ajustes.curso_id IS 'Vacío = valor general para todos. Con un curso = valor propio de ese curso, que reemplaza al general.';
COMMENT ON COLUMN ajustes.valor IS 'El valor del ajuste.';
COMMENT ON COLUMN ajustes.descripcion IS 'Para qué sirve.';
COMMENT ON COLUMN ajustes.actualizado_por IS 'Usuario que hizo el último cambio.';
COMMENT ON COLUMN ajustes.actualizado_en IS 'Cuándo se cambió por última vez.';
RESET ROLE;
-- Fin del script
