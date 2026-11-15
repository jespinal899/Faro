import { useMemo, useState } from "react";
import { Alert, Card, Col, Empty, Row, Segmented, Select, Space, Table, Tag, Typography } from "antd";
import { LineChartOutlined, TableOutlined } from "@ant-design/icons";
import { usePaleta } from "../contexto";
import { useApi } from "../hooks/useApi";
import { fFecha, fFechaHora, fMoneda, fPorcentaje, fSemana } from "../formato";
import type { PuntoPronostico, PuntoPrueba, RespuestaPronostico, SerieGrupo } from "../tipos";
import { Cargando, ErrorCarga } from "./Estados";
import Grafico from "./Grafico";
import { NOMBRES, opcionEvaluacion, opcionPronostico } from "./GraficosPronostico";

type Vista = "grafico" | "tabla";

const OPCIONES_VISTA = [
  { value: "grafico", icon: <LineChartOutlined />, title: "Ver gráfico" },
  { value: "tabla", icon: <TableOutlined />, title: "Ver tabla" },
];

const totalPronosticado = (g: SerieGrupo) => g.pronostico.reduce((s, x) => s + x.venta_neta, 0);

/** Fila de la vista de tabla del gráfico: una semana con su venta real y/o su pronóstico. */
interface FilaSemana {
  semana: string;
  real?: number;
  simulada?: boolean;
  p?: PuntoPronostico;
}

function filasSemana(serie: SerieGrupo): FilaSemana[] {
  const semanas = [...new Set([...serie.historia.map((h) => h.semana), ...serie.pronostico.map((x) => x.semana)])].sort();
  return semanas.map((semana) => {
    const h = serie.historia.find((x) => x.semana === semana);
    return {
      semana,
      real: h?.venta_neta,
      simulada: h?.incluye_simulados,
      p: serie.pronostico.find((x) => x.semana === semana),
    };
  });
}

/** Fila del resumen: un grupo con su pronóstico, o un grupo excluido con su motivo. */
interface FilaResumen {
  grupo: string;
  pronostico?: PuntoPronostico[];
  wape?: number | null;
  motivo?: string;
}

/** Diferencia de error entre modelo y línea base, dicha en palabras (no solo con color). */
function Comparacion({ modelo, base }: { modelo: number; base: number }) {
  const mejora = 100 * (1 - modelo / base);
  if (Math.abs(modelo - base) < 0.5) return <Tag>Empatan</Tag>;
  return mejora > 0 ? (
    <Tag color="green">{fPorcentaje(mejora)} menos error</Tag>
  ) : (
    <Tag color="orange">{fPorcentaje(-mejora)} más error</Tag>
  );
}

