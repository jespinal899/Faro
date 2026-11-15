import { createContext, useContext } from "react";
import { PALETAS, type Modo, type Paleta } from "./tema";

export const ModoContexto = createContext<{ modo: Modo; paleta: Paleta }>({
  modo: "claro",
  paleta: PALETAS.claro,
});

export const usePaleta = () => useContext(ModoContexto);
