"""Traduce los errores de PostgreSQL a respuestas HTTP claras.

Las reglas de negocio viven en la base (triggers y CHECK). Cuando una se
incumple, el usuario recibe un mensaje entendible en vez de un error 500.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import errors

log = logging.getLogger("lente.api")


class NoEncontrado(Exception):
    """El recurso no existe o pertenece a otro profesor (RNF-05: no se revela cuál)."""

    def __init__(self, que: str = "El recurso"):
        self.mensaje = f"{que} no existe"


def _json(status: int, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detalle})


def registrar(app: FastAPI) -> None:
    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, e: NoEncontrado):
        return _json(404, e.mensaje)

    @app.exception_handler(errors.UniqueViolation)
    async def _duplicado(_: Request, e: errors.UniqueViolation):
        return _json(409, "Ya existe un registro con esos datos")

    @app.exception_handler(errors.ForeignKeyViolation)
    async def _referencia(_: Request, e: errors.ForeignKeyViolation):
        return _json(409, "El registro está relacionado con otros datos")

    @app.exception_handler(errors.CheckViolation)
    async def _regla(_: Request, e: errors.CheckViolation):
        log.info("CheckViolation: %s", e.diag.constraint_name)
        return _json(422, "Algún dato no cumple las reglas del sistema")

    @app.exception_handler(errors.RaiseException)
    async def _negocio(_: Request, e: errors.RaiseException):
        # Mensajes escritos en los triggers de la base (ya están en español)
        return _json(409, e.diag.message_primary or "Operación no permitida")

    @app.exception_handler(errors.ObjectNotInPrerequisiteState)
    async def _espera(_: Request, e: errors.ObjectNotInPrerequisiteState):
        return _json(409, e.diag.message_primary or "Todavía no se puede hacer esta operación")
