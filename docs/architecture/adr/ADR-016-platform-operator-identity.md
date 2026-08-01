# ADR-016 — Identidade do operador de plataforma

**Status:** **Aceito** em 2026-08-01 por Jorge Alcoforado
**Data:** 2026-08-01
**PR:** `SEC-00`
**Base inspecionada:** `main` @ `6e368d1`
**Decorre de:** ADR-014 da [especificação de monólito modular](../../superpowers/specs/2026-08-01-arquitetura-modular-monolito-design.md)
**Documentos irmãos:** [matriz de claims](../security/platform-operator-claims-matrix.md) · [threat model](../security/threat-model-platform-operator.md) · [runbook de bootstrap](../../runbooks/platform-operator-bootstrap.md)

> Este ADR é **decisão**, não implementação. Nenhuma linha de runtime muda em `SEC-00`.
> As decisões **D-1** a **D-6** e as perguntas **Q-1** a **Q-5** foram resolvidas — ver seções 9, 10 e 11.
> `SEC-01A` e `SEC-01B` estão liberados. `D-6` gerou a família `SEC-RLS-*`, descrita na seção 9.1.

---

## 1. Contexto — o que a inspeção encontrou

Inspeção estática e dinâmica de `backend/app/auth/`, `backend/app/config.py`, `backend/app/routers/admin_tenants.py`, `frontend/app/(plataforma)/`, `docker-compose.yml` e do container em execução.

### 1.1 A autorização de plataforma é uma comparação de string

`require_platform_admin` (`backend/app/auth/deps.py:171-183`) faz exatamente duas coisas: resolve o usuário **municipal** por `get_current_user` e compara `current.email` contra uma allowlist de ambiente (`backend/app/config.py:64-72`, `:122-126`). Não há principal dedicado, namespace separado, issuer próprio nem audience própria.

Onze rotas dependem disso, todas em `backend/app/routers/admin_tenants.py` — criar, listar, editar, ativar, desativar tenants e contratar/descontratar módulos.

### 1.2 O e-mail não é único globalmente

```
usuario_email_per_tenant | UNIQUE (tenant_id, email) WHERE excluido IS FALSE
```

Verificado no banco. O mesmo e-mail pode existir em **quantos tenants quiser**. Como a autorização de plataforma olha só a string, **qualquer tenant capaz de criar um usuário com o e-mail certo produz um administrador de plataforma**. É o achado F-01 do spec, confirmado na camada física.

### 1.3 Um único realm de token para três atores

`build_payload` e `build_cidadao_payload` (`backend/app/auth/jwt.py:87-123`) emitem **o mesmo `iss` e o mesmo `aud`** — hoje `http://projecttech.com.br` para ambos. Não existe token de plataforma: a rota SaaS aceita o token municipal comum. Não há nada em um token que permita a uma API dizer "este token não foi emitido para mim".

### 1.4 A validação aceita dois algoritmos, e o segredo HS256 é compartilhado com o legado

`decode_token` (`jwt.py:138-169`) tenta HS256 e, falhando, RS256. O segredo HS256 vem de `utils.sistema_constante.KEY_LOGIN_GLOBAL_JWT` — a mesma constante do sistema PHP legado. Qualquer componente que conheça esse segredo forja um token aceito pela API Python, inclusive para as rotas de plataforma.

### 1.5 A UI de plataforma compartilha sessão com a municipal

`frontend/app/(plataforma)/layout.tsx` embrulha as telas no mesmo `Providers` do app municipal: mesmo `QueryClient`, mesmo cookie `aprimora_token`, mesmo cliente HTTP. Não há isolamento de credencial nem de cache.

### 1.6 As rotas de plataforma usam a sessão e o papel de banco municipais

As onze rotas recebem `db: AsyncSession = Depends(get_db)`. `get_db` (`backend/app/database.py:49-54`) instala o `tenant_id` do middleware na sessão. Não existe conexão, papel nem transação separados para a fronteira cross-tenant. `aprimora_py.tenant`, `tenant_modulo` e `modulo` **não têm RLS** (verificado em `pg_class`), o que é coerente com serem tabelas de plataforma — mas significa que a única proteção é o código.

