import { useCallback, useMemo, useState } from "react";
import { Card, Select, Segmented, Space, Switch, Table, Tooltip, Typography } from "antd";
import { BarChartOutlined, TableOutlined } from "@ant-design/icons";
import { usePaleta } from "../contexto";
import { useApi } from "../hooks/useApi";
import type { Parametros } from "../api";
import { FILTRO_DE_DIMENSION } from "../filtros";
import { fEntero, fMoneda, fMonedaCompacta, fPorcentaje } from "../formato";
import { FUENTE, type Paleta } from "../tema";
import type { FilaDesglose, RespuestaDesglose } from "../tipos";
import { Cargando, ErrorCarga, SinDatos } from "./Estados";
import Grafico, { type EventoGrafico, type OpcionGrafico } from "./Grafico";

export const DIMENSIONES = [
  { value: "grupo", label: "Grupo de producto" },
  { value: "categoria", label: "Categoría de cliente" },
  { value: "territorio", label: "Territorio" },
  { value: "estado", label: "Estado" },
  { value: "vendedor", label: "Vendedor" },
  { value: "producto", label: "Producto" },
  { value: "cliente", label: "Cliente" },
  { value: "grupo_compra", label: "Grupo de compra" },
];

/** Barras horizontales de una sola serie (sin leyenda: el título la nombra). "Otros" en gris. */
export function opcionDesglose(filas: FilaDesglose[], p: Paleta): OpcionGrafico {
  const ordenadas = [...filas].reverse(); // la mayor arriba
  return {
    aria: { enabled: true },
    textStyle: { fontFamily: FUENTE, color: p.tintaSecundaria },
    grid: { left: 8, right: 72, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (e: unknown) => {
        const f = ordenadas[(e as EventoGrafico).dataIndex];
        return [
          `<div style="color:${p.tinta};margin-bottom:4px"><b>${f.nombre}</b></div>`,
          `Ventas netas: <b>${fMoneda(f.ventas_netas)}</b>`,
          `Participación: ${fPorcentaje(f.participacion_pct)}`,
          `Margen: ${fPorcentaje(f.margen_pct)}`,
          f.clave ? `<div style="color:${p.tenue};margin-top:4px">Clic para filtrar</div>` : "",
        ].join("<br/>");
      },
    },
    xAxis: {
      type: "value",
      splitNumber: 3, // pocas marcas: las etiquetas "USD 12 M" no se encimen en pantallas angostas
      axisLabel: { color: p.tenue, formatter: (v: number) => fMonedaCompacta(v) },
      splitLine: { lineStyle: { color: p.grilla } },
    },
    yAxis: {
      type: "category",
      data: ordenadas.map((f) => f.nombre),
      axisLine: { lineStyle: { color: p.eje } },
      axisTick: { show: false },
      axisLabel: { color: p.tintaSecundaria, width: 130, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        name: "Ventas netas",
        barMaxWidth: 18,
        data: ordenadas.map((f) => ({
          value: f.ventas_netas,
          itemStyle: { color: f.clave === null ? p.tenue : p.serie1, borderRadius: [0, 4, 4, 0] },
        })),
        label: {
          show: true,
          position: "right",
          color: p.tintaSecundaria,
          formatter: (e: { dataIndex: number }) => fPorcentaje(ordenadas[e.dataIndex].participacion_pct),
        },
        cursor: "pointer",
      },
    ],
  };
}

interface Props {
  params: Parametros;
  onFiltrar: (dimension: string, fila: FilaDesglose) => void;
}

export default function GraficoDesglose({ params, onFiltrar }: Props) {
  const { paleta } = usePaleta();
  const [dimension, setDimension] = useState("grupo");
  const [pertenencia, setPertenencia] = useState(false);
  const [vista, setVista] = useState<"grafico" | "tabla">("grafico");
  const usarPertenencia = pertenencia && dimension === "grupo";
  const { datos, cargando, error, recargar } = useApi<RespuestaDesglose>("/api/desglose", {
    ...params,
    dimension,
    top: 10,
    pertenencia: usarPertenencia || undefined,
  });
  const filas = useMemo(() => datos?.filas ?? [], [datos]);
  const opcion = useMemo(() => opcionDesglose(filas, paleta), [filas, paleta]);
  const sePuedeFiltrar = Boolean(FILTRO_DE_DIMENSION[dimension]) && !usarPertenencia;

  const alHacerClic = useCallback(
    (e: EventoGrafico) => {
      const fila = [...filas].reverse()[e.dataIndex];
      if (fila?.clave && sePuedeFiltrar) onFiltrar(dimension, fila);
    },
    [filas, sePuedeFiltrar, dimension, onFiltrar],
  );

  let cuerpo;
  if (error) cuerpo = <ErrorCarga mensaje={error} reintentar={recargar} />;
  else if (cargando && !datos) cuerpo = <Cargando filas={7} />;
  else if (!filas.length) cuerpo = <SinDatos />;
  else if (vista === "tabla")
    cuerpo = (
      <Table
        size="small"
        rowKey={(f) => f.clave ?? f.nombre}
        dataSource={filas}
        pagination={false}
        scroll={{ x: true }}
        onRow={(f) => ({
          onClick: () => f.clave && sePuedeFiltrar && onFiltrar(dimension, f),
          style: { cursor: f.clave && sePuedeFiltrar ? "pointer" : undefined },
        })}
        columns={[
          { title: "Nombre", dataIndex: "nombre", ellipsis: true },
          { title: "Ventas netas", align: "right", className: "num", render: (_, f) => fMoneda(f.ventas_netas) },
          { title: "Part.", align: "right", className: "num", render: (_, f) => fPorcentaje(f.participacion_pct) },
          { title: "Margen", align: "right", className: "num", render: (_, f) => fPorcentaje(f.margen_pct) },
          { title: "Facturas", align: "right", className: "num", render: (_, f) => fEntero(f.facturas) },
        ]}
      />
    );
  else
    cuerpo = (
      <Grafico
        opcion={opcion}
        alto={Math.max(240, filas.length * 30)}
        etiqueta={`Ventas netas por ${DIMENSIONES.find((d) => d.value === dimension)?.label}`}
        onClic={alHacerClic}
      />
    );

  return (
    <Card
      size="small"
      title="Ventas netas por dimensión"
      extra={
        <Segmented
          size="small"
          value={vista}
          onChange={(v) => setVista(v as "grafico" | "tabla")}
          options={[
            { value: "grafico", icon: <BarChartOutlined />, title: "Ver gráfico" },
            { value: "tabla", icon: <TableOutlined />, title: "Ver tabla" },
          ]}
        />
      }
    >
      <Space wrap size={[12, 6]} style={{ marginBottom: 8 }}>
        <Select aria-label="Dimensión" size="small" value={dimension} options={DIMENSIONES} onChange={setDimension} style={{ width: 190 }} />
        {dimension === "grupo" && (
          <Tooltip title="Un producto puede estar en varios grupos: su venta se reparte entre ellos para no contarla dos veces.">
            <Space size={6}>
              <Switch size="small" checked={pertenencia} onChange={setPertenencia} aria-label="Repartir por pertenencia" />
              <Typography.Text type="secondary">Por pertenencia</Typography.Text>
            </Space>
          </Tooltip>
        )}
        {datos && (
          <Typography.Text type="secondary">
            Total {fMoneda(datos.total_ventas_netas)}
            {sePuedeFiltrar && " · clic para filtrar"}
          </Typography.Text>
        )}
      </Space>
      {cuerpo}
    </Card>
  );
}
