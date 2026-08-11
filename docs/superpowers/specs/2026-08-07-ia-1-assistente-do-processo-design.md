# IA-1 — Assistente do processo aberto

**Status:** aprovado · **Data:** 2026-08-07 · **Decisões:** Jorge

Primeira fatia do assistente conversacional. Substitui, para o MVP, o C1+C2 do
[`CHATBOT-PLAN.md`](../../../CHATBOT-PLAN.md) — que continua válido como destino, não como
próximo passo.

## 1. O que muda em relação ao plano de maio

O `CHATBOT-PLAN.md` é de 2026-05-28 e nunca virou código (`app/services/ia/` não existe). Três
coisas mudaram desde então, e a terceira é a que determinou o escopo desta fatia.

**A trava que o próprio plano declarava caiu.** Ele encerra dizendo que "o chatbot depende [do
sigilo gradual] para enforcement de acesso — convém fechar o sigilo antes de iniciar C2". O sigilo
está fechado: `services/sigilo.py::assert_acesso_processo` existe, devolve 404 (nunca 403, que
confirmaria existência) e há guarda proibindo o carregador cru de anexo em router.

**Apareceu um pré-requisito que o plano não conhece.** Ele antecede a modularização (2026-07-30).
As ferramentas que lista — `buscar_processo`, `meus_processos` — pertencem todas ao módulo
`protocolo`, e teriam de passar pelo gate de contratação. O plano não menciona `require_modulo`
porque `require_modulo` não existia.

**E o achado que reescreveu o escopo: um chatbot com busca muda a gravidade do item 1.0.8.**

Hoje qualquer autenticado do tenant pode ler `/usuarios`, `/grupos`, `/audit` e processos de
qualquer setor — o eixo de permissão não é aplicado na leitura. O backlog classifica isso **sem
prazo**, e com razão, porque na prática é *latente*: o menu é filtrado por permissão (`canSeeItem`),
então quem não tem acesso nunca vê o link, e alcançar o dado exige saber a URL de cor.

**Um chatbot com busca remove exatamente esse atrito.** Ele é uma interface de consulta universal em
linguagem natural: `buscar_processo("NUP 99999.000123/2026-45")` entrega numa frase o que hoje exige
conhecer a rota. O bot não cria o buraco — ele converte um buraco latente num explorável, na
velocidade da conversa. O gatilho que o item 1.0.8 registra para priorização é "a criação do
primeiro grupo não-SU"; **o chatbot com busca é um segundo gatilho, e o documento não o conhece.**

Daí o escopo desta fatia.

## 2. Escopo

**O assistente responde apenas sobre um processo que o usuário já abriu.** Ele vive dentro de
`/m/protocolo/processos/[id]`. Não busca, não lista, não encontra.

Isso contorna o item 1.0.8 em vez de depender dele: o usuário já atravessou toda a autorização que
existe hoje para abrir aquele processo. O assistente não amplia o alcance de ninguém — só reduz o
esforço de ler o que já está na tela.

| Dentro | Fora, deliberadamente |
|---|---|
| Resumo do andamento | Qualquer busca ou listagem |
| O que significa a última movimentação | Conteúdo de anexo (só metadado) |
| Prazo e temporalidade | Portal do cidadão |
| Classe CCD aplicável | Qualquer ação que mude estado |
| Glossário (NUP, CCD, TTD, LAI, sigilo) | Persistência de conversa |

## 3. A decisão de arquitetura: contexto no prompt, não tool-calling

O plano previa um catálogo de ferramentas que o modelo chama (D3). **Para esta fatia isso é a
escolha errada, e o motivo não é simplicidade.**

Com tool-calling, o guard de sigilo tem de valer em **cada** ferramenta, para sempre, inclusive na
que alguém acrescentar daqui a seis meses. É precisamente a costura router↔service onde o download
de anexo ficou aberto por sete meses: `require_permission` não cobria sigilo, o endpoint só falava
em `anexo_id`, e a listagem — que filtrava certo — dava a impressão de que o assunto estava
resolvido.

Injetando o processo **já resolvido e já autorizado** no prompt, o modelo não tem como alcançar dado
fora dele: não existe ferramenta para chamar. O isolamento vira propriedade da arquitetura em vez de
disciplina recorrente. Um caminho novo não pode esquecer um guard que não precisa aplicar.

