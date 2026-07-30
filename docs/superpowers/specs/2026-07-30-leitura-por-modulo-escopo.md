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

## Resultado da triagem (2026-07-30)

Verificado por consumo real no frontend, endpoint a endpoint. **Tentei automatizar e não convergiu:**
o `api.ts` mistura métodos planos (`api.prioridades`), objetos aninhados (`api.unidades.list`) e
construtores de URL usados como `href` (os relatórios), e cada versão do parser errava um subconjunto
diferente. O que produziu resultado foi verificação dirigida pelo símbolo real de chamada.

**O achado que muda a forma da fatia: os cadastros de "administração" são infraestrutura
transversal, não features de um módulo.**

| Endpoint | Agrupado como | Consumido de fato por |
|---|---|---|
| `GET /unidades-trabalho` | administracao | **4 módulos** — administração, frota (motoristas, solicitações, veículos), protocolo (processos, relatórios, tramitação, serviços, `AcoesProcesso`) |
| `GET /usuarios` | administracao | **3 módulos** — protocolo (relatório de assinaturas, `AssinaturasProcesso`), transporte (alvarás), administração |
| `GET /catalogo/prioridades` | administracao | **protocolo** — `AcoesProcesso.tsx` |

Unidade de trabalho e usuário são o organograma e as pessoas: todo módulo os referencia. Gatear com
`administracao` daria 403 em frota e protocolo de qualquer tenant que não contratasse administração.

### Classificação proposta dos 76

| | Quantos | Quais |
|---|---|---|
| **Gatear `protocolo`** | 58 | processos e artefatos, anexos, assinaturas, relatórios, catálogo documental, assunto, manifestante, localização, workflow — **mais** `/catalogo/prioridades`, que sai de administração |
| **Gatear `administracao`** | 12 | `/grupos` (3), `/organograma`, `/catalogo/niveis`, `/sistemas`, `/transacoes`, `/tipos-unidade`, **`/jobs` (4)** |
| **NÃO gatear — transversal** | 6 | `/usuarios`, `/usuarios/{id}`, `/unidades-trabalho`, `/unidades-trabalho/{id}` (consumo cruzado comprovado), **`/busca`**, **`/audit`** (decisão do Jorge) |

Total: 58 + 12 + 6 = 76.

Verificações que sustentam o bloco "protocolo": `api.manifestantes`, `api.assuntos`,
`api.tiposProcesso`, `api.tiposAnexo`, `api.cidades`, `api.bairros`, `api.enderecos`, `api.estados`
— todos consumidos **só** por telas de protocolo. Os relatórios não passam pelo cliente de API: são
`href` montados a partir de `BROWSER_API_URL`, o que explica por que nenhuma busca por símbolo os
encontrava.

Verificações que sustentam o bloco "administração": `api.grupos` (telas de grupos e usuários),
`api.niveis`, `api.sistemas`, `api.transacoes` (só a tela de grupos), `api.tiposUnidade`
(`components/organograma/UnidadeEditDrawer.tsx`).

### Decisões do Jorge sobre os 6 pendentes (2026-07-30)

- **`/busca` — transversal, sem gate.** É recurso do sistema, não do módulo. Quando outros módulos
  entrarem no índice, um gate de protocolo estaria errado de qualquer forma.
- **`/audit` — transversal, sem gate.** Auditoria é compliance: registra ações de todos os módulos, e
  uma prefeitura sob guarda legal não pode perder a leitura da própria trilha por não ter contratado
  o módulo administração.
- **`/jobs`, `/jobs/agenda`, `/jobs/{id}`, `/jobs/{id}/resultado` — gatear como `administracao`**,
  seguindo a tela que os exibe.

  > **Inconsistência conhecida e aceita.** O review da Task 8 fez a chamada oposta para o endpoint
  > irmão: `/jobs/limpar-antigos` (POST) foi movido de `configuracao` para `processo` exatamente
  > para não acoplar um recurso de protocolo ao módulo administração. Com esta decisão, o POST e o
  > GET do mesmo recurso pertencem a módulos diferentes, e um tenant com protocolo e sem
  > administração dispara o job mas não lê o resultado. Está registrado aqui para que quem encontrar
  > isso depois saiba que foi decisão, não descuido.

### Os 6 pendentes — o material que sustentou as decisões acima

- **`/busca`** — busca global. Hoje varre processos, mas é apresentada como recurso do sistema, não
  do módulo. Gatear com `protocolo` tira a busca inteira de um tenant sem protocolo.
- **`/jobs`, `/jobs/agenda`, `/jobs/{id}`, `/jobs/{id}/resultado`** — a Task 8 decidiu que os
  **disparos** são de protocolo (os artefatos são de protocolo), mas a **tela** `/jobs` fica em
  administração. É o único caso em que o consumo cruzado é entre a tela dona e o dado processado.
- **`/audit`** — trilha de auditoria. Nenhum consumo encontrado pelo cliente de API (a tela de
  auditoria provavelmente monta a chamada de outro jeito — confirmar). Conceitualmente é compliance,
  não módulo: um tenant sem administração contratada perderia a leitura da própria auditoria.

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

## Custo medido — e por que a memoização NÃO foi feita

**Medição de 2026-07-30**, no container de dev, tenant `sobral` com os 6 módulos contratados.
Registrada aqui para ninguém refazer a conta.

| O quê | Mediana | p95 |
|---|---|---|
| `slugs_contratados()` isolado, 200 repetições | **1,88 ms** | 2,81 ms |
| `GET /assuntos` (gateada, listagem simples) | 11,97 ms | 15,02 ms |
| `GET /usuarios` (**não** gateada, listagem simples) | 10,60 ms | 13,40 ms |
| `GET /processos` (gateada, listagem quente) | 21,91 ms | 36,10 ms |

O gate custa ~1,4 ms na comparação entre pares de listagem equivalente, coerente com os 1,88 ms
medidos isoladamente. É de 6% a 13% do request, conforme o peso do endpoint.

**Decisão: não memoizar.** Não porque o custo seja desprezível, mas porque a memoização proposta no
plano não colheria a maior parte dele. Contando as chamadas reais por request numa amostra de 29
rotas gateadas: **28 resolvem a contratação exatamente uma vez**. Memoizar por request não economiza
nada onde só há uma chamada.

A exceção é instrutiva. `GET /processos` resolve **duas** vezes:

1. `auth/modulos.py::_check_modulo` → `slugs_contratados` (o gate desta fatia);
2. `routers/processos.py::_is_super` → `services/permissoes.load_permissions` →
   `services/modulos.codigos_bloqueados` → `slugs_contratados`.

O mesmo vale para as 8 rotas que passam por `require_acesso_processo` (`services/sigilo.py`), que
também carrega permissões. São ~9 de 70.

Memoizar de verdade exigiria alcançar **as duas** chamadas — e a segunda nasce dentro de
`services/`, que não conhece (nem deve conhecer) o `Request` do HTTP. Guardar em `request.state`,
como o plano sugeria, só alcança a primeira, que é justamente a que já é única. O ganho seria zero
em 61 rotas e exigiria empurrar concern de HTTP para a camada de serviço nas outras 9.

Se um dia esses ~1,9 ms importarem, o caminho certo não é memoização por request: é tornar
`slugs_contratados` mais barato na origem (hoje faz dois SELECTs) ou cachear o catálogo de módulos,
que é global e quase imutável. Ambos ficam fora desta fatia por YAGNI.
