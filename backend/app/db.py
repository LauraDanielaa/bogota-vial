"""Pool de conexiones a PostGIS y helpers de consulta."""

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool = ConnectionPool(
    conninfo=settings.dsn,
    min_size=1,
    max_size=10,
    open=False,
    kwargs={"row_factory": dict_row},
)


def fetch_all(query: str, params: dict[str, Any] | None = None) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(query, params).fetchall()


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict | None:
    with pool.connection() as conn:
        return conn.execute(query, params).fetchone()
