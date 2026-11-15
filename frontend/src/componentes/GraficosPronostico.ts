// Opciones de ECharts del pronóstico. Convención de toda la pestaña:
//   línea continua = ventas REALES · línea discontinua = PRONÓSTICO (mismo color: es el mismo
//   grupo) · banda = rango probable del 80 % · gris punteado = línea base de referencia.
// Un solo eje; la leyenda nombra cada trazo para no depender solo del color.
import { fMoneda, fMonedaCompacta, fSemana } from "../formato";
import { FUENTE, type Paleta } from "../tema";
import type { PuntoPrueba, SerieGrupo } from "../tipos";
import type { OpcionGrafico } from "./Grafico";

export const NOMBRES = {
  real: "Ventas reales",
  pronostico: "Pronóstico",
  rango: "Rango probable 80 %",
  base: "Línea base",
} as const;

/** "#2a78d6" + 0.2 -> "rgba(42, 120, 214, 0.2)" */
export function conAlfa(hex: string, alfa: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
}

type Valor = number | null;

/** Últimas semanas reales + las 4 pronosticadas, con el rango como banda. */
export function opcionPronostico(serie: SerieGrupo, origen: string, p: Paleta): OpcionGrafico {
  const semanas = [...new Set([...serie.historia.map((h) => h.semana), ...serie.pronostico.map((x) => x.semana)])].sort();
  const etiquetas = semanas.map(fSemana);
  const real = new Map(serie.historia.map((h) => [h.semana, h]));
  const pron = new Map(serie.pronostico.map((x) => [x.semana, x]));

  // El pronóstico arranca en el último dato real (origen) para que la línea sea continua
  const valorOrigen = real.get(origen)?.venta_neta ?? null;
  const lineaPron: Valor[] = semanas.map((s) => (s === origen ? valorOrigen : (pron.get(s)?.venta_neta ?? null)));
  const inferior: Valor[] = semanas.map((s) => (s === origen ? valorOrigen : (pron.get(s)?.inferior ?? null)));
  const banda: Valor[] = semanas.map((s) => {
    if (s === origen) return valorOrigen === null ? null : 0;
    const x = pron.get(s);
    return x ? x.superior - x.inferior : null;
  });

  return {
    aria: { enabled: true },
    textStyle: { fontFamily: FUENTE, color: p.tintaSecundaria },
    grid: { left: 8, right: 24, top: 36, bottom: 8, containLabel: true },
    legend: {
      top: 0,
      left: 0,
      data: [NOMBRES.real, NOMBRES.pronostico, NOMBRES.rango],
      textStyle: { color: p.tintaSecundaria },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: p.eje } },
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0].dataIndex;
        const s = semanas[i];
        const r = real.get(s);
        const x = s === origen ? undefined : pron.get(s);
        const lineas = [`<div style="color:${p.tinta};margin-bottom:4px">Semana del ${etiquetas[i]}</div>`];
        if (r) lineas.push(`${NOMBRES.real}: <b>${fMoneda(r.venta_neta)}</b>${r.incluye_simulados ? " (incluye simuladas)" : ""}`);
        if (x) {
          lineas.push(`${NOMBRES.pronostico}: <b>${fMoneda(x.venta_neta)}</b> (${x.horizonte} sem. adelante)`);
          lineas.push(`<span style="color:${p.tenue}">${NOMBRES.rango}: ${fMoneda(x.inferior)} – ${fMoneda(x.superior)}</span>`);
        }
        return lineas.join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: etiquetas,
      boundaryGap: false,
      axisLine: { lineStyle: { color: p.eje } },
      axisTick: { show: false },
      axisLabel: { color: p.tenue, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: p.tenue, formatter: (v: number) => fMonedaCompacta(v) },
      splitLine: { lineStyle: { color: p.grilla } },
    },
    series: [
      {
        name: NOMBRES.real,
        type: "line",
        symbol: "circle", // punto lleno = real; hueco = pronóstico (no depende solo del color)
        data: semanas.map((s) => real.get(s)?.venta_neta ?? null),
        showSymbol: semanas.length <= 40,
        symbolSize: 6,
        lineStyle: { width: 2, color: p.serie1, type: "solid" },
        itemStyle: { color: p.serie1 },
        markLine: {
          symbol: "none",
          silent: true,
          lineStyle: { color: p.eje, type: "dotted", width: 1 },
          label: { formatter: "Último dato real", color: p.tenue, position: "end" },
          data: valorOrigen === null ? [] : [{ xAxis: fSemana(origen) }],
        },
      },
      {
        name: NOMBRES.pronostico,
        type: "line",
        data: lineaPron,
        symbol: "emptyCircle",
        symbolSize: 8,
        lineStyle: { width: 2, color: p.serie1, type: "dashed" },
        itemStyle: { color: p.serie1 },
      },
      // Banda del rango: base invisible + diferencia apilada y sombreada
      {
        name: "_inferior",
        type: "line",
        stack: "rango",
        data: inferior,
        symbol: "none",
        silent: true,
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
      },
      {
        name: NOMBRES.rango,
        type: "line",
        stack: "rango",
        data: banda,
        symbol: "none",
        silent: true,
        lineStyle: { opacity: 0 },
        itemStyle: { color: conAlfa(p.serie1, 0.35) },
        areaStyle: { color: conAlfa(p.serie1, 0.16) },
      },
    ],
  };
}

/** Semanas de prueba: lo que se vendió, lo que pronosticó el modelo y la línea base. */
export function opcionEvaluacion(puntos: PuntoPrueba[], nombreBase: string, p: Paleta): OpcionGrafico {
  const etiquetas = puntos.map((x) => fSemana(x.semana));
  const base = `${NOMBRES.base} (${nombreBase})`;
  return {
    aria: { enabled: true },
    textStyle: { fontFamily: FUENTE, color: p.tintaSecundaria },
    grid: { left: 8, right: 24, top: 36, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: p.tintaSecundaria } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: p.eje } },
      valueFormatter: (v: unknown) => fMoneda(v as number),
    },
    xAxis: {
      type: "category",
      data: etiquetas,
      boundaryGap: false,
      axisLine: { lineStyle: { color: p.eje } },
      axisTick: { show: false },
      axisLabel: { color: p.tenue, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: p.tenue, formatter: (v: number) => fMonedaCompacta(v) },
      splitLine: { lineStyle: { color: p.grilla } },
    },
    series: [
      {
        name: NOMBRES.real,
        type: "line",
        symbol: "circle", // punto lleno = real; hueco = pronóstico (no depende solo del color)
        data: puntos.map((x) => x.real),
        symbolSize: 6,
        lineStyle: { width: 2, color: p.serie1, type: "solid" },
        itemStyle: { color: p.serie1 },
      },
      {
        name: NOMBRES.pronostico,
        type: "line",
        data: puntos.map((x) => x.pronostico),
        symbol: "emptyCircle",
        symbolSize: 8,
        lineStyle: { width: 2, color: p.serie1, type: "dashed" },
        itemStyle: { color: p.serie1 },
      },
      {
        name: base,
        type: "line",
        data: puntos.map((x) => x.linea_base),
        symbol: "none",
        lineStyle: { width: 2, color: p.tenue, type: "dotted" },
        itemStyle: { color: p.tenue },
      },
    ],
  };
}