export default function PanelPronostico() {
  const { paleta } = usePaleta();
  const { datos, cargando, error, recargar } = useApi<RespuestaPronostico>("/api/pronostico");
  const [grupoElegido, setGrupoElegido] = useState<string | null>(null);
  const [vista, setVista] = useState<Vista>("grafico");
  const [vistaPrueba, setVistaPrueba] = useState<Vista>("grafico");
  const [horizonte, setHorizonte] = useState(1);

  const grupos = useMemo(() => datos?.grupos ?? [], [datos]);
  // Por defecto, el grupo con más venta pronosticada
  const grupo =
    grupoElegido ?? [...grupos].sort((a, b) => totalPronosticado(b) - totalPronosticado(a))[0]?.grupo ?? null;
  const serie = grupos.find((g) => g.grupo === grupo);
  const prueba = useApi<PuntoPrueba[]>(grupo ? "/api/pronostico/evaluacion" : null, { grupo: grupo ?? "", horizonte });

  const opcion = useMemo(
    () => (serie && datos?.origen ? opcionPronostico(serie, datos.origen, paleta) : null),
    [serie, datos, paleta],
  );
  const calidad = datos?.modelo?.calidad;
  const opcionPrueba = useMemo(
    () => (prueba.datos && calidad ? opcionEvaluacion(prueba.datos, calidad.linea_base, paleta) : null),
    [prueba.datos, calidad, paleta],
  );

  if (error) return <ErrorCarga mensaje={error} reintentar={recargar} />;
  if (cargando && !datos) return <Cargando filas={8} />;
  if (!datos?.disponible || !datos.modelo || !calidad || !datos.origen) {
    return (
      <Card>
        <Empty description="Todavía no hay un pronóstico registrado. Se genera con el proceso «ML - Pronóstico» (cada lunes, o a mano)." />
      </Card>
    );
  }
  const modelo = datos.modelo;
  const semanas = grupos[0]?.pronostico.map((x) => x.semana) ?? [];

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        title="Esto es una PREDICCIÓN, no un dato histórico"
        description={
          <>
            Modelo <b>{modelo.version}</b>, entrenado el {fFechaHora(modelo.entrenado_en)} solo con ventas reales hasta la
            semana del {fFecha(modelo.datos_hasta)}. Pronóstico generado el {fFechaHora(datos.generado_en)} a partir de la
            última semana completa (del {fFecha(datos.origen)}).
            {datos.usa_datos_simulados && " La historia usada incluye ventas simuladas."} Los filtros del análisis histórico no
            aplican aquí: se pronostica cada grupo completo.
          </>
        }
      />

      <Row gutter={[12, 12]}>
        <Col xs={24} xl={15}>
          <Card
            size="small"
            title="Pronóstico semanal por grupo"
            extra={
              <Space wrap size={6}>
                <Select
                  aria-label="Grupo de producto"
                  size="small"
                  value={grupo}
                  onChange={setGrupoElegido}
                  options={grupos.map((g) => ({ value: g.grupo, label: g.grupo }))}
                  style={{ width: 190 }}
                />
                <Segmented size="small" value={vista} onChange={(v) => setVista(v as Vista)} options={OPCIONES_VISTA} />
              </Space>
            }
          >
            {serie && vista === "grafico" && opcion && (
              <Grafico
                opcion={opcion}
                alto={340}
                etiqueta={`Ventas reales y pronóstico de las próximas 4 semanas de ${serie.grupo}, con su rango probable del 80 %`}
              />
            )}
            {serie && vista === "tabla" && (
              <Table<FilaSemana>
                size="small"
                rowKey="semana"
                pagination={false}
                scroll={{ x: true }}
                dataSource={filasSemana(serie)}
                columns={[
                  { title: "Semana", render: (_, f) => fSemana(f.semana) },
                  {
                    title: NOMBRES.real,
                    align: "right",
                    className: "num",
                    render: (_, f) => (f.real === undefined ? "—" : `${fMoneda(f.real)}${f.simulada ? " *" : ""}`),
                  },
                  { title: NOMBRES.pronostico, align: "right", className: "num", render: (_, f) => fMoneda(f.p?.venta_neta) },
                  {
                    title: NOMBRES.rango,
                    align: "right",
                    className: "num",
                    render: (_, f) => (f.p ? `${fMoneda(f.p.inferior)} – ${fMoneda(f.p.superior)}` : "—"),
                  },
                ]}
              />
            )}
            {serie && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Error típico de {serie.grupo} en las semanas de prueba: {fPorcentaje(serie.wape_prueba)} (línea base{" "}
                {fPorcentaje(serie.wape_prueba_linea_base)}).
                {serie.historia.some((h) => h.incluye_simulados) && " * Semana con ventas simuladas."}
              </Typography.Text>
            )}
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card size="small" title="Calidad del modelo">
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <div>
                <Typography.Text type="secondary">Error en semanas que el modelo no vio (WAPE)</Typography.Text>
                <div className="kpi-valor" data-testid="wape-prueba">
                  {fPorcentaje(calidad.wape_prueba_modelo)}
                </div>
                <Typography.Text>
                  Línea base: {fPorcentaje(calidad.wape_prueba_linea_base)}{" "}
                  <Comparacion modelo={calidad.wape_prueba_modelo} base={calidad.wape_prueba_linea_base} />
                </Typography.Text>
              </div>
              <Typography.Text>
                Validación de un año: {fPorcentaje(calidad.wape_validacion_modelo)} contra{" "}
                {fPorcentaje(calidad.wape_validacion_linea_base)}{" "}
                <Comparacion modelo={calidad.wape_validacion_modelo} base={calidad.wape_validacion_linea_base} />
              </Typography.Text>
              <Typography.Text>
                El rango probable contuvo lo vendido el <b>{fPorcentaje(calidad.cobertura_prueba_pct)}</b> de las veces
                (objetivo: {fPorcentaje(calidad.cobertura_objetivo_pct)}).
              </Typography.Text>
              <Table
                size="small"
                rowKey="horizonte"
                pagination={false}
                dataSource={calidad.por_horizonte}
                columns={[
                  { title: "Semanas adelante", dataIndex: "horizonte", align: "right" },
                  { title: "Modelo", align: "right", className: "num", render: (_, h) => fPorcentaje(h.wape_modelo) },
                  { title: "Línea base", align: "right", className: "num", render: (_, h) => fPorcentaje(h.wape_linea_base) },
                  { title: "Cobertura", align: "right", className: "num", render: (_, h) => fPorcentaje(h.cobertura_pct) },
                ]}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                WAPE: error como % del volumen vendido. Línea base: {calidad.linea_base_descripcion}. Prueba: semanas desde el{" "}
                {fFecha(modelo.prueba_desde)}. Algoritmo: <code>{modelo.algoritmo}</code>
                {modelo.commit_codigo && <> · commit {modelo.commit_codigo}</>}.
              </Typography.Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card size="small" title="Próximas 4 semanas, todos los grupos">
        <Table<FilaResumen>
          size="small"
          rowKey="grupo"
          pagination={false}
          scroll={{ x: true }}
          rowClassName={(f) => (f.grupo === grupo ? "fila-elegida" : "")}
          onRow={(f) => ({
            onClick: () => f.pronostico && setGrupoElegido(f.grupo),
            style: { cursor: f.pronostico ? "pointer" : undefined },
          })}
          dataSource={[
            ...grupos.map((g): FilaResumen => ({ grupo: g.grupo, pronostico: g.pronostico, wape: g.wape_prueba })),
            ...datos.excluidos.map((e): FilaResumen => ({ grupo: e.grupo, motivo: e.motivo })),
          ]}
          columns={[
            { title: "Grupo", dataIndex: "grupo" },
            ...semanas.map((s, i) => ({
              title: `${fSemana(s)}`,
              align: "right" as const,
              className: "num",
              onCell: (f: FilaResumen) => ({ colSpan: f.motivo ? (i === 0 ? semanas.length + 2 : 0) : 1 }),
              render: (_: unknown, f: FilaResumen) =>
                f.motivo ? (
                  <Typography.Text type="secondary">Sin pronóstico: {f.motivo}</Typography.Text>
                ) : (
                  fMoneda(f.pronostico?.[i]?.venta_neta)
                ),
            })),
            {
              title: "Total 4 semanas",
              align: "right" as const,
              className: "num",
              onCell: (f: FilaResumen) => ({ colSpan: f.motivo ? 0 : 1 }),
              render: (_: unknown, f: FilaResumen) =>
                fMoneda(f.pronostico?.reduce((s, x) => s + x.venta_neta, 0)),
            },
            {
              title: "Error típico",
              align: "right" as const,
              className: "num",
              onCell: (f: FilaResumen) => ({ colSpan: f.motivo ? 0 : 1 }),
              render: (_: unknown, f: FilaResumen) => fPorcentaje(f.wape),
            },
          ]}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0}>
                <b>Total pronosticado</b>
              </Table.Summary.Cell>
              {semanas.map((s, i) => (
                <Table.Summary.Cell key={s} index={i + 1} align="right" className="num">
                  {fMoneda(grupos.reduce((t, g) => t + (g.pronostico[i]?.venta_neta ?? 0), 0))}
                </Table.Summary.Cell>
              ))}
              <Table.Summary.Cell index={semanas.length + 1} align="right" className="num">
                <b>{fMoneda(grupos.reduce((t, g) => t + totalPronosticado(g), 0))}</b>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={semanas.length + 2} />
            </Table.Summary.Row>
          )}
        />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          Clic en un grupo para verlo en el gráfico. El total es la suma de los pronósticos (los rangos no se suman).
        </Typography.Text>
      </Card>

      {serie && serie.seguimiento.length > 0 && (
        <Card size="small" title={`Pronósticos anteriores frente a lo vendido · ${serie.grupo}`}>
          <Table
            size="small"
            rowKey={(f) => `${f.origen}-${f.semana}`}
            pagination={{ pageSize: 8, size: "small" }}
            scroll={{ x: true }}
            dataSource={serie.seguimiento}
            columns={[
              { title: "Semana", render: (_, f) => fSemana(f.semana) },
              { title: "Semanas adelante", dataIndex: "horizonte", align: "right" },
              { title: NOMBRES.pronostico, align: "right", className: "num", render: (_, f) => fMoneda(f.pronostico) },
              {
                title: "Vendido",
                align: "right",
                className: "num",
                render: (_, f) => `${fMoneda(f.real)}${f.real_incluye_simulados ? " *" : ""}`,
              },
              {
                title: "Dentro del rango",
                render: (_, f) => (f.real >= f.inferior && f.real <= f.superior ? "Sí" : "No"),
              },
            ]}
          />
        </Card>
      )}

      {serie && (
        <Card
          size="small"
          title={`¿Cómo le fue al modelo en semanas que no vio? · ${serie.grupo}`}
          extra={
            <Space wrap size={6}>
              <Segmented
                size="small"
                value={horizonte}
                onChange={(v) => setHorizonte(Number(v))}
                options={[1, 2, 3, 4].map((h) => ({ value: h, label: `${h} sem.`, title: `Pronosticado ${h} semana(s) antes` }))}
              />
              <Segmented size="small" value={vistaPrueba} onChange={(v) => setVistaPrueba(v as Vista)} options={OPCIONES_VISTA} />
            </Space>
          }
        >
          {prueba.error && <ErrorCarga mensaje={prueba.error} reintentar={prueba.recargar} />}
          {!prueba.error && vistaPrueba === "grafico" && opcionPrueba && (
            <Grafico
              opcion={opcionPrueba}
              alto={260}
              etiqueta={`Ventas reales de ${serie.grupo} en las semanas de prueba, frente al pronóstico del modelo y la línea base`}
            />
          )}
          {!prueba.error && vistaPrueba === "tabla" && (
            <Table
              size="small"
              rowKey="semana"
              pagination={false}
              scroll={{ x: true }}
              dataSource={prueba.datos ?? []}
              columns={[
                { title: "Semana", render: (_, f) => fSemana(f.semana) },
                { title: NOMBRES.real, align: "right", className: "num", render: (_, f) => fMoneda(f.real) },
                { title: NOMBRES.pronostico, align: "right", className: "num", render: (_, f) => fMoneda(f.pronostico) },
                { title: NOMBRES.base, align: "right", className: "num", render: (_, f) => fMoneda(f.linea_base) },
              ]}
            />
          )}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Línea continua: lo vendido · discontinua: lo que pronosticó el modelo {horizonte} semana(s) antes · gris: la línea
            base ({calidad.linea_base_descripcion}).
          </Typography.Text>
        </Card>
      )}
    </Space>
  );
}
