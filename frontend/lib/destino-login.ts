/**
 * Destino pós-login preservado no `?next=` (F3, Tarefa 1).
 *
 * Existe como módulo próprio porque **duas pontas precisam concordar**: o
 * `middleware.ts` escreve o parâmetro e a tela de login o consome. Duas cópias
 * da regra divergiriam, e o sintoma seria um destino que o middleware grava e o
 * login recusa — ou, pior, o contrário.
 *
 * O valor vem da URL, ou seja, **do usuário**. Redirecionar para o que ele
 * mandar é *open redirect*: uma página de login legítima, no domínio legítimo,
 * que joga a vítima num site de phishing depois de autenticar. Por isso a
 * política aqui é allowlist — só caminho interno passa —, e não uma lista de
 * coisas ruins a bloquear.
 */

/** Para onde o login vai quando não há `next` utilizável. É o launcher (F2). */
export const DESTINO_PADRAO = "/modulos";

/** Prefixos que nunca são destino: levariam a laço ou a tela de trânsito. */
const NUNCA_DESTINO = ["/login", "/alterar-senha-obrigatoria"];

/** Caracteres de controle (C0 + DEL): servem para contrabandear cabeçalho. */
function temControle(s: string): boolean {
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c < 0x20 || c === 0x7f) return true;
  }
  return false;
}

/**
 * Normaliza o `next` recebido para um caminho interno seguro, ou devolve
 * `DESTINO_PADRAO`.
 *
 * O que é recusado, e por quê:
 *
 * - qualquer coisa que não comece com `/` — `https://evil.example` e
 *   `javascript:…` são o caso óbvio;
 * - **`//evil.example` e `/\evil.example`** — o caso NÃO óbvio, e o que faz
 *   a checagem ingênua "começa com `/`" ser insuficiente: o navegador lê os
 *   dois como URL protocol-relative e sai do domínio;
 * - `/login` e `/alterar-senha-obrigatoria` — o primeiro faria laço; a segunda
 *   é decidida pelo backend (`must_change_password`, SEC-1), não pela URL;
 * - caracteres de controle.
 */
export function destinoSeguro(bruto: string | null | undefined): string {
  if (!bruto) return DESTINO_PADRAO;
  if (temControle(bruto)) return DESTINO_PADRAO;
  if (!bruto.startsWith("/")) return DESTINO_PADRAO;
  if (bruto.startsWith("//") || bruto.startsWith("/\\")) return DESTINO_PADRAO;

  const caminho = bruto.split("?")[0].split("#")[0];
  if (NUNCA_DESTINO.some((p) => caminho === p || caminho.startsWith(`${p}/`))) {
    return DESTINO_PADRAO;
  }

  return bruto;
}

/** Lê e sanitiza o `next` de uma query string (`location.search`). */
export function destinoDaQuery(search: string): string {
  return destinoSeguro(new URLSearchParams(search).get("next"));
}
