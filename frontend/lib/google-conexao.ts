/**
 * Conexão da conta Google às minutas (SI-32) — o que a janela à parte e a aba
 * de origem precisam combinar.
 *
 * Por que janela à parte: ir ao Google na MESMA aba recarregava o processo na
 * volta, e o diálogo "Redigir documento" (com o que já tinha sido digitado)
 * sumia. Agora a aba de origem não sai do lugar: a autorização acontece numa
 * janela pequena, que termina em `/google-conectado`, avisa a aba e se fecha.
 *
 * Por que `BroadcastChannel` e não `window.opener.postMessage`: as páginas do
 * Google usam Cross-Origin-Opener-Policy, que corta o vínculo entre a janela e
 * quem a abriu — na volta, `window.opener` é `null` e `janela.closed` mente
 * (diz `true` com a janela aberta). O canal só exige a mesma origem.
 */

export const CANAL_GOOGLE = "aprimora-google-conexao";

export type AvisoConexaoGoogle = { tipo: "google-conexao"; ok: boolean; erro?: string | null };

/** Mensagens por código de erro (backend: `routers/auth._erro_google`). */
export const MENSAGEM_ERRO_GOOGLE: Record<string, string> = {
  access_denied: "Você rejeitou o acesso ao Google Docs. Tente novamente.",
  state_expired: "A conexão demorou mais de 5 minutos e expirou. Tente conectar novamente.",
  google_api_error: "Erro ao conectar com o Google. Tente novamente.",
  invalid_state: "Requisição inválida. Tente novamente.",
  google_nao_configurado:
    "A integração com o Google Docs ainda não foi configurada neste servidor. Fale com o administrador do sistema.",
  conta_diferente:
    "A conexão foi iniciada por outro usuário. Entre com a sua conta e tente de novo.",
};

export function mensagemErroGoogle(codigo: string | null | undefined): string {
  return (codigo && MENSAGEM_ERRO_GOOGLE[codigo]) || "Ocorreu um erro desconhecido.";
}

/** Endereço que inicia a conexão. `popup` = termina em `/google-conectado`. */
export function urlConexaoGoogle(minutaId: number, processoId: number, popup: boolean): string {
  const base = `/api/v2/auth/google?minuta_id=${minutaId}&processo_id=${processoId}`;
  return popup ? `${base}&popup=1` : base;
}

/**
 * Abre a autorização numa janela pequena, centrada sobre a tela atual.
 * Devolve `false` quando o navegador bloqueou a janela — quem chama cai na
 * navegação na mesma aba, como antes.
 */
export function abrirJanelaGoogle(url: string): boolean {
  const largura = 520;
  const altura = 680;
  const esquerda = Math.max(0, window.screenX + (window.outerWidth - largura) / 2);
  const topo = Math.max(0, window.screenY + (window.outerHeight - altura) / 2);
  const janela = window.open(
    url,
    "aprimora-google",
    `popup=yes,width=${largura},height=${altura},left=${Math.round(esquerda)},top=${Math.round(topo)}`,
  );
  return janela != null;
}

/** A janela à parte avisa a aba de origem (mesma origem, sem `opener`). */
export function avisarAbaDeOrigem(aviso: AvisoConexaoGoogle): void {
  if (typeof BroadcastChannel === "undefined") return;
  const canal = new BroadcastChannel(CANAL_GOOGLE);
  canal.postMessage(aviso);
  canal.close();
}

/** A aba de origem escuta. Devolve a função que para de escutar. */
export function ouvirConexaoGoogle(aoReceber: (aviso: AvisoConexaoGoogle) => void): () => void {
  if (typeof BroadcastChannel === "undefined") return () => {};
  const canal = new BroadcastChannel(CANAL_GOOGLE);
  canal.onmessage = (e: MessageEvent) => {
    const d = e.data as AvisoConexaoGoogle | undefined;
    if (d && d.tipo === "google-conexao") aoReceber(d);
  };
  return () => canal.close();
}
