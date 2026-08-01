# Threat model — identidade do operador de plataforma

**Status:** proposto em `SEC-00` · **Data:** 2026-08-01
**Autoridade:** [ADR-016](../adr/ADR-016-platform-operator-identity.md) · [matriz de claims](platform-operator-claims-matrix.md)
**Base inspecionada:** `main` @ `6e368d1`

Escopo: a fronteira que separa operações **cross-tenant** (catálogo comercial, contratação, ciclo de vida de tenant) do plano municipal. Fora de escopo: o realm municipal em si, o portal do cidadão e o RBAC de negócio.

---

## 1. O que está sendo protegido

| Ativo | Por que importa |
|---|---|
| Contratação de módulos (`tenant_modulo`) | quem escreve aqui liga e desliga o produto de qualquer prefeitura |
| Ciclo de vida de tenant | criar, ativar e desativar prefeituras |
| Alcance cross-tenant | um operador enxerga **todos** os tenants; um usuário municipal, um só |
| Identidade do operador | é a credencial mais privilegiada do sistema |

**Impacto de comprometimento:** indisponibilidade de módulo contratado em qualquer município, contratação indevida, e — dependendo do que a fronteira alcançar — leitura cross-tenant. É o pior caso do produto.

## 2. Atores

| Ator | Confiança | Alcance |
|---|---|---|
| Operador de plataforma | máxima | cross-tenant |
| Super-usuário de tenant | alta **dentro do tenant** | um tenant |
| Usuário municipal comum | limitada | um tenant, conforme RBAC |
| Cidadão | mínima, autenticada | próprios processos |
| Anônimo | nenhuma | superfícies públicas |
| Sistema legado PHP | **compartilha o segredo HS256** | ver T-3 |

## 3. Vetores identificados na inspeção

Severidade considera o estado **atual** do código, não o estado após `SEC-01A`.

---

### T-1 · Colisão de e-mail entre tenants — **Crítica**

**Como funciona.** `require_platform_admin` compara `current.email` com uma allowlist. O índice do banco é `UNIQUE (tenant_id, email) WHERE excluido IS FALSE`, então o mesmo e-mail existe em vários tenants. Quem consegue criar um usuário com o e-mail certo em **qualquer** tenant vira administrador de plataforma.

**Quem explora.** Qualquer pessoa com `usuario.inserir` num tenant qualquer — inclusive um município cliente.

**Pré-condição.** `PLATFORM_ADMIN_EMAILS` preenchido no ambiente. Localmente está vazio; **em homologação não foi verificado** (Q-1 do ADR).

**Mitigação.** Principal `(issuer, subject)` dedicado; e-mail deixa de participar da decisão. Cenário 21 da matriz.

---

### T-2 · Confusão de token entre realms — **Crítica**

**Como funciona.** Municipal, cidadão e plataforma compartilham `iss` e `aud` (`http://projecttech.com.br`). Não existe token de plataforma: a rota SaaS aceita o token municipal. Nada num token diz para qual API ele foi emitido, então nenhuma API consegue recusar um token que não é seu.

**Consequência.** A separação de planos hoje é apenas a comparação de e-mail de T-1. Removida ou contornada, não sobra fronteira.

**Mitigação.** Issuer e audience próprios, validados por igualdade exata; claims municipais em token de plataforma são rejeição com alerta (seção 2 da matriz). Cenários 4, 5, 6, 16.

---

### T-3 · Segredo HS256 compartilhado com o legado PHP — **Crítica**

**Como funciona.** `decode_token` tenta HS256 com o segredo lido de `utils.sistema_constante.KEY_LOGIN_GLOBAL_JWT` — a mesma constante do PHP. Quem conhece esse valor forja um token aceito, hoje inclusive nas rotas de plataforma. O segredo está **no banco**, então um SQL injection de leitura, um dump, um backup mal guardado ou o próprio legado bastam.

**Agrava.** `decode_token` tenta HS256 **primeiro**, e só depois RS256. Migrar a emissão municipal para RS256 não fecha o buraco enquanto a validação aceitar HS256.

**Mitigação nesta fronteira.** RS256 obrigatório, chave pública do JWKS, HS256 proibido. Cenário 7.

**Não mitigado, e fora de escopo:** o realm **municipal** continua exposto a isso. Merece decisão própria.

---

### T-4 · Sessão e cache compartilhados na UI — **Alta**

**Como funciona.** `frontend/app/(plataforma)/layout.tsx` usa o mesmo `Providers`, o mesmo `QueryClient` e o mesmo cookie `aprimora_token` do app municipal. Dados cross-tenant e municipais convivem no mesmo cache, e um XSS no app municipal alcança a credencial que abre o painel de plataforma.

**Mitigação.** Árvore, provider, cookie, cliente HTTP e query cache separados (`SEC-01B`). Cenários 17 e 18.

