import Icon from "./Icon.jsx";
import { numero, pct } from "../utils/formato.js";

const SIN_DATO = "—";
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const fmt = (v, f) => (v === null || v === undefined || Number.isNaN(v) ? SIN_DATO : f(v));

/**
 * Las cuatro tarjetas de indicadores.
 * stats: { total, avance, localidades, enEjecucion, retrasadas, suspendidas, atencion }
 *        (cualquier valor puede venir en null mientras carga: se muestra "—")
 * layout="inline": valor y subtítulo en la misma línea (vista Mapa)
 * layout="stacked": subtítulo debajo del valor (vista Dashboard)
 */
export default function KpiRow({ stats, layout = "stacked" }) {
  const { total, avance, localidades, enEjecucion, retrasadas, suspendidas, atencion } = stats;
  const pctEjecucion = total ? (enEjecucion / total) * 100 : null;

  const tarjetas = [
    {
      icon: "pin",
      titulo: "Obras en seguimiento",
      valor: fmt(total, numero),
      sub:
        localidades == null
          ? SIN_DATO
          : layout === "inline"
            ? plural(localidades, "localidad", "localidades")
            : `En ${plural(localidades, "localidad", "localidades")}`,
      destacada: true,
    },
    { icon: "chart", titulo: "Avance físico promedio", valor: fmt(avance, (v) => pct(v)), sub: "Media simple por obra" },
    {
      icon: "barrier",
      titulo: "En ejecución",
      valor: fmt(enEjecucion, numero),
      sub: `${fmt(pctEjecucion, (v) => pct(v, layout === "inline" ? 0 : 1))} del total`,
    },
    {
      icon: "flag",
      titulo: "Requieren atención",
      valor: fmt(atencion, numero),
      sub:
        retrasadas == null
          ? SIN_DATO
          : `${plural(retrasadas, "retrasada", "retrasadas")} · ${plural(suspendidas ?? 0, "suspendida", "suspendidas")}`,
    },
  ];

  return (
    <section className={`kpi-row kpi-${layout}`}>
      {tarjetas.map((t) => (
        <article key={t.titulo} className={`kpi ${t.destacada ? "kpi-destacada" : ""}`}>
          <span className="kpi-icon">
            <Icon name={t.icon} size={20} />
          </span>
          <div className="kpi-body">
            <span className="kpi-titulo">{t.titulo}</span>
            <div className="kpi-valor-linea">
              <span className="kpi-valor">{t.valor}</span>
              {layout === "inline" && <span className="kpi-sub">{t.sub}</span>}
            </div>
            {layout === "stacked" && <span className="kpi-sub">{t.sub}</span>}
          </div>
        </article>
      ))}
    </section>
  );
}

/** Convierte el resumen calculado en el navegador (datos de ejemplo) al formato de KpiRow. */
export function kpisDesdeResumen(r) {
  return {
    total: r.total,
    avance: r.avance,
    localidades: r.localidades,
    enEjecucion: r.porEstado["En ejecución"],
    retrasadas: r.porEstado.Retrasada,
    suspendidas: r.porEstado.Suspendida,
    atencion: r.atencion,
  };
}

/** Convierte la respuesta de /api/obras/indicadores al formato de KpiRow. */
export function kpisDesdeApi(d) {
  if (!d) return {};
  return {
    total: d.total_obras,
    avance: d.avance_fisico_promedio === null ? null : Number(d.avance_fisico_promedio),
    localidades: d.n_localidades,
    enEjecucion: d.n_en_ejecucion,
    retrasadas: d.n_retrasadas,
    suspendidas: d.n_suspendidas,
    atencion: d.n_requieren_atencion,
  };
}
