"""Endpoints del modelo de contratos atípicos (tablas ml_atipicos_* que llena ml/atipicos).

El backend solo lee la última ejecución exitosa (vista v_atipicos_ejecucion_activa); nunca
recalcula nada. Si el modelo aún no se ha ejecutado, o si las tablas ni siquiera existen,
se responde "ejecutado": false y las obras salen sin marca, sin error.

Estos endpoints nunca devuelven el nombre del contratista ni el puntaje del modelo.
"""

import plotly.graph_objects as go
from fastapi import APIRouter

from app.db import fetch_all, fetch_one
from app.routers.dashboard import FUENTE, GRILLA, TEXTO, TEXTO_2, _a_json, _layout, _num_es, _plural

router = APIRouter(prefix="/atipicos", tags=["atipicos"])

NOTA_ATIPICO = (
    "Este contrato se sale de lo habitual frente a {n} contratos del IDU en SECOP II. Que sea atípico no "
    "significa que haya una irregularidad; puede deberse al tamaño o la complejidad de la obra."
)

SQL_EJECUCION_ACTIVA = "(SELECT id FROM v_atipicos_ejecucion_activa)"

# Contratos que tienen obra en el mapa (mismo cruce que /api/obras/mapa)
SQL_CONTRATOS_CON_OBRA = """
    (SELECT DISTINCT s.secop_id_contrato AS id_contrato
     FROM v_obras_mapa m JOIN v_obras_seguimiento s USING (objectid)
     WHERE s.secop_id_contrato IS NOT NULL)
"""


def atipicos_disponible() -> bool:
    """True si la base ya tiene las tablas y la vista del modelo de atípicos (06_ml.sql)."""
    fila = fetch_one(
        "SELECT to_regclass('ml_atipicos_ejecucion') IS NOT NULL "
        "   AND to_regclass('ml_atipicos_contrato') IS NOT NULL "
        "   AND to_regclass('v_atipicos_ejecucion_activa') IS NOT NULL AS ok"
    )
    return bool(fila and fila["ok"])


# Sustituto vacío (mismas columnas, cero filas) para cuando las tablas no existen
_ATIPICOS_VACIA = "(SELECT NULL::text AS id_contrato, NULL::jsonb AS motivos WHERE false)"


def fuente_atipicos() -> str:
    """Subconsulta SQL con los contratos atípicos de la última ejecución exitosa:
    id_contrato y motivos (lista de textos, en orden). Vacía si el modelo no se ha ejecutado."""
    if not atipicos_disponible():
        return _ATIPICOS_VACIA
    return f"""
        (SELECT a.id_contrato,
                (SELECT coalesce(jsonb_agg(m.e ->> 'texto' ORDER BY m.i), '[]'::jsonb)
                 FROM jsonb_array_elements(a.motivos) WITH ORDINALITY m(e, i)) AS motivos
         FROM ml_atipicos_contrato a
         WHERE a.es_atipico AND a.ejecucion_id = {SQL_EJECUCION_ACTIVA})
    """


def _ejecucion_activa():
    if not atipicos_disponible():
        return None
    return fetch_one(
        "SELECT id, version, ejecutado_en, n_contratos, n_atipicos, estabilidad FROM v_atipicos_ejecucion_activa"
    )


@router.get("/ejecucion")
def ultima_ejecucion():
    """Datos de la última ejecución exitosa: fecha, contratos analizados, atípicos y estabilidad.

    Los conteos con obra se calculan con las obras actuales del mapa (varias obras pueden
    compartir un contrato)."""
    e = _ejecucion_activa()
    if e is None:
        return {"ejecutado": False}
    obra = fetch_one(
        f"""
        SELECT count(DISTINCT a.id_contrato) AS contratos, count(*) AS obras
        FROM v_obras_mapa m
        JOIN v_obras_seguimiento s USING (objectid)
        JOIN {fuente_atipicos()} a ON a.id_contrato = s.secop_id_contrato
        """
    )
    return {
        "ejecutado": True,
        "version": e["version"],
        "ejecutado_en": e["ejecutado_en"],
        "n_contratos": e["n_contratos"],
        "n_atipicos": e["n_atipicos"],
        "n_atipicos_con_obra": obra["contratos"],
        "n_obras_con_contrato_atipico": obra["obras"],
        "estabilidad": None if e["estabilidad"] is None else float(e["estabilidad"]),
        "nota": NOTA_ATIPICO.format(n=e["n_contratos"]),
    }


# ---------------------------------------------------------------------------
# Gráfico de dispersión: valor vs. plazo pactado de todos los contratos
# ---------------------------------------------------------------------------
COLOR_CONTRATO = "#d6ccbf"
COLOR_ATIPICO = "#3a2a22"

TICKS_PLAZO = [(15, "15 días"), (30, "1 mes"), (90, "3 meses"), (180, "6 meses"), (365, "1 año"),
               (730, "2 años"), (1460, "4 años"), (2920, "8 años")]
TICKS_VALOR = [(10 ** k, t) for k, t in [(6, "$1 M"), (7, "$10 M"), (8, "$100 M"), (9, "$1.000 M"),
                                          (10, "$10.000 M"), (11, "$100.000 M"), (12, "$1 billón"),
                                          (13, "$10 billones")]]


