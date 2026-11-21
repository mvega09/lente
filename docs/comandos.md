# Comandos de consulta en las 3 VM

Comandos para revisar cómo trabaja LENTE: tokens y tiempo de la IA, estado de los
servicios y cuánto tardó cada tarea según la base de datos. Todos son de **solo lectura**,
salvo los marcados con 🔧 (cambian algo y piden `sudo`).

**Cómo usarlos:** entra a la VM con MobaXterm y pega el comando tal cual. Los que tienen
varias líneas (los de la base de datos) también se pegan completos.

| VM | IP | Qué corre | Alias SSH desde el PC |
|---|---|---|---|
| VM-IA | 10.60.14.181 | Ollama (qwen3:4b, qwen3:14b) | `lente-ia` |
| VM-APP | 10.60.14.182 | API, 4 workers de IA, Nginx y la web | `lente-app` |
| VM-BD | 10.60.14.183 | PostgreSQL 16, base `lente` | `lente-db` |

## Valores de referencia

| Qué | Modelo | Tokens de entrada | Tokens de salida | Tiempo normal | Meta |
|---|---|---|---|---|---|
| Revisar la idea principal (estudiante esperando) | qwen3:4b | 600 a 700 | 80 a 120 | 10 a 15 s | ≤ 15 s (RNF-01) |
| Ánimo del estudiante | qwen3:4b | ~200 | ~15 | 2 a 5 s | — |
| Preparar un texto (profesor) | qwen3:14b | 1 000 a 1 800 | 450 a 650 | 4 a 7 min | sin límite (segundo plano) |

En CPU el tiempo depende sobre todo de los **tokens de salida**: qwen3:14b escribe unos
2,5 tokens por segundo y qwen3:4b unos 9. Leer la entrada es mucho más rápido.

---

## VM-IA (10.60.14.181)

### Tokens y tiempo de cada consulta

```bash
bash ~/tokens_ollama.sh              # consultas de hoy
bash ~/tokens_ollama.sh "-2 hours"   # de las últimas 2 horas
```

Ejemplo:

```
2026-11-21T19:48:34 UTC  entrada=  656  salida= 103  segundos=  12   <- revisión de una idea principal
2026-11-21T17:13:52 UTC  entrada= 1374  salida= 439  segundos= 385   <- preparación de un texto
```

- **entrada:** tokens que lee el modelo (instrucciones + noticia + respuesta del estudiante).
- **salida:** tokens que escribe.
- **segundos:** duración de la consulta. Las horas están en UTC (Colombia = UTC − 5).

Si el script no está en la VM, cópialo desde el PC (está en el repositorio):

```powershell
scp lente/scripts/tokens_ollama.sh lente-ia:~/
```

### Ver en vivo lo que hace Ollama

```bash
journalctl -u ollama -f | grep --line-buffered -E 'new prompt|stop processing|api/chat'
```

- `new prompt ... task.n_tokens = 1374` → empezó una consulta con 1374 tokens de entrada.
- `stop processing: n_tokens = 1813` → terminó; salida = 1813 − 1374 = 439 tokens.
- `POST "/api/chat" ... 5m40s` → la respuesta completa tardó 5 min 40 s.

Se detiene con **Ctrl+C**.

### Modelos

```bash
ollama ps      # cargados en memoria ahora (qwen3:4b debe decir "Forever")
ollama list    # instalados
```

### Servicio, configuración y recursos

```bash
systemctl status ollama --no-pager | head -5
systemctl show ollama -p Environment | tr ' ' '\n' | grep OLLAMA   # OLLAMA_NUM_PARALLEL=4
journalctl -u ollama --since today --no-pager | grep -c 'POST.*/api/chat'   # consultas de hoy
free -h        # memoria (qwen3:14b ocupa ~12 GB al cargarse)
uptime         # carga del procesador (8 núcleos): cerca de 8 = ocupado al máximo
top            # procesos en vivo (salir con q)
```

### 🔧 Reiniciar Ollama

```bash
sudo systemctl restart ollama
```

Después del reinicio, los workers vuelven a cargar qwen3:4b solos (cada 10 minutos revisan).
Si un estudiante envía antes, su primera revisión tarda unos segundos más mientras carga.

---

## VM-APP (10.60.14.182)

### Estado de los servicios

```bash
systemctl is-active lente-api lente-worker@{1..4} nginx   # deben salir 6 "active"
curl -s http://127.0.0.1:8000/salud; echo                  # API y conexión con la base
curl -s -o /dev/null -w "web %{http_code}\n" http://127.0.0.1/
```

### Tareas de IA: en vivo y del día

```bash
journalctl -u 'lente-worker@*' -f | grep --line-buffered -v httpx
```

```bash
journalctl -u 'lente-worker@*' --since today --no-pager | grep -E 'revisar_idea|preparar_texto|analizar_animo|Falló'
```

Ejemplos de líneas:

```
revisar_idea 17: por_mejorar en 12775 ms (cita válida: True)     <- 12,8 s
preparar_texto 16: texto 8 listo para revisión del profesor
Falló preparar_texto 20 ...                                         <- error: se reintenta solo (máx. 3)
```

### API: en vivo y errores

```bash
journalctl -u lente-api -f
journalctl -u lente-api --since today --no-pager | grep -E 'ERROR|Traceback| 500 '
```

### Versión instalada

```bash
cd ~/lente && git log --oneline -1 && cd ~/lente-frontend && git log --oneline -1 && cd ~
ls /var/www/lente/assets     # archivo del frontend publicado (index-XXXX.js)
```

### Medir la IA sin guardar nada

