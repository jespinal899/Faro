// Prueba de punta a punta (E2E) del dashboard con un navegador real.
// Levanta la API (uvicorn) y el dashboard (Vite) contra la base local con los datos completos.
//
//   cd frontend && npx playwright test
//
// Usuario: FARO_E2E_USUARIO (por defecto "demo"); contraseña: FARO_PASSWORD_DEMO del .env.
import { existsSync, readFileSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";

// Lee el .env de la raíz sin dependencias (solo variables que no estén ya definidas)
const env = "../.env";
if (existsSync(env)) {
  for (const linea of readFileSync(env, "utf-8").split(/\r?\n/)) {
    const m = linea.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
  }
}

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    locale: "es-419",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn backend.app.main:app --port 8000",
      cwd: "..",
      url: "http://localhost:8000/api/salud",
      reuseExistingServer: true,
      timeout: 90_000,
    },
    {
      command: "npm run dev -- --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 90_000,
    },
  ],
  projects: [{ name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
