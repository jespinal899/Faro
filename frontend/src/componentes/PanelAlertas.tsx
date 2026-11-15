import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Descriptions, Drawer, Input, Segmented, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ExperimentOutlined,
  MailOutlined,
  ReloadOutlined,
  RobotOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { pedir } from "../api";
import { useApi } from "../hooks/useApi";
import { useIntervalo } from "../hooks/useIntervalo";
import { fFecha, fFechaHora, fMoneda, fMonedaDecimal, fPorcentaje, fSemana } from "../formato";
import type { Alerta, DetalleAlerta, EstadoAlerta, Severidad } from "../tipos";
import { Cargando, ErrorCarga, SinDatos } from "./Estados";

/** Cada cuánto se vuelve a consultar la lista (las alertas se generan al terminar cada carga). */
export const INTERVALO_ALERTAS_MS = 60_000;

type Filtro = "nuevas" | "seguimiento" | "cerradas" | "todas";

const FILTROS: Record<Filtro, EstadoAlerta[] | null> = {
  nuevas: ["nueva"],
  seguimiento: ["atendida"],
  cerradas: ["resuelta", "descartada"],
  todas: null,
};

export const ESTADOS: Record<EstadoAlerta, { texto: string; color: string; icono: ReactNode }> = {
  nueva: { texto: "Nueva", color: "blue", icono: <ExclamationCircleOutlined /> },
  atendida: { texto: "Atendida", color: "gold", icono: <ClockCircleOutlined /> },
  resuelta: { texto: "Resuelta", color: "green", icono: <CheckCircleOutlined /> },
  descartada: { texto: "Descartada", color: "default", icono: <CloseCircleOutlined /> },
};

// La severidad se dice con ícono y palabra, nunca solo con color
export function EtiquetaSeveridad({ severidad }: { severidad: Severidad }) {
  return severidad === "critica" ? (
    <Tag color="red" icon={<ExclamationCircleOutlined />}>
      Crítica
    </Tag>
  ) : (
    <Tag color="orange" icon={<WarningOutlined />}>
      Advertencia
    </Tag>
  );
}

export function EtiquetaEstado({ estado }: { estado: EstadoAlerta }) {
  const e = ESTADOS[estado];
  return (
    <Tag color={e.color} icon={e.icono}>
      {e.texto}
    </Tag>
  );
}

function EtiquetaCorreo({ a }: { a: Alerta }) {
  if (a.correo_enviado) {
    return (
      <Tooltip title={`Enviado el ${fFechaHora(a.ultimo_intento)} (${a.intentos_correo} intento/s)`}>
        <Tag color="green" icon={<MailOutlined />}>
          Enviado
        </Tag>
      </Tooltip>
    );
  }
  return (
    <Tag color={a.intentos_correo ? "red" : "default"} icon={<MailOutlined />}>
      {a.intentos_correo ? `Falló (${a.intentos_correo} intento/s)` : "Pendiente"}
    </Tag>
  );
}

const periodo = (a: Alerta) =>
  a.periodo_desde === a.periodo_hasta ? fFecha(a.periodo_desde) : `${fSemana(a.periodo_desde)} – ${fSemana(a.periodo_hasta)}`;

