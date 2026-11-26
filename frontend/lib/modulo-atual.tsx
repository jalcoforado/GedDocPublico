"use client";

import { createContext, useContext } from "react";

/**
 * O módulo em que a tela está, para quem precisa saber disso sem ler a URL.
 *
 * Existe para o `PageHeader` montar a trilha "Menu principal › Meus módulos ›
 * Módulo" sem chamar `usePathname`: ele está em toda tela, e dezenas de testes
 * de página simulam `next/navigation` só com o que a própria página usa — um
 * hook novo ali quebraria todos de uma vez. Quem lê a URL é o shell
 * (`app/(app)/layout.tsx`), que já a lia, e publica o resultado aqui.
 *
 * `null` = rota transversal (início, perfil, para assinar) ou tela fora do
 * shell, como nos testes: sem trilha de módulo.
 */
export interface ModuloAtual {
  slug: string;
  nome: string;
  /** Para onde o nome do módulo leva na trilha. */
  raiz: string;
}

const ModuloAtualContext = createContext<ModuloAtual | null>(null);

export const ModuloAtualProvider = ModuloAtualContext.Provider;

export function useModuloAtual(): ModuloAtual | null {
  return useContext(ModuloAtualContext);
}
