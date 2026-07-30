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

/**
 * Slug do módulo dono da rota, ou `null` se a rota é transversal.
 *
 * Casa por SEGMENTO, não por substring: `/processosx` não é `/processos`.
 */
export function moduloDoPathname(path: string): string | null {
  const limpo = path.split("?")[0].split("#")[0].replace(/\/+$/, "") || "/";
  for (const [prefixo, slug] of ROTA_MODULO) {
    if (limpo === prefixo || limpo.startsWith(`${prefixo}/`)) return slug;
  }
  return null;
}
