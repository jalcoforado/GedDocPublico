# Item 1.0.8 — leitura passa a exigir permissão

*Escopo aprovado por Jorge em 2026-08-11. Fecha o item 1.0.8 do
`docs/BACKLOG-PENDENCIAS.md`, aberto de propósito pela fatia
`feat/leitura-por-modulo` (2026-07-30), que fechou o 1.0.5.*

## O problema, em uma frase

A contratação de módulo responde *"o tenant tem este módulo?"*. Ela nunca
respondeu *"este usuário pode ler isto?"* — e ninguém mais respondia.

## A medição que motiva a fatia (2026-08-11, por introspecção da app real)

| Categoria de GET sob `/api/v2` | Quantos |
|---|---|
| usuário + `require_permission` | 107 |
| usuário + `require_modulo`, **sem permissão** | 72 |
| só usuário autenticado | 15 |
| cidadão / plataforma / público | 17 |

Dos 15 "só autenticado", 8 são de si-mesmo (`/auth/me`, `/notificacoes/*`,
`/modulos/me`, `/tenants/me/onboarding`, `/auth/google*`) e continuam livres:
exigir transação para alguém ler os próprios dados não protege nada.

## Por que agora, e não depois

Hoje **não existe nenhum grupo não-super-usuário** — medido nos dois ambientes
pelo item 1.0.7 (`utils.nivel` só tinha `Super Usuario=0`). Como
`is_super_usuario` passa por cima do gate, esta fatia é **inerte no dia em que
entra**: ninguém perde acesso a nada.

É a janela mais barata que vai existir. Depois do primeiro grupo Operacional, a
mesma mudança deixa de ser inerte e vira evento disruptivo — 79 telas virando
403 de uma vez para aquele grupo.

## O que muda

`require_permission("<codigo>")` **sem `action`** (a forma de leitura) entra
**somando** ao gate que a rota já tem. Não substitui `require_modulo`: as duas
perguntas são independentes e ambas precisam de resposta.

- **contratação** — o tenant comprou o módulo? (`require_modulo`, não olha o usuário)
- **autorização** — este usuário tem a transação? (`require_permission`, não olha o módulo)

O código de cada GET é **herdado dos irmãos de escrita no mesmo router**, e não
inventado: `/processos/*` já grava sob `processo`, então lê sob `processo`. Onde
não havia irmão de escrita, o código está justificado caso a caso, abaixo.

## O que NÃO muda, e é decisão registrada

**Catálogos de leitura seguem livres ao autenticado do tenant**: `/estados`,
`/cidades`, `/bairros`, `/enderecos`, `/tipos-processo`, `/tipos-anexo`,
`/tipos-manifestante`, `/assunto-tipo-anexo`, `/catalogo/*`, `/protocolo/ccd-classes*`,
`/protocolo/especies-documentais`, `/protocolo/ttd-regras`, `/protocolo/sugerir-ccd`.

Razão: são as listas que preenchem `<select>` de formulário em todo módulo.
Exigir transação para ler "a lista de estados" não protege dado sensível
nenhum e obrigaria todo grupo futuro a receber `catalogo` só para abrir uma
tela. O gate de módulo continua valendo neles.

**Rotas de si-mesmo seguem livres** — ver a lista de 8, acima.

## Transação nova: `auditoria`

`/audit` não tem irmão de escrita e não havia código que lhe coubesse
(`utils.transacao` tem 24 e nenhum é de auditoria). Gatear com `usuario` ou
`configuracao` seria empurrar a trilha para dentro de um código que significa
outra coisa — e o próximo a ler o código de permissões entenderia errado.

Nasce `auditoria` (migration, `MODULO_TRANSACOES` → `administracao`, seed).

## Como isto pode dar errado

1. **Gatear com o código errado.** O sintoma é 403 para quem devia ler, e só
   aparece com grupo não-SU — que hoje não existe. Por isso a fatia leva teste
   HTTP com usuário comum, e não só teste de service: a suíte inteira exercita
   super-usuário, que **retorna antes** de olhar o gate (`auth/perms.py`).
2. **Esquecer que o SU passa.** Um teste que só usa SU passa verde com o gate
   errado, com o gate ausente e com o gate certo — os três.
3. **A guarda ficar verde por vacuidade.** `ENDPOINTS_LEITURA_SEM_GATE`
   encolhe nesta fatia; se ela encolher sem que os endpoints ganhem gate de
   verdade, nada reprova. Cada remoção é conferida por introspecção.

## Verificação

- `tests/test_guarda_modularizacao.py` — listas atualizadas no mesmo commit.
- `tests/test_1_0_8_leitura_com_permissao.py` — novo: usuário comum **com** a
  transação lê; **sem** a transação leva 403; super-usuário passa nos dois
  casos (o controle que prova que o teste não está medindo o SU).
- Suíte completa, e `npx tsc --noEmit` se algo do frontend mudar (não deve).
