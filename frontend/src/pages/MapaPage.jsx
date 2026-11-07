import { useEffect, useMemo, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import KpiRow, { kpisDesdeApi } from "../components/KpiRow.jsx";
import MapaObras from "../components/MapaObras.jsx";
import { EstadoBadge, Progress, SearchInput, Select } from "../components/ui.jsx";
import { adaptarObra, fecha, nombreLocalidad, SIN_TIPO, textoBrecha } from "../data/obras.js";
import { api } from "../services/api.js";
import { COLOR_SIN_DATO, ESTADOS_SEGUIMIENTO, normalizar, RANGOS, rangoDe } from "../utils/stats.js";
import { formatoPesos, pct } from "../utils/formato.js";

// "Avance físico" = columna avance_ejecutado de la base de datos.
// avance_programado solo se usa como referencia para la brecha.

const FILTROS_INICIALES = {
  texto: "",
  localidad: "", // código, p. ej. "08"
  tipo: "",
  min: 0,
  max: 100,
  estados: [...ESTADOS_SEGUIMIENTO],
};

/* ---------------- datos ---------------- */

function filtrar(obras, f) {
  const q = normalizar(f.texto.trim());
  const rangoCompleto = f.min === 0 && f.max === 100;
  return obras.filter((o) => {
    if (q && ![o.nombre, o.contrato, o.etapa, o.localidad].some((c) => normalizar(c ?? "").includes(q))) return false;
    if (f.localidad && o.localidadCodigo !== f.localidad) return false;
    if (f.tipo && o.tipo !== f.tipo) return false;
    // Las obras sin dato de avance solo se muestran con el rango completo (0–100 %)
    if (o.avance === null ? !rangoCompleto : o.avance < f.min || o.avance > f.max) return false;
    return f.estados.includes(o.estado);
  });
}

const hayFiltros = (f) => JSON.stringify(f) !== JSON.stringify(FILTROS_INICIALES);

/** Todas las localidades con obras (según los filtros), de mayor a menor avance físico promedio. */
function avancePorLocalidad(obras) {
  const grupos = {};
  obras.forEach((o) => {
    if (!o.localidadCodigo) return;
    const g = (grupos[o.localidadCodigo] ??= { codigo: o.localidadCodigo, nombre: o.localidad, n: 0, avances: [] });
    g.n++;
    if (o.avance !== null) g.avances.push(o.avance);
  });
  return Object.values(grupos)
    .map((g) => ({
      ...g,
      avance: g.avances.length ? g.avances.reduce((a, b) => a + b, 0) / g.avances.length : null,
    }))
    .sort((a, b) => (b.avance ?? -1) - (a.avance ?? -1) || a.nombre.localeCompare(b.nombre));
}

/* ---------------- panel de filtros (columna izquierda) ---------------- */
function PanelFiltros({ filtros, setFiltros, opcionesLocalidad, tipos, conteoEstado, total, filtradas }) {
  const set = (k) => (v) => setFiltros({ ...filtros, [k]: v });
  const toggleEstado = (e) =>
    set("estados")(filtros.estados.includes(e) ? filtros.estados.filter((x) => x !== e) : [...filtros.estados, e]);

  return (
    <aside className="card filtros-panel">
      <div className="filtros-head">
        <h2>
          <Icon name="sliders" size={18} /> Filtros
        </h2>
        {hayFiltros(filtros) && (
          <button type="button" className="link-btn" onClick={() => setFiltros(FILTROS_INICIALES)}>
            Limpiar
          </button>
        )}
      </div>

      <div className="campo">
        <span className="campo-label">Buscar obra</span>
        <SearchInput value={filtros.texto} onChange={set("texto")} placeholder="Nombre, vía o contrato" />
      </div>
      <hr />
      <div className="campo">
        <span className="campo-label">Localidad</span>
        <Select
          value={filtros.localidad}
          onChange={set("localidad")}
          aria-label="Localidad"
          options={[{ value: "", label: "Todas las localidades" }, ...opcionesLocalidad]}
        />
      </div>
      <div className="campo">
        <span className="campo-label">Tipo de contrato</span>
        <Select
          value={filtros.tipo}
          onChange={set("tipo")}
          aria-label="Tipo de contrato"
          options={[{ value: "", label: "Todos los tipos" }, ...tipos.map((t) => ({ value: t, label: t }))]}
        />
      </div>

      <div className="campo">
        <div className="campo-label campo-label-row">
          <span>Avance físico</span>
          <span className="accent">
            {filtros.min}–{filtros.max} %
          </span>
        </div>
        <div className="range">
          <div className="range-track">
            <div className="range-fill" style={{ left: `${filtros.min}%`, width: `${filtros.max - filtros.min}%` }} />
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={filtros.min}
            aria-label="Avance físico mínimo"
            onChange={(e) => set("min")(Math.min(Number(e.target.value), filtros.max))}
          />
          <input
            type="range"
            min="0"
            max="100"
            value={filtros.max}
            aria-label="Avance físico máximo"
            onChange={(e) => set("max")(Math.max(Number(e.target.value), filtros.min))}
          />
        </div>
        <div className="range-labels">
          <span>0 %</span>
          <span>100 %</span>
        </div>
      </div>

      <div className="campo">
        <span className="campo-label">Estado de la obra</span>
        {ESTADOS_SEGUIMIENTO.filter((e) => conteoEstado[e]).map((e) => (
          <label key={e} className="check">
            <input type="checkbox" checked={filtros.estados.includes(e)} onChange={() => toggleEstado(e)} />
            <span>{e}</span>
            <span className="check-count">{conteoEstado[e]}</span>
          </label>
        ))}
      </div>

      <div className="nota-box">
        <Icon name="info" size={18} />
        <p>El color del punto indica el avance físico (ejecutado), no el estado contractual de la obra.</p>
      </div>

      <p className="filtros-foot">
        {filtradas} de {total} obras · {hayFiltros(filtros) ? "Con filtros" : "Sin filtros"}
      </p>
    </aside>
  );
}

/* ---------------- tarjeta de la obra seleccionada ---------------- */
function ObraSeleccionada({ obra, onCerrar }) {
  const brecha = textoBrecha(obra);
  const brechaTexto = brecha ? ` · Brecha: ${brecha}` : "";

  return (
    <section className="card side-card obra-card">
      <div className="side-card-head">
        <span className="eyebrow">Obra seleccionada</span>
        <button type="button" className="icon-btn" title="Cerrar" onClick={onCerrar}>
          <Icon name="x" size={16} />
        </button>
      </div>
      <h3 className="obra-titulo">{obra.nombre}</h3>
      <p className="muted small">
        {obra.localidad}
        {obra.etapa ? ` · ${obra.etapa}` : ""}
      </p>
      <EstadoBadge estado={obra.estado}>
        {obra.estado}
        {obra.estado === "Retrasada" && obra.brecha !== null && ` · ${Math.round(obra.brecha)} pp por debajo`}
      </EstadoBadge>

      <div className="obra-avance">
        <span className="muted small">Avance físico</span>
        <span className="obra-avance-valor">{obra.avance === null ? "Sin dato" : pct(obra.avance)}</span>
      </div>
      {obra.avance !== null && (
        <>
          <Progress value={obra.avance} marcador={obra.programado ?? undefined} alto={6} />
          <p className="muted xsmall obra-brecha">
            Programado: {obra.programado === null ? "sin dato" : pct(obra.programado)}
            {brechaTexto}
          </p>
        </>
      )}
      <hr />
      <div className="obra-datos obra-datos-grid">
        <div>
          <span className="muted xsmall">Contrato</span>
          <strong>{obra.contrato ?? "sin dato"}</strong>
        </div>
        <div className="text-right">
          <span className="muted xsmall">Tipo de contrato</span>
          <strong>{obra.tipo}</strong>
        </div>
        <div>
          <span className="muted xsmall">Contratista</span>
          <strong>{obra.contratista ?? "sin dato"}</strong>
        </div>
        <div className="text-right">
          <span className="muted xsmall">Valor del contrato</span>
          <strong>{obra.valor ? formatoPesos(obra.valor) : "sin dato"}</strong>
        </div>
        <div>
          <span className="muted xsmall">Inicio</span>
          <strong>{fecha(obra.fechaInicio)}</strong>
        </div>
        <div className="text-right">
          <span className="muted xsmall">Fin</span>
          <strong>{fecha(obra.fechaFin)}</strong>
        </div>
      </div>
      {obra.secopUrl && (
        <a className="link-btn link-arrow" href={obra.secopUrl} target="_blank" rel="noreferrer">
          Ver contrato en SECOP <Icon name="arrowUpRight" size={14} />
        </a>
      )}
    </section>
  );
}

/* ---------------- página ---------------- */
export default function MapaPage() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [seleccionadaId, setSeleccionadaId] = useState(null);
  const mapaRef = useRef(null);

  // Obras reales (v_obras_mapa) y polígonos de las localidades
  const [todas, setTodas] = useState([]);
  const [localidadesGeo, setLocalidadesGeo] = useState(null);
  const [errorApi, setErrorApi] = useState(null);
  useEffect(() => {
    api
      .obrasMapa()
      .then((filas) => setTodas(filas.map(adaptarObra).filter((o) => o.lat !== null && o.lon !== null)))
      .catch((e) => setErrorApi(e.message));
    api
      .localidadesGeojson()
      .then(setLocalidadesGeo)
      .catch((e) => setErrorApi(e.message));
  }, []);

  // Indicadores (función fn_indicadores_obras); responden al filtro de localidad
  const [indicadores, setIndicadores] = useState(null);
  useEffect(() => {
    let vigente = true;
    setIndicadores(null);
    api
      .indicadores(filtros.localidad || undefined)
      .then((d) => vigente && setIndicadores(d))
      .catch((e) => vigente && setErrorApi(e.message));
    return () => {
      vigente = false;
    };
  }, [filtros.localidad]);
  const kpis = kpisDesdeApi(indicadores);

  const obras = useMemo(() => filtrar(todas, filtros), [todas, filtros]);
  const porLocalidad = useMemo(() => avancePorLocalidad(obras), [obras]);
  const tipos = useMemo(
    () =>
      [...new Set(todas.map((o) => o.tipo))].sort(
        (a, b) => (a === SIN_TIPO) - (b === SIN_TIPO) || a.localeCompare(b)
      ),
    [todas]
  );
  const conteoEstado = useMemo(() => {
    const c = {};
    todas.forEach((o) => (c[o.estado] = (c[o.estado] || 0) + 1));
    return c;
  }, [todas]);
  const opcionesLocalidad = useMemo(
    () =>
      (localidadesGeo?.features ?? [])
        .map((f) => ({
          value: f.properties.localidad_codigo,
          label: nombreLocalidad(f.properties.localidad_codigo, f.properties.localidad_nombre),
        }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [localidadesGeo]
  );
  const contorno = useMemo(
    () => localidadesGeo?.features.find((f) => f.properties.localidad_codigo === filtros.localidad) ?? null,
    [localidadesGeo, filtros.localidad]
  );

  const conteoRangos = RANGOS.map((r) => obras.filter((o) => o.avance !== null && rangoDe(o.avance) === r).length);
  const sinAvance = obras.filter((o) => o.avance === null).length;
  // Si la obra seleccionada queda fuera de los filtros, la tarjeta se oculta
  const seleccionada = obras.find((o) => o.id === seleccionadaId) ?? null;

  const alternarLocalidad = (codigo) => setFiltros({ ...filtros, localidad: filtros.localidad === codigo ? "" : codigo });

  const pantallaCompleta = () => {
    const el = mapaRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen?.();
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Una mirada al avance de Bogotá</h1>
          <p className="page-sub">Explora las obras viales, identifica rezagos y compara el territorio.</p>
        </div>
        {errorApi && (
          <span className="api-error">
            <Icon name="info" size={15} /> No se pudieron cargar los datos ({errorApi})
          </span>
        )}
      </div>

      <KpiRow stats={kpis} layout="inline" />

      <div className="mapa-grid">
        <PanelFiltros
          filtros={filtros}
          setFiltros={setFiltros}
          opcionesLocalidad={opcionesLocalidad}
          tipos={tipos}
          conteoEstado={conteoEstado}
          total={todas.length}
          filtradas={obras.length}
        />

        {/* ---------- mapa ---------- */}
        <section className="card map-card" ref={mapaRef}>
          <div className="map-card-head">
            <div className="map-card-meta">
              <span className="dot dot-primary" />
              {obras.length} {obras.length === 1 ? "obra" : "obras"} en el mapa
              <button type="button" className="icon-btn" title="Pantalla completa" onClick={pantallaCompleta}>
                <Icon name="maximize" size={16} />
              </button>
            </div>
          </div>

          <MapaObras
            obras={obras}
            seleccionadaId={seleccionada?.id ?? null}
            onSeleccionar={setSeleccionadaId}
            contorno={contorno}
            etiquetaZona={contorno ? `${nombreLocalidad(filtros.localidad)} · Localidad` : "Bogotá, D. C. · Área urbana"}
          />

          <div className="map-legend">
            <div className="map-legend-title">
              <strong>Avance físico</strong>
              <span>Rojo: menor · Amarillo: mayor</span>
            </div>
            <div className="map-legend-bins">
              {RANGOS.map((r, i) => (
                <div key={r.etiqueta} className="legend-bin">
                  <span className="legend-dot" style={{ background: r.color }} />
                  <div>
                    <strong>{r.etiqueta}</strong>
                    <span>{conteoRangos[i]} obras</span>
                  </div>
                </div>
              ))}
              {sinAvance > 0 && (
                <div className="legend-bin">
                  <span className="legend-dot" style={{ background: COLOR_SIN_DATO }} />
                  <div>
                    <strong>Sin dato</strong>
                    <span>{sinAvance} obras</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ---------- columna derecha ---------- */}
        <div className="side-col">
          <div className="side-col-inner">
            <section className={`card side-card loc-card ${seleccionada ? "is-compact" : ""}`}>
              <div className="side-card-head">
                <h3>Avance por localidad</h3>
                <Icon name="bars" size={18} className="accent" />
              </div>
              <p className="side-card-sub">
                Promedio del avance físico ejecutado en {porLocalidad.length}{" "}
                {porLocalidad.length === 1 ? "localidad" : "localidades"}. Haz clic en una para verla en el mapa.
              </p>
              {porLocalidad.length === 0 ? (
                <p className="muted small">No hay obras con estos filtros.</p>
              ) : (
                <ul className="mini-loc-list">
                  {porLocalidad.map((l) => (
                    <li key={l.codigo}>
                      <button
                        type="button"
                        className={`mini-loc-btn ${filtros.localidad === l.codigo ? "is-active" : ""}`}
                        title={filtros.localidad === l.codigo ? "Quitar filtro de localidad" : `Ver solo ${l.nombre}`}
                        onClick={() => alternarLocalidad(l.codigo)}
                      >
                        <div className="mini-loc-line">
                          <span>
                            <strong>{l.nombre}</strong>{" "}
                            <span className="muted">
                              {l.n} {l.n === 1 ? "obra" : "obras"}
                            </span>
                          </span>
                          <strong>{l.avance === null ? "—" : pct(l.avance)}</strong>
                        </div>
                        <Progress value={l.avance ?? 0} color="var(--primary)" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {seleccionada && <ObraSeleccionada obra={seleccionada} onCerrar={() => setSeleccionadaId(null)} />}
          </div>
        </div>
      </div>
    </div>
  );
}
