import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import { EstadoBadge, Progress, SearchInput, Select } from "../components/ui.jsx";
import { adaptarObra, fecha, SIN_TIPO, textoBrecha } from "../data/obras.js";
import { api } from "../services/api.js";
import { colorAvance, ESTADOS_SEGUIMIENTO, normalizar } from "../utils/stats.js";
import { formatoPesos, pct } from "../utils/formato.js";

// Obras reales (v_obras_mapa + estado de seguimiento), agrupadas por localidad.
// "Avance físico" = avance_ejecutado.

const PORTAL_SECOP = "https://www.colombiacompra.gov.co/secop";
const VACIO = { texto: "", localidad: "", tipo: "", estado: "" };
const SIN_LOCALIDAD = "Sin localidad";

function paginas(actual, total) {
  if (total <= 6) return Array.from({ length: total }, (_, i) => i + 1);
  if (actual <= 3) return [1, 2, 3, "…", total];
  if (actual >= total - 2) return [1, "…", total - 2, total - 1, total];
  return [1, "…", actual - 1, actual, actual + 1, "…", total];
}

/** "EN EJECUCION" -> "En ejecucion" */
const oracion = (s = "") => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

function filtrar(obras, f) {
  const q = normalizar(f.texto.trim());
  return obras
    .filter(
      (o) =>
        (!q || [o.nombre, o.contrato, o.etapa, o.contratista].some((c) => normalizar(c ?? "").includes(q))) &&
        (!f.localidad || o.localidadCodigo === f.localidad) &&
        (!f.tipo || o.tipo === f.tipo) &&
        (!f.estado || o.estado === f.estado)
    )
    .sort(
      (a, b) =>
        (a.localidadCodigo ? 0 : 1) - (b.localidadCodigo ? 0 : 1) ||
        a.localidad.localeCompare(b.localidad) ||
        a.nombre.localeCompare(b.nombre)
    );
}

/* ---------------- panel derecho: información completa de la obra ---------------- */
function Dato({ etiqueta, children, ancho = false }) {
  return (
    <div className={`dato ${ancho ? "dato-ancho" : ""}`}>
      <span className="muted xsmall">{etiqueta}</span>
      <strong>{children ?? "sin dato"}</strong>
    </div>
  );
}

function ConsultaObra({ obra, enlaceManual, onVincular, onCerrar, urlRef }) {
  const [urlBorrador, setUrlBorrador] = useState("");
  useEffect(() => setUrlBorrador(""), [obra.id]);
  const urlValida = /^https?:\/\/\S+\.\S+/.test(urlBorrador.trim());
  const brecha = textoBrecha(obra);
  const urlSecop = obra.secopUrl || enlaceManual;

  return (
    <section className="card consulta-card">
      <div className="consulta-head">
        <h3>Consulta contractual</h3>
        <button type="button" className="icon-btn" title="Cerrar" onClick={onCerrar}>
          <Icon name="x" size={16} />
        </button>
      </div>
      <div className="consulta-body">
        <span className="eyebrow">Obra seleccionada</span>
        <h2 className="consulta-titulo">{obra.nombre}</h2>
        <p className="muted small">
          {obra.localidad}
          {obra.etapa ? ` · ${obra.etapa}` : ""}
        </p>
        <div className="consulta-estado">
          <EstadoBadge estado={obra.estado}>
            {obra.estado}
            {obra.estado === "Retrasada" && obra.brecha !== null && ` · ${Math.round(obra.brecha)} pp por debajo`}
          </EstadoBadge>
        </div>

        <div className="obra-avance">
          <span className="muted small">Avance físico</span>
          <span className="obra-avance-valor">{obra.avance === null ? "Sin dato" : pct(obra.avance)}</span>
        </div>
        {obra.avance !== null && (
          <>
            <Progress value={obra.avance} marcador={obra.programado ?? undefined} alto={6} />
            <p className="muted xsmall obra-brecha">
              Programado: {obra.programado === null ? "sin dato" : pct(obra.programado)}
              {brecha && ` · Brecha: ${brecha}`}
            </p>
          </>
        )}

        <hr />
        <span className="muted xsmall">Referencia contractual</span>
        <div className="consulta-ref">{obra.contrato ?? "sin dato"}</div>

        <div className="datos-grid">
          <Dato etiqueta="Tipo de contrato" ancho>
            {obra.tipo}
          </Dato>
          <Dato etiqueta="Estado del contrato (IDU)" ancho>
            {obra.estadoContrato ? oracion(obra.estadoContrato) : null}
          </Dato>
          <Dato etiqueta="Contratista" ancho>
            {obra.contratista}
          </Dato>
          <Dato etiqueta="Interventoría" ancho>
            {obra.interventoria}
          </Dato>
          <Dato etiqueta="Valor del contrato">{obra.valor ? formatoPesos(obra.valor) : null}</Dato>
          <Dato etiqueta="Total pagado">{obra.pagado ? formatoPesos(obra.pagado) : null}</Dato>
          <Dato etiqueta="Inicio">{fecha(obra.fechaInicio)}</Dato>
          <Dato etiqueta="Fin previsto">{fecha(obra.fechaFin)}</Dato>
          <Dato etiqueta="Código SIGIDU">{obra.codigoSigidu}</Dato>
          <Dato etiqueta="Actualizado en el visor">{fecha(obra.fechaActualizacion)}</Dato>
        </div>

        <label className="consulta-url-label" htmlFor="url-secop">
          <Icon name="link" size={15} className="accent" /> Contrato en SECOP
        </label>
        {urlSecop ? (
          <>
            <p className="muted xsmall consulta-nota">
              {obra.secopUrl
                ? "Enlace oficial del proceso en SECOP II, tomado de los datos abiertos."
                : "Enlace agregado manualmente para esta obra."}
            </p>
            <a className="btn btn-primary btn-block" href={urlSecop} target="_blank" rel="noreferrer">
              <Icon name="arrowUpRight" size={16} /> Abrir contrato en SECOP
            </a>
            {!obra.secopUrl && (
              <button type="button" className="link-btn xsmall consulta-quitar" onClick={() => onVincular(obra.id, null)}>
                Quitar enlace
              </button>
            )}
          </>
        ) : (
          <>
            <textarea
              id="url-secop"
              ref={urlRef}
              rows={3}
              value={urlBorrador}
              onChange={(e) => setUrlBorrador(e.target.value)}
              placeholder="Pega aquí el enlace oficial del contrato"
            />
            <p className="muted xsmall consulta-nota">
              Esta obra no tiene enlace a SECOP en los datos abiertos. Puedes agregarlo aquí.
            </p>
            <button
              type="button"
              className={`btn btn-block ${urlValida ? "btn-primary" : "btn-pending"}`}
              disabled={!urlValida}
              onClick={() => {
                onVincular(obra.id, urlBorrador.trim());
                setUrlBorrador("");
              }}
            >
              <Icon name="link" size={16} /> {urlValida ? "Vincular enlace" : "Enlace pendiente"}
            </button>
          </>
        )}
      </div>
    </section>
  );
}

