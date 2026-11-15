"""Factores que explican cada predicción (SHAP), redactados en español claro.

Se explica el modelo seleccionado SIN calibrar: la calibración (sigmoide) es monótona,
así que no cambia qué variables empujan la probabilidad hacia arriba o hacia abajo.
"""

import numpy as np
import pandas as pd
import shap

from riesgo_prorroga.datos import VARIABLES, grupo_de

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Familias UNSPSC más frecuentes en los contratos del IDU
FAMILIAS = {
    "8110": "servicios de ingeniería",
    "7214": "construcción de obras civiles",
    "7210": "mantenimiento y reparación de infraestructura",
    "8111": "servicios informáticos",
    "4323": "software",
    "8413": "seguros",
    "8013": "servicios inmobiliarios",
    "8010": "asesoría de gestión",
}


def variable_de_columna(columna: str) -> str:
    """'tipo_de_contrato_Obra' -> 'tipo_de_contrato' (columna transformada -> variable original)."""
    if columna in VARIABLES:
        return columna
    candidatas = [v for v in VARIABLES if columna.startswith(v + "_")]
    if not candidatas:
        raise ValueError(f"Columna transformada sin variable de origen: {columna}")
    return max(candidatas, key=len)


def valores_shap(pipeline, X: pd.DataFrame, X_fondo: pd.DataFrame) -> pd.DataFrame:
    """Valores SHAP por variable original (las columnas one-hot se suman)."""
    prep, modelo = pipeline.named_steps["prep"], pipeline.named_steps["modelo"]
    Xt = prep.transform(X)
    columnas = prep.get_feature_names_out()
    if hasattr(modelo, "coef_"):
        explicador = shap.LinearExplainer(modelo, prep.transform(X_fondo))
    else:
        explicador = shap.TreeExplainer(modelo)
    sv = explicador.shap_values(Xt)
    if isinstance(sv, list):          # versiones antiguas: una matriz por clase
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:                  # (filas, columnas, clases)
        sv = sv[:, :, 1]
    por_columna = pd.DataFrame(sv, columns=columnas, index=X.index)
    grupos = [grupo_de(variable_de_columna(c)) for c in columnas]
    return por_columna.T.groupby(grupos).sum().T


def _pct(v) -> str:
    return f"{round(100 * v)} %"


def _num_es(v, dec=0) -> str:
    """1234.5 -> '1.234,5' (formato colombiano)."""
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pesos(v) -> str:
    if v >= 1e9:
        return f"{_num_es(v / 1e9, 1)} mil millones de pesos"
    if v >= 1e6:
        return f"{_num_es(v / 1e6)} millones de pesos"
    return f"{_num_es(v)} pesos"


def _duracion(texto: str, dias) -> str:
    t = (texto or "").strip()
    partes = t.split()
    if len(partes) == 2 and partes[0].isdigit():
        n = int(partes[0])
        unidad = partes[1].lower()
        if unidad.startswith("mes"):
            return f"{n} {'mes' if n == 1 else 'meses'}"
        if unidad.startswith("a"):
            return f"{n} {'año' if n == 1 else 'años'}"
        return f"{n} {'día' if n == 1 else 'días'}"
    return f"{int(dias)} días"


def redactar(grupo: str, fila: pd.Series) -> str:
    """Texto del factor para un contrato. Usa los valores reales, no los transformados."""
    if grupo == "historial":
        if fila["previos_resueltos"] == 0:
            if fila["contratos_previos"] > 0:
                return "Los contratos anteriores del contratista con el IDU aún no han terminado"
            return "El contratista no tenía contratos anteriores con el IDU"
        n = int(fila["previos_resueltos"])
        return (f"El contratista prorrogó el {_pct(fila['tasa_prorroga_previa'])} de sus "
                f"{'contrato anterior' if n == 1 else f'{n} contratos anteriores'}")
    if grupo == "contratos_previos":
        n = int(fila["contratos_previos"])
        if n == 0:
            return "Es el primer contrato del contratista con el IDU"
        return f"El contratista tenía {n} {'contrato anterior' if n == 1 else 'contratos anteriores'} con el IDU"
    if grupo == "duracion":
        if fila["duracion_sin_dato"]:
            return "La duración pactada no está registrada en SECOP"
        return f"Duración pactada de {_duracion(fila['duracion_texto'], fila['duracion_dias'])}"
    if grupo == "log_valor":
        v = fila["valor_contrato"]
        return "El valor del contrato no está registrado" if pd.isna(v) else f"Valor del contrato: {_pesos(v)}"
    if grupo == "tipo_de_contrato":
        return f"Contrato de tipo {fila['tipo_de_contrato']}"
    if grupo == "modalidad_de_contratacion":
        return f"Modalidad de contratación: {fila['modalidad_de_contratacion']}"
    if grupo == "origen_de_los_recursos":
        return f"Origen de los recursos: {fila['origen_de_los_recursos']}"
    if grupo == "puede_prorrogarse":
        return "El contrato permite prórroga" if fila["puede_prorrogarse"] else "El contrato no permite prórroga"
    if grupo == "familia_categoria":
        cod = fila["familia_categoria"]
        if cod == "Sin dato":
            return "La categoría del contrato no está registrada"
        nombre = FAMILIAS.get(cod)
        return f"Categoría del contrato: {nombre} (UNSPSC {cod})" if nombre else f"Categoría UNSPSC {cod}"
    if grupo == "anio_firma":
        return "Sin fecha de firma" if pd.isna(fila["anio_firma"]) else f"Firmado en {int(fila['anio_firma'])}"
    if grupo == "mes_firma":
        return "Sin fecha de firma" if pd.isna(fila["mes_firma"]) else f"Firmado en {MESES[int(fila['mes_firma']) - 1]}"
    return grupo


def top_factores(shap_df: pd.DataFrame, datos: pd.DataFrame, n: int = 3) -> dict:
    """id_contrato -> lista de los n factores con más peso [{variable, texto, efecto}]."""
    salida = {}
    for idx, fila_shap in shap_df.iterrows():
        fila = datos.loc[idx]
        orden = fila_shap.abs().sort_values(ascending=False).index[:n]
        salida[fila["id_contrato"]] = [
            {
                "variable": g,
                "texto": redactar(g, fila),
                "efecto": "aumenta" if fila_shap[g] > 0 else "reduce",
            }
            for g in orden
        ]
    return salida
