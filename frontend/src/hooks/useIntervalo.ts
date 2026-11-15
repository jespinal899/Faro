import { useEffect, useRef } from "react";

/** Ejecuta `accion` cada `ms` milisegundos mientras la pestaña del navegador está visible
 *  (consulta periódica o *polling*: Vercel no admite WebSockets, decisión D-22). Al volver a
 *  la pestaña la ejecuta enseguida, para no mostrar datos viejos. */
export function useIntervalo(accion: () => void, ms: number | null) {
  const ultima = useRef(accion);
  useEffect(() => {
    ultima.current = accion;
  }, [accion]);

  useEffect(() => {
    if (ms === null) return;
    const tic = () => {
      if (document.visibilityState === "visible") ultima.current();
    };
    const id = window.setInterval(tic, ms);
    document.addEventListener("visibilitychange", tic);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tic);
    };
  }, [ms]);
}
