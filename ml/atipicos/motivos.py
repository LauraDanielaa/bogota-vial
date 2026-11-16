"""Motivos de un contrato atípico, redactados en español.

IsolationForest no dice por qué aísla un contrato, así que el motivo se calcula aparte:
cada variable del contrato se compara con la mediana de los contratos de su mismo tipo y
modalidad (su "grupo de referencia"). Las diferencias de al menos el doble (o la mitad)
son motivos claros; se redactan las una a tres más grandes.

Grupo de referencia: tipo + modalidad si tiene al menos MIN_GRUPO contratos; si no, solo
el tipo; si tampoco, todos los contratos.

Tamaño de una diferencia = |log2(valor / mediana)|  (1 = el doble o la mitad).
Para los días adicionados, que en casi todos los grupos tienen mediana 0, se suma un
colchón de COLCHON_DIAS a ambos lados y solo cuenta hacia arriba (tener menos prórroga de
lo habitual no es un motivo). Con mediana 0 hacen falta al menos 90 días adicionados.
"""

import math

import numpy as np
import pandas as pd

MIN_GRUPO = 8
UMBRAL = 1.0           # log2: el doble o la mitad
COLCHON_DIAS = 90
MAX_MOTIVOS = 3


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------
def _num_es(v: float, dec: int = 1) -> str:
    """3.44 -> '3,4' · 12.0 -> '12'"""
    if v >= 10 or dec == 0:
        return f"{round(v):,}".replace(",", ".")
    return f"{v:.{dec}f}".replace(".", ",")


def _minus(s: str) -> str:
    """'Licitación Pública' -> 'licitación pública' (deja las siglas como están)."""
    return " ".join(p if p.isupper() and len(p) > 1 else p.lower() for p in str(s).split())


def _veces(r: float) -> str:
    """Razón >= 2 frente a lo habitual: 'el doble de', 'el triple de', '4,5 veces'."""
    if round(r, 1) == 2.0:
        return "el doble de"
    if round(r, 1) == 3.0:
        return "el triple de"
    return f"{_num_es(r)} veces"


def _plazo(dias: float) -> str:
    if dias >= 60:
        meses = round(dias / 30)
        return f"{meses} meses"
    d = round(dias)
    return f"{d} {'día' if d == 1 else 'días'}"


def _dias(d: float) -> str:
    d = int(round(d))
    return f"{d} {'día adicionado' if d == 1 else 'días adicionados'}"


# Nombres cortos para redactar (SECOP repite o abrevia algunas modalidades)
NOMBRE_MODALIDAD = {
    "Licitación pública Obra Publica": "licitación pública",
    "Concurso de méritos abierto": "concurso de méritos",
    "Contratación Directa (con ofertas)": "contratación directa con ofertas",
    "Selección abreviada subasta inversa": "subasta inversa",
    "Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes": "selección abreviada de menor cuantía",
    "Contratación régimen especial (con ofertas)": "régimen especial con ofertas",
    "Contratación régimen especial": "régimen especial",
}
NOMBRE_TIPO = {"Otro": "otro tipo"}


def nombre_grupo(nivel: str, tipo: str, modalidad: str) -> str:
    t = NOMBRE_TIPO.get(tipo, _minus(tipo))
    if nivel == "tipo_modalidad":
        return f"contratos de {t} por {NOMBRE_MODALIDAD.get(modalidad, _minus(modalidad))}"
    if nivel == "tipo":
        return f"contratos de {t}"
    return "los contratos del IDU"


def _texto(variable: str, v: float, m: float, grupo: str) -> str:
    sube = v > m
    r = v / m if m else math.inf
    if variable == "valor_contrato":
        if sube:
            return f"Valor {_num_es(r)} veces mayor que la mediana de {grupo}"
        return f"Valor equivalente al {_num_es(100 * r, 0)} % de la mediana de {grupo}"
    if variable == "plazo_dias":
        if sube:
            return f"Plazo pactado de {_plazo(v)}, {_veces(r)} lo habitual para {grupo} ({_plazo(m)})"
        return f"Plazo pactado de {_plazo(v)}, mucho menor que lo habitual para {grupo} ({_plazo(m)})"
    if variable == "valor_dia":
        if sube:
            return f"Valor por día de plazo {_num_es(r)} veces mayor que la mediana de {grupo}"
        return f"Valor por día de plazo equivalente al {_num_es(100 * r, 0)} % de la mediana de {grupo}"
    if variable == "dias_adicionados":
        if m == 0:
            return f"{_dias(v)}; la mayoría de {grupo} no tiene días adicionados"
        return f"{_dias(v)}, {_veces(v / m)} lo habitual en {grupo} ({_dias(m)})"
    raise ValueError(variable)


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
VARIABLES_MOTIVO = ["valor_contrato", "plazo_dias", "valor_dia", "dias_adicionados"]


