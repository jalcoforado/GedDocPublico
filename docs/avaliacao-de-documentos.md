# Avaliação de documentos do processo

> **Status:** vivo · **Autoridade sobre:** pedido de avaliação, decisão por documento (aprovar/devolver), reenvio do devolvido e o que fica travado enquanto há avaliação.
> **Última verificação:** 2026-11-26 (SI-73, RF-04 V2).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Fonte de verdade executável: `backend/app/services/avaliacoes.py`,
`backend/app/routers/avaliacoes.py` e `backend/tests/test_avaliacao_documento.py`.
Migration `0148`. Depende das versões de documento: [versoes-de-documento](versoes-de-documento.md).

## O que é

Quem tramita o processo pede a um servidor do município que avalie um ou mais
documentos, com orientação e prazo opcionais. O avaliador **aprova** ou
**devolve** cada documento; devolver exige justificativa. **Avaliar não é
assinar**: nada disso toca a assinatura eletrônica.

A decisão aponta para a **versão exata** do documento (`anexo.id`). A aprovação
da versão 1 não vale para a versão 2.

## Rotas (`/api/v2`)

| Rota | Quem | O quê |
|---|---|---|
| `POST /processos/{id}/avaliacoes` | `processo`/`atualizar` | Pede: `id_avaliador`, `id_anexos`, `orientacao?`, `prazo?`. |
| `GET /processos/{id}/avaliacoes` | `processo` ou `documento_avaliar` | Pedidos do processo, do mais novo ao mais antigo. |
| `GET /avaliacoes?papel=avaliador\|solicitante&situacao=pendente\|concluida` | idem | Caixas "Para avaliar" e "Avaliações solicitadas" (paginado; só os pedidos do próprio usuário). |
| `GET /avaliacoes/{pedido}` | idem | Um pedido. |
| `POST /avaliacoes/{pedido}/decisoes` | `documento_avaliar` **e** ser o avaliador designado | `{"decisoes": [{"id_item", "resultado", "justificativa?"}]}`, várias de uma vez. |
| `POST /avaliacoes/{pedido}/itens/{item}/reenviar` | `processo`/`atualizar` | Volta para avaliação a versão corrigida de um devolvido. |

Na lista de documentos do processo, cada anexo traz `avaliacao`: a situação
mais recente **daquela versão** (`aguardando`, `aprovado`, `devolvido` ou nulo).

## Regras

- **Quem pode avaliar:** servidor ativo do mesmo município com a transação
  `documento_avaliar`, com credencial de sigilo que alcance o processo. Não
  precisa ser da unidade do processo. Quem pede não pode ser o avaliador. Fora
  disso, 422.
- **Quem decide:** só o avaliador designado (403 para os demais, mesmo com a
  transação). Se ele perder a transação depois do pedido, também não decide.
- **O que se pode pedir:** a versão vigente de documento do próprio processo
  que aceitaria versão nova (não herdado de apensamento, não peça de despacho,
  processo não arquivado nem em rascunho). Um documento tem no máximo uma
  avaliação aguardando (409, garantido também por índice único).
- **Enquanto aguarda avaliação**, o documento não recebe versão nova (409).
- **Documento com avaliação registrada não pode ser excluído** (aguardando ou
  já decidida): excluir a correção "ressuscitaria" a versão devolvida, e excluir
  a aprovada apagaria o que o avaliador aprovou. Versão nova continua possível
  depois da decisão.
- **Reenvio:** devolvido → enviar a versão nova (rota de versões) → reenviar.
  O reenvio é um item novo no mesmo pedido, com a versão corrigida, ligado ao
  devolvido (`id_avaliacao_anterior`); o pedido volta a `pendente`. Cada
  devolvido é reenviado uma vez.
- **Situação do pedido:** `pendente` enquanto houver documento aguardando;
  `concluida` quando todos foram decididos.
- **Sigilo:** toda rota confere o acesso ao processo antes de ler o pedido;
  sem acesso, ou de outra prefeitura, 404. As caixas filtram pela credencial
  atual do usuário.

## Avisos

In-app, com `link_url` para `/m/protocolo/processos/{id}`:

| Tipo | Para quem | Quando |
|---|---|---|
| `avaliacao_solicitada` | avaliador | pedido criado |
| `avaliacao_decidida` | quem pediu | cada envio de decisões (um aviso por envio, não por documento) |
| `avaliacao_reenviada` | avaliador | reenvio de um devolvido |

O aviso sai depois do commit; se falhar, o ato continua valendo.

Trilha: `audit_log` com `processo.avaliacao_solicitada`, `processo.avaliacao_decidida`
e `processo.avaliacao_reenviada`.

## Para a trava no fluxo (SI-75)

`services.avaliacoes.pendencias_do_processo` devolve quantos documentos estão
aguardando e quantos foram devolvidos sem reenvio; `.livre` é a condição
"exige aprovação documental".

## Fora deste card

- Telas (SI-74) e trava no fluxo (SI-75).
- Cancelar um pedido.
- Desentranhar um documento em avaliação continua possível.
- A permissão do avaliador é conferida, no pedido, pelos grupos globais dele
  (sem a lotação da sessão); grupo vinculado só a uma lotação não conta ali.
