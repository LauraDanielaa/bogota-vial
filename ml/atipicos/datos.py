"""Datos y variables del modelo de contratos atípicos.

Fuente: la misma vista del modelo de riesgo, v_ml_contratos (etl/sql/06_ml.sql), leída con
riesgo_prorroga.datos.leer_contratos: 1 fila por contrato de clean_secop (913).
Aparte se toma de clean_secop el enlace del proceso en SECOP II (solo para revisar a mano).
"""

import numpy as np
import pandas as pd

from comun.db import leer_sql
from riesgo_prorroga.datos import VISTA, leer_contratos

CATEGORICAS = ["tipo_de_contrato", "modalidad_de_contratacion"]
NUMERICAS = [
    "log_valor",          # log(1 + valor del contrato)
    "plazo_dias",         # plazo pactado (texto de duraci_n_del_contrato, NO fecha_fin)
    "log_valor_dia",      # log(1 + valor / plazo pactado)
    "dias_adicionados",   # días de prórroga registrados en SECOP
]
VARIABLES = CATEGORICAS + NUMERICAS

SIN_DATO = "Sin dato"


def leer(conn) -> pd.DataFrame:
    """Contratos de v_ml_contratos con su referencia y su enlace a SECOP II."""
    df = leer_contratos(conn)
    url = leer_sql(conn, "SELECT id_contrato, urlproceso AS secop_url FROM clean_secop")
    url = url.drop_duplicates("id_contrato")
    return df.merge(url, on="id_contrato", how="left")


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega las variables del modelo.

    El plazo que falta (texto 'No definido' o sin número) se completa con la mediana de los
    contratos del mismo tipo y modalidad; queda marcado en plazo_imputado y nunca se usa
    como motivo.
    """
    df = df.copy()
    for c in CATEGORICAS:
        df[c] = df[c].fillna(SIN_DATO).astype(str).str.strip().replace("", SIN_DATO)
    df["valor_contrato"] = pd.to_numeric(df["valor_contrato"], errors="coerce").clip(lower=0).fillna(0.0)
    df["dias_adicionados"] = pd.to_numeric(df["dias_adicionados"], errors="coerce").fillna(0).clip(lower=0)

    plazo = pd.to_numeric(df["duracion_dias"], errors="coerce")
    plazo = plazo.where(plazo > 0)
    df["plazo_imputado"] = plazo.isna()
    mediana_grupo = plazo.groupby([df["tipo_de_contrato"], df["modalidad_de_contratacion"]]).transform("median")
    mediana_tipo = plazo.groupby(df["tipo_de_contrato"]).transform("median")
    df["plazo_dias"] = plazo.fillna(mediana_grupo).fillna(mediana_tipo).fillna(plazo.median())

    df["valor_dia"] = df["valor_contrato"] / df["plazo_dias"]
    df["log_valor"] = np.log1p(df["valor_contrato"])
    df["log_valor_dia"] = np.log1p(df["valor_dia"])
    return df


__all__ = ["VISTA", "VARIABLES", "CATEGORICAS", "NUMERICAS", "leer", "preparar"]
