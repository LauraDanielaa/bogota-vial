#!/usr/bin/env python3
"""
Entrena los modelos de machine learning de Bogotá Vial.

Cada modelo vive en su propia carpeta (ml/<modelo>/) con una función main().
Se corre DESPUÉS del ETL, porque lee las vistas que este deja en PostGIS.

Uso (desde la raíz del repo):
    python ml/run_ml.py                    # todos los modelos
    python ml/run_ml.py riesgo_prorroga    # solo uno

Con Docker:
    docker compose run --rm etl                    # primero el ETL
    docker compose run --rm ml riesgo_prorroga     # luego el modelo

La conexión se lee de .env (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
"""

import argparse
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# nombre -> módulo con la función main()
MODELOS = {
    "riesgo_prorroga": "riesgo_prorroga.entrenar",
}


def main():
    ap = argparse.ArgumentParser(description="Entrena los modelos de ML de Bogotá Vial.")
    ap.add_argument("modelos", nargs="*", help=f"Modelos a entrenar: {', '.join(MODELOS)} (por defecto, todos)")
    args = ap.parse_args()
    desconocidos = [m for m in args.modelos if m not in MODELOS]
    if desconocidos:
        sys.exit(f"Modelo desconocido: {', '.join(desconocidos)}. Opciones: {', '.join(MODELOS)}")

    inicio = time.time()
    for nombre in args.modelos or list(MODELOS):
        print(f"== Modelo: {nombre}")
        importlib.import_module(MODELOS[nombre]).main()
    print(f"\nTerminado en {time.time() - inicio:.1f} s")


if __name__ == "__main__":
    main()
