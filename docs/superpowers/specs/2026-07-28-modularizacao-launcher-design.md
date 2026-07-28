# Modularização do sistema — catálogo de módulos, contratação e launcher

**Data:** 2026-07-28 · **Autor:** Jorge + assistente · **Status:** design aprovado, pronto para plano de implementação

## 1. Objetivo

Transformar o aprimora-py de um sistema único com menu monolítico em uma plataforma de
**módulos contratáveis**. Após o login, o usuário vê uma tela de seleção com os módulos a que tem
acesso; ao escolher um, entra no sistema com o menu daquele módulo. Referência de experiência
citada pelo Jorge: o Guardião do Governo do Estado do Ceará.

Isso é mudança de arquitetura, não de layout: cria o conceito de **contratação por tenant** (que
hoje não existe em lugar nenhum), reorganiza a superfície de rotas inteira e move o RBAC um nível
acima.

## 2. Estado atual (levantado no código, 2026-07-28)

| Achado | Evidência |
|---|---|
| Existe um `/modulos/me`, e é lixo legado | `backend/app/routers/modulos.py` lê `public.modulos` + `public.configuracoes_modulos` — tabelas do PHP, **sem `tenant_id`, sem RLS, sem filtro de permissão**. Filtra só por `ambiente`. |
| O endpoint é código morto | `api.modulos()` existe em `frontend/lib/api.ts:2127` e **nenhuma página o chama**. |
| O RBAC é por transação, não por módulo | `utils.transacao` (código) → `grupo_transacao` (inserir/atualizar/excluir) → `grupo` (tenant-scoped) → `usuario_grupo`. Não há nível "módulo". |
| O menu é árvore hardcoded | `frontend/components/Sidebar.tsx`, 611 linhas, 8 grupos fixos, cada item com `perm` opcional, filtragem client-side. |
| `aprimora_py.tenant` não tem RLS | Nenhuma migration habilita RLS nela; é protegida por `require_platform_admin` no router. **Precedente que este design reusa.** |
| Links de notificação são persistidos | `notificacao.link_url`, `String(500)` (`backend/app/models/notificacao.py:28`), enviado por e-mail e SMS. Há links já gravados e já entregues apontando para as URLs atuais. |
| O middleware perde o destino no login | `frontend/middleware.ts:14-16` redireciona para `/login` **descartando o pathname** — não há `?next=`. |

## 3. Decisões

Seis decisões tomadas pelo Jorge, mais duas de engenharia derivadas.

| # | Decisão | Escolha |
|---|---|---|
| D1 | O que decide se um módulo aparece | **Contratação do tenant E permissão do usuário** — duas dimensões independentes |
| D2 | Navegação após escolher o módulo | **Prefixo de módulo na URL** (`/m/<slug>/...`), com camada de redirect obrigatória |
| D3 | Recorte do catálogo | **5 módulos:** protocolo, pagamentos, frota, transporte, administração. "Geral" deixa de ser grupo de menu e vira o launcher |
| D4 | Onde o backend barra módulo não contratado | **Dentro do RBAC existente** — `load_permissions()` filtra; os ~38 routers herdam sem serem tocados |
| D5 | Telas que atravessam módulos | **Área comum sem prefixo** — perfil, notificações, busca, para-assinar ficam na raiz |
| D6 | Origem da árvore de menu | **Frontend, um arquivo por módulo** — `Sidebar.tsx` vira renderizador |
| D7 | Onde mora o vínculo transação↔módulo | **Tabela nossa (`aprimora_py.modulo_transacao`)**, não coluna em `utils.transacao` |
| D8 | Transação sem módulo | **Fail-open com alarme** — permanece visível, e um teste falha se existir órfã |

**Justificativa de D7.** A alternativa era `utils.transacao.id_modulo`. Recusada: `utils.*` é território
do PHP legado e a postura do projeto é independência. Uma tabela de junção nossa tem a mesma
semântica, não toca o schema herdado, e admite uma transação em mais de um módulo se um dia for
preciso.

**Justificativa de D8.** Fail-closed (transação órfã invisível) é mais seguro para licenciamento e
é a resposta errada: alguém adiciona uma transação, esquece o vínculo, e a tela **desaparece em
produção sem erro**. Fail-open erra para o outro lado — transação nova de módulo pago apareceria
em tenant que não comprou. Com o teste de guarda, o esquecimento reprova o PR antes do merge, o
que elimina os dois modos de falha. Mesmo espírito do checklist "o que costuma ser esquecido" do
CLAUDE.md: transformar omissão em falha ruidosa e precoce.

