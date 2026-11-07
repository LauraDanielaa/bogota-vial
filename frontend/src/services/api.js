// Cliente del backend. Las rutas son relativas: en desarrollo las atiende el proxy
// de Vite y en Docker las atiende nginx (ambos las reenvían al backend).
const BASE = import.meta.env.VITE_API_URL || "/api";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Error ${res.status} en ${path}`);
  return res.json();
}

export const api = {
  obrasGeojson: (filtros) => get("/obras/geojson", filtros),
  indicadores: (localidad) => get("/obras/indicadores", { localidad }),
  obrasMapa: () => get("/obras/mapa"),
  dashboard: (filtros) => get("/dashboard", filtros),
  estados: () => get("/obras/estados"),
  localidadesGeojson: () => get("/localidades/geojson"),
  localidades: () => get("/localidades"),
};
