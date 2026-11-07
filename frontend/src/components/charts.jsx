// Gráficas en SVG/CSS hechas a mano para que coincidan con el diseño.
import { COLOR_ESTADO, PLURAL_ESTADO } from "../utils/stats.js";
import { numero, pct } from "../utils/formato.js";

/* ------------------------------------------------------------------ */
/* Línea: avance programado vs ejecutado por mes                       */
/* ------------------------------------------------------------------ */
export function LineaAvance({ serie }) {
  const W = 840, H = 250;
  const x0 = 58, x1 = 760, y0 = 214, y1 = 18;
  const maxY = 80;
  const x = (i) => (serie.length === 1 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (serie.length - 1));
  const y = (v) => y0 - (v / maxY) * (y0 - y1);
  const linea = (k) => serie.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join(" ");
  const ultimo = serie[serie.length - 1];
  const yProg = y(ultimo.programado);
  let yEje = y(ultimo.ejecutado);
  if (Math.abs(yEje - yProg) < 22) yEje = yProg + 22; // que las etiquetas no se monten

  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Evolución mensual del avance">
      {[0, 20, 40, 60, 80].map((v) => (
        <g key={v}>
          <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} className="chart-grid" />
          <text x={x0 - 14} y={y(v) + 4} className="chart-axis" textAnchor="end">
            {v} %
          </text>
        </g>
      ))}
      {serie.map((p, i) => (
        <text key={p.mes} x={x(i)} y={H - 6} className="chart-axis" textAnchor="middle">
          {p.mes}
        </text>
      ))}

      <path d={linea("programado")} className="line-programado" />
      {serie.map((p, i) => (
        <circle key={`p${i}`} cx={x(i)} cy={y(p.programado)} r="2" fill="#B9A26A" />
      ))}
      <path d={linea("ejecutado")} className="line-ejecutado" />
      {serie.map((p, i) => (
        <circle key={`e${i}`} cx={x(i)} cy={y(p.ejecutado)} r="2.4" fill="#9A3B33" />
      ))}

      <text x={x(serie.length - 1) + 18} y={yProg + 4} className="chart-end-prog">
        {pct(ultimo.programado)}
      </text>
      <g transform={`translate(${x(serie.length - 1) + 12}, ${yEje - 11})`}>
        <rect width="46" height="22" rx="4" fill="#9A3B33" />
        <text x="23" y="15" textAnchor="middle" className="chart-end-eje">
          {pct(ultimo.ejecutado)}
        </text>
      </g>
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Barras horizontales: avance por localidad con línea de promedio     */
/* ------------------------------------------------------------------ */
export function BarrasLocalidad({ datos, promedio }) {
  return (
    <div className="loc-bars">
      {datos.map((d) => (
        <div key={d.nombre} className="loc-bar-row">
          <div className="loc-bar-label">
            <strong>{d.nombre}</strong>
            <span>{d.n} obras</span>
          </div>
          <div className="loc-bar-track">
            <div className="loc-bar-fill" style={{ width: `${d.avance}%` }} />
            {[25, 50, 75].map((t) => (
              <span key={t} className="loc-bar-grid" style={{ left: `${t}%` }} />
            ))}
            <span className="loc-bar-avg" style={{ left: `${promedio}%` }} />
          </div>
          <span className="loc-bar-value">{pct(d.avance)}</span>
        </div>
      ))}
      <div className="loc-bar-row loc-bar-ticks">
        <span />
        <div className="loc-bar-tickline">
          {[0, 25, 50, 75, 100].map((t) => (
            <span key={t} style={{ left: `${t}%` }}>
              {t} %
            </span>
          ))}
        </div>
        <span />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dona: distribución por estado                                       */
/* ------------------------------------------------------------------ */
export function DonaEstados({ porEstado, total }) {
  const r = 74, grosor = 24, C = 2 * Math.PI * r, gap = 3;
  let acumulado = 0;
  const segmentos = Object.entries(porEstado).map(([estado, n]) => {
    const largo = total ? (n / total) * C : 0;
    const seg = { estado, n, largo, offset: acumulado };
    acumulado += largo;
    return seg;
  });

  return (
    <div className="dona-wrap">
      <svg className="dona" viewBox="0 0 200 200" role="img" aria-label="Obras por estado">
        <g transform="rotate(-90 100 100)">
          {segmentos.map((s) =>
            s.largo > 0 ? (
              <circle
                key={s.estado}
                cx="100"
                cy="100"
                r={r}
                fill="none"
                stroke={COLOR_ESTADO[s.estado]}
                strokeWidth={grosor}
                strokeDasharray={`${Math.max(s.largo - gap, 0.5)} ${C}`}
                strokeDashoffset={-s.offset}
              />
            ) : null
          )}
        </g>
        <text x="100" y="104" textAnchor="middle" className="dona-total">
          {numero(total)}
        </text>
        <text x="100" y="128" textAnchor="middle" className="dona-sub">
          obras en total
        </text>
      </svg>

      <table className="dona-legend">
        <tbody>
          {segmentos.map((s) => (
            <tr key={s.estado}>
              <td>
                <span className="legend-square" style={{ background: COLOR_ESTADO[s.estado] }} />
                {PLURAL_ESTADO[s.estado]}
              </td>
              <td className="num strong">{s.n}</td>
              <td className="num muted">{pct(total ? (s.n / total) * 100 : 0, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Columnas: obras por tipo de contrato                                */
/* ------------------------------------------------------------------ */
export function ColumnasTipo({ porTipo }) {
  const entradas = Object.entries(porTipo);
  const W = 700, H = 200, x0 = 40, x1 = 690, y0 = 160, y1 = 20;
  const maxDato = Math.max(...entradas.map(([, n]) => n), 1);
  const maxY = Math.max(60, Math.ceil(maxDato / 20) * 20);
  const ticks = Array.from({ length: maxY / 20 + 1 }, (_, i) => i * 20);
  const banda = (x1 - x0) / entradas.length;
  const ancho = 70;
  const y = (v) => y0 - (v / maxY) * (y0 - y1);

  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Obras por tipo de contrato">
      <text x={0} y={8} className="chart-axis">Obras</text>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} className="chart-grid" />
          <text x={x0 - 18} y={y(v) + 4} className="chart-axis" textAnchor="end">
            {v}
          </text>
        </g>
      ))}
      {entradas.map(([tipo, n], i) => {
        const cx = x0 + banda * i + banda / 2;
        return (
          <g key={tipo}>
            <rect
              x={cx - ancho / 2}
              y={y(n)}
              width={ancho}
              height={y0 - y(n)}
              rx="2"
              fill={i === 0 ? "#9A3B33" : "#BCA46C"}
            />
            <text x={cx} y={y(n) - 9} textAnchor="middle" className="chart-bar-value">
              {n}
            </text>
            <text x={cx} y={y0 + 24} textAnchor="middle" className="chart-axis chart-axis-x">
              {tipo}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
