# Versão nova de documento do processo

> **Status:** vivo · **Autoridade sobre:** como se corrige um documento juntado ao processo sem apagar o anterior, o que fica bloqueado e onde cada versão aparece.
> **Última verificação:** 2026-11-26 (SI-72, RF-04 V1).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Fonte de verdade executável: `backend/app/services/anexos.py` (`enviar_nova_versao`,
`alvo_de_versao`, `criar_versao_sem_commit`), `services/minutas.py` (versão
redigida), `backend/tests/test_anexo_versao.py`, `test_jobs_acesso.py` e
`frontend/components/__tests__/AnexoVersoes.test.tsx`. Migration `0147`.

## Como funciona

`POST /api/v2/processos/{processo_id}/anexos/{anexo_id}/versoes` (arquivo + `motivo`
opcional). A versão nova é um `protocolos.anexo` **novo**, com `id_anexo_anterior`
apontando para o substituído e `versao` = anterior + 1.

- **Folha não se renumera.** A versão nova entra **no fim** do processo, como
  qualquer juntada, com número próprio. A anterior continua no processo com a
  mesma posição, as mesmas folhas e dentro do PDF completo. Uma citação
  "fls. 70" feita antes continua apontando para o mesmo papel.
- **É o mesmo documento.** A nova herda descrição, tipo, publicidade e o
  vínculo com o documento exigido (o checklist continua atendido).
- **Assinatura não passa adiante.** Ela vale para o arquivo assinado. A
  validação pública do arquivo antigo continua válida e avisa que ele foi
  substituído por versão posterior.
- **Rastro:** `audit_log` com `acao = processo.anexo_nova_versao` (anterior,
  nova, versão, motivo).

## Onde cada versão aparece

| Lugar | O que mostra |
|---|---|
| Lista de documentos do processo | A vigente; as anteriores recolhidas sob ela ("Ver versão anterior"), marcadas "substituído". |
| PDF completo do processo, numeração e folhas | Todas, na ordem de juntada. A substituída leva, em cada página, a faixa "DOCUMENTO SUBSTITUÍDO PELA VERSÃO N · mantido no processo como histórico". |
| Carimbo avulso e .zip de PDFs carimbados | Igual ao PDF completo. Versão 2+ leva "versão N" no cabeçalho. O estado entra no nome do cache (`{id}-subst-v{N}.pdf`), então substituir ou excluir a versão nova nunca serve um carimbo desatualizado. |
| Portal do cidadão | Só a vigente (se for pública). |
| Validação pública da assinatura | O arquivo assinado, com o aviso de substituição. |

## O que fica bloqueado

| Caso | Resposta | Por quê |
|---|---|---|
| Versão já substituída | 409 | Só a vigente recebe correção; nada de ramificar. Um índice único parcial garante uma sucessora viva por versão, inclusive com dois envios ao mesmo tempo. |
| Processo arquivado | 409 | Desarquive antes. |
| Herdado de apensamento | 409 | O documento pertence ao processo de origem. |
| Arquivo que acompanha o despacho, e o próprio PDF do despacho | 409 | A peça é o conjunto, já assinado. |
| Documento aguardando avaliação (SI-73) | 409 | A avaliação aponta para esta versão exata. |
| Excluir a versão substituída | 400 | É histórico. |
| Excluir versão com avaliação registrada (SI-73) | 400 | É histórico da avaliação. |
| Excluir a versão vigente assinada | 400 | Regra geral da Assinatura v2. |
| Processo acima da credencial de sigilo, ou de outra prefeitura | 404 | Guard `assert_acesso_processo` antes de tudo. |

## Duas formas de enviar a versão nova

- **Enviar arquivo:** a rota acima.
- **Redigir no sistema:** `POST /processos/{id}/minutas` com `id_anexo_substitui`
  (e `motivo_versao`). Cria um rascunho comum, marcado "versão nova de X" em
  "Documentos redigidos". Se o anterior também foi redigido e nenhum modelo nem
  texto vier, o rascunho começa com o texto dele. Só ao **finalizar** o rascunho
  o PDF entra como versão seguinte, com a regra revalidada sob trava: se outra
  versão chegou nesse meio-tempo, 409 e o rascunho continua rascunho. Despacho
  não pode ser versão de outro documento.

Documento redigido aceita versão nova pelas duas formas (antes ficava
bloqueado com "reabra a minuta").

## Arquivo errado enviado por engano

A versão **vigente** pode ser excluída enquanto não estiver assinada. A
anterior volta a ser a vigente e aceita de novo uma versão nova, que nasce
outra vez como versão 2 (a excluída deixa de contar: a busca da sucessora e o
índice único olham só `excluido = false`). Desde o SI-73, a versão com
avaliação registrada (aguardando ou decidida) também não sai: excluir a
correção "ressuscitaria" a versão devolvida. Ver
[avaliacao-de-documentos](avaliacao-de-documentos.md).

## Contagem de páginas (vale para todo upload de PDF)

`anexos.contar_paginas_pdf` lê a árvore de páginas com o `pypdf`. Até o SI-72
a conta era a busca do texto `/Type /Page` no arquivo, que também casa com o nó
`/Type /Pages`: um PDF de 17 páginas virava 18, e o erro passava para as "fls."
de todo documento seguinte. A busca textual ficou só para PDF que o `pypdf` não
abre. **Anexos antigos continuam com a contagem antiga**; recontá-los é outro
trabalho.

## Sigilo no envio e na exclusão

Até o SI-72 o upload avulso (`POST /processos/{id}/anexos`) e a exclusão
(`DELETE /processos/{id}/anexos/{anexo_id}`) não passavam pelo guard de sigilo:
quem tinha a permissão `processo` anexava ou excluía em processo acima da sua
credencial. As três rotas agora chamam `assert_acesso_processo` antes de ler o
recurso (`test_sigilo_barra_upload_versao_e_exclusao`).

## Tarefas em segundo plano: .zip e acesso ao resultado

O antigo "Pré-carimbar PDFs" agora entrega um **.zip** com um PDF carimbado por
documento ("Doc 04 - CNPJ (versão 2).pdf"; a substituída com a faixa e
" - substituída" no nome), na ordem do processo, sem os desentranhados, e um
`relatorio.txt` dentro (`tasks/carimbar_anexos.py::gerar_zip_carimbados`).

Até o SI-72, `GET /jobs/{id}` e `GET /jobs/{id}/resultado` só conferiam a
prefeitura, o módulo e a permissão `processo`: qualquer servidor baixava o
resultado de tarefa alheia trocando o id, inclusive o PDF completo de processo
sigiloso; e disparar o PDF completo ou o carimbo não olhava o sigilo. Agora
(`routers/jobs.py`): disparar exige acesso ao processo (404); consultar e baixar
só quem disparou (ou super-usuário), com o sigilo reconferido na hora.
`test_jobs_acesso.py` reprova a volta do furo. A tela de Tarefas não oferece
"Baixar" em tarefa alheia.

## Fora deste card

- Pedido de avaliação e decisão por documento: entregue no SI-73, em
  [avaliacao-de-documentos](avaliacao-de-documentos.md).
- Desentranhar uma versão continua possível. Se a vigente for desentranhada, a
  substituída volta a aparecer na lista principal, para não sumir da tela.
