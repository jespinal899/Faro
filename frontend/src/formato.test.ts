import { describe, expect, it } from "vitest";
import { fEntero, fFecha, fMoneda, fPorcentaje, fVariacion } from "./formato";

describe("formatos", () => {
  it("muestra moneda en dólares sin decimales y un guion si no hay dato", () => {
    expect(fMoneda(53991490.45)).toMatch(/53.991.490/);
    expect(fMoneda(53991490.45)).toMatch(/US\$|USD/);
    expect(fMoneda(null)).toBe("—");
  });

  it("no confunde 'sin dato' con cero", () => {
    expect(fEntero(0)).toBe("0");
    expect(fEntero(undefined)).toBe("—");
    expect(fPorcentaje(null)).toBe("—");
  });

  it("muestra la variación con signo explícito y su unidad", () => {
    expect(fVariacion(8.14)).toBe("+8.1 %");
    expect(fVariacion(-3.26)).toBe("−3.3 %");
    expect(fVariacion(0.25, "pp")).toBe("+0.3 pp");
    expect(fVariacion(null)).toBe("—");
  });

  it("muestra fechas como DD/MM/AAAA", () => {
    expect(fFecha("2016-05-31")).toBe("31/05/2016");
  });
});
