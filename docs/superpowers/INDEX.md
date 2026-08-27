# Specs e planos — índice por evidência

> **Status:** vivo (gerado a partir de evidência mensurável) · **Autoridade
> sobre:** nada. **Última verificação:** 2026-08-27.

27 specs e 26 planos, de 2026-07-13 a 2026-08-24. São
**registro de decisão**, não descrição do presente: cada um descreve o que se
pretendia no dia em que foi escrito.

**Esta pasta não pode ser reorganizada por gosto.** Migrations citam specs daqui
como *autoridade* da decisão — `0081`, `0092`–`0098` e outras. Renomear ou mover
um arquivo aqui quebra a trilha de "por que esta tabela é assim", e
`tests/test_guarda_links_docs.py` reprova.

## O que a coluna "evidência" quer dizer, e o que não quer

Ela lista o que é **verificável hoje**, não um veredito de entrega:

- **código** — algum `.py`/`.ts` cita este spec como autoridade. Sinal forte: o
  código existe e aponta para cá.
- **ledger** — há registro de execução por subagente em `.superpowers/sdd/`
  (git-ignored, local).
- **—** — nenhum dos dois. **Não** significa "não entregue": a maioria das
  fatias de 2026-07 foi entregue sem deixar nenhum desses dois rastros. Só
  significa que daqui não dá para afirmar nada.

Para saber se algo está de pé, a resposta está no código e em
[../BACKLOG-PENDENCIAS.md](../BACKLOG-PENDENCIAS.md) — não nesta tabela.

## Specs

| Spec | Último commit | Plano | Evidência |
|---|---|---|---|
| [`2026-07-13-pagamentos-pag1-cadastros-design.md`](specs/2026-07-13-pagamentos-pag1-cadastros-design.md) | 2026-07-13 | [plano](plans/2026-07-13-pagamentos-pag1-cadastros.md) | — |
| [`2026-07-14-pagamentos-caixa-autorizacao-design.md`](specs/2026-07-14-pagamentos-caixa-autorizacao-design.md) | 2026-07-14 | — | — |
| [`2026-07-16-pagamentos-demo-dashboard-design.md`](specs/2026-07-16-pagamentos-demo-dashboard-design.md) | 2026-07-16 | [plano](plans/2026-07-16-pagamentos-demo-dashboard.md) | — |
| [`2026-07-16-pagamentos-rito-ux-design.md`](specs/2026-07-16-pagamentos-rito-ux-design.md) | 2026-07-16 | [plano](plans/2026-07-16-pagamentos-rito-ux.md) | — |
| [`2026-07-17-design-system-v3-design.md`](specs/2026-07-17-design-system-v3-design.md) | 2026-07-16 | [plano](plans/2026-07-17-design-system-v3.md) | — |
| [`2026-07-20-pr-f-phases-4-5-oauth-design.md`](specs/2026-07-20-pr-f-phases-4-5-oauth-design.md) | 2026-07-20 | [plano](plans/2026-07-20-pr-f-phases-4-5-oauth-implementation.md) | — |
| [`2026-07-24-legacy-schema-bootstrap-design.md`](specs/2026-07-24-legacy-schema-bootstrap-design.md) | 2026-07-24 | [plano](plans/2026-07-24-legacy-schema-bootstrap.md) | — |
| [`2026-07-28-modularizacao-launcher-design.md`](specs/2026-07-28-modularizacao-launcher-design.md) | 2026-07-29 | — | — |
| [`2026-07-30-leitura-por-modulo-escopo.md`](specs/2026-07-30-leitura-por-modulo-escopo.md) | 2026-07-30 | [plano](plans/2026-07-30-leitura-por-modulo.md) | ledger |
| [`2026-07-31-transporte-costura-navegacao-design.md`](specs/2026-07-31-transporte-costura-navegacao-design.md) | 2026-08-01 | [plano](plans/2026-07-31-transporte-costura-navegacao.md) | ledger |
| [`2026-08-01-arquitetura-modular-monolito-design.md`](specs/2026-08-01-arquitetura-modular-monolito-design.md) | 2026-08-01 | [plano](plans/2026-08-01-arquitetura-modular-monolito.md) | — |
| [`2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md`](specs/2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md) | 2026-08-03 | [plano](plans/2026-08-04-transporte-p5-1-recadastramento-ciclo.md) | — |
| [`2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md`](specs/2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md) | 2026-08-04 | — | — |
| [`2026-08-05-transporte-p5.3-atraso-suspensao-design.md`](specs/2026-08-05-transporte-p5.3-atraso-suspensao-design.md) | 2026-08-05 | — | — |
| [`2026-08-05-transporte-p6-pontos-design.md`](specs/2026-08-05-transporte-p6-pontos-design.md) | 2026-08-05 | [plano](plans/2026-08-05-transporte-p6-pontos.md) | — |
| [`2026-08-06-pagamentos-fluxo-design.md`](specs/2026-08-06-pagamentos-fluxo-design.md) | 2026-08-07 | — | — |
| [`2026-08-07-ia-1-assistente-do-processo-design.md`](specs/2026-08-07-ia-1-assistente-do-processo-design.md) | 2026-08-27 | — | — |
| [`2026-08-11-1-0-8-leitura-com-permissao-escopo.md`](specs/2026-08-11-1-0-8-leitura-com-permissao-escopo.md) | 2026-08-12 | — | — |
| [`2026-08-13-pagamentos-onda-c13-escopo.md`](specs/2026-08-13-pagamentos-onda-c13-escopo.md) | 2026-08-13 | — | — |
| [`2026-08-16-ux-hotfix-crud-pagination-escopo.md`](specs/2026-08-16-ux-hotfix-crud-pagination-escopo.md) | 2026-08-16 | — | — |
| [`2026-08-16-ux-hotfix-dialog-focus-escopo.md`](specs/2026-08-16-ux-hotfix-dialog-focus-escopo.md) | 2026-08-16 | — | — |
| [`2026-08-16-ux-modernizacao-master.md`](specs/2026-08-16-ux-modernizacao-master.md) | 2026-08-20 | — | — |
| [`2026-08-21-transporte-p6b-linhas-design.md`](specs/2026-08-21-transporte-p6b-linhas-design.md) | 2026-08-21 | [plano](plans/2026-08-21-transporte-p6b-linhas.md) | — |
| [`2026-08-21-transporte-p7-ocorrencias-design.md`](specs/2026-08-21-transporte-p7-ocorrencias-design.md) | 2026-08-21 | [plano](plans/2026-08-21-transporte-p7-ocorrencias.md) | — |
| [`2026-08-23-transporte-p5-pendencias-design.md`](specs/2026-08-23-transporte-p5-pendencias-design.md) | 2026-08-23 | [plano](plans/2026-08-23-transporte-p5-pendencias.md) | — |
| [`2026-08-23-transporte-p8-workflows-design.md`](specs/2026-08-23-transporte-p8-workflows-design.md) | 2026-08-23 | [plano](plans/2026-08-23-transporte-p8-workflows.md) | — |
| [`2026-08-24-pagamentos-c2-integracoes-design.md`](specs/2026-08-24-pagamentos-c2-integracoes-design.md) | 2026-08-24 | [plano](plans/2026-08-24-pagamentos-c2-integracoes.md) | — |

