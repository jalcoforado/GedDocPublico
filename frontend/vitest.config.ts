import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/__tests__/**/*.test.{ts,tsx}"],
    // Execução sequencial de arquivos: o setup do jsdom é pesado e, em paralelo,
    // a contenção fazia `waitFor`/`findBy` estourar o timeout em testes não
    // relacionados (flakiness de ambiente, não de produto). Equivale a
    // `--no-file-parallelism`. Não altera lógica de produto.
    fileParallelism: false,
  },
});
