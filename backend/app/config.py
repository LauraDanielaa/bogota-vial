"""Configuración leída de variables de entorno (o del .env de la raíz del repo)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ_REPO / ".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "bogota_vial"
    db_user: str = "postgres"
    db_password: str = ""

    # Orígenes permitidos para el frontend (separados por coma)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )


settings = Settings()
