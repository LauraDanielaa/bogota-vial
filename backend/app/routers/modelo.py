"""Endpoints del modelo de riesgo de prórroga (tablas ml_prorroga_* que llena ml/riesgo_prorroga).

El backend solo lee las tablas; no carga el modelo. Si el modelo aún no se ha
entrenado, las tablas están vacías y se responde "entrenado": false.
"""

from fastapi import APIRouter

from app.db import fetch_all

router = APIRouter(prefix="/modelo", tags=["modelo"])

# Umbrales de probabilidad del nivel de riesgo (los mismos de ml/riesgo_prorroga/entrenar.py)
UMBRALES = {"medio": 0.30, "alto": 0.60}
NOTA_RIESGO = (
    "Estimación estadística de la probabilidad de que el contrato sea prorrogado, "
    "calculada con contratos anteriores del IDU en SECOP II. No es un dato oficial del IDU."
)
NOMBRE_MODELO = {
    "linea_base": "Línea base (prevalencia)",
    "regresion_logistica": "Regresión logística",
    "random_forest": "Random forest",
    "gradient_boosting": "Gradient boosting",
}

SQL_VERSION_ACTIVA = "(SELECT version FROM v_prorroga_version_activa)"


def _num(v):
    return None if v is None else float(v)


@router.get("/metricas")
def metricas_modelo():
    """Métricas de los modelos comparados en la versión activa del modelo de riesgo."""
    filas = fetch_all(
        f"SELECT * FROM ml_prorroga_metricas WHERE version = {SQL_VERSION_ACTIVA} "
        "ORDER BY seleccionado DESC, cv_pr_auc DESC NULLS LAST"
    )
    if not filas:
        return {"entrenado": False, "umbrales": UMBRALES, "nota": NOTA_RIESGO, "modelos": []}

    elegido = next(f for f in filas if f["seleccionado"])
    columnas = ["cv_pr_auc", "cv_pr_auc_std", "cv_roc_auc", "cv_brier",
                "temporal_pr_auc", "temporal_roc_auc", "brier_calibrado"]
    return {
        "entrenado": True,
        "version": elegido["version"],
        "entrenado_en": elegido["entrenado_en"],
        "modelo": elegido["modelo"],
        "modelo_nombre": NOMBRE_MODELO.get(elegido["modelo"], elegido["modelo"]),
        "supera_linea_base": elegido["supera_linea_base"],
        "conclusion": elegido["nota"],
        "n_entrenamiento": elegido["n_entrenamiento"],
        "n_positivos": elegido["n_positivos"],
        "n_vigentes": elegido["n_vigentes"],
        "temporal_n_prueba": elegido["temporal_n_prueba"],
        "linea_base_pr_auc": _num(elegido["linea_base_pr_auc"]),
        "variables": elegido["variables"],
        "umbrales": UMBRALES,
        "nota": NOTA_RIESGO,
        "modelos": [
            {
                "modelo": f["modelo"],
                "nombre": NOMBRE_MODELO.get(f["modelo"], f["modelo"]),
                "seleccionado": f["seleccionado"],
                **{c: _num(f[c]) for c in columnas},
            }
            for f in filas
        ],
    }