## 4. Modelo de dados

Migration **0073**. Três tabelas em `aprimora_py`, nenhum toque em `utils.*`.

```
aprimora_py.modulo                    CATÁLOGO GLOBAL (sem tenant_id, sem RLS)
  id, slug UNIQUE, nome, icone, ordem, ativo
  → protocolo | pagamentos | frota | transporte | administracao

aprimora_py.modulo_transacao          JUNÇÃO GLOBAL (sem tenant_id, sem RLS)
  id, id_modulo → aprimora_py.modulo(id)
      id_transacao → utils.transacao(id)
  UNIQUE (id_modulo, id_transacao)

aprimora_py.tenant_modulo             CONTRATAÇÃO (tenant_id, SEM RLS — ver 4.1)
  id, tenant_id → aprimora_py.tenant(id)
      id_modulo → aprimora_py.modulo(id)
  contratado_em, ativo, excluido
  UNIQUE parcial (tenant_id, id_modulo) WHERE excluido = false
```

### 4.1 Duas exceções ao boilerplate do CLAUDE.md

Ambas deliberadas e justificadas — não são esquecimento do checklist.

**`tenant_modulo` não leva RLS.** A regra do projeto é RLS em toda tabela tenanted. Esta é tabela
de *plataforma*, não de negócio: quem escreve nela é o platform admin, operando **sobre outros
tenants**. Uma policy sobre `current_setting('app.tenant_id')` bloquearia exatamente o caso de uso.
O precedente existe e foi verificado: `aprimora_py.tenant` também não tem RLS. Controle
equivalente: escrita só via `require_platform_admin`; leitura sempre filtrada por `tenant_id` em
código, com teste de isolamento cobrindo a API.

**`modulo` e `modulo_transacao` são catálogos globais.** Sem `tenant_id` — o catálogo de módulos
pertence ao produto, não à prefeitura. Consequência esperada e testada: `tenant_filter()` deve
levantar `ValueError` se alguém passar tenant neles.

### 4.2 A sexta linha do catálogo: `comum`

*(Refinamento identificado ao escrever o plano de F1, 2026-07-28.)*

O catálogo tem **seis** linhas, não cinco: as cinco de produto mais `comum`, com
`contratavel = false`. `modulo` ganha a coluna `contratavel BOOLEAN NOT NULL DEFAULT true`.

**Por quê.** As telas transversais da seção 12 também têm transação de permissão — `dashboard` é o
caso óbvio. Com o teste de guarda de D8 exigindo módulo para toda transação, elas reprovariam o CI
sem ter para onde ir. `comum` lhes dá dono sem virar produto: nunca aparece no launcher, nunca é
contratável, nunca é bloqueada — `slugs_contratados()` a inclui sempre, implicitamente.

Isso não contraria D3. Cinco módulos são o que a prefeitura compra e o que o launcher mostra;
`comum` é infraestrutura, e a própria seção 12 já nomeava esse conjunto.

### 4.3 Backfill

A própria migration 0073 contrata os cinco módulos para **todos os tenants existentes**. Ninguém
perde acesso no deploy — a fatia F1 é invisível por construção.

`downgrade()` remove as três tabelas na ordem inversa. Head único em 0073.

## 5. Enforcement

O ponto de mudança é `backend/app/services/permissoes.py`. A função tem dois ramos e **os dois
recebem o filtro**:

```
load_permissions(db, usuario_id, tenant_id)
│
├─ ramo SU     → todas as transações do sistema (via sistema_transacao)
├─ ramo comum  → união das grupo_transacao dos grupos do usuário
│
└─ NOVO: antes de retornar, descarta toda transação cujo módulo
         não esteja contratado pelo tenant
```

**Super-usuário bypassa permissão, não bypassa contratação.** Se a prefeitura não comprou
Pagamentos, o módulo não existe para ninguém — nem para o SU. Contratar é ato de plataforma, não
de tenant. Esta é a decisão de segurança central do design e tem teste dedicado.

Como `require_permission` e `require_any_permission` já chamam `load_permissions`, os ~38 routers
ganham o bloqueio **sem uma linha alterada**.

