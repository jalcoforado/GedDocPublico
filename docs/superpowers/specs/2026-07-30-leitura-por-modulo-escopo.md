# Fechar a leitura por módulo — escopo

**Item:** `docs/BACKLOG-PENDENCIAS.md` § 1.0.5
**Data:** 2026-07-30
**Estado:** escopo para aprovação. **Nada implementado.**

## O problema

A fatia F1 da modularização barra **escrita** de módulo não contratado, não **leitura**. São 76 GETs
que pertencem a um módulo e só exigem `get_current_user`. Consequência: um tenant que não contratou
Pagamentos não lança débito, mas continua listando débitos pela API. A contratação é meia barreira.

Os routers da geração protocolo seguem uma convenção anterior à modularização — *escrita gateada,
leitura liberada a qualquer autenticado do tenant*. Não é esquecimento pontual: é sistemático.
Pagamentos, frota e transporte já gateiam as duas pontas e não aparecem aqui.

## A decisão (Jorge, 2026-07-30)

"Fechar a leitura" são **dois** problemas, e a solução óbvia resolveria os dois sem ninguém pedir:

| | O que é | Fecha com |
|---|---|---|
| **Buraco da modularização** | tenant sem o módulo contratado lê os dados dele | contratação |
| **Buraco de autorização** | qualquer autenticado do tenant lê `/usuarios`, `/grupos`, `/audit` | permissão por usuário |

Pôr `require_permission("processo")` num GET fecharia os dois — mas o segundo é **mudança de
política de acesso**: passaria a exigir que cada usuário tivesse a transação concedida. Hoje seria
inócuo, porque todo grupo do sistema é super-usuário (`nivel.valor = 0`, verificado por query); no
dia do primeiro grupo Operacional, os 76 GETs virariam 403 até alguém conceder — e essa concessão é
decisão do dono do produto, registrada como item 1.0.7 justamente por isso.

**Decisão: esta fatia fecha apenas a contratação.** Nenhum usuário perde leitura que tenha hoje. O
buraco de autorização vira item próprio de backlog, sem prazo.

## O que muda

Nasce uma dependência `require_modulo(slug)`, ao lado de `require_permission` em
`backend/app/auth/`. Ela resolve `tenant_id` do caller, consulta os slugs contratados
(`services/modulos.slugs_contratados`, que já existe e já é usada pelo gate da F1) e devolve **403**
se o módulo não estiver disponível para o tenant.

Diferença essencial para `require_permission`: ela **não olha o usuário**. Não consulta grupo,
transação ou nível. Um usuário sem nenhuma permissão continua lendo o que lê hoje, desde que o
tenant tenha o módulo.

Aplicada aos 76, a granularidade colapsa: só existem **dois** slugs envolvidos.

| Módulo | GETs | Grupos de rota |
|---|---|---|
| `protocolo` | 62 | processos e artefatos (40), catálogo documental (7), workflow (7), localização (4), assunto (2), manifestante (2) |
| `administracao` | 14 | usuário e grupos (5), configuração e auditoria (6), unidade de trabalho (3) |

## O método — e por que ele não é opcional

**A lista do `ENDPOINTS_LEITURA_SEM_GATE` não serve como fonte de propriedade de módulo.** Ela foi
escrita para responder "que código de permissão este endpoint deveria receber", que é outra pergunta.
Pelo menos uma entrada está no módulo errado para o propósito desta fatia:

> `GET /api/v2/catalogo/prioridades` está agrupado sob `administracao / configuracao`, mas quem o
> consome é `frontend/components/AcoesProcesso.tsx` — tela de **protocolo**. Gatear pelo agrupamento
> daria 403 nas ações de processo de um tenant que tem protocolo e não tem administração.

É exatamente o defeito que o review da Task 8 pegou em `/jobs/limpar-antigos`, e ele reaparece porque
a mesma lista foi reusada para outro fim. Portanto:

**Cada um dos 76 tem a propriedade de módulo confirmada pelo consumo real** — quem chama o endpoint
no frontend — antes de receber a dependência. Onde o consumo cruzar módulos, o endpoint é
**transversal** e não recebe gate nenhum, com a razão registrada.

Cuidado ao verificar: `grep` de nome curto produz falso positivo. `niveis` casa com
`veiculosDisponiveis`, e por um momento pareceu que a frota consumia um catálogo de administração.
Confirmar pelo símbolo do cliente de API (`api.niveis`, `api.prioridades`), não pelo fragmento de
URL.

## Endpoints que merecem decisão explícita na triagem

Não são exceções decididas — são os que eu já sei que vão exigir julgamento:

- **`GET /api/v2/busca`** — busca global. Gatear com `protocolo` tira a busca inteira de um tenant
  sem protocolo. Provável transversal.
- **`GET /api/v2/audit`** — trilha de auditoria sob `administracao`. Um tenant sem administração
  contratada perde a leitura da própria auditoria. Discutível: auditoria é compliance, não módulo.
- **`GET /api/v2/jobs*`** (4) — a Task 8 já decidiu que os disparos são de protocolo; a leitura
  segue o mesmo dono por coerência.
- **`GET /api/v2/estados` / `/cidades` / `/bairros`** — geografia. É catálogo público de fato;
  gatear tem custo e nenhum ganho de sigilo.
- **`GET /api/v2/assinaturas/{id}/validar`** — confirmado que **este** é o autenticado; a validação
  pública do cidadão é outra rota, então gatear não quebra o portal.

## Testes

- Tenant **sem** o módulo: GET representativo de cada grupo devolve **403**.
- Tenant **com** o módulo: os mesmos GETs devolvem 200.
- **Usuário sem permissão nenhuma, tenant com o módulo: continua lendo.** É a prova de que a fatia
  não mudou política de acesso — a propriedade central da decisão do Jorge.
- Super-usuário de tenant sem o módulo: **403** (a dependência não tem bypass, igual ao gate da F1).
- A guarda `test_endpoint_de_modulo_tem_gate` passa a reconhecer `require_modulo` como gate válido, e
  o `ENDPOINTS_LEITURA_SEM_GATE` encolhe para os transversais decididos acima — cada um com a razão
  escrita.

## Fora de escopo

- **O buraco de autorização.** `/usuarios`, `/grupos`, `/audit` e os demais continuam legíveis por
  qualquer autenticado do tenant. Vira item de backlog.
- Concessão das 9 transações a grupos (item 1.0.7) — esta fatia deliberadamente **não** depende dela.
- Escrita: já está gateada desde a F1.
- Módulos pagamentos, frota e transporte: já gateiam leitura, não entram.

## Risco conhecido

Cada endpoint gateado ganha o custo de resolver a contratação do tenant — as mesmas consultas que o
gate da F1 já faz por request. Em 76 rotas de leitura, algumas de listagem quente, vale medir antes
de assumir que é grátis. Se pesar, o caminho é memorizar o resultado por request
(`request.state`), não abrir mão do gate.
