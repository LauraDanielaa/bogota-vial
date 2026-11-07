// Piezas pequeñas de interfaz reutilizadas en las tres vistas.
import Icon from "./Icon.jsx";
import { rangoDe } from "../utils/stats.js";

/** Select nativo con flecha propia. `inlineLabel` pone la etiqueta dentro de la caja. */
export function Select({ value, onChange, options, inlineLabel, className = "", ...rest }) {
  return (
    <label className={`select ${inlineLabel ? "select-inline" : ""} ${className}`}>
      {inlineLabel && <span className="select-inline-label">{inlineLabel}</span>}
      <select value={value} onChange={(e) => onChange(e.target.value)} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={16} className="select-chevron" />
    </label>
  );
}

export function SearchInput({ value, onChange, placeholder, onEnter }) {
  return (
    <div className="search">
      <Icon name="search" size={16} />
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onEnter?.()}
      />
    </div>
  );
}

const CLASE_ESTADO = {
  "En ejecución": "badge-ejecucion",
  Retrasada: "badge-retrasada",
  Suspendida: "badge-suspendida",
  Finalizada: "badge-finalizada",
  Caducada: "badge-caducada",
  "Sin dato": "badge-sindato",
};

export function EstadoBadge({ estado, children, dot = true }) {
  return (
    <span className={`badge ${CLASE_ESTADO[estado] ?? ""}`}>
      {dot && <span className="badge-dot" />}
      {children ?? estado}
    </span>
  );
}

/** Barra de avance. `marcador` dibuja una raya en el avance programado. */
export function Progress({ value, marcador, color, alto = 4 }) {
  return (
    <div className="progress" style={{ height: alto }}>
      <div
        className="progress-fill"
        style={{ width: `${value}%`, background: color ?? rangoDe(value).color }}
      />
      {marcador !== undefined && <span className="progress-marker" style={{ left: `${marcador}%` }} />}
    </div>
  );
}

export function Insight({ icon = "flag", children }) {
  return (
    <p className="insight">
      <Icon name={icon} size={16} />
      <span>{children}</span>
    </p>
  );
}