/** Los campos del detalle, en palabras (cada regla guarda los suyos). */
function filasDetalle(d: Record<string, unknown>): { etiqueta: string; valor: string }[] {
  const lista = (v: unknown) => (Array.isArray(v) ? v.map((x) => fSemana(String(x))).join(", ") : String(v));
  const conocidos: Record<string, [string, (v: unknown) => string]> = {
    caida_pct: ["Caída", (v) => fPorcentaje(Number(v))],
    umbral_pct: ["Umbral de caída", (v) => fPorcentaje(Number(v))],
    semanas_referencia: ["Semanas de referencia", lista],
    horizonte: ["Horizonte", (v) => `${v} semana(s) adelante`],
    version_modelo: ["Versión del modelo", String],
    origen_pronostico: ["Pronosticado desde la semana del", (v) => fFecha(String(v))],
    rango_80: ["Rango probable del 80 %", (v) => (Array.isArray(v) ? `${fMoneda(Number(v[0]))} – ${fMoneda(Number(v[1]))}` : String(v))],
    semanas_bajo_umbral: ["Semanas bajo el umbral", lista],
    lineas: ["Líneas vendidas bajo costo", String],
    facturas: ["Facturas", String],
    // Con centavos: es la cifra exacta que cita el mensaje calculado
    venta_neta: ["Venta neta de esas líneas", (v) => fMonedaDecimal(Number(v))],
  };
  return Object.entries(d).map(([clave, valor]) => {
    const c = conocidos[clave];
    return c ? { etiqueta: c[0], valor: c[1](valor) } : { etiqueta: clave, valor: JSON.stringify(valor) };
  });
}

