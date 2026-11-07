import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Lee el .env de la raíz del repo. Solo se exponen al navegador las variables
  // VITE_* y MAPBOX_* (el token de Mapbox "pk." es público por diseño).
  envDir: fileURLToPath(new URL("..", import.meta.url)),
  envPrefix: ["VITE_", "MAPBOX_"],
  server: {
    port: 5173,
    // En desarrollo, /api se redirige al backend (FastAPI en el puerto 8000).
    proxy: {
      "/api": process.env.VITE_API_PROXY || "http://localhost:8000",
    },
  },
});
