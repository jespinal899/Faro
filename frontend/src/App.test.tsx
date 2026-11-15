import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

// Los gráficos usan canvas (no existe en jsdom): se reemplazan por un marcador
vi.mock("./componentes/Grafico", () => ({
  default: ({ etiqueta }: { etiqueta: string }) => <div data-testid="grafico">{etiqueta}</div>,
}));

const KPIS = {
  actual: { ventas_netas: 1000, ventas_brutas: 1150, utilidad: 400, margen_pct: 40, unidades: 10, facturas: 2, ticket_promedio: 500, clientes_activos: 1 },
  comparacion: null,
};
const RESPUESTAS: Record<string, unknown> = {
  "/api/opciones": { territorios: ["Southeast"], estados: [], categorias: ["Novelty Shop"], grupos: ["Mugs"], vendedores: [{ id: 2, nombre: "Kayla" }], fecha_desde: "2013-01-01", fecha_hasta: "2016-05-31" },
  "/api/estado": { ultima_carga_exitosa: "2026-11-15T05:00:00Z", estado_ultima_ejecucion: "exitoso", fecha_desde: "2013-01-01", fecha_hasta: "2016-05-31", ultima_fecha_real: "2016-05-31", lineas: 2, lineas_simuladas: 0 },
  "/api/kpis": KPIS,
  "/api/tendencia": [{ periodo: "2016-01-01", ventas_netas: 1000, utilidad: 400, facturas: 2, ventas_netas_anterior: null }],
  "/api/desglose": { dimension: "grupo", pertenencia: false, total_ventas_netas: 1000, filas: [{ clave: "Mugs", nombre: "Mugs", ventas_netas: 1000, utilidad: 400, margen_pct: 40, unidades: 10, facturas: 2, participacion_pct: 100 }] },
  "/api/facturas": { pagina: 1, tamano: 10, total: 0, filas: [] },
};

let sesionAbierta = false;
const llamadas: string[] = [];

function respuesta(estado: number, cuerpo?: unknown) {
  return Promise.resolve(new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), { status: estado }));
}

beforeEach(() => {
  sesionAbierta = false;
  llamadas.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((entrada: string, init?: RequestInit) => {
      const url = new URL(entrada, "http://localhost");
      llamadas.push(`${init?.method ?? "GET"} ${url.pathname}${url.search}`);
      if (url.pathname === "/api/auth/me") {
        return sesionAbierta ? respuesta(200, { usuario: "demo", nombre: "Usuario Demo", rol: "analista" }) : respuesta(401, { detail: "Inicia sesión" });
      }
      if (url.pathname === "/api/auth/login") {
        const { password } = JSON.parse(String(init?.body));
        if (password !== "correcta") return respuesta(401, { detail: "Usuario o contraseña incorrectos" });
        sesionAbierta = true;
        return respuesta(200, { usuario: "demo", nombre: "Usuario Demo", rol: "analista" });
      }
      if (!sesionAbierta) return respuesta(401, { detail: "Inicia sesión para continuar" });
      return respuesta(200, RESPUESTAS[url.pathname]);
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("aplicación", () => {
  it("sin sesión muestra el inicio de sesión", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /ingresar/i })).toBeInTheDocument();
  });

  it("con contraseña incorrecta muestra el mensaje de la API", async () => {
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Usuario"), "demo");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: /ingresar/i }));
    expect(await screen.findByText("Usuario o contraseña incorrectos")).toBeInTheDocument();
  });

  it("al ingresar carga el dashboard con el período por defecto y la frescura de los datos", async () => {
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Usuario"), "demo");
    await userEvent.type(screen.getByLabelText("Contraseña"), "correcta");
    await userEvent.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByText("Faro · Ventas")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("kpi-ventas_netas")).toHaveTextContent(/1.000/));
    expect(screen.getByText(/Datos al 31\/05\/2016/)).toBeInTheDocument();
    // El período por defecto (año de la última fecha) se envía a la API
    expect(llamadas).toContain("GET /api/kpis?desde=2016-01-01&hasta=2016-05-31");
    expect(await screen.findAllByTestId("grafico")).toHaveLength(2);
  });
});
