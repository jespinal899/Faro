import { useRef, useState } from "react";
import { Alert, Button, Card, Collapse, Empty, Input, List, Space, Tag, Typography } from "antd";
import { ClearOutlined, RobotOutlined, SendOutlined, UserOutlined } from "@ant-design/icons";
import { ErrorApi, pedir } from "../api";
import { useApi } from "../hooks/useApi";
import { fFecha } from "../formato";
import type { AfirmacionIA, ConsultaIA, InfoAsistente, RespuestaAsistente, TipoRespuestaIA } from "../tipos";
import { Cargando, ErrorCarga } from "./Estados";

const MAX_PREGUNTA = 500;
const TURNOS_DE_CONTEXTO = 3; // preguntas anteriores que acompañan a la nueva (seguimiento)

const TIPOS: Record<TipoRespuestaIA, { etiqueta: string; color: string }> = {
  respuesta: { etiqueta: "Respuesta", color: "blue" },
  sin_datos: { etiqueta: "Sin datos suficientes", color: "gold" },
  fuera_de_alcance: { etiqueta: "Fuera de alcance", color: "default" },
  aclaracion: { etiqueta: "Necesita aclaración", color: "purple" },
  error: { etiqueta: "No se pudo responder", color: "red" },
};

interface Turno {
  pregunta: string;
  respuesta?: RespuestaAsistente;
  error?: string;
}

