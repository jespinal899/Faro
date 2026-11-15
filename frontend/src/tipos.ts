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

// ------------------------------------------------- pronóstico (Machine Learning)
// Son PREDICCIONES registradas por el modelo, no datos históricos.

export interface PuntoHistoria {
  semana: string;
  venta_neta: number;
  incluye_simulados: boolean;
}

export interface PuntoPronostico {
  semana: string;
  horizonte: number;
  venta_neta: number;
  inferior: number;
  superior: number;
}

export interface PuntoSeguimiento {
  origen: string;
  semana: string;
  horizonte: number;
  pronostico: number;
  inferior: number;
  superior: number;
  real: number;
  real_incluye_simulados: boolean;
}

export interface SerieGrupo {
  grupo: string;
  historia: PuntoHistoria[];
  pronostico: PuntoPronostico[];
  seguimiento: PuntoSeguimiento[];
  wape_prueba: number | null;
  wape_prueba_linea_base: number | null;
}

export interface CalidadHorizonte {
  horizonte: number;
  wape_modelo: number;
  wape_linea_base: number;
  cobertura_pct: number;
}

export interface CalidadModelo {
  metrica: "wape";
  linea_base: string;
  linea_base_descripcion: string;
  wape_validacion_modelo: number;
  wape_validacion_linea_base: number;
  wape_prueba_modelo: number;
  wape_prueba_linea_base: number;
  mejora_prueba_pct: number;
  cobertura_objetivo_pct: number;
  cobertura_prueba_pct: number;
  por_horizonte: CalidadHorizonte[];
}

export interface ModeloPronostico {
  version: string;
  algoritmo: string;
  entrenado_en: string;
  datos_desde: string;
  datos_hasta: string;
  prueba_desde: string;
  commit_codigo: string | null;
  calidad: CalidadModelo;
}

export interface RespuestaPronostico {
  disponible: boolean;
  modelo: ModeloPronostico | null;
  origen: string | null;
  generado_en: string | null;
  usa_datos_simulados: boolean;
  grupos: SerieGrupo[];
  excluidos: { grupo: string; motivo: string }[];
}

export interface PuntoPrueba {
  semana: string;
  origen: string;
  real: number;
  pronostico: number;
  inferior: number;
  superior: number;
  linea_base: number;
}
