import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

// Solo los módulos que se usan: el paquete final es mucho menor que ECharts completo
echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, AriaComponent, CanvasRenderer]);

export type OpcionGrafico = echarts.EChartsCoreOption;
export type EventoGrafico = { dataIndex: number; name: string };

interface Props {
  opcion: OpcionGrafico;
  /** Descripción para lectores de pantalla (el gráfico es un canvas). */
  etiqueta: string;
  alto?: number;
  onClic?: (evento: EventoGrafico) => void;
}

/** Contenedor de ECharts: crea el gráfico, lo redimensiona con el contenedor y lo libera al salir. */
export default function Grafico({ opcion, etiqueta, alto = 320, onClic }: Props) {
  const nodo = useRef<HTMLDivElement>(null);
  const instancia = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!nodo.current) return;
    const grafico = echarts.init(nodo.current, undefined, { renderer: "canvas" });
    instancia.current = grafico;
    const observador = new ResizeObserver(() => grafico.resize());
    observador.observe(nodo.current);
    return () => {
      observador.disconnect();
      grafico.dispose();
      instancia.current = null;
    };
  }, []);

  useEffect(() => {
    instancia.current?.setOption(opcion, true);
  }, [opcion]);

  useEffect(() => {
    const grafico = instancia.current;
    if (!grafico || !onClic) return;
    const manejador = (e: unknown) => onClic(e as EventoGrafico);
    grafico.on("click", manejador);
    return () => {
      grafico.off("click", manejador);
    };
  }, [onClic]);

  return <div ref={nodo} role="img" aria-label={etiqueta} style={{ width: "100%", height: alto }} />;
}
