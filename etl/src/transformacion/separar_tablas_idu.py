#!/usr/bin/env python3
"""Pasa la columna TABLAS de obras_idu_completo.csv a columnas normales.

TABLAS trae en JSON las tablas de la ficha de cada obra. Cada dato queda en
una columna con el nombre de su etiqueta, p. ej. "Avance programado del
contrato: 91,29%" queda en la columna "Avance programado del contrato".
Las metas físicas, los datos de los dos contratos (principal e interventoría),
el total pagado y los predios llevan un prefijo para no mezclarse.
También se quitan URL, TITULO_PAGINA y ESTADO_DESCARGA.

    python separar_tablas_idu.py obras_idu_completo.csv [-o salida.csv]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

QUITAR = ["URL", "TITULO_PAGINA", "ESTADO_DESCARGA", "TABLAS"]
ROLES = ["Contrato principal", "Interventoría"]  # en ese orden salen en la ficha


def limpio(v):
    return re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip()


def orden_columna(c):
    grupos = [("Avance programado", 0), ("Avance ejecutado", 1), ("Avance etapa actual - Programado", 2),
              ("Avance etapa actual - Ejecutado", 3), ("Contrato principal", 4), ("Interventoría", 5),
              ("Total pagado", 6), ("No. Predios", 7), ("Valor", 8), ("Meta física", 9)]
    for pref, n in grupos:
        if c.startswith(pref):
            return (n, c if n == 9 else "")  # solo las metas van alfabéticas
    return (10, c)


def procesar_fila(tablas):
    out = {}
    nums_por_rol = {}
    for tb in tablas:
        if not tb:
            continue
        cab = [limpio(c) for c in tb[0]]

        # avances: "Etiqueta: valor"
        if all(len(r) <= 2 and r and ":" in str(r[0]) for r in tb):
            for r in tb:
                etiqueta, _, valor = limpio(r[0]).partition(":")
                etiqueta = etiqueta.strip()
                if etiqueta in ("Programado", "Ejecutado"):
                    etiqueta = f"Avance etapa actual - {etiqueta}"
                out[etiqueta] = valor.strip()

        # metas físicas
        elif cab[:2] == ["Tipo", "Cantidad"]:
            for r in tb[1:]:
                if len(r) >= 2:
                    out[f"Meta física - {limpio(r[0])}"] = limpio(r[1])

        # info contractual, dos contratos lado a lado
        elif cab and cab[0] == "Número de contrato:":
            for r in tb:
                r = [limpio(c) for c in r]
                for i in range(0, len(r) - 1, 2):
                    rol = ROLES[min(i // 2, len(ROLES) - 1)]
                    out[f"{rol} - {r[i].rstrip(':')}"] = r[i + 1]
                    if r[i] == "Número de contrato:":
                        nums_por_rol[r[i + 1]] = rol

        # total pagado
        elif cab[:2] == ["Contrato", "Total Pagado"]:
            for k, r in enumerate(tb[1:]):
                rol = nums_por_rol.get(limpio(r[0]), ROLES[min(k, len(ROLES) - 1)])
                out[f"Total pagado - {rol.lower()}"] = limpio(r[1])

        # predios
        elif len(tb) >= 2 and ("Predios" in " ".join(cab)):
            for nombre, valor in zip(cab, [limpio(c) for c in tb[1]]):
                out[nombre] = valor

        else:  # cualquier otra tabla se guarda tal cual
            out.setdefault("Otras tablas", [])
            out["Otras tablas"].append(tb)
    if "Otras tablas" in out:
        out["Otras tablas"] = json.dumps(out["Otras tablas"], ensure_ascii=False)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("-o", "--salida")
    a = ap.parse_args()

    df = pd.read_csv(a.entrada, dtype=str, encoding="utf-8-sig")
    if "TABLAS" not in df.columns:
        sys.exit("El archivo no tiene la columna TABLAS.")

    nuevas = pd.DataFrame([procesar_fila(json.loads(t) if isinstance(t, str) and t else []) for t in df["TABLAS"]])
    nuevas = nuevas[sorted(nuevas.columns, key=orden_columna)]
    base = df.drop(columns=[c for c in QUITAR if c in df.columns])
    final = pd.concat([base, nuevas], axis=1)

    dest = Path(a.salida) if a.salida else Path(a.entrada).with_name(Path(a.entrada).stem + "_final.csv")
    final.to_csv(dest, index=False, encoding="utf-8-sig")
    print(f"{len(final)} filas x {final.shape[1]} columnas -> {dest}")
    print(f"Columnas nuevas: {nuevas.shape[1]}")


if __name__ == "__main__":
    main()