import { ESTADOS, LOCALIDADES, TIPOS } from "../data/mockData.js";

// Rangos de avance físico (color del punto en el mapa y de las barras)
export const RANGOS = [
  { etiqueta: "0–24 %", min: 0, max: 24, color: "#B23A2E" },
  { etiqueta: "25–49 %", min: 25, max: 49, color: "#E0763A" },
  { etiqueta: "50–74 %", min: 50, max: 74, color: "#E3A33A" },
  { etiqueta: "75–100 %", min: 75, max: 100, color: "#E9C548" },
];

export function rangoDe(avance) {
  return RANGOS.find((r) => avance <= r.max) ?? RANGOS[RANGOS.length - 1];
}

export const COLOR_SIN_DATO = "#9a8f85";

/** Color del punto según el avance físico (gris si la obra no tiene dato). */
export function colorAvance(avance) {
  return avance === null || avance === undefined ? COLOR_SIN_DATO : rangoDe(avance).color;
}

// Estados de seguimiento que calcula la base de datos (función clasificar_obra)
export const ESTADOS_SEGUIMIENTO = ["En ejecución", "Retrasada", "Suspendida", "Finalizada", "Caducada", "Sin dato"];

export const COLOR_ESTADO = {
  "En ejecución": "#9A3B33",
  Retrasada: "#C98B2E",
  Suspendida: "#D2665A",
  Finalizada: "#B9A26A",
};

export const PLURAL_ESTADO = {
  "En ejecución": "En ejecución",
  Retrasada: "Retrasadas",
  Suspendida: "Suspendidas",
  Finalizada: "Finalizadas",
};

const promedio = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);

export function resumen(obras) {
  const porEstado = Object.fromEntries(ESTADOS.map((e) => [e, 0]));
  const porTipo = Object.fromEntries(TIPOS.map((t) => [t, 0]));
  obras.forEach((o) => {
    porEstado[o.estado]++;
    porTipo[o.tipo]++;
  });
  return {
    total: obras.length,
    avance: promedio(obras.map((o) => o.avance)),
    programado: promedio(obras.map((o) => o.programado)),
    porEstado,
    porTipo,
    atencion: porEstado.Retrasada + porEstado.Suspendida,
    localidades: new Set(obras.map((o) => o.localidad)).size,
  };
}

/** Las `top` localidades con más obras, ordenadas por avance promedio (mayor primero). */
export function avancePorLocalidad(obras, top = 5) {
  const grupos = {};
  obras.forEach((o) => (grupos[o.localidad] ??= []).push(o.avance));
  return Object.entries(grupos)
    .map(([nombre, avances]) => ({ nombre, n: avances.length, avance: promedio(avances) }))
    .sort((a, b) => b.n - a.n)
    .slice(0, top)
    .sort((a, b) => b.avance - a.avance);
}

export const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct"];

/** Serie mensual ilustrativa que termina en el promedio actual. */
export function serieMensual(obras) {
  const { avance, programado } = resumen(obras);
  return MESES.map((mes, i) => {
    const t = Math.pow(i / (MESES.length - 1), 0.93);
    return {
      mes,
      programado: 13 + (programado - 13) * t,
      ejecutado: 11 + (avance - 11) * t + (i > 0 && i < 9 ? Math.sin(i * 1.7) * 0.6 : 0),
    };
  });
}

export function ordenLocalidad(nombre) {
  const i = LOCALIDADES.findIndex((l) => l.nombre === nombre);
  return i === -1 ? 99 : i;
}

/** Quita tildes y pasa a minúsculas, para búsquedas. */
export function normalizar(s = "") {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function coincideBusqueda(obra, texto) {
  if (!texto.trim()) return true;
  const q = normalizar(texto.trim());
  return [obra.nombre, obra.tramo, obra.contrato, obra.localidad].some((c) => normalizar(c).includes(q));
}
