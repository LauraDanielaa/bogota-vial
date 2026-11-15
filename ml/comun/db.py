"""Conexión a PostGIS para los modelos de ml/.

Se lee de las variables DB_* (en Docker las pone docker-compose) o del .env de la
raíz del repo (en local). Es la misma lógica de etl/src/carga/cargar_postgis.py;
se copia porque la imagen de ml solo incluye la carpeta ml.
"""

import os
from pathlib import Path

import pandas as pd
import psycopg2

RAIZ_REPO = Path(__file__).resolve().parents[2]


def leer_env():
    ruta = RAIZ_REPO / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def conectar():
    leer_env()
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "bogota_vial"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


def existe_relacion(conn, nombre: str) -> bool:
    """True si la tabla o vista existe (sirve para saber si ya corrió el ETL)."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (nombre,))
        return cur.fetchone()[0]


def leer_sql(conn, consulta: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(consulta, params)
        columnas = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columnas)
