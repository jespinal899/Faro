import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import dayjs from "dayjs";
import type { EjecucionEtl, RespuestaMonitoreo } from "../tipos";
import PanelOperacion from "./PanelOperacion";

const ejecucion = (id: number, cambios: Partial<EjecucionEtl> = {}): EjecucionEtl => ({
  ejecucion_id: id,
  proceso: "ventas",
  disparador: "cron",
  modo: "incremental",
  inicio: dayjs().subtract(20, "minute").toISOString(),
  fin: dayjs().subtract(19, "minute").toISOString(),
  segundos: 24.3,
  estado: "exitoso",
  leidas: 1513,
  nuevas: 120,
  actualizadas: 3,
  rechazadas: 2,
  sin_cambios: 1388,
  reconciliado: true,
  error: null,
  ...cambios,
});

const BASE: RespuestaMonitoreo = {
  etl: [ejecucion(7), ejecucion(6, { estado: "fallido", error: "OperationalError: conexión rechazada", reconciliado: null })],
  calidad_ejecucion_id: 7,
  calidad: [
    { tabla: "sales.invoices", regla: "C01", dimension: "Completitud", descripcion: "Cliente obligatorio", accion: "cuarentena", evaluadas: 1000, fallaron: 2 },
    { tabla: "sales.invoice_lines", regla: "V01", dimension: "Validez", descripcion: "Cantidad > 0", accion: "cuarentena", evaluadas: 0, fallaron: 0 },
  ],
  dimensiones: [
    { dimension: "Completitud", reglas: 1, evaluadas: 1000, fallaron: 2, cumplimiento_pct: 99.8 },
    { dimension: "Validez", reglas: 1, evaluadas: 0, fallaron: 0, cumplimiento_pct: null },
  ],
  cuarentena: [{ tabla: "sales.invoices", regla: "C01", pendientes: 2, resueltos: 5, ultimo_rechazo: "2026-11-15T20:00:00Z" }],
  modelo: {
    version: "20261115.145744",
    algoritmo: "hgb",
    entrenado_en: "2026-11-15T14:57:44Z",
    datos_hasta: "2016-05-23",
    commit_codigo: "fac7b24",
    wape_prueba: 13.54,
    wape_prueba_linea_base: 14.56,
    pronostico_origen: "2016-05-23",
    pronostico_generado_en: "2026-11-15T15:00:00Z",
  },
  notificaciones: {
    evaluaciones: [
      { evaluacion_id: 1, disparador: "demo", inicio: "2026-11-15T20:45:00Z", fin: "2026-11-15T20:45:09Z", estado: "exitosa", reglas_evaluadas: 3, alertas_nuevas: 2, correos_enviados: 2, error: null },
    ],
    alertas_por_estado: { nueva: 2, atendida: 1 },
    correos_enviados: 2,
    intentos_fallidos: 1,
    alertas_sin_entregar: 1,
  },
};

function simularApi(cuerpo: RespuestaMonitoreo) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200 }))),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("PanelOperacion", () => {
  it("resume el ETL, la calidad, la cuarentena, el modelo y las notificaciones", async () => {
    simularApi(BASE);
    render(<PanelOperacion />);
    expect(await screen.findByText("El ETL está al día")).toBeInTheDocument();

    const etl = screen.getByText(/Ejecuciones del ETL/).closest(".ant-card") as HTMLElement;
    expect(within(etl).getByText("1 fallida(s)")).toBeInTheDocument();
    expect(within(etl).getAllByText("Exitosa")).toHaveLength(1);
    expect(within(etl).getByText("Fallida")).toBeInTheDocument();

    const calidad = screen.getByText("Calidad de datos por dimensión").closest(".ant-card") as HTMLElement;
    expect(within(calidad).getByText("Completitud")).toBeInTheDocument();
    expect(within(calidad).getByText("Sin filas en esta carga")).toBeInTheDocument();
    expect(within(calidad).getByText(/sales\.invoices · C01: 2/)).toBeInTheDocument();

    expect(screen.getByText("20261115.145744")).toBeInTheDocument();
    expect(screen.getByText(/13\.5 %/)).toBeInTheDocument();
    expect(screen.getByText("Nueva: 2")).toBeInTheDocument();
    expect(screen.getByText("Resuelta: 0")).toBeInTheDocument();
    expect(screen.getByText(/1 alerta\(s\) sin correo entregado/)).toBeInTheDocument();
  });

  it("si la última ejecución falló lo dice con su error", async () => {
    simularApi({ ...BASE, etl: [ejecucion(8, { estado: "fallido", error: "OperationalError: conexión rechazada" }), ...BASE.etl] });
    render(<PanelOperacion />);
    expect(await screen.findByText("La última ejecución del ETL (#8) falló")).toBeInTheDocument();
    expect(screen.getByText(/Error: OperationalError: conexión rechazada/)).toBeInTheDocument();
  });

  it("avisa cuando hace horas que no hay cargas (los cron de GitHub se retrasan)", async () => {
    const vieja = ejecucion(9, { inicio: dayjs().subtract(6, "hour").toISOString(), fin: dayjs().subtract(5, "hour").toISOString() });
    simularApi({ ...BASE, etl: [vieja] });
    render(<PanelOperacion />);
    expect(await screen.findByText("Sin cargas en las últimas 5 horas")).toBeInTheDocument();
    expect(screen.getByText(/GitHub puede retrasar/)).toBeInTheDocument();
  });

  it("sin modelo vigente lo dice", async () => {
    simularApi({ ...BASE, modelo: null });
    render(<PanelOperacion />);
    expect(await screen.findByText("Todavía no hay un modelo vigente.")).toBeInTheDocument();
  });
});