### 1.7 Achado adicional, fora da lista F-01..F-11 do spec

**A aplicação conecta no Postgres como `ged_user`, que é SUPERUSER e BYPASSRLS.** Verificado dentro do container, na sessão real da aplicação:

```
current_user = ged_user | superuser = on
```

O papel `aprimora_app` (NOBYPASSRLS) existe e é usado apenas pelos testes. O `DATABASE_URL` versionado em `docker-compose.yml:4` aponta para `ged_user`, e a VPS sobe por esse mesmo compose.

**Consequência:** toda a RLS descrita como "última barreira de isolamento de tenant" (invariante 10 do spec) está **inerte no runtime**. O isolamento hoje depende inteiramente do filtro aplicacional. Isso não bloqueia `SEC-00`, mas contradiz uma premissa do spec e precisa de decisão própria — ver seção 9, item **D-6**.

### 1.8 Estado do ambiente inspecionado

`PLATFORM_ADMIN_EMAILS` está **vazio** no container local, então `is_platform_admin()` hoje nega todo mundo aqui e o painel está inacessível. Isso é fail-closed por acidente de configuração, não por desenho: basta alguém preencher a variável para o caminho de 1.1/1.2 ficar ativo. **O valor em homologação/produção não foi verificado** — ver item **Q-1** da seção 10.

---

## 2. Decisão

A identidade do operador de plataforma passa a viver em um **namespace de segurança separado**, com IdP, issuer, audience, chaves, sessão, cliente HTTP e papel de banco próprios. Nenhuma credencial municipal — e-mail, `usuario.id`, cookie ou token — participa de qualquer decisão cross-tenant.

### 2.1 IdP e realm

| Item | Decisão |
|---|---|
| **IdP administrativo** | **Google Workspace (OIDC)** do domínio corporativo, com um **OAuth client dedicado** ao console de operador — separado do client já usado pela integração Google Docs |
| **Por que** | O domínio corporativo já é Google Workspace; MFA, lifecycle de conta, desligamento e trilha de login já existem e já são operados. Introduzir Keycloak/Zitadel agora acrescenta um serviço a manter, com chave e backup próprios, sem ganho de segurança sobre um Workspace bem configurado |
| **Issuer** | `https://accounts.google.com` (valor canônico do Google; validado literalmente) |
| **Audience** | Client ID do OAuth client dedicado, **um por ambiente** — nunca compartilhado com dev/homolog/prod |
| **Subject** | `sub` do OIDC — opaco, estável e imutável mesmo se o e-mail mudar |
| **Identidade persistida** | `(issuer, subject)` em `platform_principal`. O e-mail é gravado **apenas como rótulo de exibição** e nunca participa da decisão |
| **Algoritmo** | `RS256`, chaves públicas do JWKS do Google. `HS256` é **proibido** nesta fronteira |
| **JWKS** | `https://www.googleapis.com/oauth2/v3/certs`, cache respeitando `Cache-Control`, teto de 24 h, refresh sob `kid` desconhecido com rate limit |
| **Restrição de domínio** | `hd` precisa ser igual ao domínio configurado em `PLATFORM_OIDC_HOSTED_DOMAIN`, **e** o `(issuer, sub)` precisa existir e estar ativo em `platform_principal`. O domínio sozinho nunca basta |

**O domínio corporativo é configuração, nunca literal no código** (D-2). `PLATFORM_OIDC_HOSTED_DOMAIN` é obrigatória em qualquer ambiente que não seja de teste: **ausente ou vazia ⇒ fail-closed** — a fronteira de plataforma nega tudo e registra erro de configuração na inicialização. Um default embutido transformaria esquecimento de configuração em porta aberta, que é exatamente o modo de falha de `PLATFORM_ADMIN_EMAILS`.

### 2.2 Separação estrutural

