import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // the automatic JSX runtime, as in the Next build (components render in tests)
  esbuild: { jsx: "automatic" },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
