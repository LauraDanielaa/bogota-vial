#!/usr/bin/env python3
"""
Ejecuta el pipeline completo, en orden:

    1. cargar       CSV y GeoJSON  ->  tablas stg_* en PostGIS
    2. transformar  sql/01_*.sql ... sql/04_*.sql  (limpieza, cruce, localidad, vistas)
    3. calidad      sql/99_calidad.sql + resumen impreso

Es repetible: se puede correr las veces que haga falta y da el mismo resultado.
Si un paso falla, se detiene.

Uso (desde la raíz del repo):
    python run_etl.py                       # todo
    python run_etl.py --etapa transformar   # solo la limpieza en SQL
    python run_etl.py --etapa calidad       # solo el reporte
    python run_etl.py --etapa cargar        # solo la carga

La conexión se lee de .env (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
La descarga de datos (src/extraccion/) no forma parte de este script.
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src" / "carga"))

import cargar_postgis  # noqa: E402

SQL_DIR = RAIZ / "sql"


def ejecutar_sql(conn, archivo: Path):
    inicio = time.time()
    with conn.cursor() as cur:
        cur.execute(archivo.read_text(encoding="utf-8"))
    conn.commit()
    print(f"  {archivo.name}  ({time.time() - inicio:.1f} s)")


def etapa_cargar():
    print("== 1. Cargar")
    cargar_postgis.main()


def etapa_transformar(conn):
    print("== 2. Transformar (SQL)")
    archivos = sorted(p for p in SQL_DIR.glob("0*.sql"))
    if not archivos:
        sys.exit(f"No hay archivos .sql en {SQL_DIR}")
    for a in archivos:
        ejecutar_sql(conn, a)


def etapa_calidad(conn):
    print("== 3. Calidad")
    ejecutar_sql(conn, SQL_DIR / "99_calidad.sql")
    with conn.cursor() as cur:
        cur.execute("SELECT seccion, metrica, valor, nota FROM v_calidad ORDER BY orden")
        filas = cur.fetchall()
    print()
    seccion_actual = None
    for seccion, metrica, valor, nota in filas:
        if seccion != seccion_actual:
            print(f"\n{seccion}")
            seccion_actual = seccion
        extra = f"   ({nota})" if nota else ""
        print(f"  {metrica:<45} {int(valor):>8}{extra}")


def main():
    ap = argparse.ArgumentParser(description="Ejecuta el pipeline ETL de Bogotá Vial.")
    ap.add_argument("--etapa", choices=["todo", "cargar", "transformar", "calidad"], default="todo")
    args = ap.parse_args()

    inicio = time.time()

    if args.etapa in ("todo", "cargar"):
        etapa_cargar()

    if args.etapa in ("todo", "transformar", "calidad"):
        try:
            conn = cargar_postgis.conectar()
        except Exception as e:
            sys.exit(f"No se pudo conectar a la base de datos: {e}")
        try:
            if args.etapa in ("todo", "transformar"):
                etapa_transformar(conn)
            if args.etapa in ("todo", "calidad"):
                etapa_calidad(conn)
        except Exception as e:
            conn.rollback()
            sys.exit(f"\nError en el SQL, se detuvo el proceso:\n{e}")
        finally:
            conn.close()

    print(f"\nTerminado en {time.time() - inicio:.1f} s")


if __name__ == "__main__":
    main()