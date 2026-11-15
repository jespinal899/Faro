import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { InfoAsistente, RespuestaAsistente } from "../tipos";
import PanelAsistente from "./PanelAsistente";

const INFO: InfoAsistente = {
  disponible: true,
  proveedor: "groq",
  modelo: "openai/gpt-oss-120b",
  limite_hora: 20,
  limite_dia: 100,
  usadas_hoy: 2,
  ejemplos: ["¿Cuáles fueron las ventas del último trimestre completo?"],
};

const RESPUESTA: RespuestaAsistente = {
  tipo: "respuesta",
  resumen: "En el primer trimestre de 2016 las ventas netas fueron USD 13,251,054.",
  hechos: [
    { texto: "Ventas netas T1 2016: USD 13,251,054", consultas: [1], respaldada: true },
    { texto: "Una cifra inventada", consultas: [], respaldada: false },
  ],
  predicciones: [{ texto: "Mugs: USD 19,733 la próxima semana", consultas: [2], respaldada: true }],
  interpretaciones: ["Podría deberse a la estacionalidad."],
  sugerencias: ["Comparar por territorio."],
  consultas: [
    {
      numero: 1,
      herramienta: "consultar_indicadores",
      descripcion: "Indicadores del 2016-01-01 al 2016-03-31, frente al mismo período del año anterior",
      parametros: { desde: "2016-01-01", hasta: "2016-03-31" },
      resultado: { indicadores: { ventas_netas: 13251054.0 } },
      error: null,
    },
  ],
  datos_al: "2016-06-02",
  ultima_carga: null,
  incluye_simulados: false,
  generado_por: "claude-haiku-5-5",
  tokens_entrada: 4000,
  tokens_salida: 300,
  costo_usd: 0.00055,
  duracion_ms: 2300,
  advertencias: ["1 afirmación(es) sin una consulta válida que la respalde."],
};

let enviados: unknown[] = [];

function simularApi(info: InfoAsistente, respuesta: { estado: number; cuerpo: unknown }) {
  enviados = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((entrada: string, init?: RequestInit) => {
      const ruta = new URL(entrada, "http://localhost").pathname;
      if (ruta === "/api/asistente/info") return Promise.resolve(new Response(JSON.stringify(info), { status: 200 }));
      enviados.push(JSON.parse(String(init?.body)));
      return Promise.resolve(new Response(JSON.stringify(respuesta.cuerpo), { status: respuesta.estado }));
    }),
  );
}

beforeEach(() => simularApi(INFO, { estado: 200, cuerpo: RESPUESTA }));
afterEach(() => vi.unstubAllGlobals());

describe("asistente de IA", () => {
  it("avisa que las respuestas las genera la IA y muestra el uso del día", async () => {
    render(<PanelAsistente />);
    expect(await screen.findByText(/respuestas generadas a partir de consultas al Data Warehouse/)).toBeInTheDocument();
    expect(screen.getByText(/Preguntas hoy: 2/)).toBeInTheDocument();
  });

  it("separa hechos con su consulta, predicciones, interpretaciones y marca lo que no tiene respaldo", async () => {
    render(<PanelAsistente />);
    await userEvent.click(await screen.findByText(INFO.ejemplos[0])); // un ejemplo pregunta directamente
    const tarjeta = await screen.findByTestId("respuesta-ia");

    expect(within(tarjeta).getByText(RESPUESTA.resumen)).toBeInTheDocument();
    expect(within(tarjeta).getByText("consulta 1")).toBeInTheDocument();
    expect(within(tarjeta).getByText("Sin respaldo")).toBeInTheDocument();
    expect(within(tarjeta).getByText("PREDICCIÓN")).toBeInTheDocument();
    expect(within(tarjeta).getByText("generada por IA")).toBeInTheDocument();
    expect(within(tarjeta).getByText(/sin una consulta válida/)).toBeInTheDocument();
    expect(within(tarjeta).getByText("Datos consultados (1)")).toBeInTheDocument();
    expect(within(tarjeta).getByText(/costo aprox\. USD 0\.0006/)).toBeInTheDocument();
    expect(enviados[0]).toEqual({ pregunta: INFO.ejemplos[0], historial: [] });
  });

  it("la pregunta siguiente lleva el turno anterior como contexto", async () => {
    render(<PanelAsistente />);
    await userEvent.click(await screen.findByText(INFO.ejemplos[0]));
    await screen.findByTestId("respuesta-ia");
    await userEvent.type(screen.getByLabelText("Pregunta para el asistente"), "¿Y por territorio?{Enter}");
    await screen.findAllByTestId("respuesta-ia");
    expect(enviados[1]).toEqual({
      pregunta: "¿Y por territorio?",
      historial: [
        { rol: "usuario", texto: INFO.ejemplos[0] },
        { rol: "asistente", texto: RESPUESTA.resumen },
      ],
    });
  });

  it("muestra el mensaje de la API cuando se llega al límite", async () => {
    simularApi(INFO, { estado: 429, cuerpo: { detail: "Llegaste al límite de preguntas (20 por hora, 100 por día)." } });
    render(<PanelAsistente />);
    await userEvent.type(await screen.findByLabelText("Pregunta para el asistente"), "¿Cuánto vendimos?{Enter}");
    expect(await screen.findByText(/Llegaste al límite de preguntas/)).toBeInTheDocument();
  });

  it("sin costo muestra el plan gratuito en lugar de USD 0", async () => {
    simularApi(INFO, { estado: 200, cuerpo: { ...RESPUESTA, costo_usd: 0, generado_por: "openai/gpt-oss-120b" } });
    render(<PanelAsistente />);
    await userEvent.click(await screen.findByText(INFO.ejemplos[0]));
    expect(await screen.findByText(/sin costo \(plan gratuito\)/)).toBeInTheDocument();
    expect(screen.getByText(/\(Groq\) usando solo consultas controladas/)).toBeInTheDocument();
  });

  it("sin clave configurada lo dice en lugar de mostrar el chat", async () => {
    simularApi({ ...INFO, disponible: false }, { estado: 503, cuerpo: {} });
    render(<PanelAsistente />);
    expect(await screen.findByText(/no está configurado/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Pregunta para el asistente")).not.toBeInTheDocument();
  });
});
