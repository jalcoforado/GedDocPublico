# Índice — por onde entrar

> **Status:** vivo · **Autoridade sobre:** roteamento da documentação.
> **Última verificação:** 2026-08-27.

Este arquivo responde uma pergunta só: **"vou mexer em X — o que preciso ler
antes?"** Ele roteia por *tarefa*, não por assunto, porque a pergunta real de
quem chega nunca é "me fale sobre pagamentos" — é "vou tocar nisto, o que me
morde?".

## A regra de precedência

Quando dois documentos discordam, vale nesta ordem:

1. **O código e os testes.** Sempre. Um teste verde é a única afirmação que se
   auto-verifica.
2. **`CLAUDE.md`** — as regras que não podem ser quebradas. É carregado em toda
   sessão de IA e é o único documento mantido como contrato.
3. **Este índice e os docs vivos** abaixo.
4. **`docs/archive/`** — histórico. Por decisão registrada lá, nada ali é
   atualizado depois de arquivado; contradição com o código significa que o
   código mudou.

Documento não é autoridade sobre nada que um teste já cubra. Quando quiser
travar um comportamento, escreva a guarda — a lista delas está no fim.

## Roteador: vou mexer em…

| Vou… | Leia antes | Por quê |
|---|---|---|
| **escrever uma migration** | `CLAUDE.md` §Migrations | Boilerplate de RLS + GRANT por papel. As três armadilhas do boilerplate custaram 20 policies quebradas por 7 meses. |
| **criar tabela nova** | idem, + `CLAUDE.md` §Multi-tenancy | `tenant_id` NOT NULL, `ENABLE + FORCE RLS`, as duas policies, GRANT na tabela **e** na sequence. |
| **adicionar um módulo/tela** | `CLAUDE.md` §Adicionando um módulo | Sete coisas que costumam ser esquecidas — inclusive a regex do nginx, sem a qual a tela "não existe" no `:8090`. |
| **gatear um endpoint** | `CLAUDE.md` §Multi-tenancy e §Modularização | Módulo, permissão e sigilo são **três eixos independentes**; nenhum substitui outro. |
| **servir conteúdo de um processo** | `CLAUDE.md` §Sigilo gradual | `assert_acesso_processo` é obrigatório, inclusive onde a assinatura não menciona processo. Um download de anexo ficou aberto 7 meses assim. |
| **mexer em permissão/RBAC** | `CLAUDE.md` §Modularização · [RUNBOOK](../RUNBOOK.md) | Todo grupo é SU hoje; o gate está inerte. Quem criar o primeiro grupo não-SU precisa conceder leitura também. |
| **rodar/consertar a suíte** | `CLAUDE.md` §Testes e §Testes—convenções | `PYTEST_DB_HOST=db` é obrigatório. Teste com super-usuário passa pelo motivo errado. |
| **fazer deploy** | `CLAUDE.md` §Deploy | O portão `workflow_run`, o auto-sobrescrever do `deploy.sh` e o nome do projeto compose vindo do diretório. |
| **operar a VPS** | [RUNBOOK](../RUNBOOK.md) | Backup, firewall, observabilidade, incidentes. |
| **onboardar um tenant** | [RUNBOOK](../RUNBOOK.md) · [runbook do operador](runbooks/platform-operator-bootstrap.md) | `provisionar_tenant` é **dois atos** com sessões distintas. |
| **mexer em papéis de banco / RLS** | [ADR-016](architecture/adr/ADR-016-platform-operator-identity.md) · [inventário de bypass](architecture/security/rls-bypass-inventory.md) | A camada 1 está **inerte no runtime** (achado F-12). `SEC-RLS-ROLLOUT` é gate humano. |
| **tocar o admin de plataforma** | [ADR-016](architecture/adr/ADR-016-platform-operator-identity.md) · [matriz de claims](architecture/security/platform-operator-claims-matrix.md) | Outro realm: RS256 de IdP dedicado, `get_platform_db`, nunca `deps.py`. |
| **mexer no frontend** | `CLAUDE.md` §Frontend · [design-system](design-system.md) | `lib/api.ts` é o cliente único; o tipo tem de casar com o `response_model`. `tsc --noEmit` antes de commitar. |
| **integrar pagamentos** | [INTEGRACAO-PAGAMENTOS](INTEGRACAO-PAGAMENTOS.md) | Contrato de arrecadação/conciliação. |
| **ligar o Google Docs** | [GOOGLE-DOCS-OAUTH-SETUP](GOOGLE-DOCS-OAUTH-SETUP.md) | OAuth das minutas. |
| **saber o que falta** | [BACKLOG-PENDENCIAS](BACKLOG-PENDENCIAS.md) | Fonte viva. Não redescubra do zero. |
| **entender por que algo é assim** | `git log` · [docs/archive/](archive/README.md) · [HISTORICO-FASES](HISTORICO-FASES.md) | Arqueologia. Nada aqui descreve o presente. |

