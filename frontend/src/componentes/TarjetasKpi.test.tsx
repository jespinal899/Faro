import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import TarjetasKpi from "./TarjetasKpi";
import type { RespuestaKpis } from "../tipos";

const datos: RespuestaKpis = {
  actual: {
    ventas_netas: 53991490.45,
    ventas_brutas: 62090220.81,
    utilidad: 26957600.65,
    margen_pct: 49.93,
    unidades: 2_400_000,
    facturas: 22250,
    ticket_promedio: 2426.58,
    clientes_activos: 663,
  },
  comparacion: {
    tipo: "anio_anterior",
    desde: "2014-01-01",
    hasta: "2014-12-31",
    valores: {} as RespuestaKpis["actual"],
    variacion_pct: { ventas_netas: 8.14, margen_pct: 0.2, facturas: -2.5, clientes_activos: 0 },
  },
};

describe("tarjetas de KPI", () => {
  it("muestra los 6 KPI principales con su valor", () => {
    render(<TarjetasKpi datos={datos} cargando={false} reintentar={() => {}} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByTestId("kpi-ventas_netas")).toHaveTextContent(/53.991.490/);
    expect(screen.getByTestId("kpi-margen_pct")).toHaveTextContent("49.9 %");
  });

  it("indica la variación con flecha y texto, no solo con color", () => {
    render(<TarjetasKpi datos={datos} cargando={false} reintentar={() => {}} />);
    expect(screen.getByLabelText("Sube +8.1 % frente al año anterior")).toBeInTheDocument();
    expect(screen.getByLabelText("Baja −2.5 % frente al año anterior")).toBeInTheDocument();
    expect(screen.getByLabelText("Sube +0.2 pp frente al año anterior")).toBeInTheDocument();
    expect(screen.getByLabelText("Sin cambio 0.0 % frente al año anterior")).toBeInTheDocument();
  });

  it("sin comparación lo dice en lugar de inventar una variación", () => {
    render(<TarjetasKpi datos={{ ...datos, comparacion: null }} cargando={false} reintentar={() => {}} />);
    expect(screen.getAllByText("Sin comparación")).toHaveLength(6);
  });

  it("muestra el error con opción de reintentar", () => {
    render(<TarjetasKpi cargando={false} error="La base de datos está despertando." reintentar={() => {}} />);
    expect(screen.getByText("La base de datos está despertando.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
