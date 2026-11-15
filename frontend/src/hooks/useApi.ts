import { useCallback, useEffect, useState } from "react";
import { pedir, type Parametros } from "../api";

interface Estado<T> {
  datos?: T;
  error?: string;
  cargando: boolean;
}

/** Pide datos a la API y expone los estados de carga, error y datos.
 *  Si cambian la ruta o los parámetros, cancela la petición anterior (sin respuestas cruzadas). */
export function useApi<T>(ruta: string | null, params?: Parametros) {
  const clave = ruta ? `${ruta}?${JSON.stringify(params ?? {})}` : null;
  const [estado, setEstado] = useState<Estado<T>>({ cargando: Boolean(ruta) });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!ruta) return;
    const control = new AbortController();
    setEstado((previo) => ({ datos: previo.datos, cargando: true }));
    pedir<T>(ruta, { params, senal: control.signal })
      .then((datos) => setEstado({ datos, cargando: false }))
      .catch((error: Error) => {
        if (!control.signal.aborted) setEstado({ cargando: false, error: error.message });
      });
    return () => control.abort();
    // `clave` resume ruta y parámetros: así un objeto nuevo con los mismos valores no repite la petición
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { ...estado, recargar };
}
