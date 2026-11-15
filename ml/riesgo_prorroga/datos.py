"""Datos y variables del modelo de riesgo de prórroga.

Fuente: vista v_ml_contratos (etl/sql/06_ml.sql), 1 fila por contrato de clean_secop.
Solo se usan variables conocidas al firmar el contrato.
"""

import numpy as np
import pandas as pd

from comun.db import leer_sql

VISTA = "v_ml_contratos"

# Variables que entran al modelo (una por columna de X)
CATEGORICAS = [
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "origen_de_los_recursos",
    "familia_categoria",       # 4 primeros dígitos del código UNSPSC de la categoría
]
NUMERICAS = [
    "puede_prorrogarse",       # 1 / 0
    "log_valor",               # log(1 + valor del contrato)
    "duracion_dias",           # duración pactada, sacada del texto de SECOP
    "duracion_sin_dato",       # 1 si el texto no trae la duración
    "anio_firma",
    "mes_firma",
    "contratos_previos",       # contratos del mismo contratista firmados antes
    "tasa_prorroga_previa",    # proporción de esos contratos (ya resueltos) que se prorrogó
    "sin_historial",           # 1 si no hay contratos anteriores resueltos
]
VARIABLES = CATEGORICAS + NUMERICAS

# Columnas que filtran la respuesta y NUNCA pueden entrar al modelo.
# ("Modificado" aparece en casi todos los prorrogados y fecha_fin ya incluye la prórroga.)
PROHIBIDAS = {
    "estado_contrato",
    "fecha_fin",
    "fecha_de_fin_del_contrato",
    "duracion_real",
    "fecha_de_notificaci_n_de_prorrogaci_n",
    "ultima_actualizacion",
    "dias_adicionados",
    "prorrogado",
    "es_vigente",
}

# Factores que se explican juntos (p. ej. la tasa de prórroga y "sin historial")
GRUPO = {
    "tasa_prorroga_previa": "historial",
    "sin_historial": "historial",
    "duracion_dias": "duracion",
    "duracion_sin_dato": "duracion",
}


def grupo_de(variable: str) -> str:
    return GRUPO.get(variable, variable)


def verificar_variables():
    """Falla si alguna variable prohibida está en la lista del modelo."""
    cruzadas = set(VARIABLES) & PROHIBIDAS
    assert not cruzadas, f"Variables prohibidas en el modelo: {cruzadas}"


def leer_contratos(conn) -> pd.DataFrame:
    df = leer_sql(conn, f"SELECT * FROM {VISTA}")
    df["fecha_firma"] = pd.to_datetime(df["fecha_firma"])
    df["valor_contrato"] = pd.to_numeric(df["valor_contrato"], errors="coerce")
    df["duracion_dias"] = pd.to_numeric(df["duracion_dias"], errors="coerce")
    df["prorrogado"] = df["prorrogado"].astype(int)
    df["es_vigente"] = df["es_vigente"].astype(bool)
    return df


def _historial(df: pd.DataFrame) -> pd.DataFrame:
    """Historial del contratista, contando solo contratos firmados ANTES del que se evalúa.

    contratos_previos: todos los anteriores (vigentes o no).
    tasa_prorroga_previa: prorrogados / anteriores ya resueltos (los vigentes sin prórroga
    todavía no se sabe cómo terminan, así que no cuentan en la tasa).
    """
    previos = np.zeros(len(df), dtype=int)
    resueltos = np.zeros(len(df), dtype=int)
    prorrogados = np.zeros(len(df), dtype=int)
    pos = {idx: i for i, idx in enumerate(df.index)}

    for _, g in df.groupby("codigo_proveedor", dropna=True):
        fechas = g["fecha_firma"].to_numpy()
        resuelto = (~g["es_vigente"]).to_numpy()
        etiqueta = g["prorrogado"].to_numpy()
        for idx, f in zip(g.index, fechas):
            if pd.isna(f):
                continue
            antes = (fechas < f) & ~pd.isna(fechas)
            i = pos[idx]
            previos[i] = antes.sum()
            resueltos[i] = (antes & resuelto).sum()
            prorrogados[i] = (antes & resuelto & (etiqueta == 1)).sum()

    out = pd.DataFrame(index=df.index)
    out["contratos_previos"] = previos
    out["previos_resueltos"] = resueltos
    out["previos_prorrogados"] = prorrogados
    out["tasa_prorroga_previa"] = np.where(resueltos > 0, prorrogados / np.maximum(resueltos, 1), np.nan)
    out["sin_historial"] = (resueltos == 0).astype(int)
    return out


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega las variables del modelo a las filas de v_ml_contratos."""
    df = df.copy()
    cat = df["categoria"].fillna("").str.extract(r"(\d{4})", expand=False)
    df["familia_categoria"] = cat.fillna("Sin dato")
    df["puede_prorrogarse"] = df["puede_prorrogarse"].fillna(False).astype(int)
    df["log_valor"] = np.log1p(df["valor_contrato"].clip(lower=0))
    df["duracion_sin_dato"] = df["duracion_dias"].isna().astype(int)
    df["anio_firma"] = df["fecha_firma"].dt.year
    df["mes_firma"] = df["fecha_firma"].dt.month
    for c in ["tipo_de_contrato", "modalidad_de_contratacion", "origen_de_los_recursos"]:
        df[c] = df[c].fillna("Sin dato")
    df = df.join(_historial(df))
    return df
