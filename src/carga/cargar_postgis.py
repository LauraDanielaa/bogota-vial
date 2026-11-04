#!/usr/bin/env python3
"""
Carga los CSV a PostGIS, en tablas stg_* (todo como texto, sin limpiar).

- Descarta las columnas sensibles de SECOP antes de que entren a la base.
- Normaliza SOLO los nombres de columna (minúsculas, sin tildes, con "_").
  Los valores no se tocan: la limpieza se hace después, en SQL.
- Es repetible: cada corrida borra y vuelve a crear las tablas stg_*.

Tablas:
    stg_obras             <- data/interim/obras_idu_final.csv
    stg_secop_contratos   <- data/raw/secop_contratos_idu_completo.csv
    stg_secop_ejecucion   <- data/raw/secop_ejecucion_idu.csv
    stg_cost              <- data/raw/datos_abiertos_bogota.csv
    stg_localidades       <- data/geo/localidades.geojson (si existe)

Conexión (variables de entorno o archivo .env en la raíz del repo):
    DB_HOST (localhost), DB_PORT (5432), DB_NAME (bogota_vial),
    DB_USER (postgres), DB_PASSWORD

Uso:
    pip install psycopg2-binary
    python src/carga/cargar_postgis.py
"""

import csv
import io
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import psycopg2
from psycopg2 import sql

RAIZ = Path(__file__).resolve().parents[2]
csv.field_size_limit(10**9)

# Columnas que NO deben entrar a la base (personas, cuentas bancarias, documentos).
# Se comparan ya normalizadas.
SENSIBLES = {
    "stg_secop_contratos": [
        "tipodocproveedor",
        "documento_proveedor",
        "nombre_representante_legal",
        "nacionalidad_representante_legal",
        "domicilio_representante_legal",
        "tipo_de_identificaci_n_representante_legal",
        "identificaci_n_representante_legal",
        "g_nero_representante_legal",
        "nombre_del_banco",
        "tipo_de_cuenta",
        "n_mero_de_cuenta",
        "nombre_ordenador_del_gasto",
        "tipo_de_documento_ordenador_del_gasto",
        "n_mero_de_documento_ordenador_del_gasto",
        "nombre_supervisor",
        "tipo_de_documento_supervisor",
        "n_mero_de_documento_supervisor",
        "nombre_ordenador_de_pago",
        "tipo_de_documento_ordenador_de_pago",
        "n_mero_de_documento_ordenador_de_pago",
    ],
}

# (tabla, lista de rutas candidatas: se usa la primera que exista)
FUENTES = [
    ("stg_obras", ["data/interim/obras_idu_final.csv"]),
    ("stg_secop_contratos", ["data/raw/secop_contratos_idu_completo.csv"]),
    ("stg_secop_ejecucion", ["data/raw/secop_ejecucion_idu.csv"]),
    ("stg_cost", ["data/raw/datos_abiertos_bogota.csv"]),
]
GEOJSON = "data/geo/localidades.geojson"


# ---------- utilidades ----------

def normalizar_nombre(nombre: str) -> str:
    """'Avance etapa actual - Programado' -> 'avance_etapa_actual_programado'."""
    s = unicodedata.normalize("NFKD", nombre)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    s = s or "columna"
    return "c_" + s if s[0].isdigit() else s


def nombres_unicos(nombres: list[str]) -> list[str]:
    vistos, salida = {}, []
    for n in nombres:
        vistos[n] = vistos.get(n, 0) + 1
        salida.append(n if vistos[n] == 1 else f"{n}_{vistos[n]}")
    return salida


def leer_env():
    ruta = RAIZ / ".env"
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


def primera_existente(rutas: list[str]) -> Path | None:
    for r in rutas:
        p = RAIZ / r
        if p.exists():
            return p
    return None


# ---------- carga de un CSV ----------

def preparar_csv(ruta: Path, tabla: str):
    """Lee el CSV, quita columnas sensibles, normaliza nombres.
    Devuelve (columnas, buffer_csv, n_filas, descartadas)."""
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        lector = csv.reader(fh)
        encabezado = next(lector)
        norm = nombres_unicos([normalizar_nombre(h) for h in encabezado])

        sens = set(SENSIBLES.get(tabla, []))
        quedan = [i for i, n in enumerate(norm) if n not in sens]
        descartadas = [n for n in norm if n in sens]

        buf = io.StringIO()
        w = csv.writer(buf)
        n = 0
        for fila in lector:
            if not fila:
                continue
            fila = fila + [""] * (len(norm) - len(fila))
            w.writerow([fila[i] for i in quedan])
            n += 1
    buf.seek(0)
    return [norm[i] for i in quedan], buf, n, descartadas


def cargar_csv(cur, tabla: str, ruta: Path):
    columnas, buf, n, descartadas = preparar_csv(ruta, tabla)

    cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(tabla)))
    cur.execute(sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(tabla),
        sql.SQL(", ").join(sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in columnas),
    ))
    cur.copy_expert(
        sql.SQL("COPY {} FROM STDIN WITH (FORMAT csv)").format(sql.Identifier(tabla)).as_string(cur),
        buf,
    )
    cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla)))
    en_base = cur.fetchone()[0]
    return n, en_base, len(columnas), descartadas


# ---------- localidades (GeoJSON) ----------

def cargar_geojson(cur, ruta: Path):
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    cur.execute("DROP TABLE IF EXISTS stg_localidades")
    cur.execute("""
        CREATE TABLE stg_localidades (
            id SERIAL PRIMARY KEY,
            propiedades JSONB,
            geom geometry(Geometry, 4326)
        )
    """)
    n = 0
    for f in datos.get("features", []):
        if not f.get("geometry"):
            continue
        cur.execute(
            "INSERT INTO stg_localidades (propiedades, geom) "
            "VALUES (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
            (json.dumps(f.get("properties", {})), json.dumps(f["geometry"])),
        )
        n += 1
    cur.execute("CREATE INDEX ON stg_localidades USING GIST (geom)")
    return n


# ---------- principal ----------

def main():
    try:
        conn = conectar()
    except psycopg2.OperationalError as e:
        sys.exit(f"No se pudo conectar a la base de datos:\n{e}\n"
                 "Revisa que PostGIS esté corriendo y las variables DB_* / .env.")
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    resumen, errores = [], []
    for tabla, rutas in FUENTES:
        ruta = primera_existente(rutas)
        if ruta is None:
            print(f"[{tabla}] no se encontró ninguno de: {', '.join(rutas)}")
            errores.append(tabla)
            continue
        n, en_base, ncols, descartadas = cargar_csv(cur, tabla, ruta)
        ok = "OK" if n == en_base else "NO COINCIDE"
        print(f"[{tabla}] {ruta.relative_to(RAIZ)}: {en_base} filas, {ncols} columnas ({ok})")
        if descartadas:
            print(f"    columnas sensibles descartadas: {len(descartadas)}")
        resumen.append((tabla, en_base))
        if n != en_base:
            errores.append(tabla)

    geo = RAIZ / GEOJSON
    if geo.exists():
        n = cargar_geojson(cur, geo)
        print(f"[stg_localidades] {GEOJSON}: {n} localidades")
        resumen.append(("stg_localidades", n))
    else:
        print(f"[stg_localidades] no existe {GEOJSON}; se omite (hará falta para asignar localidad)")

    if errores:
        conn.rollback()
        sys.exit(f"Carga cancelada (revertida) por problemas en: {', '.join(errores)}")

    conn.commit()
    cur.close()
    conn.close()
    print("Carga terminada.")


if __name__ == "__main__":
    main()