"""Vista Dashboard: indicadores, gráficos (Plotly) y conclusiones con datos reales.

Fuente: v_obras_seguimiento (obras_integradas + estado de seguimiento calculado
en la base con clasificar_obra). Son ~120 obras, así que se leen todas y se
filtran y agregan aquí en Python.

Avance físico = avance_ejecutado. avance_programado se usa como referencia.
"""

import json
from collections import Counter, defaultdict
from statistics import mean

import plotly.graph_objects as go
from fastapi import APIRouter, Query

from app.db import fetch_all

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Estilo (mismos colores del frontend)
# ---------------------------------------------------------------------------
PRIMARIO = "#9a3b33"
DORADO = "#b9a26a"
DORADO_BARRA = "#bca46c"
ARENA = "#f2eadc"
TEXTO = "#3a2a22"
TEXTO_2 = "#5f534a"
GRILLA = "#efe7da"
FUENTE = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"

ESTADOS = ["En ejecución", "Retrasada", "Suspendida", "Finalizada", "Caducada", "Sin dato"]
PLURAL_ESTADO = {
    "En ejecución": "En ejecución (al día)",
    "Retrasada": "Retrasadas",
    "Suspendida": "Suspendidas",
    "Finalizada": "Finalizadas",
    "Caducada": "Caducadas",
    "Sin dato": "Sin dato",
}
COLOR_ESTADO = {
    "En ejecución": PRIMARIO,
    "Retrasada": "#c98b2e",
    "Suspendida": "#d2665a",
    "Finalizada": DORADO,
    "Caducada": "#7a4a40",
    "Sin dato": "#cfc6bb",
}

# La base trae los nombres en mayúsculas y sin tildes
NOMBRE_LOCALIDAD = {
    "01": "Usaquén", "02": "Chapinero", "03": "Santa Fe", "04": "San Cristóbal", "05": "Usme",
    "06": "Tunjuelito", "07": "Bosa", "08": "Kennedy", "09": "Fontibón", "10": "Engativá",
    "11": "Suba", "12": "Barrios Unidos", "13": "Teusaquillo", "14": "Los Mártires",
    "15": "Antonio Nariño", "16": "Puente Aranda", "17": "La Candelaria",
    "18": "Rafael Uribe Uribe", "19": "Ciudad Bolívar", "20": "Sumapaz",
}
SIN_DATO = "Sin dato"


def _num(v):
    return None if v is None else float(v)


def _prom(valores):
    valores = [v for v in valores if v is not None]
    return mean(valores) if valores else None


def _num_es(v, dec=0):
    """1234.5 -> '1.234,5' (formato colombiano)."""
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v, dec=0):
    return f"{_num_es(v, dec)} %"


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _a_json(fig: go.Figure) -> dict:
    """Figura de Plotly -> dict JSON (lo dibuja plotly.js en el navegador)."""
    return json.loads(fig.to_json())


