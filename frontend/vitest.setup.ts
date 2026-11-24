import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";

import { esquecerSessao } from "@/lib/sessao-em-memoria";

// A sessão em memória (`lib/sessao-em-memoria.ts`) é variável de módulo: sem
// isto, o usuário de um teste nasceria pronto no `AuthProvider` do seguinte.
afterEach(() => esquecerSessao());

// jsdom não implementa ResizeObserver (o autoUpdate da Floating UI exige) nem
// matchMedia (ThemeProvider consulta a preferência do SO). Stubs mínimos aqui
// evitam que cada teste os recrie — pedidos pela spec UX-02.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