/* ---------------- página ---------------- */
export default function ListadoPage({ enlaces, onVincular }) {
  const [todas, setTodas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [borrador, setBorrador] = useState(VACIO);
  const [filtros, setFiltros] = useState(VACIO);
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(9);
  const [seleccionadaId, setSeleccionadaId] = useState(null);
  const urlRef = useRef(null);

  useEffect(() => {
    api
      .obrasMapa()
      .then((filas) => setTodas(filas.map(adaptarObra)))
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, []);

  // Indicadores de la cabecera (mismas reglas que fn_indicadores_obras)
  const general = useMemo(() => {
    const avances = todas.map((o) => o.avance).filter((v) => v !== null);
    return {
      total: todas.length,
      avance: avances.length ? avances.reduce((a, b) => a + b, 0) / avances.length : null,
      atencion: todas.filter((o) => o.estado === "Retrasada" || o.estado === "Suspendida").length,
    };
  }, [todas]);

  // Opciones de los filtros, a partir de los datos
  const opciones = useMemo(() => {
    const locs = new Map();
    todas.forEach((o) => o.localidadCodigo && locs.set(o.localidadCodigo, o.localidad));
    const conteoEstado = {};
    todas.forEach((o) => (conteoEstado[o.estado] = (conteoEstado[o.estado] || 0) + 1));
    return {
      localidades: [...locs].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label)),
      tipos: [...new Set(todas.map((o) => o.tipo))]
        .sort((a, b) => (a === SIN_TIPO) - (b === SIN_TIPO) || a.localeCompare(b))
        .map((t) => ({ value: t, label: t })),
      estados: ESTADOS_SEGUIMIENTO.filter((e) => conteoEstado[e]).map((e) => ({
        value: e,
        label: `${e} (${conteoEstado[e]})`,
      })),
    };
  }, [todas]);

  const obras = useMemo(() => filtrar(todas, filtros), [todas, filtros]);
  const conteoLocalidad = useMemo(() => {
    const c = {};
    obras.forEach((o) => (c[o.localidad] = (c[o.localidad] || 0) + 1));
    return c;
  }, [obras]);

  const totalPaginas = Math.max(1, Math.ceil(obras.length / porPagina));
  const paginaSegura = Math.min(pagina, totalPaginas);
  const visibles = obras.slice((paginaSegura - 1) * porPagina, paginaSegura * porPagina);
  const seleccionada = todas.find((o) => o.id === seleccionadaId) ?? null;
  const conFiltros = JSON.stringify(filtros) !== JSON.stringify(VACIO);

  const aplicar = () => {
    setFiltros(borrador);
    setPagina(1);
  };
  const limpiar = () => {
    setBorrador(VACIO);
    setFiltros(VACIO);
    setPagina(1);
  };
  const set = (k) => (v) => setBorrador({ ...borrador, [k]: v });
  const irAEnlace = (o) => {
    setSeleccionadaId(o.id);
    setTimeout(() => urlRef.current?.focus(), 0);
  };

  let ultimaLocalidad = null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Listado de obras</h1>
          <p className="page-sub">
            Consulta las obras por localidad y encuentra la referencia de su contrato en SECOP. Selecciona una obra
            para ver toda su información.
          </p>
        </div>
        <div className="head-stats">
          <div>
            <strong>{cargando ? "—" : general.total}</strong>
            <span>obras en Bogotá</span>
          </div>
          <div>
            <strong>{general.avance === null ? "—" : pct(general.avance)}</strong>
            <span>avance físico promedio</span>
          </div>
          <div>
            <strong>{cargando ? "—" : general.atencion}</strong>
            <span>requieren atención</span>
          </div>
        </div>
      </div>

      {error && (
        <span className="api-error">
          <Icon name="info" size={15} /> No se pudieron cargar las obras ({error})
        </span>
      )}

      <section className="card listado-filtros">
        <div className="campo campo-buscar">
          <span className="campo-label">Buscar obra o contrato</span>
          <SearchInput
            value={borrador.texto}
            onChange={set("texto")}
            onEnter={aplicar}
            placeholder="Nombre de obra, vía, contrato o contratista"
          />
        </div>
        <div className="campo">
          <span className="campo-label">Localidad</span>
          <Select
            value={borrador.localidad}
            onChange={set("localidad")}
            aria-label="Localidad"
            options={[{ value: "", label: "Todo Bogotá" }, ...opciones.localidades]}
          />
        </div>
        <div className="campo">
          <span className="campo-label">Tipo de contrato</span>
          <Select
            value={borrador.tipo}
            onChange={set("tipo")}
            aria-label="Tipo de contrato"
            options={[{ value: "", label: "Todos los tipos" }, ...opciones.tipos]}
          />
        </div>
        <div className="campo">
          <span className="campo-label">Estado de la obra</span>
          <Select
            value={borrador.estado}
            onChange={set("estado")}
            aria-label="Estado de la obra"
            options={[{ value: "", label: "Todos los estados" }, ...opciones.estados]}
          />
        </div>
        <button type="button" className="btn btn-primary btn-tall" onClick={aplicar}>
          <Icon name="sliders" size={16} /> Aplicar filtros
        </button>
        <button type="button" className="link-btn btn-tall" onClick={limpiar}>
          Limpiar
        </button>
      </section>

      <div className="listado-grid">
        {/* ---------------- tabla ---------------- */}
        <section className="card tabla-card">
          <div className="tabla-head">
            <h2>
              Obras por localidad <span className="pill pill-gold">{obras.length} obras</span>
            </h2>
            <span className="muted xsmall">Agrupado por localidad · {conFiltros ? "Con filtros" : "Sin filtros"}</span>
          </div>

          <div className="tabla-scroll">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Obra / referencia contractual</th>
                  <th>Tipo de contrato</th>
                  <th>Avance físico</th>
                  <th>Estado</th>
                  <th>Contrato SECOP</th>
                </tr>
              </thead>
              <tbody>
                {visibles.length === 0 && (
                  <tr>
                    <td colSpan={5} className="tabla-vacia">
                      {cargando ? "Cargando obras…" : "No hay obras con esos filtros."}
                    </td>
                  </tr>
                )}
                {visibles.map((o) => {
                  const nuevaLocalidad = o.localidad !== ultimaLocalidad;
                  ultimaLocalidad = o.localidad;
                  const url = o.secopUrl || enlaces[o.id];
                  const n = conteoLocalidad[o.localidad];
                  return (
                    <Fragment key={o.id}>
                      {nuevaLocalidad && (
                        <tr className="fila-grupo">
                          <td colSpan={5}>
                            <Icon name="pin" size={15} />
                            <strong>{o.localidad}</strong>
                            <span>
                              {n} {n === 1 ? "obra" : "obras"}
                              {o.localidad === SIN_LOCALIDAD ? "" : " en la localidad"}
                            </span>
                          </td>
                        </tr>
                      )}
                      <tr
                        className={`fila-obra ${o.id === seleccionadaId ? "is-selected" : ""}`}
                        onClick={() => setSeleccionadaId(o.id)}
                      >
                        <td>
                          <div className="obra-nombre">{o.nombre}</div>
                          <div className="obra-ref">
                            {[o.etapa, o.contrato].filter(Boolean).join(" · ")}
                          </div>
                        </td>
                        <td className="text-2">{o.tipo}</td>
                        <td>
                          {o.avance === null ? (
                            <span className="muted">Sin dato</span>
                          ) : (
                            <div className="avance-cell">
                              <strong>{pct(o.avance)}</strong>
                              <Progress value={o.avance} color={colorAvance(o.avance)} />
                            </div>
                          )}
                        </td>
                        <td>
                          <EstadoBadge estado={o.estado} />
                        </td>
                        <td onClick={(e) => e.stopPropagation()}>
                          {url ? (
                            <a className="contrato-link" href={url} target="_blank" rel="noreferrer">
                              Ver contrato <Icon name="arrowUpRight" size={13} strokeWidth={2.2} />
                            </a>
                          ) : (
                            <button type="button" className="contrato-link" onClick={() => irAEnlace(o)}>
                              Vincular <Icon name="link" size={13} strokeWidth={2.2} />
                            </button>
                          )}
                          <div className="muted xxsmall">
                            {o.secopUrl ? "SECOP II" : url ? "Enlace manual" : "Sin URL vinculada"}
                          </div>
                        </td>
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="paginacion">
            <span className="muted small">
              Mostrando {obras.length ? (paginaSegura - 1) * porPagina + 1 : 0}–
              {Math.min(paginaSegura * porPagina, obras.length)} de {obras.length} obras
            </span>
            <div className="paginas">
              <button
                type="button"
                className="pag-btn pag-flecha"
                disabled={paginaSegura === 1}
                onClick={() => setPagina(paginaSegura - 1)}
                aria-label="Página anterior"
              >
                <Icon name="chevronLeft" size={16} />
              </button>
              {paginas(paginaSegura, totalPaginas).map((p, i) =>
                p === "…" ? (
                  <span key={`e${i}`} className="pag-ellipsis">
                    …
                  </span>
                ) : (
                  <button
                    key={p}
                    type="button"
                    className={`pag-btn ${p === paginaSegura ? "is-active" : ""}`}
                    onClick={() => setPagina(p)}
                  >
                    {p}
                  </button>
                )
              )}
              <button
                type="button"
                className="pag-btn pag-flecha accent"
                disabled={paginaSegura === totalPaginas}
                onClick={() => setPagina(paginaSegura + 1)}
                aria-label="Página siguiente"
              >
                <Icon name="chevronRight" size={16} />
              </button>
            </div>
            <Select
              className="select-plain"
              value={String(porPagina)}
              onChange={(v) => {
                setPorPagina(Number(v));
                setPagina(1);
              }}
              aria-label="Obras por página"
              options={[9, 18, 36].map((n) => ({ value: String(n), label: `${n} por página` }))}
            />
          </div>

          <div className="tabla-foot">
            <Icon name="info" size={15} /> Fuente: visor de obras del IDU, cruzado con SECOP II por número de contrato.
          </div>
        </section>

        {/* ---------------- panel derecho ---------------- */}
        <aside className="side-col listado-side">
          {seleccionada ? (
            <ConsultaObra
              obra={seleccionada}
              enlaceManual={enlaces[seleccionada.id]}
              onVincular={onVincular}
              onCerrar={() => setSeleccionadaId(null)}
              urlRef={urlRef}
            />
          ) : (
            <section className="card consulta-card consulta-vacia">
              <div className="consulta-head">
                <h3>Consulta contractual</h3>
                <Icon name="file" size={18} className="accent" />
              </div>
              <div className="consulta-body">
                <Icon name="list" size={28} className="accent" />
                <p className="text-2 small">
                  Selecciona una obra del listado para ver su información completa: avance, contrato, contratista,
                  fechas y enlace a SECOP.
                </p>
              </div>
            </section>
          )}

          <section className="card side-card">
            <div className="side-card-head">
              <a className="portal-link" href={PORTAL_SECOP} target="_blank" rel="noreferrer">
                Portal SECOP <Icon name="arrowUpRight" size={15} strokeWidth={2.2} />
              </a>
              <Icon name="globe" size={18} className="accent" />
            </div>
            <p className="text-2 small">Consulta general de la contratación pública en Colombia.</p>
            <a className="xsmall accent" href={PORTAL_SECOP} target="_blank" rel="noreferrer">
              {PORTAL_SECOP}
            </a>
            <hr />
            <p className="muted xsmall">Es el portal general, no el enlace al contrato específico de una obra.</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
