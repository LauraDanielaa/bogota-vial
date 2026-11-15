"""
Modelo de riesgo de prórroga: probabilidad de que un contrato del IDU tenga días adicionados.

Pasos:
    1. Lee v_ml_contratos (la crea el ETL en etl/sql/06_ml.sql) y arma las variables.
    2. Compara línea base, regresión logística, random forest y gradient boosting
       (validación cruzada estratificada de 5 pliegues + validación temporal ≤2023 / 2024+).
    3. Elige el de mayor PR-AUC, lo calibra (sigmoide) y calcula:
         - contratos de entrenamiento: probabilidad fuera de pliegue
         - contratos vigentes sin prórroga: probabilidad del modelo entrenado con todo
    4. Calcula con SHAP los 3 factores de cada contrato.
    5. Guarda el modelo en ml/models/riesgo_prorroga/ y escribe en la base:
         ml_prorroga_metricas, ml_prorroga_contrato, ml_riesgo_obra

Uso:  python ml/run_ml.py riesgo_prorroga   |   docker compose run --rm ml riesgo_prorroga
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from psycopg2.extras import Json, execute_values
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate

from comun.db import conectar, existe_relacion
from riesgo_prorroga.datos import PROHIBIDAS, VARIABLES, VISTA, leer_contratos, preparar, verificar_variables
from riesgo_prorroga.factores import top_factores, valores_shap, variable_de_columna
from riesgo_prorroga.modelos import NOMBRE_MODELO, SEMILLA, candidatos

DIR_MODELOS = Path(__file__).resolve().parents[1] / "models" / "riesgo_prorroga"

ANIO_CORTE_TEMPORAL = 2023      # entrena hasta 2023, prueba 2024 en adelante
UMBRAL_MEDIO, UMBRAL_ALTO = 0.30, 0.60
# "Supera claramente a la línea base": PR-AUC al menos 0,10 por encima en validación
# cruzada y al menos 0,05 por encima en la validación temporal.
MARGEN_CV, MARGEN_TEMPORAL = 0.10, 0.05


def _r(v, dec=4):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), dec)


def evaluar(nombre, pipeline, X, y, anios):
    """Métricas de un candidato: validación cruzada y validación temporal."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    res = cross_validate(
        clone(pipeline), X, y, cv=cv,
        scoring={"pr_auc": "average_precision", "roc_auc": "roc_auc", "brier": "neg_brier_score"},
    )
    ent, prueba = anios <= ANIO_CORTE_TEMPORAL, anios > ANIO_CORTE_TEMPORAL
    modelo_t = clone(pipeline).fit(X[ent], y[ent])
    p_t = modelo_t.predict_proba(X[prueba])[:, 1]
    return {
        "modelo": nombre,
        "cv_pr_auc": res["test_pr_auc"].mean(),
        "cv_pr_auc_std": res["test_pr_auc"].std(),
        "cv_roc_auc": res["test_roc_auc"].mean(),
        "cv_brier": -res["test_brier"].mean(),
        "temporal_pr_auc": average_precision_score(y[prueba], p_t),
        "temporal_roc_auc": roc_auc_score(y[prueba], p_t),
        "temporal_n_prueba": int(prueba.sum()),
    }


def imprimir_metricas(metricas):
    print()
    print(f"  {'Modelo':<26}{'PR-AUC CV':>14}{'ROC-AUC CV':>12}{'Brier CV':>10}{'PR-AUC temp.':>14}{'ROC-AUC temp.':>15}")
    for m in metricas:
        marca = "  <- elegido" if m.get("seleccionado") else ""
        print(
            f"  {NOMBRE_MODELO[m['modelo']]:<26}"
            f"{m['cv_pr_auc']:>8.3f} ±{m['cv_pr_auc_std']:.3f}"
            f"{m['cv_roc_auc']:>12.3f}{m['cv_brier']:>10.3f}"
            f"{m['temporal_pr_auc']:>14.3f}{m['temporal_roc_auc']:>15.3f}{marca}"
        )
    print()