1. **Namespace de identidade.** `platform_principal` tem **`id` interno como chave primária** e **`UNIQUE (issuer, subject)` como chave natural** (Q-5). Auditoria, break-glass e concessões referenciam o `id`; a troca futura de IdP muda a chave natural sem reescrever a trilha. É **proibido** por constraint e por revisão vincular a linha a `utils.usuario.id`, a e-mail municipal ou a qualquer cadastro de tenant.
2. **Validação de token.** As rotas de plataforma validam `iss`, `aud`, `exp`, `nbf`, `iat`, assinatura RS256 contra o JWKS e a presença do principal ativo. Um token municipal **falha por `iss`/`aud` antes de qualquer consulta ao banco**.
3. **Nenhum caminho municipal cria plataforma.** Nenhum endpoint sob autenticação municipal cria, altera, ativa ou concede `platform_principal`. A verificação é estrutural (teste arquitetural), não só revisão.
4. **Sessão de UI separada.** O console de operador tem árvore React, provider, cookie/armazenamento, cliente HTTP e query cache próprios. Cookie de operador nunca é enviado a APIs municipais/cidadão, e vice-versa.
5. **Transação e papel de banco separados.** As rotas de plataforma não usam `get_db` nem a sessão RLS municipal: recebem o tenant alvo **explicitamente** do payload da operação e auditam operador + tenant alvo.

### 2.3 Papel de banco da fronteira de plataforma

| Papel | Uso | Privilégios |
|---|---|---|
| `aprimora_platform` (**novo**) | exclusivo das rotas de plataforma autenticadas | DML em `aprimora_py.tenant`, `tenant_modulo`, `modulo`, `platform_principal` e auditoria de plataforma. `NOBYPASSRLS`. Sem DML nas tabelas de negócio dos tenants |
| `aprimora_app` | runtime municipal | `NOBYPASSRLS`, sujeito à RLS. **Sem** DML de entitlement |
| `aprimora_worker` (**futuro**, `SEC-RLS-00B`) | Celery | grants mínimos por task |
| `aprimora_migrator` (**futuro**, `SEC-RLS-00B`) | Alembic/DDL | dono do schema; nunca usado por runtime |

A conexão de plataforma é aberta **somente após** a validação do token administrativo. Nunca é o pool padrão da aplicação.

**Nenhum papel de runtime pode ser `SUPERUSER`, e `BYPASSRLS` não é solução genérica** (D-5). Os grants de `aprimora_platform` são cross-tenant **explícitos e enumerados**, tabela a tabela — cross-tenant por grant declarado, não por contorno de RLS. Quando uma policy ou grant faltar, a correção é a policy, nunca restaurar o bypass.

**Coordenação de migrations:** `aprimora_platform` é criado pela migration de `SEC-01A`. Os papéis municipais, de worker e de DDL são criados por `SEC-RLS-00B`. As duas famílias **não** podem definir o mesmo papel — ver seção 9.1.

### 2.4 Ciclo de vida do token

- **Aquisição:** Authorization Code + PKCE no console de operador. Sem client secret no browser.
- **TTL do access token:** **15 minutos**. Curto de propósito: a revogação efetiva de um principal precisa doer pouco.
- **Renovação:** refresh token rotativo, `HttpOnly`, `Secure`, `SameSite=Strict`, escopado ao path do console. Reuso de refresh token **invalida a família inteira** e alerta.
- **Revogação:** desativar o `platform_principal` tem efeito **imediato** — o principal é consultado a cada requisição, não cacheado na sessão. Desligar a conta no Workspace corta a renovação; a desativação do principal corta o acesso já emitido.
- **Sessão máxima:** 8 horas, mesmo com refresh válido. Depois disso, reautenticação com MFA.

### 2.5 MFA e lifecycle do operador

MFA é exigido **no IdP**, não reimplementado por nós. Requisitos mínimos do Workspace: 2FA obrigatória para o grupo de operadores, chave de segurança ou TOTP (SMS não é aceito), e o token precisa trazer `amr` compatível ou, se o Workspace não o emitir de forma confiável, a política de 2FA obrigatória do grupo é a evidência de conformidade — registrada no runbook e auditada por revisão trimestral.

O lifecycle segue o do Workspace: desligamento suspende a conta, e a revisão trimestral do runbook desativa principals órfãos.

### 2.6 Fail-closed

