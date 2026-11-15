import { useEffect, useState } from "react";
import { App as AntApp, ConfigProvider, Spin, theme } from "antd";
import esES from "antd/locale/es_ES";
import { EVENTO_SESION_EXPIRADA, pedir } from "./api";
import { ModoContexto } from "./contexto";
import { FUENTE, PALETAS, type Modo } from "./tema";
import type { Usuario } from "./tipos";
import Dashboard from "./Dashboard";
import Login from "./componentes/Login";

const CLAVE_MODO = "faro-modo";

function modoInicial(): Modo {
  try {
    const guardado = window.localStorage.getItem(CLAVE_MODO);
    if (guardado === "claro" || guardado === "oscuro") return guardado;
  } catch {
    // almacenamiento no disponible (modo privado): se usa la preferencia del sistema
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro";
}

export default function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [verificando, setVerificando] = useState(true);
  const [aviso, setAviso] = useState<string>();
  const [modo, setModo] = useState<Modo>(modoInicial);

  // ¿Hay una sesión abierta? (la cookie es httpOnly: se pregunta a la API)
  useEffect(() => {
    pedir<Usuario>("/api/auth/me")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setVerificando(false));
  }, []);

  useEffect(() => {
    const expirada = () => {
      setUsuario(null);
      setAviso("Tu sesión expiró. Vuelve a iniciar sesión.");
    };
    window.addEventListener(EVENTO_SESION_EXPIRADA, expirada);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, expirada);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = modo === "oscuro" ? "dark" : "light";
    try {
      window.localStorage.setItem(CLAVE_MODO, modo);
    } catch {
      // sin almacenamiento: el modo dura solo esta visita
    }
  }, [modo]);

  async function salir() {
    try {
      await pedir("/api/auth/logout", { metodo: "POST" });
    } finally {
      setUsuario(null);
      setAviso(undefined);
    }
  }

  return (
    <ConfigProvider
      locale={esES}
      theme={{
        algorithm: modo === "oscuro" ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: { colorPrimary: PALETAS[modo].serie1, fontFamily: FUENTE, borderRadius: 8 },
      }}
    >
      <ModoContexto.Provider value={{ modo, paleta: PALETAS[modo] }}>
        <AntApp>
          {verificando ? (
            <div className="centrado">
              <Spin size="large" description="Cargando…" />
            </div>
          ) : usuario ? (
            <Dashboard
              usuario={usuario}
              modo={modo}
              onCambiarModo={() => setModo((m) => (m === "claro" ? "oscuro" : "claro"))}
              onSalir={salir}
            />
          ) : (
            <Login
              aviso={aviso}
              onIngreso={(u) => {
                setAviso(undefined);
                setUsuario(u);
              }}
            />
          )}
        </AntApp>
      </ModoContexto.Provider>
    </ConfigProvider>
  );
}
