import Icon from "./Icon.jsx";

export const VISTAS = [
  { id: "mapa", label: "Mapa", icon: "map" },
  { id: "dashboard", label: "Dashboard", icon: "chart" },
  { id: "listado", label: "Listado", icon: "list" },
];

export default function Header({ vista, onNavegar }) {
  return (
    <header className="header">
      <div className="header-inner">
        <a className="brand" href="#/" onClick={(e) => { e.preventDefault(); onNavegar("mapa"); }}>
          <span className="brand-logo">
            <Icon name="route" size={20} strokeWidth={2} />
          </span>
          <span className="brand-name">Bogotá Vial</span>
          <span className="brand-divider" />
          <span className="brand-tagline">Observatorio de obras viales</span>
        </a>

        <nav className="segmented" aria-label="Secciones">
          {VISTAS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`segmented-item ${vista === v.id ? "is-active" : ""}`}
              aria-current={vista === v.id ? "page" : undefined}
              onClick={() => onNavegar(v.id)}
            >
              <Icon name={v.icon} size={16} />
              {v.label}
            </button>
          ))}
        </nav>

        <span className="header-spacer" />
      </div>
    </header>
  );
}
