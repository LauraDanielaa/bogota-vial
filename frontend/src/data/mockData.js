// =====================================================================
// DATOS DE EJEMPLO (temporales)
// Se generan de forma determinística (siempre salen iguales) para poder
// diseñar las pantallas sin la base de datos. Más adelante se reemplazan
// por las respuestas del backend (/api/obras, /api/localidades).
// =====================================================================

export const FECHA_CORTE = "31 oct 2026";

export const TIPOS = ["Mantenimiento", "Rehabilitación", "Construcción", "Conservación"];
export const ESTADOS = ["En ejecución", "Retrasada", "Suspendida", "Finalizada"];

// Orden de las localidades = orden en que aparecen agrupadas en el listado.
export const LOCALIDADES = [
  { codigo: "08", nombre: "Kennedy", lat: 4.632, lon: -74.152, n: 20, media: 40, dispersion: 0.02,
    barrios: ["Timiza", "Américas", "Corabastos", "Kennedy Central"], vias: ["av. Primero de Mayo", "av. Las Américas", "av. Boyacá"] },
  { codigo: "10", nombre: "Engativá", lat: 4.704, lon: -74.112, n: 18, media: 52, dispersion: 0.018,
    barrios: ["Minuto de Dios", "Bolivia", "Garcés Navas", "Santa Helenita"], vias: ["Calle 80", "av. Rojas", "Calle 72"] },
  { codigo: "11", nombre: "Suba", lat: 4.742, lon: -74.083, n: 22, media: 60, dispersion: 0.022,
    barrios: ["Lisboa", "Niza", "El Rincón", "Gaitana"], vias: ["av. Suba", "Calle 145", "av. Ciudad de Cali"] },
  { codigo: "01", nombre: "Usaquén", lat: 4.716, lon: -74.035, n: 12, media: 66, dispersion: 0.016,
    barrios: ["Cedritos", "Santa Bárbara", "Toberín", "Verbenal"], vias: ["Carrera 7", "av. Novena", "Calle 170"] },
  { codigo: "07", nombre: "Bosa", lat: 4.618, lon: -74.188, n: 14, media: 28, dispersion: 0.016,
    barrios: ["Bosa Centro", "El Recreo", "La Libertad", "San Bernardino"], vias: ["Autopista Sur", "av. Bosa", "av. Ciudad de Cali"] },
  { codigo: "02", nombre: "Chapinero", lat: 4.648, lon: -74.062, n: 3, media: 55, dispersion: 0.01,
    barrios: ["Chicó", "El Retiro", "Los Rosales"], vias: ["Carrera 7", "av. Caracas"] },
  { codigo: "03", nombre: "Santa Fe", lat: 4.606, lon: -74.072, n: 2, media: 50, dispersion: 0.008,
    barrios: ["Las Nieves", "La Macarena"], vias: ["av. Jiménez", "Carrera 7"] },
  { codigo: "04", nombre: "San Cristóbal", lat: 4.562, lon: -74.088, n: 3, media: 45, dispersion: 0.01,
    barrios: ["20 de Julio", "La Victoria"], vias: ["av. Primero de Mayo", "Carrera 10"] },
  { codigo: "05", nombre: "Usme", lat: 4.505, lon: -74.112, n: 2, media: 38, dispersion: 0.01,
    barrios: ["Usme Centro", "Santa Librada"], vias: ["Autopista al Llano", "av. Boyacá"] },
  { codigo: "06", nombre: "Tunjuelito", lat: 4.578, lon: -74.135, n: 3, media: 46, dispersion: 0.008,
    barrios: ["Venecia", "El Tunal"], vias: ["Autopista Sur", "av. Boyacá"] },
  { codigo: "09", nombre: "Fontibón", lat: 4.676, lon: -74.142, n: 5, media: 55, dispersion: 0.014,
    barrios: ["Modelia", "Fontibón Centro", "Zona Franca"], vias: ["av. El Dorado", "Calle 13", "av. Ciudad de Cali"] },
  { codigo: "12", nombre: "Barrios Unidos", lat: 4.668, lon: -74.076, n: 3, media: 58, dispersion: 0.008,
    barrios: ["Doce de Octubre", "Los Andes"], vias: ["av. 68", "Calle 80"] },
  { codigo: "13", nombre: "Teusaquillo", lat: 4.640, lon: -74.085, n: 3, media: 56, dispersion: 0.008,
    barrios: ["Galerías", "La Soledad"], vias: ["av. NQS", "Calle 53"] },
  { codigo: "14", nombre: "Los Mártires", lat: 4.606, lon: -74.091, n: 2, media: 48, dispersion: 0.006,
    barrios: ["Santa Isabel", "Ricaurte"], vias: ["av. Comuneros", "Calle 13"] },
  { codigo: "15", nombre: "Antonio Nariño", lat: 4.590, lon: -74.101, n: 2, media: 47, dispersion: 0.006,
    barrios: ["Restrepo", "Santander"], vias: ["av. Primero de Mayo", "Carrera 24"] },
  { codigo: "16", nombre: "Puente Aranda", lat: 4.617, lon: -74.115, n: 5, media: 50, dispersion: 0.012,
    barrios: ["Ciudad Montes", "Galán", "Puente Aranda"], vias: ["av. 68", "Calle 13", "av. Las Américas"] },
  { codigo: "17", nombre: "La Candelaria", lat: 4.597, lon: -74.073, n: 1, media: 58, dispersion: 0.003,
    barrios: ["La Concordia"], vias: ["Carrera 4"] },
  { codigo: "18", nombre: "Rafael Uribe Uribe", lat: 4.575, lon: -74.115, n: 3, media: 44, dispersion: 0.008,
    barrios: ["Quiroga", "Marruecos"], vias: ["av. Caracas", "Calle 27 sur"] },
  { codigo: "19", nombre: "Ciudad Bolívar", lat: 4.552, lon: -74.150, n: 4, media: 36, dispersion: 0.012,
    barrios: ["Arborizadora", "Lucero", "Perdomo"], vias: ["av. Villavicencio", "av. Boyacá"] },
  { codigo: "20", nombre: "Sumapaz", lat: 4.470, lon: -74.130, n: 1, media: 30, dispersion: 0.004,
    barrios: ["Nazareth"], vias: ["vía a San Juan"] },
];

