import { useEffect, useState } from "react";
import Icon from "../components/Icon.jsx";
import KpiRow from "../components/KpiRow.jsx";
import PlotlyChart from "../components/PlotlyChart.jsx";
import { Insight, Select } from "../components/ui.jsx";
import { api } from "../services/api.js";
import { pct } from "../utils/formato.js";

// Los gráficos se arman en Python (backend/app/routers/dashboard.py, con Plotly)
// a partir de los datos reales; aquí solo se dibujan.

const FILTROS_INICIALES = { localidad: "", tipo: "", periodo: "" };

export default function DashboardPage() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let vigente = true;
    setCargando(true);
    api
      .dashboard(filtros)
      .then((d) => {
        if (!vigente) return;
        setDatos(d);
        setError(null);
      })
      .catch((e) => vigente && setError(e.message))
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
  }, [filtros]);

  const set = (k) => (v) => setFiltros((f) => ({ ...f, [k]: v }));
  const nFiltros = Object.values(filtros).filter(Boolean).length;
  const opciones = datos?.opciones ?? { localidades: [], tipos: [], periodos: [{ value: "", label: "Todos los años" }] };
  const r = datos?.resumen;
  const total = datos?.total_general;

  return (
    <div className={`page page-narrow ${cargando && datos ? "is-cargando" : ""}`}>
      <div className="page-head">
        <div>
          <h1>Análisis de obras</h1>
          <p className="page-sub">
            Cómo avanzan las {total ?? ""} obras viales del IDU frente a lo programado, en qué localidades están y en
            qué estado se encuentran. Filtra por localidad, tipo de contrato o año de inicio para comparar.
          </p>
        </div>
      </div>

      <div className="dash-filters">
        <Icon name="sliders" size={20} className="accent" />
        <Select
          inlineLabel="Localidad"
          value={filtros.localidad}
          onChange={set("localidad")}
          aria-label="Localidad"
          options={[{ value: "", label: "Todas las localidades" }, ...opciones.localidades]}
        />
        <Select
          inlineLabel="Tipo de contrato"
          value={filtros.tipo}
          onChange={set("tipo")}
          aria-label="Tipo de contrato"
          options={[{ value: "", label: "Todos los tipos" }, ...opciones.tipos]}
        />
        <Select
          inlineLabel="Período"
          value={filtros.periodo}
          onChange={set("periodo")}
          aria-label="Período (año de inicio del contrato)"
          options={opciones.periodos}
        />
        <span className="dash-filters-meta">
          {r ? `${r.total} de ${total} obras` : "Cargando…"} ·{" "}
          {nFiltros === 0 ? (
            "Sin filtros aplicados"
          ) : (
            <button type="button" className="link-btn" onClick={() => setFiltros(FILTROS_INICIALES)}>
              Quitar {nFiltros === 1 ? "filtro" : `${nFiltros} filtros`}
            </button>
          )}
        </span>
      </div>

      {error && (
        <span className="api-error">
          <Icon name="info" size={15} /> No se pudieron cargar los datos ({error})
        </span>
      )}

      <KpiRow stats={r ?? {}} layout="stacked" />

      <div className="dash-row dash-row-1">
        <section className="card chart-card">
          <div className="chart-card-head">
            <div>
              <h2>¿El avance sigue lo previsto?</h2>
              <p className="chart-sub">Avance físico promedio programado vs. ejecutado, según el año de inicio del contrato</p>
            </div>
            {datos?.avance_anio.rango && <span className="pill">{datos.avance_anio.rango}</span>}
          </div>
          <div className="chart-legend">
            <span className="legend-line legend-line-prog" /> Programado
            <span className="legend-line legend-line-eje" /> Ejecutado
            <span className="chart-legend-right">El tamaño del punto indica cuántas obras empezaron ese año</span>
          </div>
          {datos && <PlotlyChart figura={datos.avance_anio.figura} vacio={datos.avance_anio.insight} llenar />}
          {datos?.avance_anio.figura && <Insight>{datos.avance_anio.insight}</Insight>}
        </section>

        <section className="card chart-card">
          <div className="chart-card-head">
            <div>
              <h2>El avance no es igual en toda la ciudad</h2>
              <p className="chart-sub">
                Avance físico promedio por localidad · {datos?.avance_localidad.n_localidades ?? "—"} localidades
              </p>
            </div>
          </div>
          <div className="chart-legend">
            <span className="legend-line legend-line-eje" /> Avance ejecutado
            <span className="chart-legend-right">
              <span className="legend-avg" /> Promedio general: {r?.avance != null ? pct(r.avance) : "—"}
            </span>
          </div>
          {datos && <PlotlyChart figura={datos.avance_localidad.figura} vacio={datos.avance_localidad.insight} />}
          {datos?.avance_localidad.figura && <Insight icon="trendUp">{datos.avance_localidad.insight}</Insight>}
        </section>
      </div>

      <div className="dash-row dash-row-2">
        <section className="card chart-card">
          <div className="chart-card-head">
            <div>
              <h2>¿En qué estado están las obras?</h2>
              <p className="chart-sub">
                Distribución de {r ? `las ${r.total} obras` : "las obras"} según su estado de seguimiento
              </p>
            </div>
          </div>
          {datos && !datos.estados.figura && <p className="chart-vacio">{datos.estados.insight}</p>}
          {datos?.estados.figura && (
            <div className="dona-wrap">
              <PlotlyChart figura={datos.estados.figura} className="dona-plotly" />
              <table className="dona-legend">
                <tbody>
                  {datos.estados.leyenda.map((e) => (
                    <tr key={e.estado}>
                      <td>
                        <span className="legend-square" style={{ background: e.color }} />
                        {e.etiqueta}
                      </td>
                      <td className="num strong">{e.n}</td>
                      <td className="num muted">{pct(e.pct, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {datos?.estados.figura && <Insight>{datos.estados.insight}</Insight>}
        </section>

        <section className="card chart-card">
          <div className="chart-card-head">
            <div>
              <h2>¿Qué intervenciones predominan?</h2>
              <p className="chart-sub">Número de obras por etapa de la intervención</p>
            </div>
            {r && <span className="pill">Total: {r.total}</span>}
          </div>
          {datos && <PlotlyChart figura={datos.etapas.figura} vacio={datos.etapas.insight} />}
          {datos?.etapas.figura && <Insight icon="trendUp">{datos.etapas.insight}</Insight>}
        </section>
      </div>
    </div>
  );
}