```bash
cd ~/lente && .venv/bin/python -m scripts.evaluar_preparacion --textos 6 7   # preparación (~5 min por texto)
cd ~/lente && .venv/bin/python -m pytest -q -p no:cacheprovider               # pruebas automáticas
```

### 🔧 Reiniciar y publicar

```bash
sudo systemctl restart lente-api "lente-worker@*"            # después de actualizar el backend
```

```bash
cd ~/lente-frontend && git pull --ff-only && npm ci && npm run build && sudo rsync -a --delete /home/useria/lente-frontend/dist/ /var/www/lente/
```

---

## VM-BD (10.60.14.183)

Cada bloque se pega completo. Pide la clave de sudo. Si la tabla queda en pantalla, sal con **q**.
El `cd /tmp` evita el aviso «could not change directory» (el usuario postgres no puede entrar
a tu carpeta personal).

### Cuánto tardó la preparación de cada texto

```bash
cd /tmp && sudo -u postgres psql -d lente <<'SQL'
SELECT c.texto_id, left(t.titulo, 40) AS titulo, c.estado, c.intentos,
       date_trunc('second', c.tomado_en - c.creada_en)    AS espera,
       date_trunc('second', c.terminada_en - c.tomado_en) AS duracion
  FROM lente.cola_ia c LEFT JOIN lente.textos t ON t.id = c.texto_id
 WHERE c.tarea = 'preparar_texto' ORDER BY c.id DESC LIMIT 10;
SQL
```

- **espera:** tiempo en la cola antes de que un worker la tomara.
- **duracion:** tiempo de la IA.
- **intentos > 1:** hubo un error y se reintentó.

### Cuánto tardó la revisión de cada idea principal (RNF-01: ≤ 15 s)

```bash
cd /tmp && sudo -u postgres psql -d lente <<'SQL'
SELECT r.id AS respuesta, a.texto_id, r.veredicto_ia, r.cita_valida,
       round(r.tiempo_ia_ms / 1000.0, 1)                   AS seg_ia,
       date_trunc('second', c.terminada_en - c.creada_en) AS total_con_cola, c.intentos
  FROM lente.respuestas r
  JOIN lente.actividades a ON a.id = r.actividad_id
  LEFT JOIN lente.cola_ia c ON c.respuesta_id = r.id
 WHERE r.nivel = 'macro' ORDER BY r.id DESC LIMIT 10;
SQL
```

- **seg_ia:** solo la IA.
- **total_con_cola:** lo que esperó el estudiante (cola + IA).
- **cita_valida = f:** la IA citó algo que no está en el texto (revisar la respuesta).

### Resumen de los últimos 7 días por tipo de tarea

```bash
cd /tmp && sudo -u postgres psql -d lente <<'SQL'
SELECT tarea, count(*) AS total, count(*) FILTER (WHERE estado = 'fallida') AS fallidas,
       round(avg(extract(epoch FROM terminada_en - tomado_en))::numeric, 1) AS seg_promedio,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM terminada_en - tomado_en)))::numeric, 1) AS seg_p95,
       round(max(extract(epoch FROM terminada_en - tomado_en))::numeric, 1) AS seg_max
  FROM lente.cola_ia WHERE creada_en > now() - interval '7 days'
 GROUP BY tarea ORDER BY tarea;
SQL
```

**seg_p95:** el 95 % de las tareas tardó eso o menos. Es el valor que se compara con la meta de 15 s.

### Cola de la IA ahora y errores recientes

```bash
cd /tmp && sudo -u postgres psql -d lente <<'SQL'
SELECT tarea, estado, count(*), min(creada_en) AS mas_antiguo
  FROM lente.cola_ia WHERE estado IN ('pendiente', 'procesando', 'fallida')
 GROUP BY 1, 2 ORDER BY 1, 2;
SELECT id, tarea, estado, intentos, left(ultimo_error, 90) AS error, creada_en
  FROM lente.cola_ia WHERE ultimo_error IS NOT NULL ORDER BY id DESC LIMIT 10;
SQL
```

Si no sale nada, no hay trabajo pendiente ni errores.

### Textos por estado, tamaño de la base y conexiones

```bash
cd /tmp && sudo -u postgres psql -d lente <<'SQL'
SELECT estado, count(*) FROM lente.textos GROUP BY estado ORDER BY estado;
SELECT pg_size_pretty(pg_database_size('lente')) AS tamano_base;
SELECT usename, state, count(*) FROM pg_stat_activity WHERE datname = 'lente' GROUP BY 1, 2 ORDER BY 1, 2;
SQL
```

### Copias de seguridad

```bash
systemctl list-timers lente-respaldo.timer --no-pager    # próxima copia (02:00 UTC)
sudo ls -lh /var/backups/lente                           # copias guardadas
journalctl -u lente-respaldo --since "-2 days" --no-pager | tail -5
```

### Consola de la base (para consultas propias)

```bash
cd /tmp && sudo -u postgres psql -d lente
```

Dentro: `\dt lente.*` lista las tablas, `\x` alterna la vista vertical y `\q` sale.

---

## Desde el PC, sin entrar a la VM

Para la VM-IA y la VM-APP funciona `ssh <alias> "<comando>"` desde PowerShell:

```powershell
ssh lente-ia "bash ~/tokens_ollama.sh"
```

```powershell
ssh lente-app "systemctl is-active lente-api lente-worker@1 lente-worker@2 lente-worker@3 lente-worker@4 nginx"
```

```powershell
ssh lente-app "journalctl -u 'lente-worker@*' --since today --no-pager | grep -E 'revisar_idea|preparar_texto|Falló'"
```

Las consultas de la VM-BD se ejecutan mejor desde MobaXterm, porque las comillas del SQL
se rompen al pasar por PowerShell y `ssh`.