| Situação | Comportamento obrigatório |
|---|---|
| JWKS indisponível e sem cache válido | **deny** em toda rota de plataforma, `503`, alerta imediato. Nunca cair para HS256, nunca aceitar token sem verificar assinatura |
| `kid` desconhecido | uma tentativa de refresh do JWKS com rate limit; falhando, deny |
| `platform_principal` ausente, inativo, expirado ou ilegível | deny |
| Erro ao ler o principal (banco indisponível) | deny, `503` |
| `hd` ausente ou diferente do domínio corporativo | deny |
| Token válido no IdP mas sem principal | deny — autenticado não é autorizado |

Indisponibilidade do IdP torna o console inoperante **por desenho**. O procedimento nesse caso é o break-glass da seção 2.8, não relaxar a validação.

### 2.7 Estratégia local e de teste

O ambiente local **não** usa o Google. Usa um issuer fictício, com par de chaves **gerado em memória no início da suíte** e nunca versionado:

- issuer de teste: `https://operator.test.local`
- audience de teste: `aprimora-operator-test`
- chave: RSA gerada por execução, exposta por um JWKS servido em memória
- os fixtures vivem em `backend/tests/fixtures/platform_operator_tokens.py`

Duas propriedades que os testes travam desde já:

1. um token **municipal** (iss/aud de `jwt_iss`/`jwt_aud`) é rejeitado pelo validador de plataforma;
2. um token de **plataforma** é rejeitado pelo validador municipal.

Nenhuma chave, segredo ou client ID real entra no repositório. O que é ambiente vai para variável de ambiente; o que é segredo vai para o cofre descrito no runbook.

### 2.8 Break-glass

Existe para o caso de o IdP estar indisponível e haver um incidente que exija operação cross-tenant.

- **Ativação:** dupla aprovação — duas pessoas distintas do grupo de operadores, registradas nominalmente.
- **Mecanismo:** principal de emergência, pré-cadastrado e **inativo**, ativado por comando de CLI executado no host, fora das APIs. Nunca por endpoint HTTP.
- **Prazo:** validade de **60 minutos**, expiração automática gravada no próprio registro. Não é renovável; um segundo período exige nova dupla aprovação.
- **Auditoria:** ativação, cada operação e a expiração geram evento com os dois aprovadores, motivo e correlation ID. Alerta imediato para o canal de operação.
- **Pós-uso:** revisão obrigatória em até 48 h, registrada no runbook.

---

## 3. O que este ADR proíbe explicitamente

1. Autorizar operação cross-tenant por e-mail, `usuario.id`, cookie ou token municipal.
2. Aceitar HS256 em qualquer rota de plataforma.
3. Reaproveitar `jwt_iss`/`jwt_aud` municipais na fronteira de plataforma.
4. Criar, alterar ou conceder `platform_principal` por endpoint autenticado como usuário municipal.
5. Usar `get_db`/sessão RLS municipal em rota de plataforma.
6. Versionar chave privada, client secret ou lista real de operadores.
7. Tratar o mesmo `sub` vindo de issuers diferentes como a mesma identidade.
8. Fallback silencioso quando o JWKS falhar.

---

## 4. Consequências

**Positivas.** A colisão de e-mail deixa de ser um caminho de privilégio. Confusão de token passa a ser detectável por `iss`/`aud`. A revogação passa a ter efeito em minutos. O papel de banco separado limita o estrago de uma falha na fronteira. O console de operador deixa de compartilhar cache com o app municipal.

**Custos.** Passa a existir dependência operacional do Google Workspace: se ele cair, o console cai. Um OAuth client por ambiente precisa ser criado e mantido. O bootstrap do primeiro operador exige acesso ao host. Os testes ficam mais elaborados por precisarem de um IdP fictício.

**Dívida assumida e explicitamente não resolvida aqui.** A autenticação municipal continua com HS256, segredo compartilhado com o PHP e `iss`/`aud` iguais aos do cidadão. Este ADR **não** conserta isso — apenas garante que a fronteira de plataforma não dependa dela. Trocar o realm municipal é trabalho próprio, e deveria virar um ADR seu.

---

