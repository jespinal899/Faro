import { Card, Col, Row, Tooltip, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined, MinusOutlined } from "@ant-design/icons";
import { usePaleta } from "../contexto";
import { fEntero, fMoneda, fMonedaDecimal, fPorcentaje, fVariacion } from "../formato";
import type { Indicadores, RespuestaKpis } from "../tipos";
import { Cargando, ErrorCarga } from "./Estados";

interface Definicion {
  clave: keyof Indicadores;
  titulo: string;
  ayuda: string;
  valor: (v: number | null) => string;
  unidadVariacion?: "%" | "pp";
}

// 6 KPI principales (la guía pide entre 4 y 6). Fórmulas en documentation/modelos/kpis.md
export const KPIS: Definicion[] = [
  { clave: "ventas_netas", titulo: "Ventas netas", ayuda: "Σ venta neta (sin impuestos)", valor: fMoneda },
  { clave: "utilidad", titulo: "Utilidad", ayuda: "Σ utilidad de las líneas vendidas", valor: fMoneda },
  { clave: "margen_pct", titulo: "Margen", ayuda: "Σ utilidad ÷ Σ ventas netas. Se compara en puntos porcentuales.", valor: fPorcentaje, unidadVariacion: "pp" },
  { clave: "facturas", titulo: "Facturas", ayuda: "Facturas distintas del período", valor: fEntero },
  { clave: "ticket_promedio", titulo: "Ticket promedio", ayuda: "Ventas netas ÷ facturas", valor: fMonedaDecimal },
  { clave: "clientes_activos", titulo: "Clientes activos", ayuda: "Clientes distintos que compraron en el período", valor: fEntero },
];

function Variacion({ valor, unidad }: { valor: number | null | undefined; unidad: "%" | "pp" }) {
  const { paleta } = usePaleta();
  if (valor === null || valor === undefined) {
    return <Typography.Text type="secondary">Sin comparación</Typography.Text>;
  }
  // Nunca solo color: flecha + texto ("sube"/"baja") + valor con signo
  const sube = valor > 0;
  const igual = valor === 0;
  const color = igual ? undefined : sube ? paleta.sube : paleta.baja;
  const Icono = igual ? MinusOutlined : sube ? ArrowUpOutlined : ArrowDownOutlined;
  return (
    <span style={{ color }} aria-label={`${igual ? "Sin cambio" : sube ? "Sube" : "Baja"} ${fVariacion(valor, unidad)} frente al año anterior`}>
      <Icono /> {fVariacion(valor, unidad)} <Typography.Text type="secondary">vs. año anterior</Typography.Text>
    </span>
  );
}

interface Props {
  datos?: RespuestaKpis;
  cargando: boolean;
  error?: string;
  reintentar: () => void;
}

export default function TarjetasKpi({ datos, cargando, error, reintentar }: Props) {
  if (error) return <ErrorCarga mensaje={error} reintentar={reintentar} />;
  return (
    <Row gutter={[12, 12]} role="list" aria-label="Indicadores principales">
      {KPIS.map((k) => (
        <Col key={k.clave} xs={12} md={8} xl={4} role="listitem">
          <Card size="small" className="kpi">
            {cargando && !datos ? (
              <Cargando filas={2} />
            ) : (
              <>
                <Tooltip title={k.ayuda}>
                  <Typography.Text type="secondary" className="kpi-titulo">
                    {k.titulo}
                  </Typography.Text>
                </Tooltip>
                <div className="kpi-valor" data-testid={`kpi-${k.clave}`}>
                  {k.valor(datos?.actual[k.clave] ?? null)}
                </div>
                <div className="kpi-variacion">
                  <Variacion valor={datos?.comparacion?.variacion_pct[k.clave]} unidad={k.unidadVariacion ?? "%"} />
                </div>
              </>
            )}
          </Card>
        </Col>
      ))}
    </Row>
  );
}
