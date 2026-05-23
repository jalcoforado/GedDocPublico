import { defineConfig } from "@playwright/test";

// Endpoints (overrides via env):
//   PY_BASE  - nginx Strangler (Python + fallback PHP via location /)
//   PHP_BASE - PHP legacy direto (sem passar pelo nginx Python)
const PY_BASE = process.env.PY_BASE ?? "http://nginx";
const PHP_BASE = process.env.PHP_BASE ?? "http://protocolo";

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,    // banco compartilhado — evita race em cadastros
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: [["list"], ["html", { open: "never", outputFolder: "report" }]],
  use: {
    baseURL: PY_BASE,
    extraHTTPHeaders: { "x-e2e": "playwright" },
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "smoke",
      use: {
        // Cada spec pode usar `request` HTTP puro (sem browser),
        // mas mantemos chromium disponível para futuras navegações.
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  metadata: { PY_BASE, PHP_BASE },
});
