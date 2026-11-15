/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api se reenvía a la API local (uvicorn en el puerto 8000).
// En producción (Vercel) el dashboard y la API comparten dominio: no hace falta proxy.
const api = { "/api": "http://localhost:8000" };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: api },
  preview: { port: 4173, proxy: api },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        // Bibliotecas grandes en archivos aparte: el navegador las guarda en caché
        manualChunks(id) {
          if (id.includes("node_modules/echarts") || id.includes("node_modules/zrender")) return "echarts";
          if (id.includes("node_modules/antd") || id.includes("node_modules/@ant-design") || id.includes("node_modules/rc-"))
            return "antd";
          if (id.includes("node_modules/react")) return "react";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
