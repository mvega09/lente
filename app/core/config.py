"""Configuración leída desde variables de entorno o el archivo .env."""

from functools import lru_cache

from psycopg.conninfo import make_conninfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_nombre: str = "LENTE API"
    entorno: str = "desarrollo"

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "lente"
    db_app_user: str = "lente_app"
    db_app_password: str = ""
    db_ia_user: str = "lente_ia"
    db_ia_password: str = ""

    # Sesiones
    jwt_secreto: str = "solo-para-desarrollo-cambiar-en-el-archivo-env"
    jwt_algoritmo: str = "HS256"
    jwt_minutos: int = 480

    cors_origenes: list[str] = ["http://localhost:3000"]

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_modelo_validacion: str = "qwen3:4b"     # cumple RNF-01 con 1 estudiante (docs/benchmark-ia.md)
    ollama_modelo_preparacion: str = "qwen3:14b"
    ollama_keep_alive: str = "30m"
    # El modelo de validación queda siempre cargado: cargarlo toma ~30 s y el estudiante
    # está esperando (en la prueba real, la primera revisión tardó 42 s en frío).
    ollama_keep_alive_validacion: str = "-1m"
    ollama_precalentar_cada_s: int = 600
    # Límite duro por solicitud: si Ollama no responde, el trabajo se reporta y se reintenta
    ollama_timeout_revision_s: int = 90
    ollama_timeout_preparacion_s: int = 900

    def _conninfo(self, usuario: str, clave: str) -> str:
        return make_conninfo(
            host=self.db_host, port=self.db_port, dbname=self.db_name,
            user=usuario, password=clave, application_name=self.app_nombre,
        )

    @property
    def conninfo_app(self) -> str:
        """Conexión de la API (rol lente_app)."""
        return self._conninfo(self.db_app_user, self.db_app_password)

    @property
    def conninfo_ia(self) -> str:
        """Conexión del worker de IA (rol lente_ia, no ve nombres de estudiantes)."""
        return self._conninfo(self.db_ia_user, self.db_ia_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
