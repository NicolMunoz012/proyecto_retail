import sitio from "@/data/sitio.json";

// Cambiar por la URL del repositorio cuando esté publicado.
export const REPO_URL = "https://github.com/NicolMunoz012/proyecto_retail";
export const PBIX_URL = `${REPO_URL}/raw/main/powerbi/proyecto_herramientas_v2.pbix`;
export const POWERBI_URL =
  "https://app.powerbi.com/view?r=eyJrIjoiNDE4YWEzOWYtNGRmZC00MTVmLTliMzQtYThlM2QyZGFiZjE0IiwidCI6IjhkMzY4MzZlLTZiNzUtNGRlNi1iYWI5LTVmNGIxNzc1NDI3ZiIsImMiOjR9";
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

export type Region = (typeof sitio.regiones)[number];
export type Mes = (typeof sitio.meses)[number];
export type Linea = (typeof sitio.lineas)[number];
export type Analisis = (typeof sitio.anova)[number];

export const datos = sitio;

// "always": es-ES no agrupa por defecto los números de 4 cifras (2823 en vez de 2.823).
const es = (opciones: Intl.NumberFormatOptions) =>
  new Intl.NumberFormat("es-ES", { useGrouping: "always", ...opciones });

export const fmtEntero = (n: number) => es({ maximumFractionDigits: 0 }).format(n);
export const fmtMillones = (n: number, decimales = 1) =>
  es({ minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(n / 1e6);
export const fmtPct = (x: number, decimales = 0) =>
  es({ minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(x * 100);
export const fmtDecimal = (n: number, decimales: number) =>
  es({ minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(n);

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

export const LINEAS: Record<string, string> = {
  "Classic Cars": "autos clásicos",
  "Vintage Cars": "autos antiguos",
  Motorcycles: "motos",
  "Trucks and Buses": "camiones y buses",
  Planes: "aviones",
  Ships: "barcos",
  Trains: "trenes",
};

export const anioDe = (m: Mes) => Number(m.mes.slice(0, 4));
export const mesDe = (m: Mes) => Number(m.mes.slice(5, 7));
export const sumaVentas = (meses: Mes[]) => meses.reduce((s, m) => s + m.ventas, 0);

const mediana = (valores: number[]) => {
  const v = [...valores].sort((a, b) => a - b);
  const mitad = Math.floor(v.length / 2);
  return v.length % 2 ? v[mitad] : (v[mitad - 1] + v[mitad]) / 2;
};

/** Cifras derivadas que usa el texto de la página. */
export function hallazgos() {
  const { regiones, meses, lineas, totales, anova } = sitio;

  const porPedidos = [...regiones].sort((a, b) => b.pedidos - a.pedidos);
  const mayor = porPedidos[0];
  const menor = porPedidos[porPedidos.length - 1];

  const aniosCompletos = [...new Set(meses.map(anioDe))].filter(
    (a) => meses.filter((m) => anioDe(m) === a).length === 12,
  );
  const deCompletos = meses.filter((m) => aniosCompletos.includes(anioDe(m)));
  const noviembres = deCompletos.filter((m) => mesDe(m) === 11);
  const noviembreMax = [...noviembres].sort((a, b) => b.pedidos - a.pedidos)[0];
  const ultimoAnio = anioDe(meses[meses.length - 1]);
  const ultimoMes = mesDe(meses[meses.length - 1]);
  const tramo = (anio: number) => sumaVentas(meses.filter((m) => anioDe(m) === anio && mesDe(m) <= ultimoMes));

  const porMargen = [...lineas].sort((a, b) => b.margen - a.margen);
  const anovaPais = anova.find((a) => a.analisis === "País");

  return {
    mayor,
    menor,
    veces: mayor.ventas / menor.ventas,
    vecesPedidos: mayor.pedidos / menor.pedidos,
    aniosCompletos,
    partNoviembre: sumaVentas(noviembres) / sumaVentas(deCompletos),
    noviembreMax,
    medianaPedidos: mediana(meses.filter((m) => mesDe(m) !== 11).map((m) => m.pedidos)),
    ultimoAnio,
    ultimoMes,
    crecimiento: tramo(ultimoAnio) / tramo(ultimoAnio - 1) - 1,
    lineaPrincipal: lineas[0],
    partLinea: lineas[0].ventas / totales.ventas,
    margenMax: porMargen.slice(0, 2),
    paisesFuera: totales.paises - (anovaPais?.grupos ?? totales.paises),
  };
}
