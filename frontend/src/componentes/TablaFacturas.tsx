import { useState } from "react";
import { Card, Input, Space, Table, Tag, Typography } from "antd";
import type { SorterResult } from "antd/es/table/interface";
import { useApi } from "../hooks/useApi";
import type { Parametros } from "../api";
import { fEntero, fFecha, fMoneda } from "../formato";
import type { FilaFactura, PaginaFacturas } from "../tipos";
import { ErrorCarga } from "./Estados";

interface Props {
  params: Parametros;
  onAbrir: (facturaId: number) => void;
}

const ORDEN: Record<string, Record<"ascend" | "descend", string>> = {
  fecha: { ascend: "fecha_asc", descend: "fecha_desc" },
  ventas_netas: { ascend: "venta_asc", descend: "venta_desc" },
};

/** Detalle de facturas paginado en el servidor (máximo 100 por página). Clic en una fila = detalle. */
export default function TablaFacturas({ params, onAbrir }: Props) {
  const [pagina, setPagina] = useState(1);
  const [tamano, setTamano] = useState(10);
  const [orden, setOrden] = useState("fecha_desc");
  const [buscar, setBuscar] = useState<string>();
  const { datos, cargando, error, recargar } = useApi<PaginaFacturas>("/api/facturas", {
    ...params,
    pagina,
    tamano,
    orden,
    buscar,
  });

  return (
    <Card
      size="small"
      title="Facturas"
      extra={
        <Input.Search
          aria-label="Buscar por cliente"
          placeholder="Buscar cliente"
          allowClear
          size="small"
          style={{ width: 220 }}
          onSearch={(v) => {
            setBuscar(v.trim() || undefined);
            setPagina(1);
          }}
        />
      }
    >
      {error ? (
        <ErrorCarga mensaje={error} reintentar={recargar} />
      ) : (
        <Table<FilaFactura>
          size="small"
          rowKey="factura_id"
          loading={cargando}
          dataSource={datos?.filas}
          scroll={{ x: 900 }}
          locale={{ emptyText: "No hay facturas para los filtros elegidos." }}
          onRow={(f) => ({ onClick: () => onAbrir(f.factura_id), style: { cursor: "pointer" } })}
          pagination={{
            current: pagina,
            pageSize: tamano,
            total: datos?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: [10, 25, 50, 100],
            showTotal: (total) => `${fEntero(total)} facturas`,
            size: "small",
          }}
          onChange={(paginacion, _filtros, orden) => {
            const o = orden as SorterResult<FilaFactura>;
            const campo = String(o.field ?? "");
            setOrden(o.order && ORDEN[campo] ? ORDEN[campo][o.order] : "fecha_desc");
            setPagina(paginacion.current ?? 1);
            setTamano(paginacion.pageSize ?? 10);
          }}
          columns={[
            { title: "Factura", dataIndex: "factura_id", width: 90 },
            { title: "Fecha", dataIndex: "fecha", sorter: true, render: fFecha, width: 110 },
            { title: "Cliente", dataIndex: "cliente", ellipsis: true },
            { title: "Vendedor", dataIndex: "vendedor", ellipsis: true },
            { title: "Territorio", dataIndex: "territorio", width: 130 },
            { title: "Líneas", dataIndex: "lineas", align: "right", width: 70, className: "num" },
            { title: "Ventas netas", dataIndex: "ventas_netas", sorter: true, align: "right", className: "num", render: fMoneda, width: 130 },
            {
              title: "Utilidad",
              dataIndex: "utilidad",
              align: "right",
              className: "num",
              width: 120,
              render: (v: number) => <Typography.Text type={v < 0 ? "danger" : undefined}>{fMoneda(v)}</Typography.Text>,
            },
            {
              title: "Marcas",
              width: 170,
              render: (_, f) => (
                <Space size={4} wrap>
                  {f.es_simulado && <Tag color="purple">Simulada</Tag>}
                  {f.tiene_venta_bajo_costo && <Tag color="red">Bajo costo</Tag>}
                </Space>
              ),
            },
          ]}
        />
      )}
    </Card>
  );
}