// Obras "fijas" que aparecen en los mockups.
const DESTACADAS = [
  { nombre: "Rehabilitación de la av. Boyacá", corto: "Av. Boyacá", loc: "Kennedy", tramo: "Calle 6 a calle 13",
    contrato: "VIAL-026-2026", tipo: "Mantenimiento", avance: 38, programado: 58, estado: "Retrasada", lat: 4.6372, lon: -74.1228 },
  { nombre: "Mejoramiento vial de Patio Bonito", corto: "Patio Bonito", loc: "Kennedy", tramo: "Carrera 89 a carrera 92",
    contrato: "VIAL-041-2026", tipo: "Rehabilitación", avance: 62, programado: 66, estado: "En ejecución", lat: 4.6335, lon: -74.1745 },
  { nombre: "Conservación de vías en Castilla", corto: "Castilla", loc: "Kennedy", tramo: "Calle 8 a calle 10",
    contrato: "VIAL-058-2026", tipo: "Mantenimiento", avance: 45, programado: 49, estado: "En ejecución", lat: 4.6455, lon: -74.1418 },
  { nombre: "Rehabilitación de la av. Ciudad de Cali", corto: "Av. Ciudad de Cali", loc: "Engativá", tramo: "Calle 72 a calle 80",
    contrato: "VIAL-019-2026", tipo: "Mantenimiento", avance: 71, programado: 74, estado: "En ejecución", lat: 4.7035, lon: -74.1185 },
  { nombre: "Mejoramiento de accesos a Las Ferias", corto: "Las Ferias", loc: "Engativá", tramo: "Carrera 68 a carrera 70",
    contrato: "VIAL-063-2026", tipo: "Rehabilitación", avance: 24, programado: 47, estado: "Suspendida", lat: 4.6925, lon: -74.0885 },
  { nombre: "Conexión vial de Álamos", corto: "Álamos", loc: "Engativá", tramo: "Calle 64 a calle 66",
    contrato: "VIAL-074-2026", tipo: "Construcción", avance: 100, programado: 100, estado: "Finalizada", lat: 4.6962, lon: -74.1172 },
  { nombre: "Ampliación de la av. Rincón", corto: "Av. Rincón", loc: "Suba", tramo: "Av. Boyacá a carrera 91",
    contrato: "VIAL-012-2026", tipo: "Construcción", avance: 68, programado: 72, estado: "En ejecución", lat: 4.7352, lon: -74.0928 },
  { nombre: "Conservación de la malla vial de Tibabuyes", corto: "Tibabuyes", loc: "Suba", tramo: "Calle 139 a calle 145",
    contrato: "VIAL-037-2026", tipo: "Mantenimiento", avance: 47, programado: 66, estado: "Retrasada", lat: 4.7478, lon: -74.1052 },
  { nombre: "Mejoramiento vial en Prado Veraniego", corto: "Prado Veraniego", loc: "Suba", tramo: "Carrera 50 a carrera 54",
    contrato: "VIAL-082-2026", tipo: "Rehabilitación", avance: 83, programado: 85, estado: "En ejecución", lat: 4.7302, lon: -74.0602 },
];