function DetalleDeAlerta({ alertaId, onCambio }: { alertaId: number; onCambio: () => void }) {
  const { datos, cargando, error, recargar } = useApi<DetalleAlerta>(`/api/alertas/${alertaId}`);
  const [estado, setEstado] = useState<EstadoAlerta | null>(null);
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null);

  const a = datos?.alerta_id === alertaId ? datos : undefined;
  useEffect(() => {
    if (a) {
      setEstado(a.estado);
      setNota(a.nota ?? "");
    }
  }, [a]);

  if (error) return <ErrorCarga mensaje={error} reintentar={recargar} />;
  if (cargando && !a) return <Cargando filas={8} />;
  if (!a) return null;

  const guardar = async () => {
    if (!estado) return;
    setGuardando(true);
    setResultado(null);
    try {
      await pedir<DetalleAlerta>(`/api/alertas/${a.alerta_id}`, { metodo: "PATCH", cuerpo: { estado, nota } });
      setResultado({ ok: true, texto: `Estado guardado: ${ESTADOS[estado].texto}.` });
      recargar();
      onCambio();
    } catch (e) {
      setResultado({ ok: false, texto: (e as Error).message });
    } finally {
      setGuardando(false);
    }
  };
  const esModelo = a.origen === "modelo";

  return (
    <Space orientation="vertical" size={14} style={{ width: "100%" }}>
      <Space wrap size={4}>
        <EtiquetaSeveridad severidad={a.severidad} />
        <EtiquetaEstado estado={a.estado} />
        <Tag>{esModelo ? "Modelo de Machine Learning" : "Regla de negocio"}</Tag>
        {a.incluye_simulados && (
          <Tag color="purple" icon={<ExperimentOutlined />}>
            Incluye ventas SIMULADAS
          </Tag>
        )}
      </Space>

      <Typography.Paragraph style={{ margin: 0 }}>{a.mensaje}</Typography.Paragraph>

      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="Identificador">#{a.alerta_id}</Descriptions.Item>
        <Descriptions.Item label="Generada">{fFechaHora(a.creada_en)}</Descriptions.Item>
        <Descriptions.Item label="Tipo">{a.regla_nombre}</Descriptions.Item>
        <Descriptions.Item label="Indicador">{a.indicador}</Descriptions.Item>
        <Descriptions.Item label="Entidad">{a.entidad}</Descriptions.Item>
        <Descriptions.Item label={esModelo ? "Predicción" : "Valor observado"}>
          <b>{fMoneda(a.valor_observado)}</b>
        </Descriptions.Item>
        <Descriptions.Item label="Umbral">{fMoneda(a.umbral)}</Descriptions.Item>
        {a.referencia !== null && <Descriptions.Item label="Referencia">{fMoneda(a.referencia)}</Descriptions.Item>}
        <Descriptions.Item label="Período">
          {fFecha(a.periodo_desde)} al {fFecha(a.periodo_hasta)}
        </Descriptions.Item>
        {filasDetalle(a.detalle).map((f) => (
          <Descriptions.Item key={f.etiqueta} label={f.etiqueta}>
            {f.valor}
          </Descriptions.Item>
        ))}
      </Descriptions>

      <Card
        size="small"
        title={
          <Space size={6}>
            <RobotOutlined />
            Explicación y acción recomendada
            <Tag color="geekblue">GENERADO POR IA</Tag>
          </Space>
        }
      >
        {a.explicacion_ia ? (
          <>
            <Typography.Paragraph>{a.explicacion_ia}</Typography.Paragraph>
            {a.accion_recomendada_ia && (
              <Typography.Paragraph>
                <b>Acción recomendada:</b> {a.accion_recomendada_ia}
              </Typography.Paragraph>
            )}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Redactado por {a.ia_modelo ?? "un modelo de IA"} a partir de los datos de la alerta. Puede equivocarse: las
              cifras de arriba son las calculadas.
            </Typography.Text>
          </>
        ) : (
          <Typography.Text type="secondary">
            Sin explicación de IA (el servicio no respondió). Los datos de la alerta son los calculados por la regla.
          </Typography.Text>
        )}
      </Card>

      <Card size="small" title="Entrega por correo">
        {a.envios.length === 0 ? (
          <Typography.Text type="secondary">Todavía no se intentó enviar.</Typography.Text>
        ) : (
          <Table
            size="small"
            rowKey={(e) => `${e.intentado_en}-${e.intento}`}
            pagination={false}
            dataSource={a.envios}
            columns={[
              { title: "Intento", dataIndex: "intento", width: 70 },
              { title: "Fecha y hora", render: (_, e) => fFechaHora(e.intentado_en) },
              {
                title: "Resultado",
                render: (_, e) =>
                  e.resultado === "enviado" ? (
                    <Tag color="green">Enviado</Tag>
                  ) : (
                    <Tooltip title={e.error}>
                      <Tag color="red">Falló</Tag>
                    </Tooltip>
                  ),
              },
            ]}
          />
        )}
      </Card>

      <Card size="small" title="Estado">
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          {a.estado_actualizado_en && (
            <Typography.Text type="secondary">
              Último cambio: {ESTADOS[a.estado].texto.toLowerCase()} por {a.estado_actualizado_por} el{" "}
              {fFechaHora(a.estado_actualizado_en)}
            </Typography.Text>
          )}
          <Select<EstadoAlerta>
            aria-label="Nuevo estado"
            value={estado ?? undefined}
            onChange={setEstado}
            options={(Object.keys(ESTADOS) as EstadoAlerta[]).map((k) => ({
              value: k,
              label: k === "nueva" ? "Nueva (reabrir)" : ESTADOS[k].texto,
            }))}
            style={{ width: "100%" }}
          />
          <Input.TextArea
            aria-label="Nota"
            placeholder="Nota opcional: qué se revisó o se hizo"
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            maxLength={500}
            showCount
            autoSize={{ minRows: 2, maxRows: 5 }}
          />
          <Button type="primary" onClick={guardar} loading={guardando} disabled={!estado}>
            Guardar estado
          </Button>
          {resultado && <Alert type={resultado.ok ? "success" : "error"} showIcon title={resultado.texto} />}
        </Space>
      </Card>
    </Space>
  );
}

interface Props {
  /** Se llama cuando cambia el estado de una alerta (para actualizar el contador). */
  onCambio?: () => void;
}

