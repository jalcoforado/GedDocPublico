import { FileCheck2, ListChecks } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * O que os dois logins (servidor e cidadão) têm de igual. Existiam como telas
 * sem nada em comum — campos em pílula de um lado, cartão com campos
 * retangulares do outro —, e o cidadão que vinha do botão "Solicitante" caía
 * no que parecia outro produto.
 */

/** Campo em pílula do layout de referência (protótipo Figma "Sistema - Aprimora"). */
export const CAMPO_LOGIN =
  "flex h-12 w-full rounded-full border border-border-strong bg-transparent px-6 text-base text-foreground shadow-input transition-colors duration-fast placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/**
 * O mesmo campo, aplicado ao `PasswordInput`. Os `!` são necessários: as
 * classes de raio/altura/fundo do componente vêm depois no CSS e venceriam.
 */
export const CAMPO_SENHA_LOGIN = "!h-12 !rounded-full !border-border-strong !bg-transparent !px-6";

/** Botão em pílula; a cor vem de quem usa. */
export const BOTAO_LOGIN =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-full px-4 font-display text-base font-medium transition-all duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60";

const ATALHOS = [
  {
    href: "/validar",
    rotulo: "Validar documento",
    ajuda: "Confira a autenticidade de uma assinatura",
    icone: FileCheck2,
  },
  {
    href: "/cidadao/servicos",
    rotulo: "Carta de serviços",
    ajuda: "Veja o que a prefeitura oferece",
    icone: ListChecks,
  },
] as const;

/**
 * O que dá para fazer SEM entrar. Quem chega só para conferir um documento
 * assinado, ou para saber que serviço pedir, não tinha por onde começar: a
 * tela de entrada só oferecia login e cadastro.
 */
export function AtalhosPublicos({ className }: { className?: string }) {
  return (
    <nav aria-label="Acesso sem login" className={cn("space-y-2", className)}>
      <p className="px-2 text-xs font-medium uppercase tracking-wider text-foreground-subtle">
        Sem precisar entrar
      </p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {ATALHOS.map(({ href, rotulo, ajuda, icone: Icone }) => (
          <li key={href}>
            <Link
              href={href}
              className="flex h-full items-start gap-3 rounded-2xl border border-border px-4 py-3 transition-colors duration-fast hover:border-border-strong hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <Icone className="mt-0.5 h-5 w-5 shrink-0 text-brand" aria-hidden="true" />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-foreground">{rotulo}</span>
                <span className="block text-xs text-foreground-muted">{ajuda}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
