import { describe, expect, it } from "vitest";
import { aParametros, FILTROS_INICIALES, periodoPorDefecto, preajustes } from "./filtros";
import { construirUrl } from "./api";

describe("filtros", () => {
  it("solo envía a la API los filtros que tienen valor", () => {
    const url = construirUrl("/api/kpis", aParametros({ ...FILTROS_INICIALES, territorio: "Southeast" }));
    expect(url).toBe("/api/kpis?territorio=Southeast");
  });

  it("envía incluir_simulados solo cuando se excluyen", () => {
    expect(construirUrl("/api/kpis", aParametros({ ...FILTROS_INICIALES, incluir_simulados: false }))).toBe(
      "/api/kpis?incluir_simulados=false",
    );
  });

  it("codifica los valores (sin armar consultas a mano)", () => {
    const url = construirUrl("/api/kpis", aParametros({ ...FILTROS_INICIALES, territorio: "x' OR '1'='1" }));
    expect(url).toBe("/api/kpis?territorio=x%27+OR+%271%27%3D%271");
  });

  it("el período por defecto va del 1 de enero a la última fecha con datos (H01)", () => {
    expect(periodoPorDefecto("2016-05-31")).toEqual({ desde: "2016-01-01", hasta: "2016-05-31" });
  });

  it("los rangos rápidos son relativos a la última fecha con datos", () => {
    const r = preajustes("2013-01-01", "2016-05-31");
    expect(r.map((p) => p.etiqueta)).toEqual([
      "Año en curso",
      "Últimos 90 días",
      "Últimos 12 meses",
      "Año 2015 completo",
      "Todo el histórico",
    ]);
    expect(r[3]).toMatchObject({ desde: "2015-01-01", hasta: "2015-12-31" });
    expect(r[4].desde).toBe("2013-01-01");
  });
});