O tool-calling volta quando a busca voltar. Aí ele é necessário — e aí o item 1.0.8 é pré-requisito.

## 4. Fluxo

```
POST /api/v2/ia/processos/{id}/perguntar          (StreamingResponse SSE)

  1. require_permission("processo")     ← eixo de permissão
  2. require_modulo("protocolo")        ← eixo de contratação
  3. assert_acesso_processo(...)        ← eixo de sigilo
  4. get_processo_detail(...)           ← o que o usuário já veria na tela
  5. calcular_temporalidade(...)        ← número calculado em Python
  6. prompt + pergunta → claude-opus-5 → SSE
```

**Os três guards vêm antes do passo 4 de propósito.** A autorização precede a resolução do recurso;
invertido, a mensagem de erro distingue "existe" de "não existe" para quem não pode saber. Mesma
lição do conserto do anexo.

**Números não passam pelo modelo.** `calcular_temporalidade` roda em Python e o resultado entra no
contexto já pronto. O modelo redige, não calcula — a alucinação aritmética fica impossível por
construção, não por instrução.

## 5. Recusa é requisito, não enfeite

Resposta inventada sobre processo é inaceitável num sistema de governo. Duas defesas:

- **Estrutural:** o contexto é a única fonte. Não há ferramenta, não há busca, não há web.
- **De prompt:** instrução explícita de recusar quando o contexto não contém a resposta, e de citar
  sempre o número do processo / a data da movimentação de onde tirou cada afirmação.

A validação factual pesada do plano (C4) continua fora — mas com contexto fechado o espaço de
alucinação é muito menor do que o plano assumia.

## 6. Persistência: nenhuma

Sem migration, sem tabela. Cada pergunta é independente; o histórico vive na tela enquanto ela está
aberta.

**A razão é LGPD, não economia de trabalho.** `ia_mensagem` seria um repositório novo de conteúdo
ligado a processo — potencialmente sigiloso — com política de retenção a definir, direito de
eliminação a implementar e uma superfície de vazamento que hoje não existe. Não se cria isso numa
primeira fatia. Telemetria e feedback entram quando houver decisão sobre retenção.

Consequência aceita: não dá para medir custo por tenant ainda.

## 7. Degradação sem chave

`ANTHROPIC_API_KEY` não está configurada em nenhum ambiente. O sistema **não pode quebrar por causa
disso**:

- Sem chave, o endpoint devolve **503** com mensagem clara, e a tela não mostra o assistente.
- O `import anthropic` é **lazy**, dentro do cliente concreto. Nada no boot depende do SDK.
- Os testes usam um cliente dublê e **nunca tocam a rede**. A suíte tem de passar sem chave, sem
  rede e sem o pacote instalado.

## 8. Arquivos

| Arquivo | Papel |
|---|---|
| `services/ia/llm_client.py` | protocolo `LLMClient` + `AnthropicClient` (import lazy, `claude-opus-5`) |
| `services/ia/contexto.py` | monta o texto do processo a partir de `get_processo_detail` + temporalidade |
| `services/ia/assistente.py` | orquestra: guards → contexto → prompt → stream |
| `services/ia/conhecimento.py` | glossário do domínio (NUP, CCD, TTD, LAI, níveis de sigilo) |
| `routers/ia.py` | a rota SSE; registrada em `main.py` com `prefix="/api/v2"` |
| `components/protocolo/AssistenteProcesso.tsx` | painel na tela do processo |

Sem migration. Sem rota de topo nova (é `/api/v2/*`, o nginx já roteia).

## 9. Como se prova

- **Sigilo:** usuário com credencial baixa perguntando sobre processo acima dela recebe 404 — e o
  teste é **invertido** removendo o `assert_acesso_processo`, para provar que ele é quem barra.
- **Contratação:** tenant sem `protocolo` recebe 403.
- **Permissão:** teste HTTP com **usuário comum**, não super-usuário — a suíte inteira exercitando SU
  já escondeu 10 rotas com 500 no transporte.
- **Sem chave:** 503, e a suíte verde.
- **O contexto não vaza:** teste que monta o contexto de um processo e afirma que nenhum dado de
  outro processo do mesmo tenant aparece nele.
