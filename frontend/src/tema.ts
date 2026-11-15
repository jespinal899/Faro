// Paleta de los gráficos (validada con el script de la guía de visualización:
// contraste >= 3:1 y separación para daltonismo, en claro y oscuro).
// Cada color tiene un rol fijo: la serie 1 es SIEMPRE el período actual y la serie 2
// SIEMPRE el año anterior. Los textos usan tintas, nunca el color de la serie.

export type Modo = "claro" | "oscuro";

export interface Paleta {
  superficie: string;
  tinta: string;
  tintaSecundaria: string;
  tenue: string;
  grilla: string;
  eje: string;
  serie1: string;
  serie2: string;
  sube: string;
  baja: string;
}

export const PALETAS: Record<Modo, Paleta> = {
  claro: {
    superficie: "#fcfcfb",
    tinta: "#0b0b0b",
    tintaSecundaria: "#52514e",
    tenue: "#898781",
    grilla: "#e1e0d9",
    eje: "#c3c2b7",
    serie1: "#2a78d6",
    serie2: "#eb6834",
    sube: "#006300",
    baja: "#d03b3b",
  },
  oscuro: {
    superficie: "#1a1a19",
    tinta: "#f0efec",
    tintaSecundaria: "#c3c2b7",
    tenue: "#898781",
    grilla: "#2c2c2a",
    eje: "#383835",
    serie1: "#3987e5",
    serie2: "#d95926",
    sube: "#0ca30c",
    baja: "#e66767",
  },
};

export const FUENTE = 'system-ui, -apple-system, "Segoe UI", sans-serif';
