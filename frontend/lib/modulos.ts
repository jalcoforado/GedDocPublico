import { Bus, FileText, LayoutGrid, Settings, Truck, Wallet } from "lucide-react";
import type React from "react";

/**
 * Mapa rota → módulo, derivado do apêndice §12 do spec de modularização.
 *
 * Nesta fatia (F2) é o que diz à Sidebar qual menu renderizar, porque as URLs
 * ainda são as antigas. Na F3, quando as rotas virarem `/m/<slug>/…`, o slug
 * passa a vir de `params` — mas este mapa continua sendo a fonte dos redirects
 * 308 e do guard. Ou seja: não é ponte descartável.
 */
export const ROTA_MODULO: ReadonlyArray<readonly [string, string]> = [
  // A ordem importa: o primeiro prefixo que casar ganha. `/protocolo` antes de
  // nada mais que comece com "protocolo" seria ambíguo — hoje não é o caso.
  ["/processos", "protocolo"],
  ["/protocolo", "protocolo"],
  ["/workflow", "protocolo"],
  ["/relatorios", "protocolo"],
  ["/servicos", "protocolo"],
  ["/manifestantes", "protocolo"],
  ["/tipos-manifestante", "protocolo"],
  ["/tipos-processo", "protocolo"],
  ["/tipos-anexo", "protocolo"],
  ["/assuntos", "protocolo"],
  ["/templates-documento", "protocolo"],
  ["/cidades", "protocolo"],
  ["/bairros", "protocolo"],
  ["/enderecos", "protocolo"],
  ["/pagamentos", "pagamentos"],
  ["/frotas", "frota"],
  ["/transporte-regulado", "transporte"],
  ["/usuarios", "administracao"],
  ["/grupos", "administracao"],
  ["/unidades-trabalho", "administracao"],
  ["/organograma", "administracao"],
  ["/auditoria", "administracao"],
  ["/configuracoes", "administracao"],
  ["/jobs", "administracao"],
];

/** Prefixo canônico das rotas de módulo desde a F3. */
export const PREFIXO_MODULO = "/m";

/** Slugs válidos, derivados do próprio mapa — não uma segunda lista a manter. */
export const SLUGS_MODULO: ReadonlySet<string> = new Set(
  ROTA_MODULO.map(([, slug]) => slug),
);

/**
 * Slug do módulo dono da rota, ou `null` se a rota é transversal.
 *
 * Reconhece as **duas** formas, e isso não é transitório:
 *
 * - **canônica** (F3): `/m/<slug>/…` — o slug está na própria URL;
 * - **legada**: `/frotas`, `/processos`, … — continuam chegando aqui porque o
 *   308 do `next.config.js` é resolvido pelo Next **antes** do render, mas
 *   `notificacao.link_url` é registro histórico permanente e o mapa
 *   `ROTA_MODULO` segue sendo a fonte desses redirects. Apagar a segunda forma
 *   apagaria os redirects junto.
 *
 * Casa por SEGMENTO, não por substring: `/processosx` não é `/processos`, e
 * `/mapa` não é `/m/apa`.
 */
export function moduloDoPathname(path: string): string | null {
  const limpo = path.split("?")[0].split("#")[0].replace(/\/+$/, "") || "/";

  if (limpo === PREFIXO_MODULO || limpo.startsWith(`${PREFIXO_MODULO}/`)) {
    const slug = limpo.slice(PREFIXO_MODULO.length + 1).split("/")[0];
    // Slug desconhecido devolve `null`, não o texto cru: quem consome isto
    // renderiza menu e guard, e um slug inventado na URL não pode virar
    // estado de aplicação.
    return SLUGS_MODULO.has(slug) ? slug : null;
  }

  for (const [prefixo, slug] of ROTA_MODULO) {
    if (limpo === prefixo || limpo.startsWith(`${prefixo}/`)) return slug;
  }
  return null;
}

/**
 * Ícones que o catálogo pode nomear (`aprimora_py.modulo.icone`). Mapa
 * explícito de propósito: import dinâmico por nome arbitrário não sobrevive
 * ao bundler, e um nome inválido vindo do banco não pode virar erro de
 * runtime — cai no ícone genérico via `iconeDoModulo`.
 */
export const ICONES_MODULO: Record<string, React.ComponentType<{ className?: string }>> = {
  FileText,
  Wallet,
  Truck,
  Bus,
  Settings,
};

/**
 * Descrições curtas para o launcher (UX-11.2). O catálogo (`ModuloOut`) não
 * expõe descrição, e o conjunto de módulos é fixo e pequeno — um mapa local
 * evita mexer no backend por um texto de vitrine. Slug fora do mapa cai no
 * genérico: módulo novo no catálogo aparece no launcher sem quebrar (mesmo
 * fail-open do ícone).
 */
export const DESCRICAO_MODULO: Record<string, string> = {
  protocolo: "Processos, tramitação, anexos e assinatura eletrônica.",
  pagamentos: "Despesas, ordens de pagamento e conciliação bancária.",
  frota: "Veículos, motoristas, solicitações e viagens.",
  transporte: "Permissionários, alvarás e transporte regulado.",
  administracao: "Usuários, grupos, organograma e configurações do órgão.",
};

const DESCRICAO_GENERICA = "Acesse as funções deste módulo.";

/** Descrição do módulo para o launcher. Slug desconhecido → texto genérico. */
export function descricaoDoModulo(slug: string): string {
  return DESCRICAO_MODULO[slug] ?? DESCRICAO_GENERICA;
}

/** Resolve o ícone do módulo pelo nome vindo do backend. Nome desconhecido ou nulo → genérico. */
export function iconeDoModulo(
  nome: string | null | undefined,
): React.ComponentType<{ className?: string }> {
  return (nome && ICONES_MODULO[nome]) || LayoutGrid;
}
