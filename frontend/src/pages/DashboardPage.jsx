import { useEffect, useState } from "react";
import Icon from "../components/Icon.jsx";
import KpiRow from "../components/KpiRow.jsx";
import PlotlyChart from "../components/PlotlyChart.jsx";
import { Insight, Select } from "../components/ui.jsx";
import { api } from "../services/api.js";
import { numero, pct } from "../utils/formato.js";
import { colorRiesgo } from "../utils/stats.js";

// Los gráficos se arman en Python (backend/app/routers/dashboard.py, con Plotly)
// a partir de los datos reales; aquí solo se dibujan.

const FILTROS_INICIALES = { localidad: "", tipo: "", periodo: "" };
const NIVELES_TARJETA = ["Alto", "Medio", "Bajo", "Prorrogada"];

/** Recuadro "¿Cómo se calcula el riesgo?" (usa /api/modelo/metricas). */
function ComoSeCalcula({ metricas }) {
  const u = metricas?.umbrales ?? { medio: 0.3, alto: 0.6 };
  const elegido = metricas?.modelos?.find((m) => m.seleccionado);
  return (
    <section className="card riesgo-explica">
      <h3>¿Cómo se calcula el riesgo?</h3>
      <p>
        Un modelo estadístico estima la probabilidad de que el contrato de la obra sea prorrogado, a partir de{" "}
        {metricas?.n_entrenamiento ? `${numero(metricas.n_entrenamiento)} contratos` : "contratos"} anteriores del IDU
        en SECOP II. Solo usa lo que se sabe al firmar: tipo, modalidad, valor, duración pactada, categoría, fecha de
        firma e historial del contratista.
      </p>
      <p>
        Riesgo <strong>alto</strong> desde {pct(u.alto * 100)}, <strong>medio</strong> desde {pct(u.medio * 100)} y{" "}
        <strong>bajo</strong> por debajo. Las obras finalizadas o caducadas no aplican y las que ya tienen días
        adicionados aparecen como <strong>prorrogadas</strong>.
      </p>
      {metricas?.entrenado && elegido && (
        <p className="muted xsmall">
          Modelo: {metricas.modelo_nombre}. PR-AUC {numero(elegido.cv_pr_auc, 2)} frente a{" "}
          {numero(metricas.linea_base_pr_auc, 2)} de la línea base (validación cruzada).
        </p>
      )}
      {metricas?.entrenado && metricas.supera_linea_base === false && (
        <p className="riesgo-aviso">El modelo no supera claramente a la línea base: tome el riesgo con cautela.</p>
      )}
      {metricas && !metricas.entrenado && <p className="riesgo-aviso">El modelo aún no se ha entrenado: Sin calcular.</p>}
      <p className="muted xsmall">
        Prorrogada es un hecho registrado en SECOP; Alto, Medio y Bajo son estimaciones estadísticas, no datos
        oficiales del IDU.
      </p>
    </section>
  );
}

/** "2026-11-16T01:55:51..." -> "16 de noviembre de 2026" */
const fechaLarga = (iso) =>
  iso ? new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) : "sin dato";

/** Fila de contratos atípicos (modelo ml/atipicos). No depende de los filtros: compara los
 *  contratos del IDU entre sí. Si el modelo aún no se ha ejecutado, no se muestra. */