def _layout(fig: go.Figure, **extra):
    """Estilo común; cada gráfico puede sobrescribir cualquier valor (p. ej. margin)."""
    base = dict(
        font=dict(family=FUENTE, size=12, color=TEXTO_2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
        hoverlabel=dict(bgcolor="#fffdf9", bordercolor="#e2d5c1", font=dict(family=FUENTE, color=TEXTO, size=12)),
    )
    fig.update_layout(**{**base, **extra})
    return fig


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def _cargar_obras():
    filas = fetch_all(
        """
        SELECT objectid, nombre, etapa, contrato_tipo, estado_seguimiento,
               avance_ejecutado, avance_programado,
               localidad_codigo, localidad_nombre,
               extract(year FROM fecha_inicio)::int AS anio_inicio,
               fecha_actualizacion
        FROM v_obras_seguimiento
        """
    )
    obras = []
    for f in filas:
        cod = f["localidad_codigo"]
        obras.append(
            {
                "id": f["objectid"],
                "etapa": f["etapa"] or SIN_DATO,
                "tipo": f["contrato_tipo"] or SIN_DATO,
                "estado": f["estado_seguimiento"] or SIN_DATO,
                "avance": _num(f["avance_ejecutado"]),
                "programado": _num(f["avance_programado"]),
                "localidad_codigo": cod,
                "localidad": NOMBRE_LOCALIDAD.get(cod) or (f["localidad_nombre"] or "").title() or None,
                "anio": f["anio_inicio"],
                "actualizacion": f["fecha_actualizacion"],
            }
        )
    return obras


def _opciones(obras):
    localidades = sorted(
        {(o["localidad_codigo"], o["localidad"]) for o in obras if o["localidad_codigo"]}, key=lambda t: t[1]
    )
    tipos = sorted({o["tipo"] for o in obras}, key=lambda t: (t == SIN_DATO, t))
    anios = sorted({o["anio"] for o in obras if o["anio"]}, reverse=True)
    periodos = [{"value": "", "label": f"Todos los años ({min(anios)}–{max(anios)})" if anios else "Todos los años"}]
    periodos += [{"value": str(a), "label": f"Iniciadas en {a}"} for a in anios]
    return {
        "localidades": [{"value": c, "label": n} for c, n in localidades],
        "tipos": [{"value": t, "label": t} for t in tipos],
        "periodos": periodos,
    }


def _resumen(obras):
    c = Counter(o["estado"] for o in obras)
    total = len(obras)
    en_ejecucion = c["En ejecución"] + c["Retrasada"]
    return {
        "total": total,
        "avance": _prom(o["avance"] for o in obras),
        "programado": _prom(o["programado"] for o in obras),
        "localidades": len({o["localidad_codigo"] for o in obras if o["localidad_codigo"]}),
        "enEjecucion": en_ejecucion,
        "retrasadas": c["Retrasada"],
        "suspendidas": c["Suspendida"],
        "atencion": c["Retrasada"] + c["Suspendida"],
        "porEstado": {e: c[e] for e in ESTADOS},
    }


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def _grafico_por_anio(obras):
    """Avance programado vs. ejecutado promedio, por año de inicio del contrato."""
    grupos = defaultdict(list)
    for o in obras:
        if o["anio"] and o["avance"] is not None and o["programado"] is not None:
            grupos[o["anio"]].append(o)
    anios = sorted(grupos)
    if not anios:
        return None, None, "No hay obras con año de inicio y avance para estos filtros."

    x = [str(a) for a in anios]
    prog = [mean(o["programado"] for o in grupos[a]) for a in anios]
    ejec = [mean(o["avance"] for o in grupos[a]) for a in anios]
    n = [len(grupos[a]) for a in anios]

    def etiquetas(serie):
        return [""] * (len(serie) - 1) + [_pct(serie[-1])]

    # El tamaño del punto refleja cuántas obras hay en ese año (los años con 1-2 obras pesan poco)
    tamanos = [7 + 3.2 * (k ** 0.5) for k in n]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x, y=prog, name="Programado", mode="lines+markers+text",
            line=dict(color=DORADO, width=2, dash="dash"), marker=dict(size=[t * 0.75 for t in tamanos], color=DORADO),
            text=etiquetas(prog), textposition="top center", textfont=dict(color="#8a7440", size=12),
            customdata=n,
            hovertemplate="Iniciadas en %{x}<br>Programado: %{y:.1f} %<br>%{customdata} obras<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=ejec, name="Ejecutado", mode="lines+markers+text",
            line=dict(color=PRIMARIO, width=3),
            marker=dict(size=tamanos, color=PRIMARIO, line=dict(color="#fffdf9", width=1.5)),
            text=etiquetas(ejec), textposition="bottom center", textfont=dict(color=PRIMARIO, size=12),
            customdata=n,
            hovertemplate="Iniciadas en %{x}<br>Ejecutado: %{y:.1f} %<br>%{customdata} obras<extra></extra>",
        )
    )
    _layout(
        fig,
        height=290,
        margin=dict(l=8, r=16, t=16, b=8),
        hovermode="x unified",
        xaxis=dict(type="category", title=dict(text="Año de inicio del contrato", font=dict(size=11)),
                   showgrid=False, linecolor=GRILLA, tickfont=dict(size=11)),
        yaxis=dict(range=[0, 108], ticksuffix=" %", gridcolor=GRILLA, zeroline=False, tickfont=dict(size=11),
                   dtick=20),
    )

    # Conclusión: año con la brecha más grande (entre los que tienen al menos 3 obras)
    brechas = [(a, p - e, k) for a, p, e, k in zip(anios, prog, ejec, n) if k >= 3] or [
        (a, p - e, k) for a, p, e, k in zip(anios, prog, ejec, n)
    ]
    peor = max(brechas, key=lambda t: t[1])
    brecha_total = mean(o["programado"] for a in anios for o in grupos[a]) - mean(
        o["avance"] for a in anios for o in grupos[a]
    )
    if brecha_total <= 0.05:
        insight = "En conjunto, las obras van al ritmo de lo programado."
    elif len(anios) == 1:
        insight = (
            f"Las obras iniciadas en {anios[0]} van {_num_es(brecha_total, 1)} pp por debajo de lo programado."
        )
    else:
        insight = (
            f"En conjunto, el avance va {_num_es(brecha_total, 1)} pp por debajo de lo programado. "
            f"La mayor brecha está en las obras iniciadas en {peor[0]} ({_num_es(peor[1], 1)} pp, "
            f"{_plural(peor[2], 'obra', 'obras')})."
        )
    rango = x[0] if len(x) == 1 else f"{x[0]} – {x[-1]}"
    return _a_json(fig), rango, insight


