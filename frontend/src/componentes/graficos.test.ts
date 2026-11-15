import { describe, expect, it } from "vitest";
import { PALETAS } from "../tema";
import { opcionTendencia } from "./GraficoTendencia";
import { opcionDesglose } from "./GraficoDesglose";

const p = PALETAS.claro;

describe("gráfico de tendencia", () => {
  it("compara con el año anterior con leyenda y la serie 2 discontinua", () => {
    const op = opcionTendencia(
      [
        { periodo: "2016-01-01", ventas_netas: 100, utilidad: 50, facturas: 3, ventas_netas_anterior: 90 },
        { periodo: "2016-02-01", ventas_netas: 120, utilidad: 60, facturas: 4, ventas_netas_anterior: null },
      ],
      "mes",
      p,
    ) as { series: { name: string; lineStyle: { color: string; type: string } }[]; legend?: unknown; yAxis: object };
    expect(op.series.map((s) => s.name)).toEqual(["Período actual", "Año anterior"]);
    expect(op.series[0].lineStyle).toMatchObject({ color: p.serie1, type: "solid" });
    expect(op.series[1].lineStyle).toMatchObject({ color: p.serie2, type: "dashed" });
    expect(op.legend).toBeDefined();
    expect(Array.isArray(op.yAxis)).toBe(false); // un solo eje
  });

  it("sin datos del año anterior muestra una sola serie y sin leyenda", () => {
    const op = opcionTendencia(
      [{ periodo: "2013-01-01", ventas_netas: 100, utilidad: 50, facturas: 3, ventas_netas_anterior: null }],
      "mes",
      p,
    ) as { series: unknown[]; legend?: unknown };
    expect(op.series).toHaveLength(1);
    expect(op.legend).toBeUndefined();
  });
});

describe("gráfico de desglose", () => {
  it("ordena la mayor arriba y pinta 'Otros' en gris (no es una categoría)", () => {
    const op = opcionDesglose(
      [
        { clave: "A", nombre: "A", ventas_netas: 300, utilidad: 1, margen_pct: 1, unidades: 1, facturas: 1, participacion_pct: 60 },
        { clave: "B", nombre: "B", ventas_netas: 150, utilidad: 1, margen_pct: 1, unidades: 1, facturas: 1, participacion_pct: 30 },
        { clave: null, nombre: "Otros (3)", ventas_netas: 50, utilidad: 1, margen_pct: 1, unidades: 1, facturas: null, participacion_pct: 10 },
      ],
      p,
    ) as { yAxis: { data: string[] }; series: { data: { itemStyle: { color: string } }[] }[] };
    expect(op.yAxis.data).toEqual(["Otros (3)", "B", "A"]); // ECharts dibuja de abajo hacia arriba
    expect(op.series[0].data.map((d) => d.itemStyle.color)).toEqual([p.tenue, p.serie1, p.serie1]);
  });
});
