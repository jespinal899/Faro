import { useMemo, useState } from "react";
import { Card, Segmented, Space, Table, Typography } from "antd";
import { LineChartOutlined, TableOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { usePaleta } from "../contexto";
import { useApi } from "../hooks/useApi";
import type { Parametros } from "../api";
import { fDia, fFecha, fMes, fMoneda, fMonedaCompacta, fVariacion } from "../formato";
import { FUENTE, type Paleta } from "../tema";
import type { PuntoTendencia } from "../tipos";
import { Cargando, ErrorCarga, SinDatos } from "./Estados";
import Grafico, { type OpcionGrafico } from "./Grafico";

export type Granularidad = "mes" | "semana" | "dia";

const variacion = (a: number, b: number | null) => (b ? (100 * (a - b)) / b : null);

/**
 * Índices de los períodos que el rango de fechas cubre solo en parte (p. ej. junio con 2 días).
 * Sin marcarlos, la caída del último punto parece un desplome de ventas.
 * Las semanas empiezan el lunes, igual que date_trunc('week') en la API.
 */
export function periodosIncompletos(
  puntos: PuntoTendencia[],
  granularidad: Granularidad,
  desde?: string,
  hasta?: string,
): Set<number> {
  const incompletos = new Set<number>();
  if (granularidad === "dia") return incompletos;
  puntos.forEach((x, i) => {
    const inicio = dayjs(x.periodo);
    const fin = granularidad === "mes" ? inicio.endOf("month") : inicio.add(6, "day");
    if ((desde && dayjs(desde).isAfter(inicio, "day")) || (hasta && dayjs(hasta).isBefore(fin, "day"))) incompletos.add(i);
  });
  return incompletos;
}

/** Opción de ECharts: período actual (serie 1) vs. año anterior (serie 2, discontinua). Un solo eje. */
export function opcionTendencia(
  puntos: PuntoTendencia[],
  granularidad: Granularidad,
  p: Paleta,
  incompletos: Set<number> = new Set(),
): OpcionGrafico {
  const etiquetas = puntos.map((x, i) => (granularidad === "mes" ? fMes(x.periodo) : fDia(x.periodo)) + (incompletos.has(i) ? "*" : ""));
  const hayAnterior = puntos.some((x) => x.ventas_netas_anterior !== null);
  const muchos = puntos.length > 60;
  const linea = (color: string, tipo: "solid" | "dashed") => ({
    type: "line" as const,
    showSymbol: puntos.length <= 24,
    symbolSize: 8,
    lineStyle: { width: 2, color, type: tipo },
    itemStyle: { color },
    emphasis: { focus: "series" as const },
  });
  return {
    aria: { enabled: true },
    textStyle: { fontFamily: FUENTE, color: p.tintaSecundaria },
    grid: { left: 8, right: 24, top: hayAnterior ? 36 : 12, bottom: muchos ? 44 : 8, containLabel: true },
    legend: hayAnterior
      ? { top: 0, left: 0, icon: "roundRect", itemWidth: 14, itemHeight: 4, textStyle: { color: p.tintaSecundaria } }
      : undefined,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: p.eje } },
      formatter: (params: unknown) => {
        const lista = params as { dataIndex: number }[];
        const x = puntos[lista[0].dataIndex];
        const fila = (color: string, texto: string, valor: string) =>
          `<div style="display:flex;gap:8px;align-items:center"><span style="width:10px;height:3px;background:${color};display:inline-block"></span>${texto}<b style="margin-left:auto;padding-left:12px">${valor}</b></div>`;
        return [
          `<div style="margin-bottom:4px;color:${p.tinta}">${etiquetas[lista[0].dataIndex]}</div>`,
          fila(p.serie1, "Período actual", fMoneda(x.ventas_netas)),
          hayAnterior ? fila(p.serie2, "Año anterior", fMoneda(x.ventas_netas_anterior)) : "",
          hayAnterior ? `<div style="color:${p.tenue};margin-top:4px">Variación: ${fVariacion(variacion(x.ventas_netas, x.ventas_netas_anterior))}</div>` : "",
          incompletos.has(lista[0].dataIndex) ? `<div style="color:${p.tenue}">* Período incompleto</div>` : "",
        ].join("");
      },
    },
    xAxis: {
      type: "category",
      data: etiquetas,
      boundaryGap: false,
      axisLine: { lineStyle: { color: p.eje } },
      axisTick: { show: false },
      axisLabel: { color: p.tenue, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: p.tenue, formatter: (v: number) => fMonedaCompacta(v) },
      splitLine: { lineStyle: { color: p.grilla } },
    },
    dataZoom: muchos ? [{ type: "inside" }, { type: "slider", height: 18, bottom: 8, borderColor: p.grilla }] : [],
    series: [
      { ...linea(p.serie1, "solid"), name: "Período actual", data: puntos.map((x) => x.ventas_netas) },
      ...(hayAnterior
        ? [{ ...linea(p.serie2, "dashed"), name: "Año anterior", data: puntos.map((x) => x.ventas_netas_anterior) }]
        : []),
    ],
  };
}