const TOTAL_TIPO = { Mantenimiento: 48, Rehabilitación: 36, Construcción: 28, Conservación: 16 };
const TOTAL_ESTADO = { "En ejecución": 86, Retrasada: 18, Suspendida: 8, Finalizada: 16 };

const PLANTILLAS = {
  Mantenimiento: [(v) => `Mantenimiento de la ${v}`, (_, b) => `Mantenimiento vial en ${b}`, (_, b) => `Reparcheo de la malla vial de ${b}`],
  Rehabilitación: [(v) => `Rehabilitación de la ${v}`, (_, b) => `Mejoramiento vial de ${b}`, (_, b) => `Rehabilitación de accesos a ${b}`],
  Construcción: [(v) => `Ampliación de la ${v}`, (_, b) => `Construcción de ciclorruta en ${b}`, (_, b) => `Conexión vial de ${b}`],
  Conservación: [(_, b) => `Conservación de vías en ${b}`, (_, b) => `Conservación de la malla vial de ${b}`],
};

// ---------- generador pseudoaleatorio con semilla ----------
function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(2026);
const entre = (a, b) => a + rand() * (b - a);
const elegir = (arr) => arr[Math.floor(rand() * arr.length)];
const limitar = (v, a, b) => Math.max(a, Math.min(b, v));
function barajar(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
const capitalizar = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function avancesSegunEstado(estado, media) {
  if (estado === "Finalizada") return [100, 100];
  let avance, programado;
  if (estado === "Retrasada") {
    avance = limitar(media + entre(-22, 2), 5, 85);
    programado = avance + entre(14, 26);
  } else if (estado === "Suspendida") {
    avance = entre(10, 55);
    programado = avance + entre(12, 30);
  } else {
    avance = limitar(media + entre(-18, 18), 5, 95);
    programado = avance + entre(-1, 8);
  }
  return [Math.round(avance), Math.round(limitar(programado, avance, 100))];
}

function tramoAleatorio() {
  const tipo = rand() < 0.5 ? "Calle" : "Carrera";
  const desde = Math.floor(entre(1, 160));
  return `${tipo} ${desde} a ${tipo.toLowerCase()} ${desde + Math.floor(entre(2, 9))}`;
}

function generar() {
  const locPorNombre = Object.fromEntries(LOCALIDADES.map((l) => [l.nombre, l]));
  const tiposRest = { ...TOTAL_TIPO };
  const estadosRest = { ...TOTAL_ESTADO };
  const usadosLoc = {};
  const contratosUsados = new Set();
  const nombres = new Set();
  const obras = [];

  DESTACADAS.forEach((d, i) => {
    const loc = locPorNombre[d.loc];
    tiposRest[d.tipo]--;
    estadosRest[d.estado]--;
    usadosLoc[d.loc] = (usadosLoc[d.loc] || 0) + 1;
    contratosUsados.add(d.contrato);
    nombres.add(d.nombre);
    obras.push({ id: i + 1, ...d, localidad: loc.nombre, localidadCodigo: loc.codigo });
  });

  const tipos = barajar(Object.entries(tiposRest).flatMap(([t, n]) => Array(n).fill(t)));
  const estados = barajar(Object.entries(estadosRest).flatMap(([e, n]) => Array(n).fill(e)));

  for (const loc of LOCALIDADES) {
    const faltan = loc.n - (usadosLoc[loc.nombre] || 0);
    for (let k = 0; k < faltan; k++) {
      const tipo = tipos.pop();
      const estado = estados.pop();
      let nombre, corto;
      for (let intento = 0; intento < 8; intento++) {
        const via = elegir(loc.vias);
        const barrio = elegir(loc.barrios);
        const plantilla = elegir(PLANTILLAS[tipo]);
        nombre = plantilla(via, barrio);
        corto = nombre.includes(via) ? capitalizar(via) : barrio;
        if (!nombres.has(nombre)) break;
      }
      nombres.add(nombre);

      let contrato;
      do {
        contrato = `VIAL-${String(Math.floor(entre(1, 160))).padStart(3, "0")}-2026`;
      } while (contratosUsados.has(contrato));
      contratosUsados.add(contrato);

      const [avance, programado] = avancesSegunEstado(estado, loc.media);
      const r = loc.dispersion;
      obras.push({
        id: obras.length + 1,
        nombre,
        corto,
        localidad: loc.nombre,
        localidadCodigo: loc.codigo,
        tramo: tramoAleatorio(),
        contrato,
        tipo,
        estado,
        avance,
        programado,
        lat: loc.lat + (rand() + rand() - 1) * r,
        lon: loc.lon + (rand() + rand() - 1) * r * 1.1,
      });
    }
  }

  return obras.map((o) => ({
    ...o,
    diasRezago: o.estado === "Retrasada" ? Math.round((o.programado - o.avance) * 1.1) : 0,
    secopUrl: null,
  }));
}

export const OBRAS = generar();
