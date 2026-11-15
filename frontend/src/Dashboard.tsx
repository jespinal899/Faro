import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Col, Layout, Row, Tabs, Typography } from "antd";
import { AlertOutlined, BarChartOutlined, DashboardOutlined, LineChartOutlined, RobotOutlined } from "@ant-design/icons";
import { useApi } from "./hooks/useApi";
import { useIntervalo } from "./hooks/useIntervalo";
import { aParametros, FILTRO_DE_DIMENSION, FILTROS_INICIALES, periodoPorDefecto, type Etiquetas, type EstadoFiltros } from "./filtros";
import type { Modo } from "./tema";
import type { EstadoDatos, FilaDesglose, Opciones, RespuestaKpis, ResumenAlertas, Usuario } from "./tipos";
import BarraFiltros from "./componentes/BarraFiltros";
import DetalleFactura from "./componentes/DetalleFactura";
import Encabezado from "./componentes/Encabezado";
import GraficoDesglose from "./componentes/GraficoDesglose";
import GraficoTendencia from "./componentes/GraficoTendencia";
import PanelAlertas, { INTERVALO_ALERTAS_MS } from "./componentes/PanelAlertas";
import PanelAsistente from "./componentes/PanelAsistente";
import PanelOperacion from "./componentes/PanelOperacion";
import PanelPronostico from "./componentes/PanelPronostico";
import TablaFacturas from "./componentes/TablaFacturas";
import TarjetasKpi from "./componentes/TarjetasKpi";

type Pestana = "historico" | "pronostico" | "asistente" | "alertas" | "operacion";

interface Props {
  usuario: Usuario;
  modo: Modo;
  onCambiarModo: () => void;
  onSalir: () => void;
}

export default function Dashboard({ usuario, modo, onCambiarModo, onSalir }: Props) {
  const opciones = useApi<Opciones>("/api/opciones");
  const estado = useApi<EstadoDatos>("/api/estado");
  // Contador de alertas nuevas en la pestaña: se consulta cada minuto (polling, D-22)
  const alertas = useApi<ResumenAlertas>("/api/alertas/resumen");
  useIntervalo(alertas.recargar, INTERVALO_ALERTAS_MS);
  const [filtros, setFiltros] = useState<EstadoFiltros>(FILTROS_INICIALES);
  const [etiquetas, setEtiquetas] = useState<Etiquetas>({});
  const [inicializado, setInicializado] = useState(false);
  const [facturaAbierta, setFacturaAbierta] = useState<number | null>(null);
  const [pestana, setPestana] = useState<Pestana>("historico");
  // El asistente queda montado una vez abierto: la conversación no se pierde al cambiar de pestaña
  const [asistenteAbierto, setAsistenteAbierto] = useState(false);

  const porDefecto = useCallback(
    (): EstadoFiltros =>
      opciones.datos?.fecha_hasta
        ? { ...FILTROS_INICIALES, ...periodoPorDefecto(opciones.datos.fecha_hasta) }
        : FILTROS_INICIALES,
    [opciones.datos],
  );

  // Período inicial: el año de la última fecha con datos (se compara con los mismos meses del año anterior)
  useEffect(() => {
    if (!inicializado && opciones.datos) {
      setFiltros(porDefecto());
      setInicializado(true);
    }
  }, [inicializado, opciones.datos, porDefecto]);

  const params = useMemo(() => aParametros(filtros), [filtros]);
  const listo = inicializado || Boolean(opciones.error);
  const kpis = useApi<RespuestaKpis>(listo ? "/api/kpis" : null, params);

  const cambiar = useCallback((cambios: Partial<EstadoFiltros>) => setFiltros((f) => ({ ...f, ...cambios })), []);

  const filtrarDesde = useCallback((dimension: string, fila: FilaDesglose) => {
    const clave = FILTRO_DE_DIMENSION[dimension];
    if (!clave || fila.clave === null) return;
    const esId = clave.endsWith("_id");
    setFiltros((f) => ({ ...f, [clave]: esId ? Number(fila.clave) : fila.clave }));
    if (esId) setEtiquetas((e) => ({ ...e, [clave]: fila.nombre }));
  }, []);

  return (
    <Layout className="app">
      <Encabezado usuario={usuario} estado={estado.datos} modo={modo} onCambiarModo={onCambiarModo} onSalir={onSalir} />
      <Layout.Content className="contenido">
        <Tabs
          activeKey={pestana}
          onChange={(k) => {
            setPestana(k as Pestana);
            if (k === "asistente") setAsistenteAbierto(true);
          }}
          items={[
            {
              key: "historico",
              label: "Análisis histórico",
              icon: <BarChartOutlined />,
              children: (
                <div className="pestana">
                  <BarraFiltros
                    filtros={filtros}
                    etiquetas={etiquetas}
                    opciones={opciones.datos}
                    onCambiar={cambiar}
                    onLimpiar={() => {
                      setFiltros(porDefecto());
                      setEtiquetas({});
                    }}
                  />
                  <TarjetasKpi datos={kpis.datos} cargando={kpis.cargando || !listo} error={kpis.error} reintentar={kpis.recargar} />
                  {listo && (
                    <>
                      <Row gutter={[12, 12]}>
                        <Col xs={24} xl={15}>
                          <GraficoTendencia params={params} />
                        </Col>
                        <Col xs={24} xl={9}>
                          <GraficoDesglose params={params} onFiltrar={filtrarDesde} />
                        </Col>
                      </Row>
                      <TablaFacturas key={JSON.stringify(params)} params={params} onAbrir={setFacturaAbierta} />
                    </>
                  )}
                </div>
              ),
            },
            {
              key: "pronostico",
              label: "Pronóstico (predicción)",
              icon: <LineChartOutlined />,
              // Solo se pide a la API cuando se abre la pestaña
              children: pestana === "pronostico" ? <PanelPronostico /> : null,
            },
            {
              key: "asistente",
              label: "Asistente (IA)",
              icon: <RobotOutlined />,
              children: asistenteAbierto ? <PanelAsistente /> : null,
            },
            {
              key: "alertas",
              label: (
                <Badge
                  count={alertas.datos?.nuevas ?? 0}
                  size="small"
                  offset={[10, -2]}
                  color={alertas.datos?.criticas_nuevas ? "red" : "blue"}
                  title={`${alertas.datos?.nuevas ?? 0} alerta(s) nueva(s)`}
                >
                  <span>
                    <AlertOutlined /> Alertas
                  </span>
                </Badge>
              ),
              children: pestana === "alertas" ? <PanelAlertas onCambio={alertas.recargar} /> : null,
            },
            {
              key: "operacion",
              label: "Operación",
              icon: <DashboardOutlined />,
              children: pestana === "operacion" ? <PanelOperacion /> : null,
            },
          ]}
        />
        <Typography.Paragraph type="secondary" className="pie">
          Faro · Todos los indicadores provienen del Data Warehouse. Las ventas a partir del 1-jun-2016 son
          <b> simuladas</b> para la demostración y se pueden excluir con el filtro «Incluir simulados». El pronóstico es una
          <b> predicción</b> del modelo de Machine Learning, no un dato histórico.
        </Typography.Paragraph>
      </Layout.Content>
      <DetalleFactura facturaId={facturaAbierta} onCerrar={() => setFacturaAbierta(null)} />
    </Layout>
  );
}