def medianas_de_referencia(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada contrato: nivel y nombre de su grupo de referencia y la mediana de cada
    variable en ese grupo. Los plazos imputados no cuentan para las medianas de plazo."""
    t, mo = df["tipo_de_contrato"], df["modalidad_de_contratacion"]
    n_tm = df.groupby([t, mo])["id_contrato"].transform("size")
    n_t = df.groupby(t)["id_contrato"].transform("size")
    nivel = np.where(n_tm >= MIN_GRUPO, "tipo_modalidad", np.where(n_t >= MIN_GRUPO, "tipo", "todos"))

    out = pd.DataFrame(index=df.index)
    out["nivel"] = nivel
    out["n_grupo"] = np.where(nivel == "tipo_modalidad", n_tm, np.where(nivel == "tipo", n_t, len(df)))
    out["grupo"] = [nombre_grupo(n, a, b) for n, a, b in zip(nivel, t, mo)]

    real = df.copy()
    for c in ["plazo_dias", "valor_dia"]:
        real[c] = real[c].where(~df["plazo_imputado"])
    for c in VARIABLES_MOTIVO:
        m_tm = real.groupby([t, mo])[c].transform("median")
        m_t = real.groupby(t)[c].transform("median")
        m_all = real[c].median()
        out[f"med_{c}"] = np.where(nivel == "tipo_modalidad", m_tm, np.where(nivel == "tipo", m_t, m_all))
    return out


def _tamano(variable: str, v: float, m: float) -> float:
    if variable == "dias_adicionados":
        return math.log2((v + COLCHON_DIAS) / (m + COLCHON_DIAS)) if v > m else 0.0
    if v is None or m is None or pd.isna(v) or pd.isna(m) or v <= 0 or m <= 0:
        return 0.0
    return abs(math.log2(v / m))


def motivos_de(fila: pd.Series, ref: pd.Series) -> list[dict]:
    """Las una a tres diferencias claras más grandes del contrato frente a su grupo.

    [{"variable", "texto", "contrato", "mediana", "tamano"}] ordenadas de mayor a menor;
    lista vacía si no hay ninguna diferencia clara.
    """
    candidatos = {}
    for c in VARIABLES_MOTIVO:
        if c in ("plazo_dias", "valor_dia") and fila["plazo_imputado"]:
            continue
        v, m = float(fila[c]), ref[f"med_{c}"]
        if pd.isna(m):
            continue
        tam = _tamano(c, v, float(m))
        if tam >= UMBRAL:
            candidatos[c] = (tam, v, float(m))

    # El valor por día es el cociente de los otros dos: solo se usa como motivo si ni el
    # valor ni el plazo lo son por sí solos (si no, repetiría lo mismo).
    if "valor_dia" in candidatos and ("valor_contrato" in candidatos or "plazo_dias" in candidatos):
        del candidatos["valor_dia"]

    orden = sorted(candidatos.items(), key=lambda kv: kv[1][0], reverse=True)[:MAX_MOTIVOS]
    return [
        {"variable": c, "texto": _texto(c, v, m, ref["grupo"]), "contrato": round(v, 2),
         "mediana": round(m, 2), "tamano": round(tam, 3)}
        for c, (tam, v, m) in orden
    ]


def calcular(df: pd.DataFrame) -> list[list[dict]]:
    """Motivos de todos los contratos (en el mismo orden de df)."""
    ref = medianas_de_referencia(df)
    return [motivos_de(df.loc[i], ref.loc[i]) for i in df.index]
