/**
 * Código de validação pública de assinatura, do jeito que a pessoa traz.
 *
 * O código é um `secrets.token_urlsafe(16)` (backend `services/assinaturas.py`):
 * letras, números, `-` e `_` — maiúscula e minúscula contam. No comprovante ele
 * aparece solto e dentro do link do QR (`…/validar/<código>`, ver
 * `config.validacao_publica_url`). Quem copia do PDF costuma trazer espaço ou
 * quebra de linha no meio, e quem copia do celular traz o link inteiro.
 *
 * Por isso: se veio um link, fica o que está depois de `/validar/`; do resto,
 * sai tudo o que não pode fazer parte do código (espaço, ponto, aspas…).
 * Hífen e sublinhado ficam — são do código.
 */
export function normalizarCodigoValidacao(entrada: string): string {
  let s = entrada.trim();
  const i = s.toLowerCase().lastIndexOf("/validar/");
  if (i >= 0) s = s.slice(i + "/validar/".length).split(/[?#/]/)[0];
  try {
    s = decodeURIComponent(s);
  } catch {
    // `%` solto: segue como está e o filtro abaixo limpa.
  }
  return s.replace(/[^A-Za-z0-9_-]/g, "");
}
