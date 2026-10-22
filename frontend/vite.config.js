import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo todo pasa por el mismo origen (localhost:5173), igual que en
// producción detrás de Caddy: /api y /media van a Django, /ws a la visión.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/media": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8001", ws: true },
    },
  },
});