### 5.1 A lacuna, nomeada

Endpoints que usam só `get_current_user`, sem `require_permission`, não passam por esse caminho.
Não é hipótese: é o caso do próprio `/modulos/me` hoje. A fatia F1 inclui uma varredura de todos os
routers, listando cada endpoint sem `require_permission`, com veredito por endpoint — ou é
transversal por natureza (auth, health, perfil, notificações) e entra numa allowlist explícita, ou
é buraco e ganha a dependência. O teste `test_endpoints_desprotegidos.py` congela esse resultado.

### 5.2 `/modulos/me` reescrito

Passa a devolver os módulos **contratados pelo tenant ∩ os que o usuário tem alguma transação** —
exatamente a regra de D1. Vira a fonte do launcher e do switcher. As tabelas legadas
`public.modulos` e `public.configuracoes_modulos` deixam de ser lidas em F1 e saem do ORM em F4.

## 6. Shell do frontend

```
app/(launcher)/modulos/page.tsx      ← tela de seleção, layout próprio (sem sidebar)
app/(app)/m/[modulo]/layout.tsx      ← Shell com a Sidebar do módulo ativo
app/(app)/m/[modulo]/…               ← as telas de módulo, realocadas
app/(app)/perfil, /notificacoes,     ← transversais, Shell sem menu de módulo
        /busca, /para-assinar
```

**O módulo ativo não precisa de estado.** Está na URL — `params.modulo` chega no `layout.tsx` do
segmento dinâmico. É o dividendo direto de D2: nada de cookie como fonte de verdade, nada de "qual
módulo eu estava?" ao abrir um link vindo de e-mail. O cookie entra só como conveniência (lembrar
o último módulo para pular o launcher no próximo login).

**A Sidebar vira renderizador.** As 611 linhas viram cinco arquivos `lib/menus/<slug>.ts`, cada um
exportando a estrutura `MenuGroup[]` que já existe, com o `perm` de hoje intacto, mais um
`lib/menus/index.ts` mapeando slug → menu. `<Sidebar modulo={slug} />` monta o menu do módulo e
poda por permissão como já faz.

**Switcher no Header.** Dropdown alimentado por `/modulos/me`, navegando para `/m/<slug>`. Trocar
de módulo não passa pelo launcher — o launcher é porta de entrada, não pedágio.

**Usuário com um módulo só:** `/modulos` redireciona direto para dentro dele. O launcher continua
acessível pela URL e pelo switcher.

**O guard de módulo no frontend é UX, não segurança.** O `m/[modulo]/layout.tsx` confere o slug
contra `/modulos/me` e devolve ao launcher se não bater. A barreira real está na seção 5.

## 7. Rotas, redirects e nginx

### 7.1 Redirects

Colapsam por segmento de topo — são ~25 regras, não 68, porque `next.config.js` aceita curinga:

```js
{ source: '/pagamentos/:path*',       destination: '/m/pagamentos/:path*',          permanent: true }
{ source: '/frotas/:path*',           destination: '/m/frota/:path*',               permanent: true }
{ source: '/transporte-regulado/:p*', destination: '/m/transporte/:p*',             permanent: true }
{ source: '/processos/:path*',        destination: '/m/protocolo/processos/:path*', permanent: true }
…
```

`permanent: true` emite **308**, que preserva método e corpo — necessário porque alguns desses
caminhos recebem POST de formulário. É estático, resolvido antes de qualquer render, e funciona no
build `standalone` que o projeto usa (`frontend/next.config.js`).

### 7.2 nginx

A regex de `location ~ ^/(...)` em `nginx/default.conf` **mantém todos os tokens atuais** e ganha
`m`. Manter é obrigatório: sem o token antigo, a URL antiga cai no fallback legado e morre antes de
chegar ao Next para ser redirecionada. Remover os tokens antigos só seria possível com os links
antigos extintos — o que, dado que `notificacao.link_url` é registro histórico permanente, na
prática significa nunca.

### 7.3 `notificacao.link_url` não é migrado

Os links já gravados continuam valendo pelo 308. Reescrever URL em linha histórica é risco sem
ganho: essas linhas são registro do que foi enviado, não configuração. O que muda em F4 é a
*geração* — link novo já nasce prefixado.

### 7.4 Correção acoplada: preservar o destino no login