---

### T-5 · Sessão e papel de banco municipais na fronteira cross-tenant — **Alta**

**Como funciona.** As oito rotas usam `get_db`, que instala o `tenant_id` do middleware. Não há transação, papel nem conexão separados. Um bug numa rota de plataforma opera com os mesmos privilégios do runtime municipal — e vice-versa.

**Agrava — achado F-12 (seção 1.7 do ADR).** O runtime conecta como `ged_user`, **SUPERUSER e BYPASSRLS**, verificado na sessão real. A RLS descrita como última barreira de isolamento está inerte. Um bug de filtro aplicacional vaza cross-tenant sem que a RLS impeça — e o `SUPERUSER` significa que qualquer execução de SQL arbitrário alcança o cluster inteiro, não só o dado do tenant.

**Mitigação.** Papel `aprimora_platform` dedicado e tenant alvo explícito, em `SEC-01A`. **F-12 tem contenção própria e prioritária:** `SEC-RLS-00A` (caracterizar e inventariar, sem mexer no runtime) → `SEC-RLS-00B` (papéis mínimos, nenhum de runtime `SUPERUSER`) → `SEC-RLS-ROLLOUT` (promoção por ambiente). Concluída a família, o invariante 10 volta a ser controle vigente; até lá, não contar com ele em análise de risco.

---

### T-6 · Escalonamento por dentro do tenant até a plataforma — **Alta**

**Como funciona.** F-02 do spec: quem tem `usuario.atualizar` associa grupos arbitrários, grupos recebem nível arbitrário e `nivel.valor == 0` vira super-usuário. Combinado com T-1, o caminho é: autoelevar dentro do tenant → criar usuário com o e-mail do operador → alcançar a plataforma.

**Mitigação.** T-1 quebra o último elo. `SEC-02` quebra o primeiro. **Os dois são necessários** — nenhum sozinho fecha a cadeia.

---

### T-7 · Revogação lenta ou inexistente — **Média**

**Como funciona.** Hoje revogar acesso de plataforma significa editar uma variável de ambiente e reiniciar o processo. Não há revogação por identidade, nem trilha de quem operou o quê.

**Mitigação.** Principal consultado a cada requisição, access token de 15 min, refresh rotativo com detecção de reuso, desativação com efeito imediato.

---

### T-8 · Bootstrap e break-glass sem controle — **Média**

**Como funciona.** Não existe procedimento de bootstrap: o primeiro administrador nasce de uma variável de ambiente, sem aprovação, sem registro e sem prazo.

**Mitigação.** Runbook com bootstrap no host, dupla aprovação, break-glass de 60 minutos com expiração automática e auditoria (ADR §2.8).

---

## 4. Riscos que a decisão **introduz**

| Risco | Severidade | Tratamento |
|---|---|---|
| Dependência do Google Workspace: se cair, o console cai | Média | Fail-closed é intencional; break-glass cobre o incidente. Alternativa auto-hospedada registrada no ADR §5 |
| Comprometimento de uma conta do Workspace vira comprometimento da plataforma | Alta | MFA obrigatória com fator forte, `hd` + principal explícito, TTL curto, auditoria e revisão trimestral |
| Erro de configuração de `aud` entre ambientes | Média | Client por ambiente e cenário 6 como teste |
| Cache de JWKS envenenado ou obsoleto | Baixa | HTTPS, respeito ao `Cache-Control`, teto de 24 h, refresh por `kid` com rate limit |
| Falso senso de segurança: fechar a plataforma e deixar o municipal como está | **Alta** | Registrado no ADR §4 e em T-3. Este ADR **não** conserta o realm municipal |

## 5. O que continua aberto depois de `SEC-01A/B`

1. **Realm municipal** — HS256, segredo compartilhado com o PHP, `iss`/`aud` iguais aos do cidadão (T-3).
2. **`ged_user` como runtime** — RLS inerte (**F-12**). Fecha na família `SEC-RLS-*`, que é **anterior** a `RBAC-01`; até `SEC-RLS-ROLLOUT` concluir, segue aberto.
3. **Autorização fina dentro da plataforma** — todo principal ativo tem as mesmas oito rotas.
4. **Rate limiting e detecção de anomalia** no console.
5. **Autoelevação dentro do tenant** — só fecha em `SEC-02` (T-6).

## 6. Como validar que o modelo se sustenta

`SEC-01A` só é aceito com os 24 cenários da matriz verdes, e em particular:

- cenário **21** (colisão de e-mail) escrito **antes** da implementação, falhando;
- cenário **12** (JWKS indisponível) provando `503` e não `allow`;
- cenário **7** (HS256 com o segredo municipal) provando rejeição por algoritmo;
- teste arquitetural provando que nenhum caminho municipal cria `platform_principal` (cenário 22).
