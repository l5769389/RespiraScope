import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: resolve(import.meta.dirname),
  plugins: [react()],
  build: {
    assetsDir: "",
    emptyOutDir: true,
    outDir: resolve(import.meta.dirname, "assets"),
    rollupOptions: {
      input: resolve(import.meta.dirname, "src/main.jsx"),
      output: {
        assetFileNames: "[name][extname]",
        chunkFileNames: "[name].js",
        entryFileNames: "console.js",
      },
    },
    sourcemap: false,
  },
});
