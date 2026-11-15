---
name: lente-publicar
description: Publica cambios del backend LENTE siguiendo el flujo PC → VM-APP → pruebas → GitHub. Úsala siempre que se haya editado código, documentación o pruebas en la carpeta lente y haya que guardarlos, probarlos en la VM-APP o subirlos a GitHub (mvega09/lente), aunque el usuario solo diga "súbelo", "guárdalo", "haz commit" o "publícalo".
---

# Publicar cambios de LENTE

El código se edita en el PC (`PROYECTO GRADO\lente`), pero las pruebas deben
correr en la VM-APP (10.60.14.182), que es donde vive el entorno real de Python
(`.venv`) y desde donde se llega a Ollama. GitHub es la copia de respaldo y
corre las mismas pruebas en cada push. Por eso el orden importa: nada llega a
GitHub sin haber pasado antes las pruebas en la VM-APP.

## Remotos de git (ya configurados en la copia del PC)

- `app` = `lente-app:/home/useria/lente` (la VM-APP acepta pushes a su rama
  actual gracias a `receive.denyCurrentBranch=updateInstead`).
- `origin` = GitHub `mvega09/lente` (privado). La VM-APP no tiene credenciales
  de GitHub: se publica siempre desde el PC con `gh`/git.

## Pasos

1. Revisar qué cambió: `git status --short` y `git diff --stat`.
   No incluir `.env`, claves ni archivos generados por accidente.
2. Commit con mensaje en español, en imperativo y explicando el porqué:
   ```bash
   git add -A && git commit -q -F - <<'EOF'
   Resumen corto en imperativo

   - Detalle de qué cambió y por qué.

   Co-Authored-By: ...   # la línea de atribución que indique el sistema
   EOF
   ```
3. Llevarlo a la VM-APP y correr las pruebas allí:
   ```bash
   git push -q app main && ssh lente-app 'cd ~/lente && .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -3'
   ```
   `-p no:cacheprovider` evita que pytest deje la carpeta `.pytest_cache` y
   ensucie el árbol de trabajo de la VM.
   Si se cambió la documentación, comprobar también:
   `ssh lente-app 'cd ~/lente && .venv/bin/mkdocs build --strict --site-dir /tmp/s && rm -rf /tmp/s'`
4. Solo si todo pasa: `git push -q origin main`.
5. Confirmar las pruebas automáticas de GitHub (workflow `Pruebas`):
   ```bash
   gh run list --repo mvega09/lente --limit 1
   gh run watch <id> --repo mvega09/lente --exit-status   # en segundo plano
   ```

## Si algo falla

- **Pruebas fallan en la VM-APP:** corregir en el PC, nuevo commit (no
  `--amend` de algo ya publicado) y repetir desde el paso 3.
- **Se generó un archivo en la VM-APP** (por ejemplo `docs/api.md` con
  `scripts/generar_docs_api.py`): hacer commit allí y traerlo al PC con
  `git pull --ff-only app main`, para que las dos copias no se separen.
- **Una dependencia nueva:** agregarla a `requirements.txt` e instalarla en la
  VM-APP con `.venv/bin/pip install -q "paquete>=x"`; GitHub la instala solo.

## Reglas de seguridad del proyecto

- Nunca correr pruebas contra la base real `lente`; las de integración
  necesitan `DB_NAME` con "prueba" y `LENTE_PRUEBAS_INTEGRACION=1`.
- Nunca subir claves: `db/schema.sql` lleva `CAMBIE_ESTA_CLAVE` en lugar de las
  contraseñas reales.
- Responder al usuario en español y explicar en términos sencillos.
