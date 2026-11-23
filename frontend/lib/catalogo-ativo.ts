/**
 * Catálogo oferecido na ABERTURA de processo: só o que está ativo (SI-54).
 *
 * `GET /assuntos` e `GET /tipos-processo` devolvem também os inativos, e é
 * certo que devolvam: a tela de cadastro precisa deles para reativar, e os
 * filtros de Processos e dos Relatórios precisam deles porque processo antigo
 * continua tendo aquele assunto. Quem não pode oferecê-los é quem ABRE
 * processo — desativar um assunto não servia para nada enquanto o Novo
 * processo e o Balcão continuavam listando-o.
 *
 * O item já escolhido fica, mesmo inativo: o mesmo formulário edita rascunho,
 * e um rascunho cujo assunto foi desativado depois apareceria com o campo em
 * branco — e o usuário, sem saber, trocaria de assunto ao salvar.
 *
 * Isto é UX, não regra: o backend ainda aceita abrir processo com assunto
 * inativo (`abertura_processo.conferir_referencias_do_tenant` confere só
 * tenant e exclusão).
 */
export function ativosOuEscolhido<T extends { id: number; ativo: boolean }>(
  itens: readonly T[],
  idEscolhido: number | "" | null | undefined,
): T[] {
  return itens.filter((item) => item.ativo || item.id === idEscolhido);
}
