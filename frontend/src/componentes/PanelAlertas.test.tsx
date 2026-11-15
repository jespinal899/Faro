import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Alerta, DetalleAlerta } from "../tipos";
import PanelAlertas from "./PanelAlertas";

const CAIDA: Alerta = {
  alerta_id: 1,
  creada_en: "2026-11-15T20:45:00Z",
  regla: "caida_ventas",
  regla_nombre: "Caída de ventas",
  severidad: "critica",
  origen: "regla",
  indicador: "Ventas netas semanales",
  entidad: "Total WWI",
  valor_observado: 421418,
  umbral: 910925,
  referencia: 1071676,
  unidad: "%",
  periodo_desde: "2016-06-06",
  periodo_hasta: "2016-06-11",
  detalle: { caida_pct: 60.68, umbral_pct: 15, semanas_referencia: ["2016-05-09", "2016-05-16"] },
  mensaje: "Las ventas netas de la semana del 06/06/2016 cayeron 60.7 %.",
  explicacion_ia: "La caída coincide con días simulados de bajo volumen.",
  accion_recomendada_ia: "Revisar los pedidos de la semana.",
  ia_modelo: "openai/gpt-oss-120b",
  incluye_simulados: true,
  estado: "nueva",
  estado_actualizado_en: null,
  estado_actualizado_por: null,
  nota: null,
  correo_enviado: true,
  intentos_correo: 1,
  ultimo_intento: "2026-11-15T20:45:05Z",
};

const COSTO: Alerta = {
  ...CAIDA,
  alerta_id: 2,
  creada_en: "2026-11-15T18:00:00Z",
  regla: "ventas_bajo_costo",
  regla_nombre: "Ventas bajo costo",
  severidad: "advertencia",
  indicador: "Pérdida por ventas bajo costo",
  valor_observado: 2046,
  umbral: 0,
  referencia: null,
  detalle: { lineas: 30 },
  mensaje: "30 líneas bajo costo.",
  explicacion_ia: null,
  accion_recomendada_ia: null,
  incluye_simulados: false,
  estado: "atendida",
  estado_actualizado_en: "2026-11-15T19:00:00Z",
  estado_actualizado_por: "analista",
  nota: "Revisado",
  correo_enviado: false,
  intentos_correo: 3,
};

const DETALLE: DetalleAlerta = {
  ...CAIDA,
  envios: [
    { canal: "correo", intento: 1, intentado_en: "2026-11-15T20:45:01Z", resultado: "fallido", error: "timeout" },
    { canal: "correo", intento: 2, intentado_en: "2026-11-15T20:45:05Z", resultado: "enviado", error: null },
  ],
};

let parches: { ruta: string; cuerpo: unknown }[] = [];

function simularApi(lista: Alerta[] | { estado: number }) {
  parches = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((entrada: string, init?: RequestInit) => {
      const ruta = new URL(entrada, "http://localhost").pathname;
      const json = (cuerpo: unknown, estado = 200) => Promise.resolve(new Response(JSON.stringify(cuerpo), { status: estado }));
      if (init?.method === "PATCH") {
        parches.push({ ruta, cuerpo: JSON.parse(String(init.body)) });
        return json({ ...DETALLE, estado: "atendida" });
      }
      if (ruta === "/api/alertas") return Array.isArray(lista) ? json(lista) : json({ detail: "Base caída" }, lista.estado);
      if (ruta === "/api/alertas/1") return json(DETALLE);
      return json({ detail: "no" }, 404);
    }),
  );
}

beforeEach(() => simularApi([CAIDA, COSTO]));
afterEach(() => vi.unstubAllGlobals());

describe("PanelAlertas", () => {
  it("muestra por defecto las nuevas, con severidad, correo y datos simulados en palabras", async () => {
    render(<PanelAlertas />);
    const tabla = await screen.findByRole("table");
    expect(within(tabla).getByText("Caída de ventas")).toBeInTheDocument();
    expect(within(tabla).queryByText("Ventas bajo costo")).not.toBeInTheDocument();
    expect(within(tabla).getByText("Crítica")).toBeInTheDocument();
    expect(within(tabla).getByText("Enviado")).toBeInTheDocument();
    expect(within(tabla).getByText("Simulado")).toBeInTheDocument();
    expect(within(tabla).getByText("Nueva")).toBeInTheDocument();
  });

  it("filtra por estado y dice cuántas hay en cada uno", async () => {
    const user = userEvent.setup();
    render(<PanelAlertas />);
    await screen.findByRole("table");
    await user.click(screen.getByText("Todas (2)"));
    const tabla = screen.getByRole("table");
    expect(within(tabla).getByText("Ventas bajo costo")).toBeInTheDocument();
    expect(within(tabla).getByText("Falló (3 intento/s)")).toBeInTheDocument();
    await user.click(screen.getByText("Cerradas (0)"));
    expect(screen.getByText("No hay alertas en este estado.")).toBeInTheDocument();
  });

  it("el detalle separa lo calculado de lo GENERADO POR IA y muestra cada intento de correo", async () => {
    const user = userEvent.setup();
    render(<PanelAlertas />);
    await user.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByRole("dialog");
    expect(await within(panel).findByText("GENERADO POR IA")).toBeInTheDocument();
    expect(within(panel).getByText(DETALLE.mensaje)).toBeInTheDocument();
    expect(within(panel).getByText(DETALLE.explicacion_ia!)).toBeInTheDocument();
    expect(within(panel).getByText("Revisar los pedidos de la semana.")).toBeInTheDocument();
    expect(within(panel).getByText("Incluye ventas SIMULADAS")).toBeInTheDocument();
    // Campos de la regla en palabras
    expect(within(panel).getByText("Caída")).toBeInTheDocument();
    expect(within(panel).getByText("60.7 %")).toBeInTheDocument();
    expect(within(panel).getByText("Semanas de referencia")).toBeInTheDocument();
    // Entrega: un intento fallido y uno enviado
    const entrega = within(panel).getByText("Entrega por correo").closest(".ant-card") as HTMLElement;
    expect(within(entrega).getByText("Falló")).toBeInTheDocument();
    expect(within(entrega).getByText("Enviado")).toBeInTheDocument();
  });

  it("cambia el estado con una nota y avisa para actualizar el contador", async () => {
    const user = userEvent.setup();
    const onCambio = vi.fn();
    render(<PanelAlertas onCambio={onCambio} />);
    await user.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByRole("dialog");
    await within(panel).findByText("GENERADO POR IA");

    await user.click(within(panel).getByRole("combobox", { name: "Nuevo estado" }));
    await user.click(await screen.findByTitle("Atendida"));
    await user.type(within(panel).getByRole("textbox", { name: "Nota" }), "Se avisó al equipo");
    await user.click(within(panel).getByRole("button", { name: "Guardar estado" }));

    await waitFor(() => expect(parches).toHaveLength(1));
    expect(parches[0]).toEqual({ ruta: "/api/alertas/1", cuerpo: { estado: "atendida", nota: "Se avisó al equipo" } });
    expect(await within(panel).findByText("Estado guardado: Atendida.")).toBeInTheDocument();
    expect(onCambio).toHaveBeenCalled();
  });

  it("sin alertas nuevas lo dice", async () => {
    simularApi([COSTO]);
    render(<PanelAlertas />);
    expect(await screen.findByText("No hay alertas nuevas.")).toBeInTheDocument();
  });

  it("si la API falla, muestra el error con opción de reintentar", async () => {
    simularApi({ estado: 503 });
    render(<PanelAlertas />);
    expect(await screen.findByText("Base caída")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