def comprobar_sin_prohibidas(pipeline_entrenado):
    """Demuestra que ninguna variable prohibida entró al modelo."""
    verificar_variables()
    columnas = list(pipeline_entrenado.named_steps["prep"].get_feature_names_out())
    origen = {variable_de_columna(c) for c in columnas}
    assert origen == set(VARIABLES), f"Variables inesperadas: {origen ^ set(VARIABLES)}"
    assert not (origen & PROHIBIDAS), f"Variables prohibidas: {origen & PROHIBIDAS}"
    print(f"  Variables del modelo ({len(VARIABLES)}): {', '.join(VARIABLES)}")
    print(f"  Columnas tras la transformación: {len(columnas)}")
    print(f"  Prohibidas revisadas, ninguna presente: {', '.join(sorted(PROHIBIDAS))}")


def main():
    conn = conectar()
    if not existe_relacion(conn, VISTA) or not existe_relacion(conn, "ml_prorroga_metricas"):
        sys.exit(f"No existe {VISTA} o las tablas ml_*. Corre primero el ETL: docker compose run --rm etl")

    verificar_variables()
    version = datetime.now().strftime("%Y%m%d-%H%M%S")

    # ---------------- datos ----------------
    df = preparar(leer_contratos(conn))
    entren = df[~df["es_vigente"]]
    vigentes = df[df["es_vigente"]]
    X, y = entren[VARIABLES], entren["prorrogado"].to_numpy()
    anios = entren["anio_firma"].to_numpy()
    print(f"  Contratos: {len(df)} · entrenamiento: {len(entren)} ({y.sum()} prorrogados, "
          f"{100 * y.mean():.1f} %) · vigentes sin prórroga (solo predicción): {len(vigentes)}")

    # ---------------- comparación ----------------
    modelos = candidatos()
    metricas = [evaluar(n, p, X, y, anios) for n, p in modelos.items()]
    base = next(m for m in metricas if m["modelo"] == "linea_base")
    mejor = max((m for m in metricas if m["modelo"] != "linea_base"), key=lambda m: m["cv_pr_auc"])
    mejor["seleccionado"] = True
    supera = bool(mejor["cv_pr_auc"] - base["cv_pr_auc"] >= MARGEN_CV
                  and mejor["temporal_pr_auc"] - base["temporal_pr_auc"] >= MARGEN_TEMPORAL)
    imprimir_metricas(metricas)

    # ---------------- calibración y probabilidades ----------------
    calibrado = CalibratedClassifierCV(
        clone(modelos[mejor["modelo"]]), method="sigmoid",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA),
    )
    cv_externo = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA + 1)
    p_oof = cross_val_predict(calibrado, X, y, cv=cv_externo, method="predict_proba")[:, 1]
    mejor["brier_calibrado"] = brier_score_loss(y, p_oof)
    calibrado.fit(X, y)
    p_vig = calibrado.predict_proba(vigentes[VARIABLES])[:, 1] if len(vigentes) else np.array([])
    print(f"  Calibrado ({NOMBRE_MODELO[mejor['modelo']]}): Brier fuera de pliegue {mejor['brier_calibrado']:.3f} "
          f"· PR-AUC fuera de pliegue {average_precision_score(y, p_oof):.3f}")

    if supera:
        nota = (f"{NOMBRE_MODELO[mejor['modelo']]} supera a la línea base: PR-AUC {mejor['cv_pr_auc']:.2f} "
                f"vs. {base['cv_pr_auc']:.2f} (validación cruzada) y {mejor['temporal_pr_auc']:.2f} "
                f"vs. {base['temporal_pr_auc']:.2f} (2024 en adelante).")
    else:
        nota = (f"ATENCIÓN: {NOMBRE_MODELO[mejor['modelo']]} NO supera claramente a la línea base "
                f"(PR-AUC {mejor['cv_pr_auc']:.2f} vs. {base['cv_pr_auc']:.2f} en validación cruzada, "
                f"{mejor['temporal_pr_auc']:.2f} vs. {base['temporal_pr_auc']:.2f} en 2024 en adelante). "
                "Sus probabilidades aportan poco frente a la tasa general de prórroga.")
    print(f"  {nota}")

    # ---------------- explicación (SHAP) ----------------
    explicado = clone(modelos[mejor["modelo"]]).fit(X, y)
    comprobar_sin_prohibidas(explicado)
    fondo = X.sample(min(200, len(X)), random_state=SEMILLA)
    shap_df = valores_shap(explicado, df[VARIABLES], fondo)
    factores = top_factores(shap_df, df)

    # ---------------- guardar modelo ----------------
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_MODELOS / f"riesgo_prorroga_{version}.joblib"
    joblib.dump({"version": version, "modelo": mejor["modelo"], "calibrado": calibrado,
                 "explicado": explicado, "variables": VARIABLES}, ruta)
    ruta.with_suffix(".json").write_text(
        json.dumps({"version": version, "modelo": mejor["modelo"], "supera_linea_base": supera, "nota": nota,
                    "variables": VARIABLES, "metricas": [{k: _r(v) if isinstance(v, float) else v
                                                         for k, v in m.items()} for m in metricas]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Modelo guardado en {ruta}")

    # ---------------- escribir en la base ----------------
    n_pos, n_ent, n_vig = int(y.sum()), len(entren), len(vigentes)
    filas_metricas = [
        (version, m["modelo"], bool(m.get("seleccionado")), n_ent, n_pos, n_vig,
         _r(m["cv_pr_auc"]), _r(m["cv_pr_auc_std"]), _r(m["cv_roc_auc"]), _r(m["cv_brier"]),
         _r(m["temporal_pr_auc"]), _r(m["temporal_roc_auc"]), m["temporal_n_prueba"],
         _r(base["cv_pr_auc"]), _r(m.get("brier_calibrado")),
         supera if m.get("seleccionado") else None, VARIABLES,
         nota if m.get("seleccionado") else None)
        for m in metricas
    ]
    filas_pred = [
        (version, f["id_contrato"], _r(p, 6), "fuera_de_pliegue", int(f["prorrogado"]), Json(factores[f["id_contrato"]]))
        for (_, f), p in zip(entren.iterrows(), p_oof)
    ] + [
        (version, f["id_contrato"], _r(p, 6), "vigente", None, Json(factores[f["id_contrato"]]))
        for (_, f), p in zip(vigentes.iterrows(), p_vig)
    ]

    with conn, conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO ml_prorroga_metricas (version, modelo, seleccionado, n_entrenamiento, n_positivos,
                n_vigentes, cv_pr_auc, cv_pr_auc_std, cv_roc_auc, cv_brier, temporal_pr_auc, temporal_roc_auc,
                temporal_n_prueba, linea_base_pr_auc, brier_calibrado, supera_linea_base, variables, nota)
            VALUES %s""", filas_metricas)
        execute_values(cur, """
            INSERT INTO ml_prorroga_contrato (version, id_contrato, probabilidad, origen, prorrogado, factores)
            VALUES %s""", filas_pred)
        cur.execute("""
            INSERT INTO ml_riesgo_obra (version, objectid, id_contrato, nivel, probabilidad, dias_adicionados, factores)
            SELECT %(v)s, o.objectid, o.secop_id_contrato,
                   clasificar_riesgo(o.estado_seguimiento, o.secop_id_contrato, c.dias_adicionados,
                                     p.probabilidad, %(um)s, %(ua)s),
                   p.probabilidad, c.dias_adicionados, p.factores
            FROM v_obras_seguimiento o
            LEFT JOIN clean_secop c ON c.id_contrato = o.secop_id_contrato
            LEFT JOIN ml_prorroga_contrato p ON p.version = %(v)s AND p.id_contrato = o.secop_id_contrato
            """, {"v": version, "um": UMBRAL_MEDIO, "ua": UMBRAL_ALTO})
        cur.execute("SELECT nivel, count(*) FROM ml_riesgo_obra WHERE version = %s GROUP BY 1 ORDER BY 2 DESC",
                    (version,))
        niveles = cur.fetchall()
    conn.close()

    print(f"  Versión {version}: {len(filas_pred)} contratos con probabilidad.")
    print("  Obras por nivel de riesgo: " + " · ".join(f"{n}: {k}" for n, k in niveles))
