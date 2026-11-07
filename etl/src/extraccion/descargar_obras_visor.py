#!/usr/bin/env python3
"""Obras del visor de proyectos del IDU a CSV.

API: https://webidu.idu.gov.co/visor_proyectos/api/proyectos
Se guardan los atributos básicos de cada obra y el centroide (lon, lat).

Con --entrada se lee un JSON ya descargado en vez de llamar a la API
(en algunas redes el sitio aparece bloqueado).
"""

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://webidu.idu.gov.co/visor_proyectos/api/proyectos"
COLUMNAS_ATRIBUTOS = ["OBJECTID", "NOMBRE", "ETAPA", "CONTRATO", "CODIGO_SIGIDU", "FOTO2"]


def descargar(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def a_filas(datos: dict) -> list[dict]:
    filas = []
    for f in datos.get("features", []):
        atr = f.get("attributes", {})
        cen = f.get("centroid") or {}
        fila = {c: atr.get(c) for c in COLUMNAS_ATRIBUTOS}
        fila["lon"] = cen.get("x")
        fila["lat"] = cen.get("y")
        filas.append(fila)
    return filas


def main():
    ap = argparse.ArgumentParser(description="Descarga las obras del visor del IDU a CSV.")
    ap.add_argument("--salida", default="data/raw/obras_idu_visor.csv")
    ap.add_argument("--entrada", help="JSON local con la respuesta de la API")
    args = ap.parse_args()

    if args.entrada:
        with open(args.entrada, encoding="utf-8") as fh:
            datos = json.load(fh)
    else:
        print(f"Descargando {URL} ...")
        try:
            datos = descargar(URL)
        except Exception as e:
            sys.exit(f"No se pudo descargar: {e}")

    filas = a_filas(datos)
    esperado = datos.get("count")
    if esperado is not None and esperado != len(filas):
        print(f"Aviso: el API dice {esperado} obras pero se leyeron {len(filas)}.")

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS_ATRIBUTOS + ["lon", "lat"])
        w.writeheader()
        w.writerows(filas)

    print(f"{len(filas)} obras guardadas en {salida}")


if __name__ == "__main__":
    main()