# PR SEC-1 — `must_change_password` e hardening básico de senha temporária

> **Status:** proposta de escopo. Não implementar antes de autorização.
> **Data:** 2026-06-05.
> **Objetivo:** transformar a senha temporária em um fluxo obrigatório de
> primeira troca, sem quebrar login, reset de senha, assinatura v2 ou
> provisionamento SaaS.
> **Não implementa:** 2FA, política de complexidade, expiração periódica,
> recuperação por e-mail, OAuth/gov.br, device management — ver §10.

## 1. Contexto e princípios

### O que já existe

| Fluxo | Onde |
|---|---|
| Provisionamento de tenant (cria admin SU + senha gerada de 12 chars urlsafe) | [backend/app/services/provisioning_tenant.py](../backend/app/services/provisioning_tenant.py) — chamado por [routers/admin_tenants.py](../backend/app/routers/admin_tenants.py) e [cli/tenant.py](../backend/app/cli/tenant.py) |
| Reset de senha de outro usuário (admin municipal) | [services/usuario_senha.py](../backend/app/services/usuario_senha.py) → `resetar_senha_usuario` → [routers/usuarios.py](../backend/app/routers/usuarios.py#L210) `POST /usuarios/{id}/resetar-senha` |
| Alteração da própria senha | [services/conta.py](../backend/app/services/conta.py) → `alterar_senha` → [routers/auth.py](../backend/app/routers/auth.py#L102) `POST /auth/alterar-senha` |
| Criação de usuário pelo admin (com senha definida pelo admin) | [routers/usuarios.py](../backend/app/routers/usuarios.py#L106) `POST /usuarios` |
| Login | [routers/auth.py](../backend/app/routers/auth.py#L23) `POST /auth/login` |
| `/auth/me` | [routers/auth.py](../backend/app/routers/auth.py#L91) — retorna `MeResponse{id, nome, email, cargo, id_unidade_trabalho}` |
| Hash bcrypt + verify (com aceite MD5 legado) | [auth/password.py](../backend/app/auth/password.py) |
| Tela "Trocar senha" autenticada (componente self-service) | [frontend/components/TrocarSenhaCard.tsx](../frontend/components/TrocarSenhaCard.tsx) (usada em `/perfil`) |
| Middleware Next (gate por presença de cookie) | [frontend/middleware.ts](../frontend/middleware.ts) |
| `useAuth` hook (carrega `/auth/me` + `/permissoes/me`) | [frontend/lib/auth.tsx](../frontend/lib/auth.tsx) |

### Problema

Há **senha temporária** (gerada no provisionamento e no reset), exibida **uma única
vez** ao administrador, mas o sistema **não força a troca no primeiro acesso**.
Consequências:

- O admin inicial de um tenant pode permanecer com a senha temporária
  indefinidamente. Se o canal de entrega da senha (e-mail/WhatsApp/print) for
  comprometido, o atacante mantém acesso silencioso.
- O reset administrativo (admin municipal redefinindo a senha de um servidor)
  produz uma senha conhecida pelo admin, que continua válida sem fricção. Não há
  separação cognitiva entre "senha temporária" e "senha do usuário".
- Em demo comercial e em auditoria, a ausência de "must-change at first login"
  é um *finding* clássico de fragilidade básica em SaaS.

### Princípios deste PR

1. **Cirúrgico.** Uma coluna boolean, uma flag em `MeResponse`, um guard no
   backend, um guard no frontend, uma rota nova. Diff localizável.
2. **Não quebrar nada que já funciona.** Login continua autenticando.
   `alterar_senha` continua aceitando senha atual MD5 (compat). Assinatura v2
   continua bloqueando MD5 (já é). Provisionamento continua retornando senha em
   claro uma única vez. Reset continua exibindo a senha uma única vez.
3. **Backfill conservador.** Todos os usuários existentes começam com
   `must_change_password = false`. Só **novos** admins de tenant e **reset
   futuro** marcam `true`. (Decisão deliberada — ver D-BACKFILL.)
4. **Backend é a fonte da verdade.** O frontend redireciona por UX, mas o
   backend bloqueia rotas críticas — defesa em profundidade. Se o frontend
   falhar, o backend ainda protege.
5. **Senha nunca em log.** Já é o caso ([usuario_senha.py:64-68](../backend/app/services/usuario_senha.py#L64-L68));
   este PR reforça e cobre por teste explícito.

### Decisões a tomar (consolidadas)

Cada uma marcada com `[D-XXX]` e referenciada onde aplicável.

| ID | Decisão | Recomendação inicial |
|---|---|---|
| `D-COLUNA-LOCAL` | onde fica o flag? | `utils.usuario.must_change_password BOOL NOT NULL DEFAULT FALSE` — mesma tabela do `senha`/`senha_bcrypt`, sem JOIN, sem novo schema |
| `D-LOGIN-FLAG` | retornar a flag onde? | **em `/auth/me`** (e adicionar também no `LoginResponse` para latência: o frontend já tem a info no callback do login, sem 2 round-trips) |
| `D-BACKEND-GUARD` | bloquear rotas no backend? | sim — nova dependência `require_password_ok` consumida em **vez de** `get_current_user` nas rotas críticas; whitelist explícita das rotas permitidas (`/auth/me`, `/auth/alterar-senha`, `/auth/logout`) |
| `D-WHITELIST-ROTAS` | quais rotas o usuário com flag=true pode acessar? | `/auth/me`, `/auth/alterar-senha`, `/auth/logout`, `/permissoes/me`, `/branding/me` — o mínimo para o frontend hidratar a tela de troca |
| `D-FRONT-GUARD` | onde guardar no frontend? | `AuthProvider` ([lib/auth.tsx](../frontend/lib/auth.tsx)) detecta `must_change_password=true` e redireciona para `/alterar-senha-obrigatoria` (nova rota dedicada — não reusar `/perfil`, ver D-TELA) |
| `D-TELA` | reaproveitar `/perfil` ou rota dedicada? | rota dedicada **`/alterar-senha-obrigatoria`** — sem sidebar, sem permissão, microcopy específica ("Por segurança, altere sua senha temporária antes de continuar"). Reusa o componente `TrocarSenhaCard` por dentro |
| `D-MIDDLEWARE-NEXT` | middleware do Next bloqueia? | **não** — middleware do Next só conhece cookie (presença), não tem acesso a DB nem ao JWT decodificado. Guard fica no `AuthProvider` (client-side) + backend (defesa em profundidade) |
| `D-BACKFILL` | usuários existentes começam com? | `false` (default da coluna) — não rompe ninguém em produção; novos admins e resets futuros marcam `true` |
| `D-ADMIN-CRIAR-USUARIO` | criação de usuário em `POST /usuarios` (admin define senha)? | marcar `must_change_password=true` — a senha foi definida pelo admin, não pelo usuário final |
| `D-SESSAO-POS-TROCA` | manter sessão ou exigir novo login? | **manter** — o JWT continua válido; próximo `/auth/me` retorna `must_change_password=false` e o guard libera a navegação. Sem fricção de logout (e nada ganha em segurança aqui — atacante com token já tem o token) |
| `D-CIDADAO` | aplicar a cidadãos (`utils.cidadao` / `utils.usuario_externo`)? | **fora de escopo deste PR**. Cidadão usa fluxo de cadastro próprio (define a própria senha no signup) — não há "senha temporária do cidadão". Pode entrar em SEC-2 se necessário |
| `D-AUDITORIA-EVENTOS` | novos eventos? | reaproveitar `usuario.senha_alterada` (já existe). Adicionar `payload.must_change_password_antes` e `payload.must_change_password_depois` ao audit log da troca/reset (sem nunca incluir senha) |

---

## 2. Modelo de dados

### 2.1 Nova coluna

```sql
-- 0030_must_change_password.py (Alembic)
ALTER TABLE utils.usuario
  ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
```

`[D-COLUNA-LOCAL]` — mesma tabela do `senha`/`senha_bcrypt`. Indexação
**não** necessária (consulta sempre por PK / por sessão). Sem efeito em RLS.

### 2.2 Backfill

`[D-BACKFILL]` — **nenhum UPDATE** na migração. O `DEFAULT FALSE` cuida dos
usuários existentes. Os 2 admins SaaS em produção (`admin@local.test` em dev
e o equivalente em prod) continuam livres da fricção.

Alternativa rejeitada: marcar `true` para usuários que ainda têm `senha_bcrypt =
NULL` (legado MD5 puro) — rejeitada porque esses usuários **já vão precisar
rotacionar para bcrypt no próximo login** (a assinatura v2 bloqueia MD5), e
adicionar must-change em cima dobra a fricção sem ganho real.

### 2.3 Atualização do modelo SQLAlchemy

[backend/app/models/usuario.py](../backend/app/models/usuario.py) — adicionar:

```python
must_change_password: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default="false"
)
```

`server_default="false"` é importante para o caso de `INSERT` sem a coluna
explícita (compat com inserts via ORM que não passam o campo).

---

## 3. Login e `/auth/me`

### 3.1 `LoginResponse`

`[D-LOGIN-FLAG]` — adicionar campo em [backend/app/schemas/auth.py](../backend/app/schemas/auth.py):

```python
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario_id: int
    usuario_email: str
    nome: str
    must_change_password: bool = False   # << novo
```

`[routers/auth.py:74](../backend/app/routers/auth.py#L74)` populá-lo com `user.must_change_password`. **Login NUNCA é bloqueado pela flag** — apenas informa.

### 3.2 `MeResponse`

```python
class MeResponse(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str | None = None
    id_unidade_trabalho: int | None = None
    must_change_password: bool = False   # << novo
```

Fonte da verdade contínua: o frontend pode confiar em `/auth/me` em qualquer
momento (não só logo após login) — útil se a flag mudar enquanto a sessão
está aberta (admin externo reseta a senha do usuário enquanto ele está logado).

### 3.3 Login não bloqueia

Regra explícita: usuários com `must_change_password=true` **conseguem logar**.
O bloqueio acontece depois, nas rotas protegidas.

---

## 4. Reset de senha (admin → usuário)

[backend/app/services/usuario_senha.py](../backend/app/services/usuario_senha.py)
→ `resetar_senha_usuario` — após gerar `senha_temp` e hashar:

```python
user.senha_bcrypt = hash_password(senha_temp)
user.senha = ""                            # zera MD5 (já existe)
user.must_change_password = True           # << novo
```

E no payload do audit log:

```python
payload={
    "id_usuario_afetado": user.id,
    "afetado_super_usuario": perms_afetado.is_super_usuario,
    "marca_must_change_password": True,    # << novo (sinalização)
}
```

**Não muda a resposta da API** — `ResetSenhaResponse` continua retornando a
senha em claro uma única vez. O admin municipal recebe um aviso de UI
adicional (frontend): "O usuário deverá trocar a senha no próximo acesso."

### 4.1 Self-reset (auto-reset por admin de si mesmo)

Edge case: admin reseta a senha **de si mesmo** via `/usuarios/{id}/resetar-senha`
(o `usuario_id` coincide com o ator). Hoje isso é tecnicamente possível mas
sem sentido — o admin tem o `/auth/alterar-senha` para isso. Após o PR, se
acontecer, ele cai no fluxo must-change normal no próximo `/auth/me`. Não
precisa de tratamento especial.

---

## 5. Alteração da própria senha

[backend/app/services/conta.py](../backend/app/services/conta.py) →
`alterar_senha`:

```python
usuario.senha_bcrypt = hash_password(nova_senha)
usuario.must_change_password = False       # << novo (libera o guard)
# usuario.senha = ""  # OPCIONAL — ver §5.1
```

### 5.1 Zerar MD5 também?

Hoje `alterar_senha` **não** zera `usuario.senha` (MD5). A docstring justifica:
"Grava apenas bcrypt — desbloqueia a assinatura". Mas o MD5 ainda fica no DB.

**Recomendação:** zerar `usuario.senha = ""` em `alterar_senha` também, igual
ao `resetar_senha_usuario`. Mantém consistência (`senha` legada deixa de
funcionar para autenticação), elimina superfície de ataque (MD5 não vaza em
backup), e a assinatura v2 já checa `bcrypt` como fonte primária. Esta
mudança é **opcional** e pode ficar fora do SEC-1 se preferirmos
escopo mínimo — marcar como `[D-ZERAR-MD5-ALTERAR]`.

Recomendação inicial: **incluir** (custa 1 linha, melhora higiene).

### 5.2 Audit log

Já existe `audit_log(acao="usuario.senha_alterada", payload={"metodo": "bcrypt"})`.
Adicionar ao payload:

```python
payload={"metodo": "bcrypt", "limpou_must_change_password": True}
```

A senha **continua** ausente do payload. Teste novo verifica explicitamente.

---

## 6. Provisionamento SaaS

[backend/app/services/provisioning_tenant.py](../backend/app/services/provisioning_tenant.py)
→ `provisionar_tenant`:

```python
usuario = Usuario(
    ...
    senha_bcrypt=hash_password(senha_temp),
    must_change_password=True,             # << novo
    ...
)
```

Funciona tanto para API admin (`POST /admin/tenants`) quanto para CLI
(`python -m app.cli.tenant create ...`) — ambos usam `provisionar_tenant`.

### 6.1 Criação de usuário pelo admin municipal

[backend/app/routers/usuarios.py:106](../backend/app/routers/usuarios.py#L106)
→ `POST /usuarios`:

```python
user = Usuario(
    ...
    senha_bcrypt=hash_password(payload.senha),
    must_change_password=True,             # << novo (D-ADMIN-CRIAR-USUARIO)
    ...
)
```

Justificativa: a senha foi definida **pelo admin**, não pelo usuário final.
O usuário final precisa trocar.

Edge case: hoje `POST /usuarios` também grava MD5 (compat PHP). Esse hash MD5
**continua sendo gravado por enquanto** — a remoção fica para um PR de "drop
MD5 columns" pós-cutover do PHP (ver [CUTOVER.md](../CUTOVER.md) passo 8).
Não é parte do SEC-1.

### 6.2 RUNBOOK + admin SaaS docs

- [docs/saas-pr3a-admin-tenants-escopo.md](./saas-pr3a-admin-tenants-escopo.md): atualizar para refletir que o admin inicial nasce com must-change.
- [tests-e2e/README.md](../tests-e2e/README.md) — N/A (não toca).
- README ou novo `docs/sec-pr1-must-change-password-operacao.md` (curto): explicar UX, exemplos de fluxo, comportamento esperado em demo.

---

## 7. Guard de backend (rotas protegidas)

### 7.1 Estratégia: dependência opt-in via wrapper

`[D-BACKEND-GUARD]` — criar nova dependência em [backend/app/auth/deps.py](../backend/app/auth/deps.py):

```python
async def require_password_ok(
    user: Usuario = Depends(get_current_user),
) -> Usuario:
    """Mesmo que get_current_user, mas rejeita usuários com
    must_change_password=true. Use em vez de get_current_user nas rotas
    de negócio. Rotas que precisam funcionar com a flag (alterar-senha,
    /me, logout) continuam usando get_current_user direto."""
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troca de senha obrigatória",
            headers={"X-Must-Change-Password": "true"},
        )
    return user
```

`X-Must-Change-Password: true` no header permite ao frontend detectar a
condição mesmo em chamadas que não consultam `/auth/me` previamente —
útil para clientes externos (futuro) e para o axios/fetch interceptor.

### 7.2 Onde aplicar?

Avaliação: a base de código tem ~30+ routers e cada um declara dependências
locais. Refatorar tudo num único PR é arriscado e cria diff grande.

**Estratégia incremental** — duas opções:

**Opção A (recomendada): substituição em `require_permission` + `require_tenant_id`.**

A maioria das rotas de negócio usa `require_permission(...)` ou `require_tenant_id`,
que por sua vez dependem de `get_current_user`. Basta substituir
`get_current_user` por `require_password_ok` **dentro** dessas duas funções:

```python
# require_permission interno:
async def require_permission(codigo: str, acao: str = "ler"):
    async def _dep(
        user: Usuario = Depends(require_password_ok),  # << era get_current_user
        ...
    ):
        ...
    return _dep
```

Isso cobre **todas as rotas que já dependem dessas helpers** sem alterar
cada router. Diff cirúrgico em [backend/app/auth/deps.py](../backend/app/auth/deps.py).

**Opção B (rejeitada): middleware global.**

Faria sentido em greenfield, mas aqui exigiria reescrever a hierarquia de
dependências de auth, com risco alto de regressão na assinatura v2 e nos
fluxos cidadão.

### 7.3 Whitelist explícita

`[D-WHITELIST-ROTAS]` — as seguintes rotas **mantêm `get_current_user`** (sem
must-change guard):

| Rota | Por quê |
|---|---|
| `GET /auth/me` | usuário precisa saber que ele tem `must_change_password=true` |
| `POST /auth/alterar-senha` | a única forma de sair do estado |
| `POST /auth/logout` | usuário pode escolher sair sem trocar |
| `GET /permissoes/me` | `AuthProvider` no frontend carrega em paralelo com `/me` |
| `GET /branding/me` | UI de login/tela de troca precisa de logo+cor |

Cidadão (`/cidadao/*`) **não** é afetado — usa `get_current_cidadao`, fluxo
separado.

### 7.4 Rotas não-cobertas pelo guard

Algumas rotas usam `get_current_user` direto, fora de `require_permission`.
Inventário (a confirmar na implementação):

- `GET /auth/me` ✓ (intencional)
- `POST /auth/alterar-senha` ✓ (intencional)
- `POST /auth/logout` ✓ (intencional)
- `GET /permissoes/me` — verificar
- `GET /branding/me` — verificar
- `POST /admin/tenants` (require_platform_admin) — admin SaaS faz manutenção
  inicial. Decisão: **manter livre do guard** (admin de plataforma raramente
  está sujeito a senha temporária; e se estiver, ele troca via fluxo normal
  primeiro).

Tudo o que sobrar (rotas de negócio: processos, assuntos, servicos, dashboard,
assinatura, workflow, organograma, etc.) cai sob `require_permission` ou
`require_tenant_id` e é coberto automaticamente.

### 7.5 Teste obrigatório

Pytest novo: para CADA router de negócio (busca, processos, servicos,
dashboard, assinaturas, workflow, audit, relatorios, usuarios, etc.), criar
1 teste de smoke que verifica que `must_change_password=true` retorna 403 em
uma rota arbitrária (GET list). Manter pequeno e focado.

---

## 8. Frontend

### 8.1 Tipos

[frontend/lib/api.ts](../frontend/lib/api.ts) — atualizar:

```ts
export interface MeResponse {
  id: number;
  nome: string;
  email: string;
  cargo: string | null;
  id_unidade_trabalho: number | null;
  must_change_password: boolean;   // << novo
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  usuario_id: number;
  usuario_email: string;
  nome: string;
  must_change_password: boolean;   // << novo
}
```

### 8.2 Nova rota `/alterar-senha-obrigatoria`

`[D-TELA]` — criar [frontend/app/alterar-senha-obrigatoria/page.tsx](../frontend/app/alterar-senha-obrigatoria/page.tsx)
**fora do grupo `(app)`** (sem sidebar, sem navegação lateral, sem
PageHeader institucional). Layout próprio, minimalista, similar ao
`/login`:

```tsx
"use client";
// Layout sem sidebar; usa o BrandingProvider/ToastProvider que já existem
// no app/layout.tsx raiz.
export default function AlterarSenhaObrigatoriaPage() {
  // 1. Lê /auth/me; se must_change_password === false, redireciona pra /home.
  // 2. Renderiza TrocarSenhaCard (já existe) com:
  //    - heading "Altere sua senha"
  //    - microcopy: "Por segurança, altere sua senha temporária antes de continuar."
  //    - botão "Sair" (logout) como escape secundário.
  // 3. No onSuccess do TrocarSenhaCard, faz router.push("/home").
}
```

Adicionar `/alterar-senha-obrigatoria` ao **PUBLIC_PATHS do middleware**
(presença do cookie ainda é exigida — usuário precisa estar logado para
chegar lá), MAS a rota não é bloqueada pelo guard de `AuthProvider`.

### 8.3 `AuthProvider` guard

`[D-FRONT-GUARD]` — em [frontend/lib/auth.tsx](../frontend/lib/auth.tsx),
estender o `useEffect` de hidratação:

```tsx
useEffect(() => {
  Promise.all([api.me(), api.permissoes()])
    .then(([u, p]) => {
      setUser(u);
      setPerms(p);
      // Guard: se must_change, força a rota de troca (exceto se já estiver lá).
      if (u.must_change_password && pathname !== "/alterar-senha-obrigatoria") {
        router.replace("/alterar-senha-obrigatoria");
      }
    })
    .catch(() => router.replace("/login"))
    .finally(() => setLoading(false));
}, [router, pathname]);
```

### 8.4 Interceptor para 403 + header

Se uma chamada de API retornar **403 com header `X-Must-Change-Password: true`**
(o backend acabou de marcar a flag e a sessão ficou stale), o cliente deve
redirecionar. Adicionar em [frontend/lib/api.ts](../frontend/lib/api.ts) na
função `request`:

```ts
if (res.status === 403) {
  if (res.headers.get("X-Must-Change-Password") === "true") {
    if (typeof window !== "undefined" &&
        window.location.pathname !== "/alterar-senha-obrigatoria") {
      window.location.href = "/alterar-senha-obrigatoria";
    }
  }
}
```

### 8.5 Toast pós-reset (UX do admin que resetou)

A tela admin de listagem de usuários, ao receber a `senha_temporaria`,
exibe um modal com a senha (já existe). **Acrescentar microcopy** ao modal:

> "O usuário deverá trocar a senha no primeiro acesso."

Achar o modal: provavelmente em [frontend/app/(app)/usuarios](../frontend/app/(app)/usuarios).
A microcopy é cosmética; o comportamento backend já marca a flag.

### 8.6 Toast pós-login (opcional)

Após `/auth/login` retornar `must_change_password=true`, o `LoginPage`
poderia exibir um toast "Senha temporária detectada — você será levado à
troca" antes do redirect. **Opcional**, decisão de UX. Não estritamente
necessário porque o `AuthProvider` já redireciona; toast só dá feedback.

---

## 9. Segurança — checklist

| Regra | Onde fica garantida | Teste |
|---|---|---|
| Senha nunca em audit log | `services/usuario_senha.py`, `services/conta.py`, `services/provisioning_tenant.py` | `test_audit_nao_registra_senha` — varre todos os payloads de audit emitidos pelas 3 funções e garante ausência de qualquer string ≥4 chars que coincida com a senha gerada |
| Hash nunca retornado pela API | `schemas/usuario.py` (UsuarioOut sem `senha`/`senha_bcrypt`), `schemas/auth.py` (Me/Login sem hash) | `test_usuario_out_nao_contem_hash` |
| `alterar_senha` exige senha atual | `services/conta.py:31` (já existe) | teste existente preservado |
| Reset admin → bcrypt + zera MD5 | `services/usuario_senha.py:52-53` (já existe) | teste novo: `test_reset_zera_md5_e_marca_must_change` |
| Login não bloqueia must-change | `routers/auth.py` | `test_login_aceita_must_change_password_true` |
| Sessão pós-troca permanece válida | JWT não muda; flag muda no DB | `test_sessao_continua_apos_troca` |
| Frontend não mostra senha após fechar o modal | UI — modal de senha temporária guarda em estado local, sem persistir | inspeção visual + teste vitest |
| Rate-limit de login preservado | nginx (já existe) | spec auth e2e existente |

---

## 10. Fora de escopo (explícito)

| Item | Por quê fora |
|---|---|
| 2FA / TOTP | Outro PR (SEC-2). Stack de SMS/Auth app exige biblioteca, UI, recuperação |
| Política de complexidade (maiúscula, símbolo, etc.) | Outro PR. SEC-1 mantém `min_length=6` atual |
| Expiração periódica (rotação a cada N dias) | Outro PR. Exige novo campo `senha_alterada_em` e job de notificação |
| Recuperação por e-mail / "esqueci minha senha" | Outro PR. Exige integração SMTP, tokens de reset, templates |
| Envio de senha por e-mail | Idem |
| Convite por e-mail no provisionamento | Idem |
| OAuth / gov.br / SSO | Outro epic |
| Device management / login por dispositivo | Outro epic |
| Revogação global de sessões | Exige denylist de JWTs ou TTL curto; outro PR |
| Login por certificado (e-CPF, ICP-Brasil) | Outro epic |
| Mudanças em assinatura v2 | Imutável neste PR |
| Mudança em criptografia de assinatura | Imutável neste PR |
| Cidadão (`must_change_password` para usuário externo) | Cidadão se cadastra e define própria senha — sem senha temporária. Pode entrar em SEC-2 se necessário |
| Drop da coluna `senha` (MD5) em `utils.usuario` | Esperado em PR pós-cutover do PHP, conforme [CUTOVER.md](../CUTOVER.md) passo 8 |

---

## 11. Plano de testes

### 11.1 Backend (pytest)

Novos arquivos em `backend/tests/`:

- `test_must_change_password_modelo.py`
  - migration 0030 aplica/desaplica.
  - Backfill: todos os usuários existentes têm `must_change_password=false` após o upgrade.
  - Default em `INSERT` sem o campo retorna `false`.

- `test_must_change_password_provisionamento.py`
  - `provisionar_tenant` cria admin com `must_change_password=true`.
  - CLI tenant create idem.

- `test_must_change_password_reset.py`
  - `resetar_senha_usuario` marca `must_change_password=true`.
  - Audit log do reset contém `marca_must_change_password=True` no payload.
  - Audit log NÃO contém a senha temporária em claro.

- `test_must_change_password_alterar.py`
  - `alterar_senha` marca `must_change_password=false`.
  - Audit log da troca contém `limpou_must_change_password=True`.
  - Audit log NÃO contém senha em claro.
  - (D-ZERAR-MD5-ALTERAR) `usuario.senha` fica `""` após a troca.

- `test_must_change_password_login.py`
  - Login com `must_change=true` retorna 200 e `LoginResponse.must_change_password=true`.
  - `/auth/me` retorna `must_change_password=true`.

- `test_must_change_password_guard.py`
  - `require_password_ok`: 403 com header `X-Must-Change-Password: true` quando flag=true.
  - Whitelist: `/auth/me`, `/auth/alterar-senha`, `/auth/logout`, `/permissoes/me`,
    `/branding/me` retornam 2xx com flag=true.
  - 1 teste de smoke por router de negócio (processos, servicos, dashboard,
    assinaturas, workflow, audit, relatorios, usuarios) retorna 403 com flag=true.
  - Usuário normal (flag=false) continua acessando tudo (regressão).

### 11.2 Frontend (vitest)

Novos arquivos em `frontend/`:

- `frontend/app/alterar-senha-obrigatoria/__tests__/page.test.tsx`
  - Renderiza heading "Altere sua senha".
  - Renderiza microcopy "Por segurança, altere sua senha temporária antes de continuar."
  - Se `/auth/me` retornar `must_change_password=false`, redireciona para `/home`.
  - Troca com sucesso chama `api.alterarSenha(...)` e redireciona para `/home`.
  - Botão "Sair" chama `api.logout()` e redireciona para `/login`.

- `frontend/lib/__tests__/auth-guard.test.tsx` (extensão de testes do `AuthProvider`)
  - `me.must_change_password=true` em `/home` → `router.replace("/alterar-senha-obrigatoria")`.
  - `me.must_change_password=true` em `/alterar-senha-obrigatoria` → não redireciona.
  - `me.must_change_password=false` → permanece na rota atual.

- Atualizar mock de `api.me` em testes existentes (componentes que usam `useAuth`)
  para incluir `must_change_password: false`.

### 11.3 Playwright (smoke E2E)

Adicionar **2 tests** a `tests-e2e/specs/ux1-smoke.spec.ts` OU criar
`sec1-must-change.spec.ts` (preferência: arquivo novo, mantém ux1-smoke
focado em UX):

- Test 1: provisiona tenant via API admin (ou usa CLI), faz login com senha
  temporária, verifica que `/auth/me` retorna `must_change_password=true`,
  navega para `/dashboard` e verifica redirect para `/alterar-senha-obrigatoria`.
- Test 2: troca a senha pela tela, verifica que `/auth/me` retorna `false` e
  que agora consegue acessar `/dashboard`.

### 11.4 tsc

Sem novos erros.

---

## 12. Sequência sugerida de implementação

Cada passo termina com testes verdes e é seguro pra commit independente.

1. **Migration + modelo**: alembic 0030, atualiza model `Usuario`. Pytest mínimo de
   schema/default. ✓ Commit.

2. **Provisionamento + reset + alterar marcam flag**: editar
   `provisioning_tenant.py`, `usuario_senha.py`, `conta.py`. Pytest para cada.
   ✓ Commit.

3. **Login retorna flag em `LoginResponse` + `/auth/me`**: editar schemas + routers.
   Pytest para login. ✓ Commit.

4. **`require_password_ok` + hook em `require_permission`/`require_tenant_id`**:
   editar `auth/deps.py`. Pytest do guard + 1 teste por router. ✓ Commit.

5. **Tela `/alterar-senha-obrigatoria` + `AuthProvider` guard**:
   criar página, ajustar `lib/auth.tsx`, ajustar `lib/api.ts` (interceptor 403).
   Vitest da página + guard. ✓ Commit.

6. **Microcopy + UX do modal de reset admin**: ajustar tela admin de usuários
   para mostrar "deverá trocar a senha no primeiro acesso". ✓ Commit.

7. **Playwright smoke SEC-1**: provisionar → login → redirect → troca → libera.
   ✓ Commit.

8. **Docs**: criar `docs/sec-pr1-must-change-password-operacao.md` curto
   explicando UX final. ✓ Commit.

Total estimado: 7-8 commits. Cada um auditável e revogável.

---

## 13. Riscos

| Risco | Mitigação |
|---|---|
| Refator de `require_permission`/`require_tenant_id` quebra rotas que não eram cobertas | Pytest novo: 1 teste por router de negócio (cobertura ampla, baixo custo). Se algum router não usa `require_permission`/`require_tenant_id`, pegar caso a caso |
| Admin SaaS atual (`admin@local.test`) recebe flag involuntariamente | Backfill é `false` por padrão. Verificar via teste explícito no upgrade |
| Frontend redireciona em loop se a flag não desaparecer após troca | Test do guard: `must_change_password=false` não redireciona. Em produção, garantir que `alterar_senha` realmente seta `false` no commit (não só em memória) |
| Sessão antiga (token JWT emitido antes da flag virar true) ignora must-change | `/auth/me` lê do DB a cada chamada. Frontend roda `/auth/me` no carregamento → detecta. Backend guard checa o DB em toda chamada protegida. Sem janela de bypass |
| Usuário fecha o navegador sem trocar e volta depois → reinicia | OK por design. Flag persiste no DB. Próxima sessão repete o guard |
| Senha em log via Sentry/observability | Verificar que nenhum `logger.info(senha)` foi acidentalmente adicionado. Pytest cobre audit_log; Sentry depende de breadcrumb manual (não automatizado para senha) |
| Cookie HttpOnly + 403 + cliente sem JS (curl externo) | Cliente recebe 403 com header `X-Must-Change-Password: true`. Documentar em `docs/sec-pr1-must-change-password-operacao.md` para integradores |
| Cidadão (usuario_externo) cai por engano em `require_password_ok` | `require_password_ok` deriva de `get_current_user` que filtra por `utils.usuario`. Cidadão usa `get_current_cidadao` (outra função). Sem cross-fluxo |
| MD5 zerado em `alterar_senha` quebra alguma autenticação legada que ainda usa MD5 | A `verify_password` (auth/password.py) já prefere bcrypt; cai para MD5 só se bcrypt for `None`. Após `alterar_senha`, bcrypt está populado — MD5 nunca é consultado. Seguro |

---

## 14. Entregáveis do PR

- Migration `backend/alembic/versions/0030_must_change_password.py`
- Model `backend/app/models/usuario.py` (+ 1 campo)
- Schemas `backend/app/schemas/auth.py` (Me/Login + flag)
- Service `backend/app/services/provisioning_tenant.py` (marca true no admin inicial)
- Service `backend/app/services/usuario_senha.py` (marca true no reset)
- Service `backend/app/services/conta.py` (marca false na troca; zera MD5)
- Router `backend/app/routers/auth.py` (Login retorna flag)
- Router `backend/app/routers/usuarios.py` (POST /usuarios marca true)
- Deps `backend/app/auth/deps.py` (require_password_ok; hook em require_permission/require_tenant_id)
- Page `frontend/app/alterar-senha-obrigatoria/page.tsx` (nova rota)
- Lib `frontend/lib/auth.tsx` (guard no AuthProvider)
- Lib `frontend/lib/api.ts` (MeResponse/LoginResponse + flag + interceptor 403)
- Modal de usuários (microcopy "deverá trocar a senha")
- Testes pytest novos: ~7 arquivos
- Testes vitest novos: 2 arquivos + atualizações de mocks existentes
- Spec Playwright novo: `tests-e2e/specs/sec1-must-change.spec.ts`
- Doc operacional curto: `docs/sec-pr1-must-change-password-operacao.md`

---

## 15. Estimativa de tamanho

- ~10 arquivos backend modificados, 1 migration nova
- ~5 arquivos frontend modificados, 1 página nova
- ~7 testes pytest novos
- ~2 testes vitest novos + atualização de mocks
- 1 spec Playwright novo
- 2 docs (este escopo + operação)

Total: ~30 arquivos, em 7-8 commits sequenciais. Compatível com "PR cirúrgico"
da prática de aprimora-py.

---

## 16. Próximos passos

1. Aguardar aprovação deste escopo.
2. Se aprovado: detalhar `escopo-implementavel` (versão com sinais de
   commit e linhas de código) — segue o padrão dos outros PRs de aprimora-py.
3. Implementar por fases (passos 1–8 da seção 12), com autorização explícita
   entre fases — segue o padrão das fases A–G do UX-1.
