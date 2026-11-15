// Cliente de la API. El navegador solo habla con /api (nunca con la base de datos).
// La sesión viaja en una cookie httpOnly: este código no la ve ni la guarda.

export type Parametros = Record<string, string | number | boolean | null | undefined>;

export class ErrorApi extends Error {
  readonly estado: number;
  constructor(estado: number, mensaje: string) {
    super(mensaje);
    this.estado = estado;
  }
}

/** Se emite cuando la API responde 401 en una ruta de datos: la sesión expiró. */
export const EVENTO_SESION_EXPIRADA = "faro:sesion-expirada";

const MENSAJES: Record<number, string> = {
  401: "Inicia sesión para continuar.",
  404: "No se encontró lo que buscas.",
  422: "Algún filtro no es válido. Revisa los valores elegidos.",
  423: "Cuenta bloqueada temporalmente.",
  503: "La base de datos está despertando. Reintenta en unos segundos.",
  504: "La consulta tardó demasiado. Reduce el rango de fechas.",
};

export function construirUrl(ruta: string, params?: Parametros): string {
  const consulta = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== "") consulta.append(clave, String(valor));
  }
  const texto = consulta.toString();
  return texto ? `${ruta}?${texto}` : ruta;
}

export async function pedir<T>(
  ruta: string,
  opciones: { params?: Parametros; metodo?: "GET" | "POST"; cuerpo?: unknown; senal?: AbortSignal } = {},
): Promise<T> {
  const { params, metodo = "GET", cuerpo, senal } = opciones;
  let respuesta: Response;
  try {
    respuesta = await fetch(construirUrl(ruta, params), {
      method: metodo,
      headers: cuerpo === undefined ? undefined : { "Content-Type": "application/json" },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      credentials: "same-origin",
      signal: senal,
    });
  } catch (error) {
    if (senal?.aborted) throw error;
    throw new ErrorApi(0, "No hay conexión con el servidor.");
  }
  if (respuesta.status === 204) return undefined as T;
  let datos: unknown;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    const detalle = (datos as { detail?: unknown } | null)?.detail;
    const mensaje =
      typeof detalle === "string" ? detalle : (MENSAJES[respuesta.status] ?? "Ocurrió un error inesperado.");
    const esSesion = ruta.startsWith("/api/auth/");
    if (respuesta.status === 401 && !esSesion) window.dispatchEvent(new Event(EVENTO_SESION_EXPIRADA));
    throw new ErrorApi(respuesta.status, mensaje);
  }
  return datos as T;
}