## Os documentos vivos

Cada um declara, no topo, seu **status**, sua **última verificação** e sobre o
que tem **autoridade**. Documento sem autoridade declarada é anotação, não
contrato — e o leitor precisa saber a diferença antes de agir.

### Contrato — mantidos como código

| Documento | Autoridade sobre |
|---|---|
| `CLAUDE.md` | As regras invioláveis. Carregado em toda sessão de IA. |
| [README](../README.md) | Orientação inicial, como rodar, como verificar. |
| [RUNBOOK](../RUNBOOK.md) | Operação: onboarding, backup, firewall, incidentes. |
| [BACKLOG-PENDENCIAS](BACKLOG-PENDENCIAS.md) | O que está em aberto, com data em cada evidência. |
| [ADR-016](architecture/adr/ADR-016-platform-operator-identity.md) | Identidade do operador de plataforma e papéis de banco. |

### Referência de domínio

| Documento | Autoridade sobre |
|---|---|
| [design-system](design-system.md) | Tokens, componentes, padrões de UI. |
| [INTEGRACAO-PAGAMENTOS](INTEGRACAO-PAGAMENTOS.md) | Contrato de arrecadação e conciliação. |
| [GOOGLE-DOCS-OAUTH-SETUP](GOOGLE-DOCS-OAUTH-SETUP.md) | Setup do OAuth das minutas. |
| [runbooks/platform-operator-bootstrap](runbooks/platform-operator-bootstrap.md) | Concessão/revogação de principal de plataforma. |
| [architecture/security/threat-model-platform-operator](architecture/security/threat-model-platform-operator.md) | Modelo de ameaça da fronteira de plataforma. |
| [acessos-teste-local](acessos-teste-local.md) | Credenciais e atalhos do ambiente local. |

### Registro — não descrevem o presente

| Documento | O que é |
|---|---|
| [HISTORICO-FASES](HISTORICO-FASES.md) | ~50 fases construídas, na ordem em que foram escritas. |
| [superpowers/INDEX](superpowers/INDEX.md) | Specs e planos por fatia, com o status de cada um. |
| [archive/](archive/README.md) | Escopo de PR mesclado, plano executado, recap de sessão. |
| [demo-roteiro-apresentacao](demo-roteiro-apresentacao.md) | Roteiro de demo. Parado desde 2026-06-07. |
| [assinatura-v2-operacao](assinatura-v2-operacao.md) | Operação da assinatura v2. Parado desde 2026-05-28. |
| [roadmap-pos-sec1-funcionalidades-mercado](roadmap-pos-sec1-funcionalidades-mercado.md) | Levantamento de mercado, não compromisso. |

## O que é mantido por teste, e não por documento

Estas propriedades **não** dependem de alguém lembrar de atualizar um `.md`.
Quando a documentação e uma destas discordarem, a guarda está certa:

| Guarda | Trava |
|---|---|
| `test_guarda_links_docs.py` | Todo `.md` citado em código ou doc vivo existe. |
| `test_guarda_modularizacao.py` | Transação nova declara módulo; leitura gateada. |
| `test_guarda_ordem_rotas.py` | Rota literal declarada antes da paramétrica irmã. |
| `test_guarda_anexo_sigiloso.py` | Carregador cru de anexo proibido em router. |
| `test_guarda_link_url.py` | `notificacao.link_url` nasce com `/m/<slug>/`. |
| `test_guarda_portas_publicadas.py` | Nada volta a publicar em `0.0.0.0`. |
| `test_guarda_portao_de_deploy.py` | O portão de deploy e o SHA aprovado. |
| `test_guarda_md5.py` | Nada volta a **gravar** MD5. |
| `test_guarda_contrato_paginado.py` | Tipo do `api.ts` casa com o `response_model`. |
| `test_rls_papeis_minimos.py` | Nenhum papel de runtime ganha `BYPASSRLS`. |
| `frontend/__tests__/rotas-modulo.test.ts` | Prefixo `/m/`, 308s, página órfã. |
| `frontend/__tests__/menus.test.tsx` | Permissão esperada por item de menu. |

## Como manter isto

- **Documento novo entra neste índice no mesmo commit.** Doc que ninguém acha é
  doc que não existe — foi assim que uma tela do transporte ficou meses
  alcançável só digitando a URL.
- **Toda evidência leva data.** Regra já vigente no
  [BACKLOG-PENDENCIAS](BACKLOG-PENDENCIAS.md) §4, estendida aqui aos documentos:
  "zero ocorrências" escrito no presente é a afirmação que menos anuncia o
  próprio vencimento.
- **Preferir guarda a parágrafo.** Se dá para escrever um teste, escreva o
  teste e cite-o aqui. Só o teste continua verdadeiro sozinho.
- **Mover documento é mudar ponteiro.** `test_guarda_links_docs.py` reprova quem
  esquecer — inclusive as citações que moram em docstring de migration.