export default function PanelAlertas({ onCambio }: Props) {
  const { datos, cargando, error, recargar } = useApi<Alerta[]>("/api/alertas", { limite: 200 });
  const [filtro, setFiltro] = useState<Filtro>("nuevas");
  const [abierta, setAbierta] = useState<number | null>(null);
  const [actualizado, setActualizado] = useState<Date | null>(null);
  useIntervalo(recargar, INTERVALO_ALERTAS_MS);
  useEffect(() => {
    if (datos) setActualizado(new Date());
  }, [datos]);

  const alertas = useMemo(() => datos ?? [], [datos]);
  const cuenta = (f: Filtro) => alertas.filter((a) => FILTROS[f]?.includes(a.estado) ?? true).length;
  const visibles = alertas.filter((a) => FILTROS[filtro]?.includes(a.estado) ?? true);

  if (error && !datos) return <ErrorCarga mensaje={error} reintentar={recargar} />;

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        title="Alertas automáticas"
        description={
          <>
            Se evalúan al terminar cada carga del ETL y cada pronóstico: caída de ventas, pronóstico bajo el umbral (Machine
            Learning) y ventas bajo costo. Cada alerta se envía por correo y aquí se registra su seguimiento. La explicación
            y la acción recomendada las redacta una IA y se identifican como tales. La lista se actualiza cada minuto.
          </>
        }
      />
      <Card
        size="small"
        title="Alertas"
        extra={
          <Space wrap size={6}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {actualizado && `Actualizado ${actualizado.toLocaleTimeString("es-419", { hour: "2-digit", minute: "2-digit" })}`}
            </Typography.Text>
            <Button size="small" icon={<ReloadOutlined />} onClick={recargar} loading={cargando} aria-label="Actualizar alertas" />
          </Space>
        }
      >
        <Segmented<Filtro>
          value={filtro}
          onChange={setFiltro}
          style={{ marginBottom: 12 }}
          options={[
            { value: "nuevas", label: `Nuevas (${cuenta("nuevas")})` },
            { value: "seguimiento", label: `Atendidas (${cuenta("seguimiento")})` },
            { value: "cerradas", label: `Cerradas (${cuenta("cerradas")})` },
            { value: "todas", label: `Todas (${alertas.length})` },
          ]}
        />
        {cargando && !datos ? (
          <Cargando filas={5} />
        ) : visibles.length === 0 ? (
          <SinDatos texto={filtro === "nuevas" ? "No hay alertas nuevas." : "No hay alertas en este estado."} />
        ) : (
          <Table<Alerta>
            size="small"
            rowKey="alerta_id"
            dataSource={visibles}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            scroll={{ x: true }}
            onRow={(a) => ({ onClick: () => setAbierta(a.alerta_id), style: { cursor: "pointer" } })}
            columns={[
              { title: "Generada", render: (_, a) => <span className="num">{fFechaHora(a.creada_en)}</span> },
              { title: "Severidad", render: (_, a) => <EtiquetaSeveridad severidad={a.severidad} /> },
              {
                title: "Alerta",
                render: (_, a) => (
                  <div style={{ minWidth: 220 }}>
                    <b>{a.regla_nombre}</b> · {a.entidad}
                    {a.incluye_simulados && (
                      <Tag color="purple" style={{ marginLeft: 6 }}>
                        Simulado
                      </Tag>
                    )}
                    <div>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {a.indicador}
                      </Typography.Text>
                    </div>
                  </div>
                ),
              },
              { title: "Período", render: (_, a) => <span className="num">{periodo(a)}</span> },
              {
                title: "Valor / umbral",
                align: "right",
                className: "num",
                render: (_, a) => `${fMoneda(a.valor_observado)} / ${fMoneda(a.umbral)}`,
              },
              { title: "Correo", render: (_, a) => <EtiquetaCorreo a={a} /> },
              { title: "Estado", render: (_, a) => <EtiquetaEstado estado={a.estado} /> },
              {
                title: "",
                render: (_, a) => (
                  <Button size="small" type="link" onClick={() => setAbierta(a.alerta_id)}>
                    Ver detalle
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Drawer
        open={abierta !== null}
        onClose={() => setAbierta(null)}
        size="min(600px, 100vw)"
        title={abierta !== null ? `Alerta #${abierta}` : ""}
        destroyOnHidden
      >
        {abierta !== null && (
          <DetalleDeAlerta
            alertaId={abierta}
            onCambio={() => {
              recargar();
              onCambio?.();
            }}
          />
        )}
      </Drawer>
    </Space>
  );
}
