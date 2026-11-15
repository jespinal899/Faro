import { Alert, Card, Col, Progress, Row, Space, Table, Tag, Tooltip, Typography } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, SyncOutlined, WarningOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { useApi } from "../hooks/useApi";
import { useIntervalo } from "../hooks/useIntervalo";
import { fEntero, fFecha, fFechaHora, fPorcentaje } from "../formato";
import type { EjecucionEtl, EstadoAlerta, EvaluacionAlertas, RespuestaMonitoreo } from "../tipos";
import { Cargando, ErrorCarga } from "./Estados";
import { ESTADOS } from "./PanelAlertas";

dayjs.extend(relativeTime);

export const INTERVALO_MONITOREO_MS = 60_000;
/** El ETL está programado cada hora: más de 2 horas sin una carga exitosa es un retraso. */
const HORAS_ATRASO = 2;

function EtiquetaEjecucion({ estado }: { estado: string }) {
  if (estado === "exitoso" || estado === "exitosa")
    return (
      <Tag color="green" icon={<CheckCircleOutlined />}>
        Exitosa
      </Tag>
    );
  if (estado === "fallido" || estado === "fallida")
    return (
      <Tag color="red" icon={<CloseCircleOutlined />}>
        Fallida
      </Tag>
    );
  return (
    <Tag color="blue" icon={<SyncOutlined spin />}>
      En curso
    </Tag>
  );
}

const DISPARADORES: Record<string, string> = { cron: "Programada", manual: "Manual", ci: "CI", demo: "Demo" };
const disparador = (d: string) => DISPARADORES[d] ?? d;

function Frescura({ ultima }: { ultima?: EjecucionEtl }) {
  if (!ultima) return <Alert type="warning" showIcon title="Todavía no hay ejecuciones del ETL." />;
  const horas = ultima.fin ? dayjs().diff(dayjs(ultima.fin), "hour", true) : null;
  const fallo = ultima.estado === "fallido";
  const atrasado = horas !== null && horas > HORAS_ATRASO;
  return (
    <Alert
      type={fallo ? "error" : atrasado ? "warning" : "success"}
      showIcon
      title={
        fallo
          ? `La última ejecución del ETL (#${ultima.ejecucion_id}) falló`
          : atrasado
            ? `Sin cargas en las últimas ${Math.floor(horas)} horas`
            : "El ETL está al día"
      }
      description={
        <>
          Última ejecución: #{ultima.ejecucion_id}, {disparador(ultima.disparador).toLowerCase()}, terminó{" "}
          {ultima.fin ? `${fFechaHora(ultima.fin)} (${dayjs(ultima.fin).fromNow()})` : "— (sigue en curso)"}.
          {fallo && ultima.error && <> Error: {ultima.error}</>}
          {atrasado && !fallo && (
            <> El ETL se programa cada hora, pero GitHub puede retrasar o saltarse las ejecuciones programadas.</>
          )}
        </>
      }
    />
  );
}