def _grafico_por_localidad(obras, promedio):
    """Barras horizontales: avance físico promedio por localidad, con línea del promedio general."""
    grupos = defaultdict(list)
    for o in obras:
        if o["localidad_codigo"]:
            grupos[o["localidad"]].append(o["avance"])
    datos = [(loc, _prom(v), len(v)) for loc, v in grupos.items()]
    datos = [d for d in datos if d[1] is not None]
    if not datos:
        return None, "No hay obras con localidad y avance para estos filtros.", 0
    datos.sort(key=lambda d: d[1])  # Plotly dibuja de abajo hacia arriba: el mayor queda arriba
    nombres = [d[0] for d in datos]
    valores = [d[1] for d in datos]
    conteos = [d[2] for d in datos]

    fig = go.Figure()
    fig.add_trace(go.Bar(  # pista de fondo (100 %)
        y=nombres, x=[100] * len(nombres), orientation="h", marker=dict(color=ARENA),
        hoverinfo="skip", width=0.62,
    ))
    fig.add_trace(go.Bar(
        y=nombres, x=valores, orientation="h", marker=dict(color=PRIMARIO), width=0.62,
        text=[_pct(v) for v in valores], textposition="outside", cliponaxis=False,
        textfont=dict(color=TEXTO, size=11),
        customdata=conteos,
        hovertemplate="<b>%{y}</b><br>Avance físico: %{x:.1f} %<br>%{customdata} obras<extra></extra>",
    ))
    if promedio is not None:
        fig.add_shape(type="line", x0=promedio, x1=promedio, y0=-0.6, y1=len(nombres) - 0.4,
                      line=dict(color=TEXTO, width=1.5))
    _layout(
        fig,
        height=max(220, 26 * len(nombres) + 40),
        barmode="overlay",
        margin=dict(l=8, r=44, t=8, b=8),
        xaxis=dict(range=[0, 100], ticksuffix=" %", gridcolor="rgba(0,0,0,0)", zeroline=False,
                   tickvals=[0, 25, 50, 75, 100], tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=12, color=TEXTO), automargin=True),
    )

    mejor, peor = datos[-1], datos[0]
    if promedio is None or len(datos) < 2:
        insight = f"{mejor[0]}: {_pct(mejor[1])} de avance físico promedio."
    else:
        insight = (
            f"{mejor[0]} supera el promedio en {round(mejor[1] - promedio)} pp; "
            f"{peor[0]} está {round(promedio - peor[1])} pp por debajo."
        )
    return _a_json(fig), insight, len(datos)


