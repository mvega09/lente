from fastapi import APIRouter

from app.core.deps import Conn

router = APIRouter(tags=["salud"])


@router.get("/salud", summary="Comprueba que la API y la base de datos respondan")
async def salud(conn: Conn) -> dict:
    async with conn.cursor() as cur:
        await cur.execute("SELECT current_user AS rol, version() AS version")
        fila = await cur.fetchone()
    return {"api": "ok", "base_de_datos": "ok", "rol": fila["rol"], "postgres": fila["version"]}
