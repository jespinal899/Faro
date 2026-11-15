import { Button, Card, DatePicker, Select, Space, Switch, Tag, Typography } from "antd";
import { ClearOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { preajustes, type Etiquetas, type EstadoFiltros } from "../filtros";
import type { Opciones } from "../tipos";

interface Props {
  filtros: EstadoFiltros;
  etiquetas: Etiquetas;
  opciones?: Opciones;
  onCambiar: (cambios: Partial<EstadoFiltros>) => void;
  onLimpiar: () => void;
}

const lista = (valores: string[] = []) => valores.map((v) => ({ value: v, label: v }));

/** Filtros en una sola fila, encima de todos los gráficos: afectan a todo el dashboard. */
export default function BarraFiltros({ filtros, etiquetas, opciones, onCambiar, onLimpiar }: Props) {
  const rango: [Dayjs, Dayjs] | null =
    filtros.desde && filtros.hasta ? [dayjs(filtros.desde), dayjs(filtros.hasta)] : null;
  const minimo = opciones?.fecha_desde ? dayjs(opciones.fecha_desde) : undefined;
  const maximo = opciones?.fecha_hasta ? dayjs(opciones.fecha_hasta) : undefined;
  const rapidos =
    opciones?.fecha_desde && opciones.fecha_hasta
      ? preajustes(opciones.fecha_desde, opciones.fecha_hasta).map((p) => ({
          label: p.etiqueta,
          value: [dayjs(p.desde), dayjs(p.hasta)] as [Dayjs, Dayjs],
        }))
      : [];

  // Filtros que llegan al hacer clic en un gráfico (no tienen selector propio)
  const chips: { clave: keyof EstadoFiltros; texto: string }[] = [];
  if (filtros.estado) chips.push({ clave: "estado", texto: `Estado: ${filtros.estado}` });
  if (filtros.cliente_id) chips.push({ clave: "cliente_id", texto: `Cliente: ${etiquetas.cliente_id ?? filtros.cliente_id}` });
  if (filtros.producto_id) chips.push({ clave: "producto_id", texto: `Producto: ${etiquetas.producto_id ?? filtros.producto_id}` });

  return (
    <Card size="small" className="barra-filtros" role="search" aria-label="Filtros del dashboard">
      <Space wrap size={[12, 8]} align="center">
        <DatePicker.RangePicker
          aria-label="Período"
          value={rango}
          format="DD/MM/YYYY"
          allowClear
          presets={rapidos}
          minDate={minimo}
          maxDate={maximo}
          onChange={(valores) =>
            onCambiar({
              desde: valores?.[0]?.format("YYYY-MM-DD"),
              hasta: valores?.[1]?.format("YYYY-MM-DD"),
            })
          }
        />
        <Select
          aria-label="Territorio"
          placeholder="Territorio"
          allowClear
          style={{ minWidth: 150 }}
          value={filtros.territorio}
          options={lista(opciones?.territorios)}
          onChange={(v) => onCambiar({ territorio: v })}
        />
        <Select
          aria-label="Categoría de cliente"
          placeholder="Categoría de cliente"
          allowClear
          style={{ minWidth: 180 }}
          value={filtros.categoria}
          options={lista(opciones?.categorias)}
          onChange={(v) => onCambiar({ categoria: v })}
        />
        <Select
          aria-label="Grupo de producto"
          placeholder="Grupo de producto"
          allowClear
          style={{ minWidth: 170 }}
          value={filtros.grupo}
          options={lista(opciones?.grupos)}
          onChange={(v) => onCambiar({ grupo: v })}
        />
        <Select
          aria-label="Vendedor"
          placeholder="Vendedor"
          allowClear
          showSearch={{ optionFilterProp: "label" }}
          style={{ minWidth: 170 }}
          value={filtros.vendedor_id}
          options={(opciones?.vendedores ?? []).map((v) => ({ value: v.id, label: v.nombre }))}
          onChange={(v) => onCambiar({ vendedor_id: v })}
        />
        <Space size={6}>
          <Switch
            size="small"
            checked={filtros.incluir_simulados}
            onChange={(v) => onCambiar({ incluir_simulados: v })}
            aria-label="Incluir datos simulados"
          />
          <Typography.Text>Incluir simulados</Typography.Text>
        </Space>
        <Space size={6}>
          <Switch
            size="small"
            checked={filtros.solo_bajo_costo}
            onChange={(v) => onCambiar({ solo_bajo_costo: v })}
            aria-label="Solo ventas bajo costo"
          />
          <Typography.Text>Solo ventas bajo costo</Typography.Text>
        </Space>
        <Button icon={<ClearOutlined />} onClick={onLimpiar}>
          Limpiar
        </Button>
      </Space>
      {chips.length > 0 && (
        <div className="chips" aria-label="Filtros aplicados desde los gráficos">
          {chips.map((c) => (
            <Tag key={c.clave} closable color="blue" onClose={() => onCambiar({ [c.clave]: undefined })}>
              {c.texto}
            </Tag>
          ))}
        </div>
      )}
    </Card>
  );
}