function Afirmaciones({ titulo, items, etiqueta }: { titulo: string; items: AfirmacionIA[]; etiqueta?: string }) {
  if (!items.length) return null;
  return (
    <div className="ia-seccion">
      <Typography.Text strong>
        {titulo} {etiqueta && <Tag color="purple">{etiqueta}</Tag>}
      </Typography.Text>
      <ul>
        {items.map((a, i) => (
          <li key={i}>
            {a.texto}{" "}
            {a.consultas.map((n) => (
              <Tag key={n} className="ia-cita" title="Consulta al Data Warehouse que respalda esta cifra">
                consulta {n}
              </Tag>
            ))}
            {!a.respaldada && (
              <Tag color="orange" title="No cita una consulta válida: no la tomes como dato">
                Sin respaldo
              </Tag>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Consultas({ consultas }: { consultas: ConsultaIA[] }) {
  if (!consultas.length) return null;
  return (
    <Collapse
      size="small"
      ghost
      items={[
        {
          key: "consultas",
          label: `Datos consultados (${consultas.length})`,
          children: (
            <List
              size="small"
              dataSource={consultas}
              renderItem={(c) => (
                <List.Item>
                  <Space direction="vertical" size={2} style={{ width: "100%" }}>
                    <Typography.Text>
                      <b>Consulta {c.numero}.</b> {c.descripcion}
                    </Typography.Text>
                    {c.error ? (
                      <Typography.Text type="danger">Rechazada: {c.error}</Typography.Text>
                    ) : (
                      <pre className="ia-datos">{JSON.stringify(c.resultado, null, 2)}</pre>
                    )}
                  </Space>
                </List.Item>
              )}
            />
          ),
        },
      ]}
    />
  );
}

function TarjetaRespuesta({ r, onPreguntar }: { r: RespuestaAsistente; onPreguntar: (texto: string) => void }) {
  const tipo = TIPOS[r.tipo];
  return (
    <Card size="small" className="ia-respuesta" data-testid="respuesta-ia">
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Space wrap size={6}>
          <RobotOutlined />
          <Tag color={tipo.color}>{tipo.etiqueta}</Tag>
          {r.incluye_simulados && <Tag color="purple">Incluye ventas simuladas</Tag>}
        </Space>
        {r.resumen && <Typography.Paragraph style={{ marginBottom: 0 }}>{r.resumen}</Typography.Paragraph>}
        {r.advertencias.map((a) => (
          <Alert key={a} type="warning" showIcon title={a} />
        ))}
        <Afirmaciones titulo="Hechos consultados" items={r.hechos} />
        <Afirmaciones titulo="Pronóstico" items={r.predicciones} etiqueta="PREDICCIÓN" />
        {r.interpretaciones.length > 0 && (
          <div className="ia-seccion">
            <Typography.Text strong>
              Interpretación <Tag>generada por IA</Tag>
            </Typography.Text>
            <ul>
              {r.interpretaciones.map((x, i) => (
                <li key={i}>
                  <Typography.Text type="secondary">{x}</Typography.Text>
                </li>
              ))}
            </ul>
          </div>
        )}
        {r.sugerencias.length > 0 && (
          <div className="ia-seccion">
            <Typography.Text strong>Análisis sugeridos</Typography.Text>
            <div>
              {r.sugerencias.map((s) => (
                <Button key={s} size="small" type="link" onClick={() => onPreguntar(s)} style={{ whiteSpace: "normal", textAlign: "left", height: "auto" }}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        )}
        <Consultas consultas={r.consultas} />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          Datos al {fFecha(r.datos_al)} · Generado por {r.generado_por} en {(r.duracion_ms / 1000).toFixed(1)} s · costo
          aprox. USD {r.costo_usd.toFixed(4)}
        </Typography.Text>
      </Space>
    </Card>
  );
}

export default function PanelAsistente() {
  const info = useApi<InfoAsistente>("/api/asistente/info");
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const fin = useRef<HTMLDivElement>(null);

  async function preguntar(pregunta: string) {
    const limpia = pregunta.trim();
    if (limpia.length < 3 || enviando) return;
    const historial = turnos
      .filter((t) => t.respuesta)
      .slice(-TURNOS_DE_CONTEXTO)
      .flatMap((t) => [
        { rol: "usuario", texto: t.pregunta },
        { rol: "asistente", texto: t.respuesta!.resumen.slice(0, 2000) || "(sin resumen)" },
      ]);
    setTurnos((ts) => [...ts, { pregunta: limpia }]);
    setTexto("");
    setEnviando(true);
    try {
      const respuesta = await pedir<RespuestaAsistente>("/api/asistente", {
        metodo: "POST",
        cuerpo: { pregunta: limpia, historial },
      });
      setTurnos((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, respuesta } : t)));
    } catch (e) {
      const mensaje = e instanceof ErrorApi ? e.message : "Ocurrió un error inesperado.";
      setTurnos((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, error: mensaje } : t)));
    } finally {
      setEnviando(false);
      info.recargar();
      setTimeout(() => fin.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }), 50);
    }
  }

  if (info.error) return <ErrorCarga mensaje={info.error} reintentar={info.recargar} />;
  if (info.cargando && !info.datos) return <Cargando filas={4} />;
  if (!info.datos?.disponible) {
    return (
      <Card>
        <Empty description="El asistente de IA no está configurado en este entorno." />
      </Card>
    );
  }
  const datos = info.datos;

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        icon={<RobotOutlined />}
        title="Asistente de IA: respuestas generadas a partir de consultas al Data Warehouse"
        description={
          <>
            Responde con {datos.modelo} usando solo consultas controladas (indicadores, tendencias, rankings y el
            pronóstico); no accede a datos de clientes. Cada cifra muestra la consulta que la respalda: revísala en
            «Datos consultados». Las interpretaciones las genera la IA y pueden equivocarse. Preguntas hoy: {datos.usadas_hoy}{" "}
            de {datos.limite_dia}.
          </>
        }
      />

      <Card
        size="small"
        title="Conversación"
        extra={
          turnos.length > 0 && (
            <Button size="small" icon={<ClearOutlined />} onClick={() => setTurnos([])} disabled={enviando}>
              Nueva conversación
            </Button>
          )
        }
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {turnos.length === 0 && (
            <div>
              <Typography.Text type="secondary">Prueba con una de estas preguntas:</Typography.Text>
              <div className="ia-ejemplos">
                {datos.ejemplos.map((ej) => (
                  <Button key={ej} size="small" onClick={() => preguntar(ej)}>
                    {ej}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {turnos.map((t, i) => (
            <Space key={i} direction="vertical" size={6} style={{ width: "100%" }}>
              <div className="ia-pregunta">
                <UserOutlined /> {t.pregunta}
              </div>
              {t.respuesta && <TarjetaRespuesta r={t.respuesta} onPreguntar={preguntar} />}
              {t.error && <Alert type="error" showIcon title={t.error} />}
              {!t.respuesta && !t.error && (
                <Typography.Text type="secondary" aria-live="polite">
                  Consultando el Data Warehouse…
                </Typography.Text>
              )}
            </Space>
          ))}
          <div ref={fin} />
          <Space.Compact style={{ width: "100%" }}>
            <Input.TextArea
              aria-label="Pregunta para el asistente"
              placeholder="Pregunta sobre las ventas de WWI (Enter para enviar, Shift+Enter para nueva línea)"
              value={texto}
              maxLength={MAX_PREGUNTA}
              showCount
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={enviando}
              onChange={(e) => setTexto(e.target.value)}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  preguntar(texto);
                }
              }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={enviando}
              disabled={texto.trim().length < 3}
              onClick={() => preguntar(texto)}
            >
              Preguntar
            </Button>
          </Space.Compact>
        </Space>
      </Card>
    </Space>
  );
}