def _figura_dispersion(puntos):
    grupos = [
        # (atípico, con obra, nombre, estilo del marcador)
        (False, False, "Contratos", dict(color=COLOR_CONTRATO, size=6, opacity=0.85)),
        (False, True, "Con obra en el mapa", dict(color=COLOR_CONTRATO, size=9, symbol="diamond",
                                                  line=dict(color=TEXTO_2, width=1))),
        (True, False, "Atípicos", dict(color=COLOR_ATIPICO, size=8, line=dict(color="#fffdf9", width=1))),
        (True, True, "Atípicos con obra en el mapa", dict(color=COLOR_ATIPICO, size=12, symbol="diamond",
                                                          line=dict(color="#fffdf9", width=1.5))),
    ]
    fig = go.Figure()
    for atipico, con_obra, nombre, marcador in grupos:
        sel = [p for p in puntos if p["atipico"] == atipico and p["con_obra"] == con_obra]
        if not sel:
            continue
        fig.add_trace(go.Scatter(  # Scatter y no Scattergl: el frontend usa plotly.js-basic
            x=[p["plazo_dias"] for p in sel], y=[p["valor"] for p in sel], mode="markers", name=nombre,
            marker=marcador,
            customdata=[[p["referencia"] or "Sin referencia", p["tipo"] or "Sin dato", p["modalidad"] or "Sin dato"]
                        for p in sel],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
        ))
    plazos = [p["plazo_dias"] for p in puntos]
    valores = [p["valor"] for p in puntos]
    tx = [t for t in TICKS_PLAZO if min(plazos) / 2 <= t[0] <= max(plazos) * 2]
    ty = [t for t in TICKS_VALOR if min(valores) / 10 <= t[0] <= max(valores) * 10]
    _layout(
        fig,
        height=380,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11, color=TEXTO)),
        margin=dict(l=8, r=16, t=36, b=8),
        hovermode="closest",
        xaxis=dict(type="log", title=dict(text="Plazo pactado (escala logarítmica)", font=dict(size=11)),
                   tickvals=[t[0] for t in tx], ticktext=[t[1] for t in tx], gridcolor=GRILLA,
                   zeroline=False, tickfont=dict(size=10)),
        yaxis=dict(type="log", title=dict(text="Valor del contrato (escala logarítmica)", font=dict(size=11)),
                   tickvals=[t[0] for t in ty], ticktext=[t[1] for t in ty], gridcolor=GRILLA,
                   zeroline=False, tickfont=dict(size=10, family=FUENTE)),
    )
    return _a_json(fig)


@router.get("/dispersion")
def dispersion():
    """Valor contra plazo pactado de todos los contratos de la última ejecución (913), con los
    atípicos resaltados y los que tienen obra en el mapa marcados aparte.

    Cada punto trae solo referencia, tipo, modalidad, valor, plazo y las dos marcas; nada del
    contratista ni el puntaje. Los contratos sin plazo pactado o sin valor no se pueden dibujar
    en escala logarítmica y solo se cuentan."""
    e = _ejecucion_activa()
    if e is None:
        return {"ejecutado": False}
    filas = fetch_all(
        f"""
        SELECT a.referencia, a.tipo_de_contrato AS tipo, a.modalidad_de_contratacion AS modalidad,
               a.valor_contrato, a.plazo_dias, a.es_atipico, (o.id_contrato IS NOT NULL) AS con_obra
        FROM ml_atipicos_contrato a
        LEFT JOIN {SQL_CONTRATOS_CON_OBRA} o ON o.id_contrato = a.id_contrato
        WHERE a.ejecucion_id = %(id)s
        ORDER BY a.referencia
        """,
        {"id": e["id"]},
    )
    puntos = [
        {"referencia": f["referencia"], "tipo": f["tipo"], "modalidad": f["modalidad"],
         "valor": float(f["valor_contrato"]), "plazo_dias": f["plazo_dias"],
         "atipico": f["es_atipico"], "con_obra": f["con_obra"]}
        for f in filas
        if f["plazo_dias"] and f["valor_contrato"] and float(f["valor_contrato"]) > 0
    ]
    n_atipicos = sum(f["es_atipico"] for f in filas)
    n_atipicos_obra = sum(f["es_atipico"] and f["con_obra"] for f in filas)
    insight = (
        f"{_plural(n_atipicos, 'contrato se sale', 'contratos se salen')} de lo común frente a "
        f"{_num_es(len(filas))} contratos del IDU; "
        f"{_plural(n_atipicos_obra, 'tiene', 'tienen')} obra en el mapa."
    )
    return {
        "ejecutado": True,
        "ejecutado_en": e["ejecutado_en"],
        "n_contratos": len(filas),
        "n_en_grafico": len(puntos),
        "n_sin_dibujar": len(filas) - len(puntos),
        "n_atipicos": n_atipicos,
        "n_atipicos_con_obra": n_atipicos_obra,
        "puntos": puntos,
        "figura": _figura_dispersion(puntos) if puntos else None,
        "insight": insight,
    }
