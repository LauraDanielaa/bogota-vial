const pesos = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatoPesos(valor) {
  if (valor === null || valor === undefined || valor === "") return "sin dato";
  return pesos.format(Number(valor));
}

/** 67.19 -> "67,2 %" (con `decimales` fijos). */
export function pct(valor, decimales = 0) {
  return `${Number(valor).toLocaleString("es-CO", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  })} %`;
}

export function numero(valor, decimales = 0) {
  return Number(valor).toLocaleString("es-CO", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}
