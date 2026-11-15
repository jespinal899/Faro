// Contratos de la API (ver documentation/api/openapi.json)

export interface Usuario {
  usuario: string;
  nombre: string;
  rol: string;
}

export interface Indicadores {
  ventas_netas: number;
  ventas_brutas: number;
  utilidad: number;
  margen_pct: number | null;
  unidades: number;
  facturas: number;
  ticket_promedio: number | null;
  clientes_activos: number;
}

export interface Comparacion {
  tipo: "anio_anterior";
  desde: string;
  hasta: string;
  valores: Indicadores;
  variacion_pct: Partial<Record<keyof Indicadores, number | null>>;
}

export interface RespuestaKpis {
  actual: Indicadores;
  comparacion: Comparacion | null;
}

export interface PuntoTendencia {
  periodo: string;
  ventas_netas: number;
  utilidad: number;
  facturas: number;
  ventas_netas_anterior: number | null;
}

export interface FilaDesglose {
  clave: string | null;
  nombre: string;
  ventas_netas: number;
  utilidad: number;
  margen_pct: number | null;
  unidades: number;
  facturas: number | null;
  participacion_pct: number | null;
}

export interface RespuestaDesglose {
  dimension: string;
  pertenencia: boolean;
  total_ventas_netas: number;
  filas: FilaDesglose[];
}

export interface FilaFactura {
  factura_id: number;
  fecha: string;
  cliente: string;
  vendedor: string;
  territorio: string;
  lineas: number;
  unidades: number;
  ventas_netas: number;
  utilidad: number;
  es_simulado: boolean;
  tiene_venta_bajo_costo: boolean;
}

export interface PaginaFacturas {
  pagina: number;
  tamano: number;
  total: number;
  filas: FilaFactura[];
}

export interface LineaFactura {
  linea_factura_id: number;
  producto_id: number;
  producto: string;
  grupo_principal: string;
  cantidad: number;
  precio_unitario: number | null;
  venta_bruta: number;
  impuesto: number;
  venta_neta: number;
  utilidad: number;
  es_venta_bajo_costo: boolean;
}

export interface Factura {
  factura_id: number;
  pedido_id: number | null;
  fecha: string;
  cliente_id: number;
  cliente: string;
  categoria_cliente: string;
  grupo_compra: string;
  vendedor: string;
  ciudad: string;
  estado: string;
  territorio: string;
  es_simulado: boolean;
  ventas_netas: number;
  utilidad: number;
  lineas: LineaFactura[];
}

export interface Opciones {
  territorios: string[];
  estados: string[];
  categorias: string[];
  grupos: string[];
  vendedores: { id: number; nombre: string }[];
  fecha_desde: string | null;
  fecha_hasta: string | null;
}

export interface EstadoDatos {
  ultima_carga_exitosa: string | null;
  estado_ultima_ejecucion: string | null;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  ultima_fecha_real: string | null;
  lineas: number;
  lineas_simuladas: number;
}
