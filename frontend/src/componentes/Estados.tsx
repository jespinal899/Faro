import { Alert, Button, Empty, Skeleton } from "antd";

/** Estados de carga, error y ausencia de datos (la guía los exige en el dashboard). */
export function Cargando({ filas = 4 }: { filas?: number }) {
  return <Skeleton active paragraph={{ rows: filas }} title={false} aria-busy="true" />;
}

export function ErrorCarga({ mensaje, reintentar }: { mensaje: string; reintentar?: () => void }) {
  return (
    <Alert
      type="error"
      showIcon
      title="No se pudieron cargar los datos"
      description={mensaje}
      action={
        reintentar && (
          <Button size="small" onClick={reintentar}>
            Reintentar
          </Button>
        )
      }
    />
  );
}

export function SinDatos({ texto = "No hay ventas para los filtros elegidos." }: { texto?: string }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={texto} />;
}
