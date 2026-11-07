// Conversión de las obras reales que entrega la API (/api/obras/mapa) al formato
// que usan las vistas Mapa y Listado.
// "Avance físico" = avance_ejecutado; avance_programado es solo la referencia.
import { LOCALIDADES } from "./mockData.js";

export const SIN_TIPO = "Sin dato";

// Nombres con tildes por código de localidad (la base los trae en mayúsculas sin tildes)
const NOMBRE_LOCALIDAD = Object.fromEntries(LOCALIDADES.map((l) => [l.codigo, l.nombre]));
const titulo = (s = "") => s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
export const nombreLocalidad = (codigo, crudo) =>
  NOMBRE_LOCALIDAD[codigo] ?? (crudo ? titulo(crudo) : "Sin localidad");

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));

/** Nombre corto para etiquetas: lo que va antes del primer " - ", máx. 42 caracteres. */
function nombreCorto(nombre = "") {
  const base = nombre.split(" - ")[0].trim();
  return base.length > 42 ? `${base.slice(0, 40).trim()}…` : base;
}

/** Fila de /api/obras/mapa -> objeto que usa la interfaz. */
export function adaptarObra(r) {
  return {
    id: r.objectid,
    nombre: r.nombre ?? "Obra sin nombre",
    corto: nombreCorto(r.nombre ?? "Obra"),
    etapa: r.etapa,
    contrato: r.contrato,
    codigoSigidu: r.codigo_sigidu,
    tipo: r.contrato_tipo || SIN_TIPO,
    estado: r.estado_seguimiento || "Sin dato",
    estadoContrato: r.estado_contrato,
    avance: num(r.avance_ejecutado),
    programado: num(r.avance_programado),
    brecha: num(r.brecha_pp),
    contratista: r.contratista,
    interventoria: r.interventoria_contratista,
    interventoriaContrato: r.interventoria_contrato,
    valor: num(r.valor_contrato),
    pagado: num(r.total_pagado),
    fechaInicio: r.fecha_inicio,
    fechaFin: r.fecha_fin,
    fechaActualizacion: r.fecha_actualizacion,
    enSecop: r.en_secop,
    localidadCodigo: r.localidad_codigo,
    localidad: nombreLocalidad(r.localidad_codigo, r.localidad_nombre),
    secopUrl: r.secop_url,
    lat: num(r.lat),
    lon: num(r.lon),
  };
}

/** "2024-03-19" -> "19 de mar de 2024" */
export const fecha = (iso) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" })
    : "sin dato";

/** Diferencia ejecutado - programado como texto: "−20,0 pp" / "+1,5 pp" / "0 pp". */
export function textoBrecha(obra) {
  if (obra.avance === null || obra.programado === null) return null;
  const b = obra.avance - obra.programado;
  if (b === 0) return "0 pp";
  return `${b > 0 ? "+" : "−"}${Math.abs(b).toFixed(1).replace(".", ",")} pp`;
}
