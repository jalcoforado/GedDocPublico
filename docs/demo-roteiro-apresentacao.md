# Roteiro de demonstração comercial — Aprimora SaaS

> **Status:** PARADO · **Autoridade sobre:** nada — roteiro de demonstração, não descreve o sistema atual.
> **Última verificação:** 2026-06-07 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

> **Não use como referência do estado atual.** Sem alteração desde a data
> acima; o sistema mudou bastante desde então. Fica por valor histórico.


Três versões aninhadas (5 / 15 / 30 minutos). Pegue a versão certa para o
público; cada bloco maior **inclui** os blocos da versão menor.

## Pré-requisitos do operador

Antes da apresentação, **uma vez**:

```bash
# 1. Sobe os containers (se não estiverem subindo).
docker compose up -d

# 2. Garante que a imagem do backend tem dev deps (PyJWT etc).
#    Se for ambiente novo, pode ser necessário: docker compose build backend --no-cache.

# 3. Cria/atualiza tenant `demo` + todos os dados de apresentação.
docker exec aprimora-py-backend python -m app.cli.seed_demo apply --tenant demo

# 4. Adiciona `demo.aprimora.local` no /etc/hosts (Linux/Mac) ou
#    %SystemRoot%\System32\drivers\etc\hosts (Windows):
#    127.0.0.1   demo.aprimora.local
```

**Credenciais demo** (gravadas no `seed_demo apply`):
- URL: `http://demo.aprimora.local:8090/login`
- Email: `admin@demo.test`
- Senha: `Demo@12345`

Re-rodar `apply` sempre que a janela de prazos passar (1+ semanas) para
refrescar as datas relativas dos processos.

Limpar tudo ao fim da apresentação (opcional):
```bash
docker exec aprimora-py-backend python -m app.cli.seed_demo reset --tenant demo
```

## Versão 5 minutos — Prefeito / Secretário

**Objetivo:** mostrar que a plataforma resolve um problema real em poucos
cliques, com prazo medido e auditável.

| Tempo | Tela / URL | Ação | Resultado esperado | Fala-chave |
|---|---|---|---|---|
| 0:00 | `http://demo.aprimora.local:8090/cidadao` | Mostrar carta de serviços (6 serviços com cards, destaques, busca) | 6 cards visíveis, 4 destacados, busca filtra | "Hoje a prefeitura tem N serviços. O cidadão entra aqui, vê o que ele pode pedir, e abre na hora." |
| 1:00 | Clicar em **Solicitação de Poda de Árvore** | Mostrar página pública do serviço com prazo, documentos exigidos | Página com 10 dias, lista de docs (foto + comprovante) | "Tudo o que o cidadão precisa saber antes de abrir. Nada escondido." |
| 1:30 | Abrir solicitação em vivo (CPF de teste 999.000.000-50) | Anexar foto sintética (qualquer PDF) | Número de protocolo gerado, tela de acompanhamento | "Pronto. Protocolo aberto, número emitido. Antes era 5 dias só pra protocolar." |
| 2:30 | `http://demo.aprimora.local:8090/login` → admin@demo.test | Login como admin | Dashboard executivo carrega | (transição) |
| 2:45 | Tela do dashboard | Mostrar 3 cards de prazo: dentro / vencendo / atrasado + lista de processos atrasados | Verde (~6), amarelo (1), vermelho (1) processos | "O gestor vê tudo. Em uma tela." |
| 3:30 | `/processos` → abrir processo `DEMO-T*-2026-011` | Mostrar processo concluído + assinatura digital + QR code (se feito ao vivo na versão 30min) | Processo com timeline | "Assinatura interna, validada publicamente. Cidadão consulta sozinho." |
| 4:30 | (fechar) | Pergunta provocativa | — | "Quanto custa hoje processar essa poda em papel? Quantos dias? Quantos se perdem?" |

**Fallback:** se a navegação travar, abrir `/cidadao` em outra aba e
explicar de viva voz. Se nem isso funcionar, mostrar screenshots do dashboard
(prints capturados antes).

## Versão 15 minutos — Gestor de Protocolo

**Objetivo:** mostrar fluxo operacional ponta-a-ponta, com checklist e
complementação documental — o que diferencia da concorrência.

Inclui tudo da versão 5min, **com tempo expandido** nestes pontos:

