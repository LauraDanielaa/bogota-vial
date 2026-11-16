import { useEffect, useMemo, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import KpiRow, { kpisDesdeApi } from "../components/KpiRow.jsx";
import MapaObras from "../components/MapaObras.jsx";
import { EstadoBadge, Progress, SearchInput, Select } from "../components/ui.jsx";
import { adaptarObra, fecha, nombreLocalidad, SIN_TIPO, textoBrecha } from "../data/obras.js";
import { api } from "../services/api.js";
import {
  COLOR_SIN_DATO,
  colorRiesgo,
  ESTADOS_SEGUIMIENTO,
  NIVELES_RIESGO,
  normalizar,
  RANGOS,
  rangoDe,
} from "../utils/stats.js";
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
  riesgos: [...NIVELES_RIESGO],
  soloAtipicos: false,
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
    if (!f.riesgos.includes(o.riesgo)) return false;
    if (f.soloAtipicos && !o.atipico) return false;
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

/** Línea de la leyenda para el anillo punteado de las obras con contrato atípico. */
function LeyendaAtipico({ n }) {
  if (!n) return null;
  return (
    <div className="legend-bin">
      <span className="legend-ring" />
      <div>
        <strong>Contrato atípico</strong>
        <span>
          {n} {n === 1 ? "obra" : "obras"}
        </span>
      </div>
    </div>
  );
}

/* ---------------- panel de filtros (columna izquierda) ---------------- */
function PanelFiltros({
  filtros,
  setFiltros,
  opcionesLocalidad,
  tipos,
  conteoEstado,
  conteoRiesgo,
  nAtipicos,
  verPor,
  total,
  filtradas,
}) {
  const set = (k) => (v) => setFiltros({ ...filtros, [k]: v });
  const alternar = (k, valor) =>
    set(k)(filtros[k].includes(valor) ? filtros[k].filter((x) => x !== valor) : [...filtros[k], valor]);
  const toggleEstado = (e) => alternar("estados", e);

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

      <div className="campo">
        <span className="campo-label">Riesgo de atraso</span>
        {NIVELES_RIESGO.filter((n) => conteoRiesgo[n]).map((n) => (
          <label key={n} className="check">
            <input type="checkbox" checked={filtros.riesgos.includes(n)} onChange={() => alternar("riesgos", n)} />
            <span className="riesgo-dot" style={{ background: colorRiesgo(n) }} />
            <span>{n}</span>
            <span className="check-count">{conteoRiesgo[n]}</span>
          </label>
        ))}
      </div>

      {nAtipicos > 0 && (
        <div className="campo">
          <span className="campo-label">Contrato</span>
          <label className="check">
            <input
              type="checkbox"
              checked={filtros.soloAtipicos}
              onChange={() => set("soloAtipicos")(!filtros.soloAtipicos)}
            />
            <span className="legend-ring" />
            <span>Solo obras con contrato atípico</span>
            <span className="check-count">{nAtipicos}</span>
          </label>
        </div>
      )}

      <div className="nota-box">
        <Icon name="info" size={18} />
        <p>
          {verPor === "riesgo"
            ? "El color indica el riesgo de atraso: Prorrogada es un hecho registrado en SECOP; Alto, Medio y Bajo son estimaciones de un modelo estadístico, no datos oficiales del IDU."
            : "El color del punto indica el avance físico (ejecutado), no el estado contractual de la obra."}
        </p>
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
  const [verPor, setVerPor] = useState("avance"); // color de los puntos: "avance" | "riesgo"
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
  const conteoRiesgo = useMemo(() => {
    const c = {};
    todas.forEach((o) => (c[o.riesgo] = (c[o.riesgo] || 0) + 1));
    return c;
  }, [todas]);
  // Obras con contrato atípico (0 si el modelo de atípicos aún no se ha ejecutado: no se muestra nada)
  const nAtipicos = useMemo(() => todas.filter((o) => o.atipico).length, [todas]);
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
  const atipicosVisibles = obras.filter((o) => o.atipico).length;
  const riesgoVisibles = NIVELES_RIESGO.map((n) => ({ nivel: n, n: obras.filter((o) => o.riesgo === n).length })).filter(
    (r) => r.n > 0
  );
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
          <h1>Panorama de las obras viales en Bogotá</h1>
          <p className="page-sub">Información para monitorear la ejecución de las obras, detectar retrasos y comparar el avance entre localidades.</p>
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
          conteoRiesgo={conteoRiesgo}
          nAtipicos={nAtipicos}
          verPor={verPor}
          total={todas.length}
          filtradas={obras.length}
        />

        {/* ---------- mapa ---------- */}
        <section className="card map-card" ref={mapaRef}>
          <div className="map-card-head">
            <div className="ver-por" role="group" aria-label="Ver puntos por">
              <span>Ver puntos por:</span>
              <div className="mini-tabs">
                {[
                  ["avance", "Avance físico"],
                  ["riesgo", "Riesgo de atraso"],
                ].map(([valor, texto]) => (
                  <button
                    key={valor}
                    type="button"
                    className={`mini-tab ${verPor === valor ? "is-active" : ""}`}
                    aria-pressed={verPor === valor}
                    onClick={() => setVerPor(valor)}
                  >
                    {texto}
                  </button>
                ))}
              </div>
            </div>
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
            verPor={verPor}
          />

          {verPor === "riesgo" ? (
            <div className="map-legend">
              <div className="map-legend-title">
                <strong>Riesgo de atraso</strong>
                <span>Más oscuro: mayor riesgo</span>
              </div>
              <div className="map-legend-bins">
                {riesgoVisibles.length === 0 && <span className="map-legend-note">No hay obras con estos filtros.</span>}
                {riesgoVisibles.map((r) => (
                  <div key={r.nivel} className="legend-bin">
                    <span className="legend-dot riesgo-dot" style={{ background: colorRiesgo(r.nivel) }} />
                    <div>
                      <strong>{r.nivel}</strong>
                      <span>
                        {r.n} {r.n === 1 ? "obra" : "obras"}
                      </span>
                    </div>
                  </div>
                ))}
                <LeyendaAtipico n={atipicosVisibles} />
              </div>
            </div>
          ) : (
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
              <LeyendaAtipico n={atipicosVisibles} />
            </div>
          </div>
          )}
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
