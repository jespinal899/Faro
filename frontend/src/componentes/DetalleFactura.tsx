import { Descriptions, Modal, Table, Tag, Typography } from "antd";
import { useApi } from "../hooks/useApi";
import { fEntero, fFecha, fMoneda, fMonedaDecimal } from "../formato";
import type { Factura, LineaFactura } from "../tipos";
import { Cargando, ErrorCarga } from "./Estados";

/** Navegación de resumen a detalle: una factura con sus líneas. */
export default function DetalleFactura({ facturaId, onCerrar }: { facturaId: number | null; onCerrar: () => void }) {
  const { datos, cargando, error, recargar } = useApi<Factura>(facturaId ? `/api/facturas/${facturaId}` : null);
  const f = datos?.factura_id === facturaId ? datos : undefined;

  return (
    <Modal
      open={facturaId !== null}
      onCancel={onCerrar}
      footer={null}
      width={900}
      title={
        <span>
          Factura {facturaId} {f?.es_simulado && <Tag color="purple">Simulada</Tag>}
        </span>
      }
    >
      {error ? (
        <ErrorCarga mensaje={error} reintentar={recargar} />
      ) : cargando || !f ? (
        <Cargando filas={6} />
      ) : (
        <>
          <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} style={{ marginBottom: 12 }}>
            <Descriptions.Item label="Fecha">{fFecha(f.fecha)}</Descriptions.Item>
            <Descriptions.Item label="Pedido">{f.pedido_id ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Vendedor">{f.vendedor}</Descriptions.Item>
            <Descriptions.Item label="Cliente">{f.cliente}</Descriptions.Item>
            <Descriptions.Item label="Categoría">{f.categoria_cliente}</Descriptions.Item>
            <Descriptions.Item label="Grupo de compra">{f.grupo_compra}</Descriptions.Item>
            <Descriptions.Item label="Entrega">{`${f.ciudad}, ${f.estado} (${f.territorio})`}</Descriptions.Item>
            <Descriptions.Item label="Ventas netas">
              <b>{fMoneda(f.ventas_netas)}</b>
            </Descriptions.Item>
            <Descriptions.Item label="Utilidad">
              <Typography.Text type={f.utilidad < 0 ? "danger" : undefined}>{fMoneda(f.utilidad)}</Typography.Text>
            </Descriptions.Item>
          </Descriptions>
          <Table<LineaFactura>
            size="small"
            rowKey="linea_factura_id"
            dataSource={f.lineas}
            pagination={false}
            scroll={{ x: 760 }}
            columns={[
              { title: "Producto", dataIndex: "producto", ellipsis: true },
              { title: "Grupo", dataIndex: "grupo_principal", width: 150 },
              { title: "Cantidad", dataIndex: "cantidad", align: "right", className: "num", render: fEntero, width: 90 },
              { title: "Precio unitario", dataIndex: "precio_unitario", align: "right", className: "num", render: fMonedaDecimal, width: 120 },
              { title: "Venta neta", dataIndex: "venta_neta", align: "right", className: "num", render: fMonedaDecimal, width: 120 },
              {
                title: "Utilidad",
                dataIndex: "utilidad",
                align: "right",
                className: "num",
                width: 140,
                render: (v: number, l) => (
                  <span>
                    <Typography.Text type={v < 0 ? "danger" : undefined}>{fMonedaDecimal(v)}</Typography.Text>{" "}
                    {l.es_venta_bajo_costo && <Tag color="red">Bajo costo</Tag>}
                  </span>
                ),
              },
            ]}
          />
        </>
      )}
    </Modal>
  );
}
