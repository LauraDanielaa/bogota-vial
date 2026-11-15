"""Endpoints del modelo de riesgo de prórroga (tablas ml_prorroga_* que llena ml/riesgo_prorroga).

El backend solo lee las tablas; no carga el modelo. Si el modelo aún no se ha
entrenado, las tablas están vacías y se responde "entrenado": false. Si las tablas
ni siquiera existen (la base todavía no ha pasado por etl/sql/06_ml.sql), se
responde igual, sin error: el riesgo queda "Sin calcular".
"""

from fastapi import APIRouter

from app.db import fetch_all, fetch_one

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


def riesgo_disponible() -> bool:
    """True si la base ya tiene las tablas y la vista del modelo de riesgo (06_ml.sql)."""
    fila = fetch_one(
        "SELECT to_regclass('ml_riesgo_obra') IS NOT NULL "
        "   AND to_regclass('ml_prorroga_metricas') IS NOT NULL "
        "   AND to_regclass('v_prorroga_version_activa') IS NOT NULL AS ok"
    )
    return bool(fila and fila["ok"])


# Sustitutos vacíos (mismas columnas, cero filas) para cuando las tablas no existen
_RIESGO_OBRA_VACIA = (
    "(SELECT NULL::text AS version, NULL::integer AS objectid, NULL::text AS nivel, "
    "NULL::numeric AS probabilidad, NULL::jsonb AS factores WHERE false)"
)
_METRICAS_VACIA = (
    "(SELECT NULL::text AS version, NULL::text AS modelo, NULL::boolean AS seleccionado, "
    "NULL::boolean AS supera_linea_base, NULL::timestamptz AS entrenado_en WHERE false)"
)


def fuentes_riesgo() -> dict:
    """Fragmentos SQL para cruzar con el riesgo: las tablas reales si existen o
    sustitutos vacíos si no (así el riesgo sale 'Sin calcular' en vez de un error 500).

    Claves: riesgo_obra, metricas, version (expresión con la versión activa).
    """
    if riesgo_disponible():
        return {"riesgo_obra": "ml_riesgo_obra", "metricas": "ml_prorroga_metricas", "version": SQL_VERSION_ACTIVA}
    return {"riesgo_obra": _RIESGO_OBRA_VACIA, "metricas": _METRICAS_VACIA, "version": "NULL::text"}


def _num(v):
    return None if v is None else float(v)


@router.get("/metricas")
def metricas_modelo():
    """Métricas de los modelos comparados en la versión activa del modelo de riesgo."""
    if not riesgo_disponible():
        return {"entrenado": False, "umbrales": UMBRALES, "nota": NOTA_RIESGO, "modelos": []}
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