## 5. Alternativas consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Keycloak/Zitadel auto-hospedado** | Controle total e independência de fornecedor, ao custo de mais um serviço com banco, backup, atualização de segurança e chave própria para operar. Para uma equipe pequena, aumenta a superfície mais do que a reduz. **Reavaliar** se houver exigência de soberania de identidade ou operador fora do Workspace |
| **Par de chaves interno, emitido por serviço próprio** | Sem dependência externa, mas reimplementa MFA, rotação, lifecycle e revogação — exatamente as partes em que errar é caro |
| **Manter allowlist de e-mail, tornando o e-mail globalmente único** | Continua fazendo de um dado mutável e reutilizável a credencial de autorização, e não resolve confusão de token nem separação de sessão |
| **mTLS no console de operador** | Forte, mas distribuir e rotacionar certificado de cliente para pessoas é operacionalmente pior que OIDC + MFA. Continua disponível como camada adicional se a exposição do console mudar |
| **Restringir o console por rede/VPN apenas** | Defesa em profundidade útil, **não** substituto: não identifica quem operou nem separa realms. Pode ser somada depois |

---

## 6. Matriz de claims

Normativa, em documento próprio: [`../security/platform-operator-claims-matrix.md`](../security/platform-operator-claims-matrix.md).

Resumo: `iss`, `aud`, `exp`, `iat`, `sub`, `hd` e assinatura RS256 são **obrigatórios**; `nbf` é validado quando presente; `email` é aceito apenas como rótulo; qualquer claim municipal (`usuario_id`, `cidadao_id`, `tenant_id`, `conexao`, `app`) em token de plataforma é **motivo de rejeição**, não de ignorar.

---

## 7. Threat model

Em documento próprio: [`../security/threat-model-platform-operator.md`](../security/threat-model-platform-operator.md), com foco em confusão de token e nos oito vetores identificados na inspeção.

---

## 8. Como `SEC-01A` e `SEC-01B` consomem este ADR

`SEC-01A` recebe daqui: o formato do principal `(issuer, subject)`, a lista de claims a validar, o algoritmo, a fonte do JWKS, a política de cache, o comportamento fail-closed, o papel de banco `aprimora_platform` e os fixtures de teste.

`SEC-01B` recebe: o realm/audience do console, o fluxo Authorization Code + PKCE, a separação de cookie/cache/cliente e as quatro superfícies que não podem compartilhar credencial (operador, staff, cidadão, público).

O primeiro commit de `SEC-01A` reproduz a colisão de identidade como teste vermelho, conforme a seção 15 do plano.

---

## 9. Decisões — resolvidas em 2026-08-01

| ID | Decisão | Resolução |
|---|---|---|
| **D-1** | IdP administrativo | **Aprovado.** Google Workspace OIDC, OAuth client dedicado e configuração separada por ambiente |
| **D-2** | Domínio corporativo aceito em `hd` | **Aprovado como configuração.** `PLATFORM_OIDC_HOSTED_DOMAIN`, obrigatória por ambiente. **Domínio real nunca no código.** Ausente em ambiente não-teste ⇒ fail-closed |
| **D-3** | TTL e sessão | **Aprovado.** Access token de 15 min, sessão máxima de 8 h |
| **D-4** | Break-glass | **Aprovado.** Dupla aprovação, justificativa obrigatória, auditoria e expiração automática em 60 min |
| **D-5** | Papel `aprimora_platform` | **Aprovado.** Criado com privilégios explicitamente enumerados. Não pode ser `SUPERUSER` e não recebe `BYPASSRLS` como solução genérica |
| **D-6** | Runtime como `ged_user` (SUPERUSER, BYPASSRLS) | **Aprovado para contenção prioritária.** Registrado como achado **F-12** no spec e endereçado pela família `SEC-RLS-*` — ver 9.1 |

### 9.1 F-12 e a família `SEC-RLS-*`

O achado da seção 1.7 passa a se chamar **F-12** e entra na tabela 4.2 da especificação com severidade **Crítica**.