def _grafico_estados(resumen):
    total = resumen["total"]
    filas = [(e, resumen["porEstado"][e]) for e in ESTADOS if resumen["porEstado"][e]]
    if not filas:
        return None, [], "No hay obras para estos filtros."
    fig = go.Figure(go.Pie(
        labels=[PLURAL_ESTADO[e] for e, _ in filas],
        values=[n for _, n in filas],
        marker=dict(colors=[COLOR_ESTADO[e] for e, _ in filas], line=dict(color="#fffdf9", width=2)),
        hole=0.66, sort=False, direction="clockwise", rotation=0, textinfo="none",
        hovertemplate="%{label}: %{value} obras (%{percent})<extra></extra>",
    ))
    _layout(
        fig,
        height=220,
        margin=dict(l=4, r=4, t=4, b=4),
        annotations=[
            dict(text=f"<b>{total}</b>", x=0.5, y=0.56, showarrow=False, font=dict(size=34, color=TEXTO, family=FUENTE)),
            dict(text="obras en total", x=0.5, y=0.38, showarrow=False, font=dict(size=11, color=TEXTO_2, family=FUENTE)),
        ],
    )
    leyenda = [
        {"estado": e, "etiqueta": PLURAL_ESTADO[e], "color": COLOR_ESTADO[e], "n": n, "pct": 100 * n / total}
        for e, n in filas
    ]
    atencion = resumen["atencion"]
    if atencion:
        insight = (
            f"{_plural(atencion, 'obra requiere', 'obras requieren')} atención "
            f"({_pct(100 * atencion / total)} del total): {_plural(resumen['retrasadas'], 'retrasada', 'retrasadas')} "
            f"y {_plural(resumen['suspendidas'], 'suspendida', 'suspendidas')}."
        )
    else:
        insight = "Ninguna obra está retrasada ni suspendida con estos filtros."
    return _a_json(fig), leyenda, insight


def _grafico_etapas(obras):
    """Número de obras por etapa de la intervención."""
    c = Counter(o["etapa"] for o in obras)
    if not c:
        return None, "No hay obras para estos filtros."
    datos = sorted(c.items(), key=lambda t: t[1])  # el mayor queda arriba
    etapas = [d[0] for d in datos]
    valores = [d[1] for d in datos]
    colores = [DORADO_BARRA] * (len(datos) - 1) + [PRIMARIO]
    fig = go.Figure(go.Bar(
        y=etapas, x=valores, orientation="h", marker=dict(color=colores), width=0.62,
        text=valores, textposition="outside", cliponaxis=False, textfont=dict(color=TEXTO, size=12),
        hovertemplate="<b>%{y}</b><br>%{x} obras<extra></extra>",
    ))
    _layout(
        fig,
        height=max(200, 32 * len(etapas) + 40),
        margin=dict(l=8, r=32, t=8, b=8),
        xaxis=dict(gridcolor=GRILLA, zeroline=False, tickfont=dict(size=10),
                   title=dict(text="Obras", font=dict(size=11))),
        yaxis=dict(tickfont=dict(size=12, color=TEXTO), automargin=True),
    )
    top, n_top = datos[-1]
    total = sum(valores)
    insight = f"{top} concentra {_plural(n_top, 'obra', 'obras')}: el {_pct(100 * n_top / total, 1)} de la cartera."
    return _a_json(fig), insight


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.get("")
def dashboard(
    localidad: str | None = Query(None, description="Código de localidad, p. ej. '08'"),
    tipo: str | None = Query(None, description="Tipo de contrato (o 'Sin dato')"),
    periodo: str | None = Query(None, description="Año de inicio del contrato, p. ej. '2024'"),
):
    todas = _cargar_obras()
    obras = [
        o
        for o in todas
        if (not localidad or o["localidad_codigo"] == localidad)
        and (not tipo or o["tipo"] == tipo)
        and (not periodo or str(o["anio"]) == periodo)
    ]
    resumen = _resumen(obras)

    fig_anio, rango_anios, insight_anio = _grafico_por_anio(obras)
    fig_loc, insight_loc, n_loc = _grafico_por_localidad(obras, resumen["avance"])
    fig_estados, leyenda_estados, insight_estados = _grafico_estados(resumen)
    fig_etapas, insight_etapas = _grafico_etapas(obras)

    actualizaciones = [o["actualizacion"] for o in todas if o["actualizacion"]]
    return {
        "total_general": len(todas),
        "actualizado": max(actualizaciones) if actualizaciones else None,
        "opciones": _opciones(todas),
        "resumen": resumen,
        "avance_anio": {"figura": fig_anio, "rango": rango_anios, "insight": insight_anio},
        "avance_localidad": {"figura": fig_loc, "n_localidades": n_loc, "insight": insight_loc},
        "estados": {"figura": fig_estados, "leyenda": leyenda_estados, "insight": insight_estados},
        "etapas": {"figura": fig_etapas, "total": resumen["total"], "insight": insight_etapas},
    }
