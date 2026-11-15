// Estado de los filtros del dashboard y su traducción a parámetros de la API.
import dayjs from "dayjs";
import type { Parametros } from "./api";

export interface EstadoFiltros {
  desde?: string;
  hasta?: string;
  territorio?: string;
  estado?: string;
  categoria?: string;
  grupo?: string;
  vendedor_id?: number;
  cliente_id?: number;
  producto_id?: number;
  solo_bajo_costo: boolean;
  incluir_simulados: boolean;
}

/** Nombres para mostrar de los filtros que se guardan por ID (cliente, producto, vendedor). */
export type Etiquetas = Partial<Record<"cliente_id" | "producto_id" | "vendedor_id", string>>;

export const FILTROS_INICIALES: EstadoFiltros = { solo_bajo_costo: false, incluir_simulados: true };

export function aParametros(f: EstadoFiltros): Parametros {
  return {
    desde: f.desde,
    hasta: f.hasta,
    territorio: f.territorio,
    estado: f.estado,
    categoria: f.categoria,
    grupo: f.grupo,
    vendedor_id: f.vendedor_id,
    cliente_id: f.cliente_id,
    producto_id: f.producto_id,
    solo_bajo_costo: f.solo_bajo_costo || undefined,
    incluir_simulados: f.incluir_simulados ? undefined : false,
  };
}

/** Período por defecto: del 1 de enero del último año con datos hasta la última fecha.
 *  Se compara solo con los mismos meses del año anterior (2016 está incompleto: hallazgo H01). */
export function periodoPorDefecto(fechaHasta: string): { desde: string; hasta: string } {
  const hasta = dayjs(fechaHasta);
  return { desde: hasta.startOf("year").format("YYYY-MM-DD"), hasta: hasta.format("YYYY-MM-DD") };
}

export interface Preajuste {
  etiqueta: string;
  desde: string;
  hasta: string;
}

/** Rangos rápidos, relativos a la última fecha con datos (no a "hoy": los datos son de 2013-2016). */
export function preajustes(fechaDesde: string, fechaHasta: string): Preajuste[] {
  const fin = dayjs(fechaHasta);
  const f = (d: dayjs.Dayjs) => d.format("YYYY-MM-DD");
  const anioAnterior = fin.subtract(1, "year");
  return [
    { etiqueta: "Año en curso", desde: f(fin.startOf("year")), hasta: f(fin) },
    { etiqueta: "Últimos 90 días", desde: f(fin.subtract(89, "day")), hasta: f(fin) },
    { etiqueta: "Últimos 12 meses", desde: f(fin.subtract(1, "year").add(1, "day")), hasta: f(fin) },
    { etiqueta: `Año ${anioAnterior.year()} completo`, desde: f(anioAnterior.startOf("year")), hasta: f(anioAnterior.endOf("year")) },
    { etiqueta: "Todo el histórico", desde: fechaDesde, hasta: f(fin) },
  ];
}

/** Dimensiones del desglose que se pueden usar como filtro al hacer clic (drill-down). */
export const FILTRO_DE_DIMENSION: Record<string, keyof EstadoFiltros> = {
  grupo: "grupo",
  categoria: "categoria",
  territorio: "territorio",
  estado: "estado",
  vendedor: "vendedor_id",
  producto: "producto_id",
  cliente: "cliente_id",
};