### Bloco extra A — Checklist documental + complementação (3min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 5:00 | `/processos` → buscar `DEMO-T*-2026-002` (alvará, doc pendente) | Abrir o processo | Vê checklist: 1 de 3 docs (CNPJ ok, falta contrato social + planta) |
| 5:45 | Mostrar item pendente | Explicar key estável (`contrato-social`) | "O sistema sabe qual documento o servidor pediu. Não é texto livre." |
| 6:15 | `/processos` → buscar `DEMO-T*-2026-004` (complementação aberta) | Abrir, mostrar painel de complementação | Vê mensagem do servidor + lista de docs pedidos |
| 6:45 | (sem ação — só explicar) | Mostrar como o cidadão veria essa solicitação na tela pública | — |
| 7:00 | `/processos` → buscar `DEMO-T*-2026-005` (complementação respondida) | Abrir | Mostra histórico: data de solicitação, data de resposta, anexos novos |
| 7:30 | (transição) | — | "Tudo gravado. Tudo auditável. Sem WhatsApp de servidor falando 'me manda de novo'." |

### Bloco extra B — Prazos em detalhe (2min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 8:00 | Dashboard | Clicar em "Atrasados" | Lista filtrada com processo `DEMO-T*-2026-008` (Ouvidoria, atrasado há 5 dias) |
| 8:30 | Hover/click no processo | Mostrar responsável (unidade) + dias de atraso | "Sabe quem está atrasado. E em quê." |
| 9:00 | Dashboard → "Vencendo" | Lista com processo de evento público (`DEMO-T*-2026-007`) | "Falta 1 dia. Alerta automático." |
| 9:30 | (transição) | — | "Não é relatório de fim de mês. É vivo, agora." |

### Bloco extra C — Carimbo, comprovante PDF, audit (2min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 10:00 | Qualquer processo | Mostrar timeline de movimentações | Movimentação de abertura (admin@demo.test) |
| 10:30 | Botão "Comprovante PDF" | Gerar e abrir | PDF gerado em segundos |
| 11:00 | (mencionar) | Audit log do backend grava cada ação | "Tudo o que aconteceu fica registrado. Para sempre." |

### Bloco extra D — Reset / transparência (1min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 12:00 | (não no navegador — explicar) | Mostrar `seed_demo reset` no terminal | Comando único limpa toda a demo |
| 12:30 | — | — | "Tudo o que você viu agora pode ser apagado num comando. Nada do que está aqui é dado real — é demo." |
| 13:00 | Carta de serviços | Voltar para a tela do cidadão | Loop pro fechamento |

Resto (13:00–15:00) idêntico aos blocos finais do 5min (assinatura,
validação, pergunta de fechamento).

## Versão 30 minutos — Equipe técnica / TI

**Objetivo:** mostrar arquitetura multi-tenant, RBAC, sigilo, operações,
para convencer a equipe técnica que vai operar e integrar.

Inclui tudo da versão 15min, **com tempo expandido** nestes pontos:

### Bloco extra E — Admin de catálogo (3min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 15:00 | `/admin/servicos` | Mostrar lista admin (não pública) | Vê os 6 serviços + flags admin (ativo, destaque, ordem) |
| 15:45 | Botão "Novo serviço" | Criar `demo-vacina-covid` ao vivo: nome, slug, prazo 5d, 1 doc obrigatório | Card aparece na carta pública em segundos |
| 17:00 | Voltar à carta `/cidadao` | Confirmar que o serviço novo está visível | — |
| 17:30 | (mencionar) | `documentos_exigidos` tem `key` estável — admin pode renomear `nome` sem perder vínculo dos anexos | "Sem retrabalho quando o nome muda." |

### Bloco extra F — Unidades, grupos, permissões, sigilo (3min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 18:00 | `/organograma` | Mostrar árvore de unidades demo | 5 unidades em árvore |
| 18:45 | `/usuarios` | Mostrar 4 servidores demo, lotações distintas | — |
| 19:30 | (mencionar) | Sigilo gradual (ostensivo / interno / reservado / secreto / ultrassecreto) implementado por LAI | — |
| 20:00 | (mencionar) | RBAC: cada ação tem permissão específica; grupos compõem | — |
| 20:30 | (transição) | — | "Não é admin/usuário binário. É hierarquia, lotação, sigilo, tudo conforme a Lei de Acesso à Informação." |

### Bloco extra G — Multi-tenant SaaS (3min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 21:00 | Abrir nova aba: `http://sobral.aprimora.local:8090/cidadao` | Mostrar carta de Sobral lado a lado | Tenant diferente, branding diferente |
| 21:45 | (mencionar) | Cada prefeitura é um tenant isolado por RLS no Postgres | "Isolamento de dados na camada de banco. Sem nesting condition em query." |
| 22:30 | (logado como plataforma) | Mostrar `/admin/tenants` se houver permissão | Lista os 2 tenants |
| 23:30 | (mencionar) | Subdomain → branding → tenant via TenantMiddleware | — |
| 24:00 | (transição) | — | "Uma instalação, N prefeituras. Custo marginal próximo de zero." |

### Bloco extra H — Operações / observabilidade (3min)

