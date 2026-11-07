import { useEffect, useRef } from "react";

// plotly.js se carga solo cuando se usa (vista Dashboard), así el mapa abre rápido.
let plotlyPromesa = null;
const cargarPlotly = () =>
  (plotlyPromesa ??= import("plotly.js-basic-dist-min").then((m) => m.default ?? m));

const CONFIG = { displayModeBar: false, responsive: true, locale: "es" };

/**
 * Dibuja una figura armada en Python (plotly.graph_objects -> fig.to_json()).
 * `figura` = { data, layout }, o null si no hay datos.
 * `llenar`: el gráfico crece para ocupar el alto libre de la tarjeta
 *           (usa el alto de la figura como mínimo).
 */
export default function PlotlyChart({ figura, className = "", vacio = "Sin datos para estos filtros.", llenar = false }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let vivo = true;
    // Solo redimensiona si el gráfico existe y está visible
    const ro = new ResizeObserver(() => {
      if (!el.isConnected || !el._fullLayout || el.offsetParent === null) return;
      cargarPlotly().then((Plotly) => {
        try {
          Plotly.Plots.resize(el);
        } catch {
          /* el gráfico se quitó mientras tanto */
        }
      });
    });
    cargarPlotly().then((Plotly) => {
      if (!vivo) return;
      if (!figura) {
        Plotly.purge(el);
        return;
      }
      const layout = { ...figura.layout, autosize: true };
      if (llenar) delete layout.height; // toma el alto del contenedor
      Plotly.react(el, figura.data, layout, CONFIG);
      ro.observe(el);
    });
    return () => {
      vivo = false;
      ro.disconnect();
    };
  }, [figura, llenar]);

  // Liberar memoria al salir de la vista
  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el && plotlyPromesa) plotlyPromesa.then((Plotly) => Plotly.purge(el));
    };
  }, []);

  const alto = figura?.layout?.height;
  return (
    <>
      {!figura && <p className="chart-vacio">{vacio}</p>}
      <div
        ref={ref}
        className={`plotly-chart ${llenar ? "plotly-llenar" : ""} ${className}`}
        style={figura ? (llenar ? { minHeight: alto } : { height: alto }) : { display: "none" }}
      />
    </>
  );
}
