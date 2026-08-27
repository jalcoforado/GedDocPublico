"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/m/protocolo/relatorios", label: "Processos" },
  { href: "/m/protocolo/relatorios/tramitacao", label: "Tramitação" },
  { href: "/m/protocolo/relatorios/assinaturas", label: "Assinaturas" },
];

/**
 * Navegação entre os relatórios. **Não são abas**, apesar de parecerem.
 *
 * Isto foi `role="tablist"` + `role="tab"` até 2026-08-27, e estava errado por
 * um motivo que a aparência esconde: cada item é um `<Link>` para **outra
 * rota**. Não existe painel, porque não existe conteúdo trocando na mesma
 * página — o navegador troca de página inteira.
 *
 * O padrão ARIA (APG) é explícito: `role="tab"` promete um `tabpanel` na mesma
 * página, controlado por `aria-controls`. Link que navega não tem o que
 * controlar. Quem usa leitor de tela ouvia "aba", procurava o painel e não
 * achava — o mesmo sintoma das abas de verdade, mas aqui a correção é o
 * oposto: **tirar** os papéis, não completá-los.
 *
 * O certo é o que já estava aqui do lado: `<nav>` com links e `aria-current=
 * "page"` no ativo. É como um leitor de tela espera navegação secundária, e
 * `aria-current` é o que anuncia onde o usuário está.
 *
 * Migrar isto para `components/ui/tabs` seria piorar. A guarda
 * `__tests__/tabs-a11y.test.ts` cobre `role="tablist"` escrito à mão; ela não
 * distingue os dois casos, e é por isso que a decisão fica escrita aqui.
 */
export function RelatoriosNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Tipos de relatório" className="border-b border-border">
      <ul className="flex gap-1">
        {LINKS.map((t) => {
          const ativo = pathname === t.href;
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "flex h-11 items-center px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  ativo
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