| Tempo | Tela | Ação | Resultado |
|---|---|---|---|
| 25:00 | (no terminal) | `curl http://demo.aprimora.local:8090/api/v2/health` | `{"status":"ok", "db":"ok", ...}` |
| 25:30 | (mostrar arquivos) | `RUNBOOK.md` no GitHub do projeto | Diagrama + comandos prontos |
| 26:30 | (mencionar) | CLI: `python -m app.cli.tenant create / list / deactivate` | "Onboarding de novo tenant via CLI ou API admin." |
| 27:00 | (mencionar) | Backup por tenant disponível (`app.cli.backup`) | — |
| 27:30 | (mencionar) | Audit log estruturado (JSON) com tenant_id, request_id, IP | — |

### Bloco extra I — Roadmap aberto + Q&A (3min)

| Tempo | Conteúdo |
|---|---|
| 28:00 | Mostrar últimos commits no repositório (SEC-1, TECH-1, TECH-2). Mostrar `docs/` com escopos de cada iniciativa: PR4d-complementação, PR5a-dashboard, etc. |
| 29:00 | Lista do roadmap próximo (ex.: chatbot conversacional, integrações, etc — referenciar `docs/codex-avaliacao-geral-roadmap-pr4d.md` se disponível) |
| 29:30 | Q&A — TI pergunta. |

## Observações de discurso (para qualquer versão)

- **Não fale "demo" o tempo todo na frente do cliente.** O tenant se chama
  "Prefeitura Demo" para clareza interna; na fala, diga "imagine a
  prefeitura X" ou "veja como funcionaria na sua prefeitura".
- **Não use senhas reais.** As credenciais demo (`admin@demo.test` /
  `Demo@12345`) são **só para o tenant demo**. Em qualquer outro ambiente,
  use senhas dinâmicas geradas pelo provisionamento.
- **Se algo travar**, não improvise sobre o backend — diga "este é um
  ambiente local, em produção usamos o seguinte" e siga adiante.
- **Não invente roadmap** — referencie os `docs/*-escopo.md` versionados.
- **Nada do que estiver em `*.test` ou `99900000000`+** é dado real. Pode
  citar isso explicitamente se a plateia perguntar sobre LGPD: "tudo o que
  vocês veem é fictício; os e-mails terminam em `.test` (domínio reservado
  RFC 6761) e os CPFs começam com 999 (reservados para uso interno)."

## Fluxo mínimo coberto pela demo

Marcando o que cada versão cobre:

| Bloco | 5min | 15min | 30min |
|---|---|---|---|
| 1. Dashboard executivo | ✅ | ✅ | ✅ |
| 2. Carta de Serviços | ✅ | ✅ | ✅ |
| 3. Cidadão solicita serviço | ✅ | ✅ | ✅ |
| 4. Cidadão acompanha | ⚪ (mencionar) | ✅ | ✅ |
| 5. Servidor abre/vê processo | ✅ | ✅ | ✅ |
| 6. Checklist documental | ⚪ | ✅ | ✅ |
| 7. Complementação documental | ⚪ | ✅ | ✅ |
| 8. Prazos (verde/amarelo/vermelho) | ✅ | ✅ | ✅ |
| 9. Assinatura | ✅ (mostrar resultado) | ✅ | ✅ ao vivo |
| 10. Validação pública | ⚪ | ⚪ | ✅ (QR code) |
| 11. Admin SaaS / multi-tenant | ⚪ | ⚪ | ✅ |

⚪ = mencionado mas não navegado.

## Limitações conhecidas

- **Assinatura ao vivo** requer login e senha bcrypt válida do servidor que
  vai assinar. Para a versão 30min, o operador deve testar **antes** que o
  admin@demo.test consegue assinar (fluxo: abrir o processo
  `DEMO-T*-2026-011`, ir em assinaturas, solicitar assinatura própria, e
  assinar). Se não passar bem o fluxo nos ensaios, manter como "mostrar
  resultado" em vez de ao vivo.
- **`reset` apaga apenas dados marcados como demo** (slug `demo-*`,
  e-mail `*@demo.test`, CPF `999*`, `numero_origem demo-*`). Se você
  criou serviço/processo extra com nome qualquer durante a demo, o reset
  NÃO remove. Cleanup completo do tenant: `app.cli.tenant deactivate demo`
  ou `DELETE FROM aprimora_py.tenant WHERE slug='demo'` (cuidado).
- **Datas dos processos são relativas a `now()` no momento do apply.**
  Se passar 2+ semanas sem rodar `apply` de novo, os "vencendo" viram
  "atrasado" e os "no prazo" viram "vencendo". Re-rodar `apply` resolve.
- **Anexos são PDFs sintéticos** gerados via reportlab — abrem no viewer
  PDF do navegador, com rodapé "DOCUMENTO DEMO".
- **Notificações por e-mail e WhatsApp não estão no escopo do DEMO-1** —
  se a plateia perguntar, dizer que estão no roadmap.
