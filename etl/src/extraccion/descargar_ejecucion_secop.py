#!/usr/bin/env python3
"""Ejecución de contratos de SECOP II (datos.gov.co, recurso mfmm-jqmq).

Se hace una consulta $q por cada palabra clave y se dejan solo las filas
donde la palabra aparece en el nombre del plan, la descripción o la
referencia de artículos. Salida en CSV con es_obra_vial y palabras_encontradas.

Ejemplos:
    python descargar_ejecucion_secop.py
    python descargar_ejecucion_secop.py -k asfalto transmilenio "malla vial"
    python descargar_ejecucion_secop.py --sin-palabras --max 1000
"""
import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.datos.gov.co/resource/mfmm-jqmq.json"
COLS_TEXTO = ["nombreplan", "descripci_n", "referencia_de_articulos"]
PALABRAS_OBRA = [
    "asfalto", "transmilenio", "pavimento", "malla vial", "bacheo", "puente", "ciclorruta",
    "andén", "calzada", "troncal", "intersección", "espacio público", "mantenimiento vial",
    "avenida", "separador", "túnel", "alameda", "cicloinfraestructura", "vial", "vía",
    "concreto", "mezcla asfáltica", "carpeta asfáltica", "sardinel", "adoquín",
]


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def esc(t):
    return t.replace("'", "''")


def pedir(params, token):
    headers = {"X-App-Token": token} if token else {}
    for intento in range(3):
        try:
            r = requests.get(URL, headers=headers, params=params, timeout=60)
            if r.status_code == 400:
                sys.exit(f"Consulta rechazada (400): {r.text[:300]}")
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"    reintento {intento + 1}/3 ({type(e).__name__})", flush=True)
            time.sleep(2 ** intento)
    print("    se omite este bloque tras 3 fallos", flush=True)
    return []


def descargar_palabra(q, token, pagina=10000, maximo=None):
    # $q resultó mucho más rápido que encadenar LIKEs
    filas, off = [], 0
    while True:
        print(f"  consultando '{q}' (desde fila {off})...", flush=True)
        lote = pedir({"$q": q, "$limit": pagina, "$offset": off, "$order": ":id"}, token)
        if not lote:
            break
        filas += lote
        off += len(lote)
        print(f"    {len(filas)} filas", flush=True)
        if maximo and len(filas) >= maximo:
            return filas[:maximo]
        if len(lote) < pagina:
            break
    return filas


def descargar(palabras, token, maximo=None):
    if palabras is None:
        return pd.DataFrame(pedir({"$limit": maximo or 1000}, token))
    todo = []
    for p in palabras:
        todo += descargar_palabra(p.strip(), token, maximo=maximo)
    df = pd.DataFrame(todo)
    return df.drop_duplicates() if not df.empty else df


def marcar_palabras(df, palabras):
    cols = [c for c in COLS_TEXTO if c in df.columns]
    txt = df[cols].fillna("").astype(str).agg(" ".join, axis=1).map(lambda t: sin_tildes(t.upper()))
    kws = [(p.strip(), sin_tildes(p.upper().strip())) for p in palabras]
    df["palabras_encontradas"] = txt.map(lambda t: "; ".join(p for p, k in kws if k in t))
    df["es_obra_vial"] = df["palabras_encontradas"] != ""
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", "--palabras", nargs="+", default=PALABRAS_OBRA)
    ap.add_argument("--sin-palabras", action="store_true", help="no filtrar por palabras (solo marcar)")
    ap.add_argument("--max", type=int, help="límite de filas")
    ap.add_argument("--salida", default="data/raw/secop_ejecucion_idu.csv")
    a = ap.parse_args()

    print("Descargando...", flush=True)
    df = descargar(None if a.sin_palabras else a.palabras, os.environ.get("SOCRATA_APP_TOKEN"), maximo=a.max)
    if df.empty:
        sys.exit("La consulta no devolvió filas.")

    df = marcar_palabras(df, a.palabras)
    if not a.sin_palabras:  # $q busca en todas las columnas, no solo en las de texto
        df = df[df["es_obra_vial"]]
        if df.empty:
            sys.exit("Hubo resultados pero ninguno con la palabra en descripción o nombre del plan.")
    df["fecha_descarga"] = pd.Timestamp.now().strftime("%Y-%m-%d")

    out = Path(a.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nListo: {len(df)} filas x {df.shape[1]} columnas -> {out}")
    print("Columnas:", ", ".join(df.columns))


if __name__ == "__main__":
    main()