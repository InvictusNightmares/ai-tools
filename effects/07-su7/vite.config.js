import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  esbuild: { jsx: "automatic" },
  build: { sourcemap: true, chunkSizeWarningLimit: 1600 },
});