function FilaAtipicos({ ejecucion, dispersion }) {
  return (
    <div className="dash-row dash-row-riesgo">
      <section className="card chart-card">
        <div className="chart-card-head">
          <div>
            <h2>¿Qué contratos se salen de lo común?</h2>
            <p className="chart-sub">
              Valor contra plazo pactado de los {numero(ejecucion.n_contratos)} contratos del IDU en SECOP II, en
              escala logarítmica. Los rombos tienen obra en el mapa.
            </p>
          </div>
        </div>
        {dispersion && (
          <PlotlyChart figura={dispersion.figura} vacio="No hay contratos con valor y plazo pactado para dibujar." />
        )}
        {dispersion?.n_sin_dibujar > 0 && (
          <p className="muted xsmall">
            {numero(dispersion.n_sin_dibujar)} contratos sin plazo pactado o sin valor en SECOP no aparecen en el
            gráfico.
          </p>
        )}
        {dispersion?.insight && <Insight icon="info">{dispersion.insight}</Insight>}
      </section>

      <div className="riesgo-side">
        <section className="card riesgo-kpi">
          <span className="kpi-titulo">Obras con contrato atípico</span>
          <span className="riesgo-kpi-valor">{numero(ejecucion.n_obras_con_contrato_atipico)}</span>
          <span className="kpi-sub">Frente a {numero(ejecucion.n_contratos)} contratos del IDU</span>
          <span className="muted xsmall">Última ejecución: {fechaLarga(ejecucion.ejecutado_en)}</span>
        </section>
        <section className="card riesgo-explica">
          <h3>¿Qué es un contrato atípico?</h3>
          <p>
            Un modelo estadístico compara cada contrato con los demás contratos del IDU por su valor, plazo pactado,
            valor por día, días adicionados, tipo y modalidad, y señala los que se salen de lo habitual. Para cada
            uno explica en qué se diferencia de los contratos de su mismo tipo y modalidad.
          </p>
          <p className="muted xsmall">
            Que un contrato sea atípico no significa que haya una irregularidad; puede deberse al tamaño o la
            complejidad de la obra.
          </p>
        </section>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [atipicos, setAtipicos] = useState(null); // { ejecucion, dispersion } o null si no hay ejecución

  useEffect(() => {
    api
      .modeloMetricas()
      .then(setMetricas)
      .catch(() => setMetricas(null));
    api
      .atipicosEjecucion()
      .then((ejecucion) => {
        if (!ejecucion?.ejecutado) return;
        setAtipicos({ ejecucion, dispersion: null });
        return api.atipicosDispersion().then((d) => d?.ejecutado && setAtipicos({ ejecucion, dispersion: d }));
      })
      .catch(() => {
        /* sin datos de atípicos: la fila no se muestra */
      });
  }, []);

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

      <div className="dash-row dash-row-riesgo">
        <section className="card chart-card">
          <div className="chart-card-head">
            <div>
              <h2>¿Dónde está el riesgo de atraso?</h2>
              <p className="chart-sub">
                Obras por nivel de riesgo de prórroga en cada localidad (obras finalizadas, caducadas o sin contrato
                en SECOP no se incluyen)
              </p>
            </div>
          </div>
          {datos && <PlotlyChart figura={datos.riesgo_localidad.figura} vacio={datos.riesgo_localidad.insight} />}
          {datos?.riesgo_localidad.figura && <Insight>{datos.riesgo_localidad.insight}</Insight>}
        </section>

        <div className="riesgo-side">
          <section className="card riesgo-kpi">
            <span className="kpi-titulo">Obras en riesgo alto</span>
            <span className="riesgo-kpi-valor">
              {!datos ? "—" : datos.riesgo_localidad.modelo.entrenado ? datos.riesgo_localidad.n_alto : "Sin calcular"}
            </span>
            <span className="kpi-sub">
              {datos?.riesgo_localidad.modelo.entrenado
                ? `De ${r?.total ?? "—"} obras con estos filtros`
                : "El modelo de riesgo aún no se ha entrenado"}
            </span>
            {datos?.riesgo_localidad.modelo.entrenado && (
              <div className="riesgo-niveles">
                {NIVELES_TARJETA.filter((n) => datos.riesgo_localidad.por_nivel[n]).map((n) => (
                  <span key={n} className="badge badge-riesgo">
                    <span className="riesgo-dot" style={{ background: colorRiesgo(n) }} />
                    {n}: {datos.riesgo_localidad.por_nivel[n]}
                  </span>
                ))}
              </div>
            )}
          </section>
          <ComoSeCalcula metricas={metricas} />
        </div>
      </div>

      {atipicos && <FilaAtipicos ejecucion={atipicos.ejecucion} dispersion={atipicos.dispersion} />}
    </div>
  );
}
