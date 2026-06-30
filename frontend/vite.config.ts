import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The React app talks directly to the FastAPI backend (CORS is open there).
// Set VITE_API_URL in .env to point at the backend (default: http://localhost:8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
