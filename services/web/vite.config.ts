import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  define: { __BUILD_ID__: JSON.stringify(Date.now().toString(36)) },
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});
