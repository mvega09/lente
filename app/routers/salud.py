from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from app.core.db import get_conn

router = APIRouter(tags=["salud"])


@router.get("/salud", summary="Comprueba que la API y la base de datos respondan")
async def salud(conn: AsyncConnection = Depends(get_conn)) -> dict:
    async with conn.cursor() as cur:
        await cur.execute("SELECT current_user AS rol, version() AS version")
        fila = await cur.fetchone()
    return {"api": "ok", "base_de_datos": "ok", "rol": fila["rol"], "postgres": fila["version"]}
