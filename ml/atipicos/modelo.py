"""IsolationForest sobre los contratos de v_ml_contratos.

Las categóricas (tipo y modalidad) van en one-hot; las categorías con menos de
MIN_FRECUENCIA contratos se agrupan en una sola columna, para que un contrato no quede
marcado solo por ser de una modalidad poco común. Las numéricas entran tal cual
(IsolationForest no necesita escalarlas).
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from atipicos.datos import CATEGORICAS, NUMERICAS, VARIABLES

SEMILLA = 42
SEMILLAS_VALIDACION = [7, 21, 123, 2024, 31415]   # cinco semillas distintas de SEMILLA
CONTAMINACION = 0.05
N_ARBOLES = 500
MIN_FRECUENCIA = 10

PARAMETROS = {
    "algoritmo": "IsolationForest",
    "contaminacion": CONTAMINACION,
    "n_arboles": N_ARBOLES,
    "semilla": SEMILLA,
    "semillas_validacion": SEMILLAS_VALIDACION,
    "min_frecuencia_categoria": MIN_FRECUENCIA,
    "variables": VARIABLES,
}


def pipeline(semilla: int = SEMILLA) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=MIN_FRECUENCIA,
                                  sparse_output=False), CATEGORICAS),
            ("num", "passthrough", NUMERICAS),
        ]
    )
    bosque = IsolationForest(
        n_estimators=N_ARBOLES, contamination=CONTAMINACION, random_state=semilla, n_jobs=-1,
    )
    return Pipeline([("prep", prep), ("bosque", bosque)])


def ajustar(df: pd.DataFrame, semilla: int = SEMILLA) -> tuple[np.ndarray, np.ndarray]:
    """Entrena con todos los contratos y los califica.

    Devuelve (marcado, puntaje): marcado = True si IsolationForest lo deja en el ~5 % más
    aislado; puntaje = -score_samples (más alto = más atípico). El puntaje solo sirve para
    ordenar dentro de la ejecución; no se muestra en la web.
    """
    modelo = pipeline(semilla).fit(df[VARIABLES])
    marcado = modelo.predict(df[VARIABLES]) == -1
    puntaje = -modelo.score_samples(df[VARIABLES])
    return marcado, puntaje
