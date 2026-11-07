#!/usr/bin/env python3
"""Contratos de obra del IDU en SECOP II (datos.gov.co, recurso jbjy-vk9h).

Filtra por entidad, tipo de contrato, ciudad y palabras clave en el objeto,
y guarda el resultado en CSV con dos columnas extra:
es_obra_vial y palabras_encontradas.

Ejemplos:
    python descargar_contratos_secop.py
    python descargar_contratos_secop.py -k asfalto transmilenio "malla vial"
    python descargar_contratos_secop.py --sin-palabras
    python descargar_contratos_secop.py --todos-los-tipos
    python descargar_contratos_secop.py --entidades IDU UMV
    python descargar_contratos_secop.py --desde 2020-01-01

Si existe la variable SOCRATA_APP_TOKEN se envía en la consulta.
"""
import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www.datos.gov.co/resource/jbjy-vk9h.json"

# texto que se busca en nombre_entidad
ENTIDADES = {
    "IDU": "INSTITUTO DE DESARROLLO URBANO",
    "UMV": "UNIDAD ADMINISTRATIVA ESPECIAL DE REHABILITACION Y MANTENIMIENTO VIAL",
}

PALABRAS_OBRA = [
    "asfalto", "transmilenio", "pavimento", "malla vial", "bacheo", "puente", "ciclorruta",
    "andén", "calzada", "troncal", "intersección", "espacio público", "mantenimiento vial",
    "avenida", "separador", "túnel", "alameda", "cicloinfraestructura", "vial", "vía",
]


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def esc(t):
    return t.replace("'", "''")


def variantes(palabras):
    # Socrata no tiene unaccent, toca buscar con y sin tilde
    out = set()
    for p in palabras:
        up = p.upper().strip()
        out.add(up)
        out.add(sin_tildes(up))
    return sorted(out)


def construir_where(entidades, solo_obra, desde, solo_bogota, palabras):
    ents = " OR ".join(
        f"upper(nombre_entidad) like '%{esc(ENTIDADES.get(e.upper(), e.upper()))}%'" for e in entidades
    )
    partes = [f"({ents})"]
    if solo_obra:
        partes.append("tipo_de_contrato = 'Obra'")
    if solo_bogota:
        partes.append("(upper(ciudad) like '%BOGOT%' OR upper(departamento) like '%BOGOT%')")
    if desde:
        partes.append(f"fecha_de_firma >= '{desde}T00:00:00'")
    if palabras:
        kws = " OR ".join(f"upper(objeto_del_contrato) like '%{esc(v)}%'" for v in variantes(palabras))
        partes.append(f"({kws})")
    return " AND ".join(partes)


def descargar(where, token, pagina=50000, maximo=None):
    headers = {"X-App-Token": token} if token else {}
    filas, offset = [], 0
    while True:
        params = {"$where": where, "$limit": pagina, "$offset": offset, "$order": "id_contrato"}
        for intento in range(4):
            try:
                r = requests.get(BASE, headers=headers, params=params, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if intento == 3:
                    sys.exit(f"Error consultando la API: {e}")
                time.sleep(2 ** intento)
        lote = r.json()
        if not lote:
            break
        filas += lote
        offset += len(lote)
        print(f"  descargadas {len(filas)} filas...", flush=True)
        if maximo and len(filas) >= maximo:
            filas = filas[:maximo]
            break
        if len(lote) < pagina:
            break
    return pd.DataFrame(filas)


def aplanar(df):
    # las columnas de URL llegan como {'url': ...}
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, dict)).any():
            df[c] = df[c].map(lambda v: v.get("url") if isinstance(v, dict) else v)
    return df


def marcar_palabras(df, palabras):
    if "objeto_del_contrato" not in df.columns:
        df["palabras_encontradas"] = ""
        df["es_obra_vial"] = False
        return df
    obj = df["objeto_del_contrato"].fillna("").map(lambda t: sin_tildes(t.upper()))
    kws = [(p.strip(), sin_tildes(p.upper().strip())) for p in palabras]
    df["palabras_encontradas"] = obj.map(lambda t: "; ".join(p for p, k in kws if k in t))
    df["es_obra_vial"] = df["palabras_encontradas"] != ""
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entidades", nargs="+", default=["IDU"], help="IDU, UMV o un texto del nombre de la entidad")
    ap.add_argument("-k", "--palabras", nargs="+", default=PALABRAS_OBRA, help="palabras clave del objeto del contrato")
    ap.add_argument("--sin-palabras", action="store_true", help="no filtrar por palabras clave (solo marcar)")
    ap.add_argument("--todos-los-tipos", action="store_true", help="no filtrar por tipo_de_contrato = Obra")
    ap.add_argument("--desde", help="fecha mínima de firma, AAAA-MM-DD")
    ap.add_argument("--sin-filtro-bogota", action="store_true", help="no exigir ciudad/departamento Bogotá")
    ap.add_argument("--max", type=int, help="límite de filas")
    ap.add_argument("--salida", default="data/raw/secop_contratos_idu.csv")
    a = ap.parse_args()

    filtro_palabras = None if a.sin_palabras else a.palabras
    where = construir_where(a.entidades, not a.todos_los_tipos, a.desde, not a.sin_filtro_bogota, filtro_palabras)
    print("Filtro SoQL:", where[:400], "..." if len(where) > 400 else "")
    df = descargar(where, os.environ.get("SOCRATA_APP_TOKEN"), maximo=a.max)

    if df.empty:
        sys.exit("La consulta no devolvió filas.")

    df = aplanar(df)
    df["fecha_descarga"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    df = marcar_palabras(df, a.palabras)

    out = Path(a.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")  # sig para que Excel lea las tildes

    print(f"\nListo: {len(df)} filas x {df.shape[1]} columnas -> {out}")
    print(f"Con palabras clave (es_obra_vial=True): {int(df['es_obra_vial'].sum())}")
    print("Columnas:", ", ".join(df.columns))


if __name__ == "__main__":
    main()