export default function GraficoTendencia({ params }: { params: Parametros }) {
  const { paleta } = usePaleta();
  const [granularidad, setGranularidad] = useState<Granularidad>("mes");
  const [vista, setVista] = useState<"grafico" | "tabla">("grafico");
  const { datos, cargando, error, recargar } = useApi<PuntoTendencia[]>("/api/tendencia", { ...params, granularidad });
  const desde = params.desde as string | undefined;
  const hasta = params.hasta as string | undefined;
  const incompletos = useMemo(
    () => periodosIncompletos(datos ?? [], granularidad, desde, hasta),
    [datos, granularidad, desde, hasta],
  );
  const opcion = useMemo(
    () => opcionTendencia(datos ?? [], granularidad, paleta, incompletos),
    [datos, granularidad, paleta, incompletos],
  );
  const etiqueta = (x: PuntoTendencia, i: number) =>
    (granularidad === "mes" ? fMes(x.periodo) : fDia(x.periodo)) + (incompletos.has(i) ? "*" : "");

  let cuerpo;
  if (error) cuerpo = <ErrorCarga mensaje={error} reintentar={recargar} />;
  else if (cargando && !datos) cuerpo = <Cargando filas={7} />;
  else if (!datos?.length) cuerpo = <SinDatos />;
  else if (vista === "tabla")
    cuerpo = (
      <Table
        size="small"
        rowKey="periodo"
        dataSource={datos}
        pagination={{ pageSize: 12, size: "small" }}
        scroll={{ x: true }}
        columns={[
          // el índice de render es el de la página; se busca la posición en la serie completa
          { title: "Período", render: (_, x) => etiqueta(x, datos.indexOf(x)) },
          { title: "Ventas netas", align: "right", className: "num", render: (_, x) => fMoneda(x.ventas_netas) },
          { title: "Año anterior", align: "right", className: "num", render: (_, x) => fMoneda(x.ventas_netas_anterior) },
          { title: "Variación", align: "right", className: "num", render: (_, x) => fVariacion(variacion(x.ventas_netas, x.ventas_netas_anterior)) },
          { title: "Facturas", align: "right", className: "num", dataIndex: "facturas" },
        ]}
      />
    );
  else
    cuerpo = (
      <Grafico
        opcion={opcion}
        etiqueta={`Tendencia de ventas netas por ${granularidad}, comparada con el año anterior`}
      />
    );

  return (
    <Card
      title="Tendencia de ventas netas"
      size="small"
      loading={false}
      extra={
        <Space wrap size={6}>
          <Segmented
            size="small"
            value={granularidad}
            onChange={(v) => setGranularidad(v as Granularidad)}
            options={[
              { label: "Mes", value: "mes" },
              { label: "Semana", value: "semana" },
              { label: "Día", value: "dia" },
            ]}
          />
          <Segmented
            size="small"
            value={vista}
            onChange={(v) => setVista(v as "grafico" | "tabla")}
            options={[
              { value: "grafico", icon: <LineChartOutlined />, title: "Ver gráfico" },
              { value: "tabla", icon: <TableOutlined />, title: "Ver tabla" },
            ]}
          />
        </Space>
      }
    >
      {cuerpo}
      {incompletos.size > 0 && !error && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          * Período incompleto: el rango elegido ({fFecha(desde)} – {fFecha(hasta)}) no lo cubre entero. El año anterior se
          compara con el mismo tramo de fechas.
        </Typography.Text>
      )}
    </Card>
  );
}
