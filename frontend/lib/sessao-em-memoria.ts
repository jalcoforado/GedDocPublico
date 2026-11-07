import type { MeResponse } from "@/lib/api";

/**
 * O último `/auth/me` desta aba, em MEMÓRIA (variável de módulo — nada em
 * localStorage/sessionStorage, nada sobrevive a recarregar a página).
 *
 * Existe por causa da troca entre os grupos de rota `(app)` e `(launcher)`:
 * cada um monta o próprio `AuthProvider`, então ir de `/modulos` para um
 * módulo (ou voltar) desmontava um e montava o outro, e a tela inteira
 * piscava um "Carregando..." enquanto o `/auth/me` repetia uma resposta que
 * a aba já tinha. Com isto o provider novo nasce com o usuário conhecido e
 * revalida em segundo plano; se a revalidação falhar (sessão expirou), o
 * fluxo é o de sempre — vai para o login — e a cópia é apagada.
 *
 * Não é fonte de autorização: o backend decide tudo. É o mesmo dado que já
 * estava na memória do provider anterior, um instante antes.
 */
let ultimo: MeResponse | null = null;

export function sessaoEmMemoria(): MeResponse | null {
  return ultimo;
}

export function guardarSessao(me: MeResponse): void {
  ultimo = me;
}

export function esquecerSessao(): void {
  ultimo = null;
}