`frontend/middleware.ts` passa a preservar o pathname original (`?next=`) e restaurá-lo após o
login. Hoje isso é incômodo; com URLs de módulo chegando por e-mail e SMS, vira perda real — o
servidor clica no link da notificação, cai no login e aterrissa no launcher sem saber o que ia ver.
Entra em F3 porque é a fatia que torna o problema agudo.

## 8. Administração da contratação

**Onde:** a área de plataforma existente. O detalhe do tenant em `app/(plataforma)/` ganha aba
**Módulos**, alimentada por `GET/PUT /admin/tenants/{id}/modulos`, sob `require_platform_admin` —
mesmo padrão dos endpoints vizinhos em `backend/app/routers/admin_tenants.py`.

**Descontratar é soft-delete e não destrói nada.** `excluido = true` tira o módulo do launcher e
faz a API negar; os dados permanecem íntegros. Uma prefeitura que suspende Pagamentos por um
trimestre e volta encontra tudo onde deixou — o mínimo defensável para dado público sob guarda
legal.

**Tenant novo:** `provisionar_tenant` ganha `--modulos`, default = todos os cinco. Mudar esse
default silenciosamente para um subconjunto quebraria a expectativa de quem já usa o comando; quem
vende por módulo passa a lista.

**`seed_bootstrap` passa a garantir o catálogo.** `modulo` e `modulo_transacao` viram pré-requisito
global idempotente, a cada deploy — igual ao que ele já faz com `protocolos.acao`. Sem isso, um
deploy em banco novo sobe com catálogo vazio e launcher em branco: exatamente o modo de falha que
custou o PR #8.

## 9. Fatiamento da entrega

Quatro fatias, cada uma deployável e reversível sozinha.

| Fatia | Entrega | Muda o que o usuário vê? |
|---|---|---|
| **F1** | Migration 0073 (catálogo + junção + contratação + backfill), `load_permissions()` filtrando, `/modulos/me` real, varredura de endpoints desprotegidos, seed_bootstrap | **Não** — deploy invisível |
| **F2** | Launcher `/modulos`, shell `m/[modulo]`, menus em 5 arquivos, switcher no Header, aba Módulos no admin de plataforma | Sim — mas URLs ainda as antigas |
| **F3** | Rotas `/m/<slug>/...`, redirects 308, token `m` no nginx, guard de módulo, `?next=` no middleware | Sim — URLs novas |
| **F4** | Limpeza: `public.modulos`/`configuracoes_modulos` fora do ORM, `Sidebar.tsx` antiga deletada, geração de `link_url` prefixada | Não |

**Por que nesta ordem.** O risco concentrado não é a modelagem — é a mudança de URL, que atinge
links já gravados e já enviados. Isolá-la numa fatia própria, depois que catálogo e shell já estão
em produção e estáveis, permite tratá-la com o cuidado que pede em vez de diluí-la no meio de
outras centenas de linhas.

## 10. Testes

**Backend** (`PYTEST_DB_HOST=db` obrigatório):

| Arquivo | O que trava |
|---|---|
| `test_modulos_catalogo.py` | Catálogo é global: `tenant_filter()` levanta `ValueError` se receber tenant |
| `test_modulos_contratacao.py` | Contratar/descontratar; unicidade parcial `WHERE excluido = false`; soft-delete preserva dados |
| `test_permissoes_modulo.py` | **Crítico:** `load_permissions()` filtra nos dois ramos. Caso explícito de super-usuário em tenant sem Pagamentos → volta sem as transações de pagamento |
| `test_modulos_me.py` | Interseção contratação × permissão; cross-tenant devolve 404, não 403 |
| `test_transacao_sem_modulo.py` | Nenhuma transação órfã — a guarda do fail-open (D8) |
| `test_endpoints_desprotegidos.py` | Varre routers, lista endpoints sem `require_permission`, compara com allowlist explícita; endpoint novo desprotegido reprova o PR |
| `test_tenant_modulo_isolamento.py` | `tenant_modulo` não tem RLS por decisão — o teste garante que a API não vaza contratação de outro tenant |

Os três últimos são testes de *regressão estrutural*: não testam comportamento, testam que ninguém
esqueceu.

**Frontend** (vitest no host, mais `npx tsc --noEmit` limpo — gate obrigatório não coberto pelo CI):

