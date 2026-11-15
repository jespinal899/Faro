import { Button, Dropdown, Space, Tag, Tooltip, Typography } from "antd";
import { ClockCircleOutlined, ExperimentOutlined, LogoutOutlined, MoonOutlined, SunOutlined, UserOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { fFecha, fFechaHora } from "../formato";
import type { EstadoDatos, Usuario } from "../tipos";
import type { Modo } from "../tema";
import Logo from "./Logo";

dayjs.extend(relativeTime);

interface Props {
  usuario: Usuario;
  estado?: EstadoDatos;
  modo: Modo;
  onCambiarModo: () => void;
  onSalir: () => void;
}

export default function Encabezado({ usuario, estado, modo, onCambiarModo, onSalir }: Props) {
  return (
    <header className="encabezado">
      <div className="encabezado-marca">
        <Logo />
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Faro · Ventas
          </Typography.Title>
          <Typography.Text type="secondary" className="subtitulo">
            Análisis histórico de WideWorldImporters desde el Data Warehouse
          </Typography.Text>
        </div>
      </div>

      <Space wrap size="small" className="encabezado-estado">
        {estado && (
          <Tooltip title={`Estado de la última ejecución del ETL: ${estado.estado_ultima_ejecucion ?? "—"}`}>
            <Tag icon={<ClockCircleOutlined />} variant="outlined">
              Datos al {fFecha(estado.fecha_hasta)} · actualizado {fFechaHora(estado.ultima_carga_exitosa)}
              {estado.ultima_carga_exitosa && ` (${dayjs(estado.ultima_carga_exitosa).fromNow()})`}
            </Tag>
          </Tooltip>
        )}
        {estado && estado.lineas_simuladas > 0 && (
          <Tooltip title="Ventas generadas por el simulador para la demostración. Se pueden excluir en los filtros.">
            <Tag icon={<ExperimentOutlined />} color="purple">
              Incluye datos SIMULADOS desde {fFecha(estado.ultima_fecha_real ? dayjs(estado.ultima_fecha_real).add(1, "day").format("YYYY-MM-DD") : null)}
            </Tag>
          </Tooltip>
        )}
        <Tooltip title={modo === "claro" ? "Modo oscuro" : "Modo claro"}>
          <Button
            type="text"
            aria-label={modo === "claro" ? "Cambiar a modo oscuro" : "Cambiar a modo claro"}
            icon={modo === "claro" ? <MoonOutlined /> : <SunOutlined />}
            onClick={onCambiarModo}
          />
        </Tooltip>
        <Dropdown
          menu={{ items: [{ key: "salir", icon: <LogoutOutlined />, label: "Cerrar sesión", onClick: onSalir }] }}
        >
          <Button type="text" icon={<UserOutlined />}>
            {usuario.nombre}
          </Button>
        </Dropdown>
      </Space>
    </header>
  );
}
