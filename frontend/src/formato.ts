// Formatos en español latinoamericano. "—" = sin dato (nunca se muestra un 0 que no existe).
import dayjs from "dayjs";
import "dayjs/locale/es";

dayjs.locale("es");

const LOCALE = "es-419";
const SIN_DATO = "—";

const moneda = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const monedaDecimal = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const monedaCompacta = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const entero = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const decimal1 = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const vacio = (v: number | null | undefined): v is null | undefined => v === null || v === undefined;

export const fMoneda = (v: number | null | undefined) => (vacio(v) ? SIN_DATO : moneda.format(v));
export const fMonedaDecimal = (v: number | null | undefined) => (vacio(v) ? SIN_DATO : monedaDecimal.format(v));
export const fMonedaCompacta = (v: number | null | undefined) => (vacio(v) ? SIN_DATO : monedaCompacta.format(v));
export const fEntero = (v: number | null | undefined) => (vacio(v) ? SIN_DATO : entero.format(v));
export const fPorcentaje = (v: number | null | undefined) => (vacio(v) ? SIN_DATO : `${decimal1.format(v)} %`);

/** Variación con signo explícito: "+8,1 %" o, para el margen, "+0,3 pp". */
export function fVariacion(v: number | null | undefined, unidad: "%" | "pp" = "%"): string {
  if (vacio(v)) return SIN_DATO;
  const signo = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${signo}${decimal1.format(Math.abs(v))} ${unidad}`;
}

export const fFecha = (iso: string | null | undefined) => (iso ? dayjs(iso).format("DD/MM/YYYY") : SIN_DATO);
export const fFechaHora = (iso: string | null | undefined) => (iso ? dayjs(iso).format("DD/MM/YYYY HH:mm") : SIN_DATO);
export const fMes = (iso: string) => dayjs(iso).format("MMM YYYY");
export const fDia = (iso: string) => dayjs(iso).format("DD MMM YYYY");
/** Semana por su lunes: "30 may 16". */
export const fSemana = (iso: string) => dayjs(iso).format("DD MMM YY");
