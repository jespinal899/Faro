import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { PALETAS } from "../tema";
import type { RespuestaPronostico, SerieGrupo } from "../tipos";
import PanelPronostico from "./PanelPronostico";
import { NOMBRES, opcionEvaluacion, opcionPronostico } from "./GraficosPronostico";

vi.mock("./Grafico", () => ({
  default: ({ etiqueta }: { etiqueta: string }) => <div data-testid="grafico">{etiqueta}</div>,
}));

const p = PALETAS.claro;
const ORIGEN = "2016-05-23";

const serie = (grupo: string, base: number): SerieGrupo => ({
  grupo,
  historia: [
    { semana: "2016-05-16", venta_neta: base, incluye_simulados: false },
    { semana: ORIGEN, venta_neta: base + base / 10, incluye_simulados: false },
  ],
  pronostico: [1, 2, 3, 4].map((h) => ({
    semana: `2016-0${h < 2 ? "5-30" : `6-${String(6 + (h - 2) * 7).padStart(2, "0")}`}`,
    horizonte: h,
    venta_neta: base,
    inferior: base - base / 5,
    superior: base + base / 5,
  })),
  seguimiento: [],
  wape_prueba: 13.4,
  wape_prueba_linea_base: 14.8,
});

const RESPUESTA: RespuestaPronostico = {
  disponible: true,
  origen: ORIGEN,
  generado_en: "2026-11-15T15:00:00Z",
  usa_datos_simulados: false,
  modelo: {
    version: "20261115.145744",
    algoritmo: "hgb[rezagos+contexto](max_depth=2)",
    entrenado_en: "2026-11-15T14:57:44Z",
    datos_desde: "2013-01-07",
    datos_hasta: ORIGEN,
    prueba_desde: "2016-02-08",
    commit_codigo: "fac7b24",
    calidad: {
      metrica: "wape",
      linea_base: "media_movil_13",
      linea_base_descripcion: "el promedio de las últimas 13 semanas (un trimestre)",
      wape_validacion_modelo: 11.48,
      wape_validacion_linea_base: 11.47,
      wape_prueba_modelo: 13.54,
      wape_prueba_linea_base: 14.56,
      mejora_prueba_pct: 7.0,
      cobertura_objetivo_pct: 80,
      cobertura_prueba_pct: 76.4,
      por_horizonte: [1, 2, 3, 4].map((h) => ({ horizonte: h, wape_modelo: 13, wape_linea_base: 14, cobertura_pct: 77 })),
    },
  },
  grupos: [serie("Mugs", 20_000), serie("Packaging Materials", 650_000)],
  excluidos: [{ grupo: "Novelty Items", motivo: "historia insuficiente: 22 semanas" }],
};

function simularApi(respuesta: RespuestaPronostico) {
  vi.stubGlobal(
    "fetch",
    vi.fn((entrada: string) => {
      const ruta = new URL(entrada, "http://localhost").pathname;
      const cuerpo = ruta === "/api/pronostico" ? respuesta : [];
      return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200 }));
    }),
  );
}

beforeEach(() => simularApi(RESPUESTA));
afterEach(() => vi.unstubAllGlobals());

describe("panel del pronóstico", () => {
  it("lo identifica como predicción, con la versión del modelo", async () => {
    render(<PanelPronostico />);
    expect(await screen.findByText("Esto es una PREDICCIÓN, no un dato histórico")).toBeInTheDocument();
    expect(screen.getByText("20261115.145744")).toBeInTheDocument();
  });

  it("dice en palabras si mejora o empata con la línea base", async () => {
    render(<PanelPronostico />);
    expect(await screen.findByTestId("wape-prueba")).toHaveTextContent("13.5 %");
    expect(screen.getByText(/7\.0 % menos error/)).toBeInTheDocument(); // prueba
    expect(screen.getByText("Empatan")).toBeInTheDocument(); // validación de un año
  });

  it("elige por defecto el grupo de mayor venta y muestra el excluido con su motivo", async () => {
    render(<PanelPronostico />);
    expect(await screen.findAllByTestId("grafico")).not.toHaveLength(0);
    expect(screen.getAllByTestId("grafico")[0]).toHaveTextContent("Packaging Materials");
    const fila = screen.getByText("Novelty Items").closest("tr")!;
    expect(within(fila).getByText(/Sin pronóstico: historia insuficiente/)).toBeInTheDocument();
  });

  it("sin modelo vigente lo dice en lugar de inventar un pronóstico", async () => {
    simularApi({ ...RESPUESTA, disponible: false, modelo: null, origen: null, grupos: [], excluidos: [] });
    render(<PanelPronostico />);
    expect(await screen.findByText(/Todavía no hay un pronóstico registrado/)).toBeInTheDocument();
  });
});

describe("gráficos del pronóstico", () => {
  type Serie = { name: string; data: (number | null)[]; stack?: string; lineStyle: { type?: string; color?: string }; markLine?: { data: unknown[] } };

  it("pronóstico discontinuo que arranca en el último dato real, con banda del rango", () => {
    const s = serie("Mugs", 100);
    const op = opcionPronostico(s, ORIGEN, p) as { series: Serie[]; legend: { data: string[] } };
    const [real, pron, inferior, banda] = op.series;
    expect(op.legend.data).toEqual([NOMBRES.real, NOMBRES.pronostico, NOMBRES.rango]);
    expect(real.lineStyle).toMatchObject({ type: "solid", color: p.serie1 });
    expect(pron.lineStyle).toMatchObject({ type: "dashed", color: p.serie1 }); // mismo grupo, mismo color
    // Semanas: 16-may, 23-may (origen), y las 4 pronosticadas
    expect(real.data).toEqual([100, 110, null, null, null, null]);
    expect(pron.data).toEqual([null, 110, 100, 100, 100, 100]);
    expect(inferior.stack).toBe("rango");
    expect(banda.stack).toBe("rango");
    expect(banda.data).toEqual([null, 0, 40, 40, 40, 40]); // superior - inferior; 0 en el origen
    expect(real.markLine?.data).toHaveLength(1);
  });

  it("evaluación: real continuo, pronóstico discontinuo y línea base gris", () => {
    const op = opcionEvaluacion(
      [{ semana: "2016-02-08", origen: "2016-02-01", real: 10, pronostico: 11, inferior: 9, superior: 13, linea_base: 12 }],
      "media_movil_13",
      p,
    ) as { series: Serie[] };
    expect(op.series.map((x) => x.lineStyle.type)).toEqual(["solid", "dashed", "dotted"]);
    expect(op.series[2].lineStyle.color).toBe(p.tenue);
    expect(op.series[2].name).toContain("media_movil_13");
  });
});