- `menus/index` — todo slug do catálogo tem menu; todo `href` aponta para rota existente
- `Sidebar` — monta o menu do módulo ativo e poda por `perm`
- Launcher — mostra só contratado ∩ permitido; usuário com um módulo cai direto dentro
- `next.config` — cada rota de topo antiga tem regra de redirect

**E2E Playwright:**

1. Login → launcher → Pagamentos → menu correto → switcher → Protocolo
2. Usuário sem Pagamentos: card ausente **e** `/m/pagamentos` devolve ao launcher
3. Link antigo `/pagamentos/contas-a-pagar` → 308 → `/m/pagamentos/contas-a-pagar`

## 11. Critérios de aceite

- **F1** — deploy sem diferença visível; suíte completa verde; `alembic downgrade -1` reverte
  limpo; `alembic heads` mostra head único em 0073
- **F2** — launcher e switcher funcionando com as URLs antigas ainda válidas
- **F3** — os três roteiros E2E passam; nenhuma rota de topo sem redirect
- **F4** — tabelas legadas fora do ORM; `Sidebar.tsx` antiga deletada; notificação nova nasce com
  link prefixado

## 12. Apêndice — mapeamento rota → módulo

Enumeração completa das rotas de `app/(app)/` hoje. É o insumo direto de F3 (realocação e
redirects) e de F2 (composição dos cinco arquivos de menu). Onde havia leitura ambígua, a escolha
está justificada.

**protocolo** — o domínio do processo, com os cadastros que só ele consome
`/processos/*` · `/protocolo/*` (balcão, CCD, TTD, vencendo-prazo) · `/workflow/*` ·
`/relatorios`, `/relatorios/assinaturas`, `/relatorios/tramitacao` · `/servicos` ·
`/manifestantes` · `/tipos-manifestante` · `/tipos-processo` · `/tipos-anexo` · `/assuntos` ·
`/templates-documento` · `/cidades` · `/bairros` · `/enderecos`

> Os catálogos de localização (cidades/bairros/endereços) vão para protocolo, não para
> administração: quem os consome é o endereço do manifestante. Se um segundo módulo passar a
> depender deles, viram transversais — não é o caso hoje.

**pagamentos** — `/pagamentos/*` (dashboard, caixa, contas-a-pagar, autorização, tesouraria,
conciliação, cadastros/*)

**frota** — `/frotas/*` (veículos, motoristas, solicitações, manutenções, abastecimentos,
vistorias, ocorrências, relatórios)

**transporte** — `/transporte-regulado/*` (permissionários, empresas, veículos, alvarás, relatório)

**administracao** — `/usuarios` · `/grupos` · `/unidades-trabalho` · `/organograma` ·
`/auditoria` · `/configuracoes` · `/jobs`

> `/auditoria` e `/jobs` são administração, não transversais: são ferramentas de quem administra o
> tenant, não telas que todo usuário atravessa. `/organograma` sai do grupo "Geral" e vem para cá
> pelo mesmo motivo — é estrutura organizacional, matéria de administração.

**comum (sem prefixo, D5)** — `/home` · `/dashboard` · `/perfil`, `/perfil/notificacoes` ·
`/para-assinar` · `/busca` · `/modulos` (launcher)

> `/home` e `/dashboard` ficam transversais porque agregam **através** dos módulos — a home "o que
> precisa de mim" cruza débitos, processos e assinaturas. Movê-las para dentro de um módulo
> destruiria essa visão consolidada. `/para-assinar` idem: assina-se documento de qualquer origem.
> Note que `/pagamentos/dashboard` é outra coisa — dashboard financeiro, propriedade do módulo.

Fora de `(app)`, sem alteração: `app/cidadao/*` (portal público), `app/(plataforma)/*` (admin de
tenants), `/login`, `/validar`, `/alterar-senha-obrigatoria`.

## 13. Fora de escopo

- Menu servido pelo backend (D6 escolheu o contrário) — reabrir só se surgir demanda de reordenar
  menu por tenant sem deploy
- Subdomínio por módulo (colide com o `TenantMiddleware`, que já usa o subdomínio para resolver o
  tenant)
- Cobrança, faturamento ou billing atrelado à contratação — `tenant_modulo` registra o vínculo, não
  o contrato comercial
- Permissões dentro do módulo — o RBAC por transação continua exatamente como é hoje