export default function PanelOperacion() {
  const { datos, cargando, error, recargar } = useApi<RespuestaMonitoreo>("/api/monitoreo");
  useIntervalo(recargar, INTERVALO_MONITOREO_MS);

  if (error && !datos) return <ErrorCarga mensaje={error} reintentar={recargar} />;
  if (cargando && !datos) return <Cargando filas={10} />;
  if (!datos) return null;

  const { etl, dimensiones, calidad, cuarentena, modelo, notificaciones: n } = datos;
  const pendientes = cuarentena.reduce((s, c) => s + c.pendientes, 0);
  const fallidas = etl.filter((e) => e.estado === "fallido").length;

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      <Frescura ultima={etl[0]} />

      <Card size="small" title="Ejecuciones del ETL (fuente → staging → Data Warehouse)" extra={fallidas > 0 && <Tag color="red">{fallidas} fallida(s)</Tag>}>
        <Table<EjecucionEtl>
          size="small"
          rowKey="ejecucion_id"
          dataSource={etl}
          pagination={{ pageSize: 5, hideOnSinglePage: true }}
          scroll={{ x: true }}
          columns={[
            { title: "#", dataIndex: "ejecucion_id", width: 50 },
            { title: "Inicio", render: (_, e) => <span className="num">{fFechaHora(e.inicio)}</span> },
            { title: "Disparo", render: (_, e) => `${disparador(e.disparador)} · ${e.modo}` },
            {
              title: "Estado",
              render: (_, e) =>
                e.error ? (
                  <Tooltip title={e.error}>
                    <span>
                      <EtiquetaEjecucion estado={e.estado} />
                    </span>
                  </Tooltip>
                ) : (
                  <EtiquetaEjecucion estado={e.estado} />
                ),
            },
            { title: "Leídas", align: "right", className: "num", render: (_, e) => fEntero(e.leidas) },
            { title: "Nuevas", align: "right", className: "num", render: (_, e) => fEntero(e.nuevas) },
            { title: "Actualizadas", align: "right", className: "num", render: (_, e) => fEntero(e.actualizadas) },
            {
              title: "Rechazadas",
              align: "right",
              className: "num",
              render: (_, e) => (e.rechazadas > 0 ? <b>{fEntero(e.rechazadas)}</b> : fEntero(e.rechazadas)),
            },
            {
              title: "Reconciliada",
              render: (_, e) =>
                e.reconciliado === null ? "—" : e.reconciliado ? <Tag color="green">Sí</Tag> : <Tag color="red">No</Tag>,
            },
            { title: "Duración", align: "right", className: "num", render: (_, e) => (e.segundos === null ? "—" : `${e.segundos} s`) },
          ]}
        />
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} xl={14}>
          <Card
            size="small"
            title="Calidad de datos por dimensión"
            extra={
              datos.calidad_ejecucion_id && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Ejecución #{datos.calidad_ejecucion_id} · {calidad.length} reglas
                </Typography.Text>
              )
            }
          >
            {dimensiones.length === 0 ? (
              <Typography.Text type="secondary">Sin resultados de calidad todavía.</Typography.Text>
            ) : (
              <Table
                size="small"
                rowKey="dimension"
                pagination={false}
                dataSource={dimensiones}
                columns={[
                  { title: "Dimensión", dataIndex: "dimension" },
                  { title: "Reglas", align: "right", className: "num", dataIndex: "reglas" },
                  { title: "Filas evaluadas", align: "right", className: "num", render: (_, d) => fEntero(d.evaluadas) },
                  { title: "Incumplen", align: "right", className: "num", render: (_, d) => fEntero(d.fallaron) },
                  {
                    title: "Cumplimiento",
                    render: (_, d) =>
                      d.cumplimiento_pct === null ? (
                        <Typography.Text type="secondary">Sin filas en esta carga</Typography.Text>
                      ) : (
                        <Tooltip title={fPorcentaje(d.cumplimiento_pct)}>
                          <Progress
                            percent={Math.floor(d.cumplimiento_pct * 10) / 10}
                            size="small"
                            status={d.fallaron > 0 ? "exception" : "success"}
                            format={(p) => `${p} %`}
                            style={{ minWidth: 120, margin: 0 }}
                          />
                        </Tooltip>
                      ),
                  },
                ]}
              />
            )}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Registros en cuarentena pendientes de corrección: <b>{fEntero(pendientes)}</b>
              {cuarentena.length > 0 &&
                ` (${cuarentena
                  .filter((c) => c.pendientes > 0)
                  .map((c) => `${c.tabla} · ${c.regla}: ${c.pendientes}`)
                  .join("; ")})`}
              . Se reintentan en cada ejecución.
            </Typography.Text>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card size="small" title="Modelo de pronóstico vigente" style={{ marginBottom: 12 }}>
            {modelo ? (
              <Space orientation="vertical" size={2}>
                <Typography.Text>
                  Versión <b>{modelo.version}</b> · entrenado el {fFechaHora(modelo.entrenado_en)}
                </Typography.Text>
                <Typography.Text type="secondary">
                  Datos hasta la semana del {fFecha(modelo.datos_hasta)}
                  {modelo.commit_codigo && ` · código ${modelo.commit_codigo}`}
                </Typography.Text>
                <Typography.Text>
                  Error en prueba (WAPE): {fPorcentaje(modelo.wape_prueba)} · línea base {fPorcentaje(modelo.wape_prueba_linea_base)}
                </Typography.Text>
                <Typography.Text>
                  Último pronóstico: {fFechaHora(modelo.pronostico_generado_en)} (desde la semana del{" "}
                  {fFecha(modelo.pronostico_origen)})
                </Typography.Text>
              </Space>
            ) : (
              <Typography.Text type="secondary">Todavía no hay un modelo vigente.</Typography.Text>
            )}
          </Card>

          <Card size="small" title="Notificaciones">
            <Space wrap size={4} style={{ marginBottom: 8 }}>
              {(Object.keys(ESTADOS) as EstadoAlerta[]).map((k) => (
                <Tag key={k} color={ESTADOS[k].color} icon={ESTADOS[k].icono}>
                  {ESTADOS[k].texto}: {n.alertas_por_estado[k] ?? 0}
                </Tag>
              ))}
            </Space>
            <div>
              <Typography.Text>
                Correos enviados: <b>{n.correos_enviados}</b> · intentos fallidos: {n.intentos_fallidos}
              </Typography.Text>
            </div>
            {n.alertas_sin_entregar > 0 && (
              <Alert
                type="warning"
                showIcon
                icon={<WarningOutlined />}
                style={{ margin: "8px 0" }}
                title={`${n.alertas_sin_entregar} alerta(s) sin correo entregado: se reintentan en la próxima evaluación.`}
              />
            )}
            <Table<EvaluacionAlertas>
              size="small"
              rowKey="evaluacion_id"
              pagination={{ pageSize: 5, hideOnSinglePage: true }}
              dataSource={n.evaluaciones}
              style={{ marginTop: 8 }}
              columns={[
                { title: "Evaluación", render: (_, e) => <span className="num">{fFechaHora(e.inicio)}</span> },
                { title: "Disparo", render: (_, e) => disparador(e.disparador) },
                {
                  title: "Estado",
                  render: (_, e) =>
                    e.error ? (
                      <Tooltip title={e.error}>
                        <span>
                          <EtiquetaEjecucion estado={e.estado} />
                        </span>
                      </Tooltip>
                    ) : (
                      <EtiquetaEjecucion estado={e.estado} />
                    ),
                },
                { title: "Nuevas", align: "right", className: "num", dataIndex: "alertas_nuevas" },
                { title: "Correos", align: "right", className: "num", dataIndex: "correos_enviados" },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
