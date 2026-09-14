/// <reference types="vitest/config" />
import path from "node:path"
import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig(({ command, mode }) => {
  // Vite exposes VITE_* from .env files to the app, not to process.env; merge both so
  // the guard sees frontend/.env locally and the dashboard variables on Cloudflare Pages.
  const env = { ...loadEnv(mode, __dirname, "VITE_"), ...process.env }
  if (command === "build" && !env.VITE_API_BASE_URL) {
    throw new Error(
      "VITE_API_BASE_URL is required at build time (e.g. https://bitlux-api.onrender.com/api/v1). " +
        "Set it in Cloudflare Pages → Settings → Environment variables, or in frontend/.env locally.",
    )
  }
  return {
    base: "/",
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: { port: 5173, strictPort: true },
    build: { outDir: "dist", sourcemap: true },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      include: ["src/**/*.test.{ts,tsx}"],
    },
  }
})