**Não trocar a credencial do `docker-compose.yml` sem caracterização.** O runtime roda com bypass há tempo suficiente para que caminhos hoje funcionais dependam dele sem que ninguém saiba quais. Trocar a URL de conexão como primeira ação transforma um achado de segurança conhecido em incidente de disponibilidade desconhecido. A ordem é caracterizar, depois conter.

Três PRs, nesta ordem, **antes** de `RBAC-01` e de qualquer rollout de módulo:

| PR | Entrega | Muda runtime? |
|---|---|---|
| `SEC-RLS-00A` | Prova em teste que `ged_user` ignora RLS; roda as suítes com `aprimora_app`; inventaria grants, policies, funções `SECURITY DEFINER` e consultas que dependem do bypass; classifica API municipal, worker, migrations e plataforma | **Não** |
| `SEC-RLS-00B` | Papéis mínimos: runtime municipal sujeito a RLS, papel separado para DDL, worker com grants mínimos, `aprimora_platform` com grants cross-tenant explícitos. Nenhum papel de runtime `SUPERUSER`. Rollback por configuração durante o rollout | Sim, atrás de configuração |
| `SEC-RLS-ROLLOUT` | Gate operacional: teste/dev → homologação → produção, com paridade, observabilidade e rollback comprovados | Gate, não código |

**Regra que atravessa a família:** policy ou grant que falhar é **corrigido**; restaurar `BYPASSRLS` como atalho é proibido. Em `SEC-RLS-ROLLOUT`, produção só depois de validar todos os módulos, jobs, uploads, exports e tasks Celery, e de testar isolamento com **usuário comum não-SU** — a suíte só com superusuário já escondeu um 500 em produção neste repositório.

**Coordenação com `SEC-01A`:** as duas famílias tocam papéis de banco. A divisão é fixa — `SEC-01A` cria **apenas** `aprimora_platform`; `SEC-RLS-00B` cria os papéis municipal, de worker e de DDL, e **não redefine** `aprimora_platform`, apenas verifica que ele já atende às regras. `SEC-RLS-00A` não cria papel nenhum.

---

## 10. Perguntas — respondidas em 2026-08-01

| ID | Pergunta | Resposta |
|---|---|---|
| **Q-1** | Valor de `PLATFORM_ADMIN_EMAILS` na VPS | **Desconhecido.** Tratar como **potencialmente preenchido**: `SEC-01A` permanece **P0**. Não bloqueia a implementação local. O runbook ganha uma verificação de **presença e quantidade** que **não expõe os e-mails em log** |
| **Q-2** | Quem compõe o grupo de operadores | **Nenhum operador real vai para código ou seed.** A entrega é uma **CLI de bootstrap**; o grupo autorizado é configuração por ambiente |
| **Q-3** | Host próprio para o console | **Sim, preparar para origem/host próprio configurável**, com cookies, CORS, CSP, sessão e cache separados. **Domínio definitivo não é hardcoded** |
| **Q-4** | Cofre de segredos | **Variáveis de ambiente protegidas no host**, por ora. Migração para cofre fica registrada como trabalho futuro e **não bloqueia** `SEC-01A` |
| **Q-5** | `sub` como identidade permanente | **Aprovado** o desenho recomendado: `platform_principal.id` como PK interna, `UNIQUE (issuer, subject)` como chave natural |

---

## 11. Registro de aprovação

- [x] **D-1** IdP aprovado: **Google Workspace OIDC**, client dedicado e configuração por ambiente
- [x] **D-2** Domínio `hd`: **variável obrigatória por ambiente**, fail-closed se ausente; domínio real fora do código
- [x] **D-3** TTL de 15 min e sessão máxima de 8 h aprovados
- [x] **D-4** Break-glass aprovado: dupla aprovação, justificativa, auditoria, expiração em 60 min
- [x] **D-5** Papel `aprimora_platform` aprovado, com grants explícitos, sem `SUPERUSER` e sem `BYPASSRLS` genérico
- [x] **D-6** Encaminhado como **F-12** e família `SEC-RLS-00A/00B/ROLLOUT`, anterior a `RBAC-01`
- [x] **Q-1** a **Q-5** respondidas — seção 10
- [x] Aprovado por: **Jorge Alcoforado** em **01 / 08 / 2026**