## Planos sem spec pareado

- [`2026-07-14-pagamentos-R1-caixa.md`](plans/2026-07-14-pagamentos-R1-caixa.md)
- [`2026-07-14-pagamentos-R2-debitos-autorizacao.md`](plans/2026-07-14-pagamentos-R2-debitos-autorizacao.md)
- [`2026-07-28-modularizacao-f1.md`](plans/2026-07-28-modularizacao-f1.md)
- [`2026-07-30-modularizacao-f2.md`](plans/2026-07-30-modularizacao-f2.md)
- [`2026-08-03-modularizacao-f3.md`](plans/2026-08-03-modularizacao-f3.md)
- [`2026-08-04-transporte-p5-2-atendimento.md`](plans/2026-08-04-transporte-p5-2-atendimento.md)
- [`2026-08-05-transporte-p5.3.md`](plans/2026-08-05-transporte-p5.3.md)
- [`2026-08-06-pagamentos-f1-fundacao.md`](plans/2026-08-06-pagamentos-f1-fundacao.md)
- [`2026-08-25-pagamentos-f2-ajustes-versionamento.md`](plans/2026-08-25-pagamentos-f2-ajustes-versionamento.md)
- [`2026-08-26-pagamentos-f3-ordem-cronologica.md`](plans/2026-08-26-pagamentos-f3-ordem-cronologica.md)

## Convenção

`YYYY-MM-DD-<tema>-design.md` (ou `-escopo.md`) para spec; mesmo prefixo em
`plans/` para o plano de implementação. A data é a de **redação**, não a de
entrega — e é por isso que ela não serve para inferir status.
