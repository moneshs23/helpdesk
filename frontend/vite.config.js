import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Proxy API calls to the FastAPI backend during development so the frontend
// can use relative "/api/..." URLs and work identically over LAN.
export default defineConfig({
    plugins: [react()],
    server: {
        host: true, // listen on 0.0.0.0 for LAN access
        port: 5173,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
    preview: {
        host: true,
        port: 4173,
    },
});
