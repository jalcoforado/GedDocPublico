# PR SEC-1 — `must_change_password` e hardening básico de senha temporária (escopo implementável)

> **Predecessor:** [sec-pr1-must-change-password-escopo.md](sec-pr1-must-change-password-escopo.md)
> **Revisão:** v2 (2026-06-05) — corrige estratégia de guard, ordem de commits e whitelist após revisão técnica.
> **Status:** consolidado para implementação. Aguarda autorização explícita.
> **Branch sugerido:** `feat/sec1-must-change-password`.
> **Tamanho esperado:** 1 PR médio dividido em 8 commits sequenciais; ~30 arquivos
> (backend + frontend + testes + docs).

---

## 0. Decisões fechadas (entram inalteradas)

| ID | Decisão |
|---|---|
| **D-COLUNA-LOCAL** | ✅ `utils.usuario.must_change_password BOOLEAN NOT NULL DEFAULT FALSE`. Backfill conservador (`false` para todos os existentes). Usuários atuais não são forçados a trocar senha após a migration. |
| **D-LOGIN-FLAG** | ✅ Login continua funcionando para `must_change_password=true`. Resposta de `/auth/login` **e** `/auth/me` expõem a flag. Nunca retornar hash nem senha. Assinatura v2 não muda. |
| **D-BACKEND-GUARD** | ✅ **Guard central injetado dentro de `get_current_user`** (corrigido na v2). Cobre **toda** rota que depende de `get_current_user` direto ou indiretamente (`require_permission`, `require_acesso_processo`, `require_platform_admin`). Retorna 403 com header `X-Must-Change-Password: true`. SU/permissões/RLS preservados. |
| **D-WHITELIST-ROTAS** | ✅ Whitelist mínima de **rotas autenticadas** que precisam funcionar com flag=true: `/auth/me`, `/auth/alterar-senha`, `/permissoes/me`, `/admin/me`. Cada uma troca `Depends(get_current_user)` por `Depends(get_current_user_no_password_gate)`. Rotas públicas (`/branding/me`, `/health`) e rotas sem dep de usuário (`/auth/logout`) **não fazem parte da whitelist** porque não passam pelo gate. |
| **D-FRONT-GUARD** | ✅ `AuthProvider` redireciona para `/alterar-senha-obrigatoria` quando flag=true. Interceptor HTTP no `request` intercepta 403 com `X-Must-Change-Password: true` e força redirect, **exceto** em `/login`, `/alterar-senha-obrigatoria` e `/cidadao/*`. Após troca: libera navegação. |
| **D-TELA** | ✅ Rota nova `/alterar-senha-obrigatoria`, **fora** do layout `(app)` (sem sidebar). Mensagem: *"Por segurança, altere sua senha temporária antes de continuar."* Não exibe senha temporária. Botão "Sair" disponível. Após sucesso → atualiza estado + redireciona para `/home`. |
| **D-BACKFILL** | ✅ Migration grava `default false`; nenhum `UPDATE` no upgrade. |
| **D-ADMIN-INICIAL** | ✅ `provisionar_tenant` cria admin com `must_change_password=true`. Senha temporária continua exibida uma única vez. RUNBOOK atualizado. |
| **D-RESET-SENHA** | ✅ `resetar_senha_usuario` marca `must_change_password=true`, grava bcrypt, zera MD5, exibe senha uma única vez, audita sem senha. |
| **D-ALTERAR-SENHA** | ✅ `alterar_senha` marca `must_change_password=false`, grava bcrypt, zera MD5, audita sem senha. Sessão **mantida** após troca (JWT continua válido). |
| **D-CIDADAO** | ✅ Cidadão (`utils.usuario_externo`, `get_current_cidadao`) fica **fora** deste PR. |
| **D-AUDITORIA** | ✅ Eventos: `usuario.senha_resetada` e `usuario.senha_alterada` (já existem) — payload anexa `marca_must_change_password` e `limpou_must_change_password`. Sem evento extra `usuario.must_change_password_liberado` (duplicaria `usuario.senha_alterada`). Nunca registrar senha/hash/token. `alterar_senha` passa a propagar `request` para o `audit_log` (consistência com `resetar_senha_usuario`). |
| **D-ZERAR-MD5-ALTERAR** | ✅ Toda troca de senha (auto e reset) limpa `senha` (MD5). Assinatura v2 continua bloqueando MD5 (regra intacta). |

---

## 1. Arquivos: criar / modificar (inventário completo)

### 1.1 Criar (5)

| Arquivo | Conteúdo |
|---|---|
| `backend/alembic/versions/0030_must_change_password.py` | Migration: adiciona coluna `must_change_password BOOLEAN NOT NULL DEFAULT FALSE` em `utils.usuario`. Downgrade dropa a coluna. |
| `frontend/app/alterar-senha-obrigatoria/page.tsx` | Page Next 15 (App Router) fora do grupo `(app)`. Layout próprio sem sidebar. Renderiza `TrocarSenhaCard` adaptado. |
| `frontend/app/alterar-senha-obrigatoria/__tests__/page.test.tsx` | Vitest: renderiza, valida microcopy, redireciona após sucesso, redireciona se flag já é `false`, não dispara chamadas extras. |
| `tests-e2e/specs/sec1-must-change.spec.ts` | Playwright smoke + defesa em profundidade: provisiona → login → redirect → API de negócio bloqueada → troca → libera. |
| `docs/sec-pr1-must-change-password-operacao.md` | Doc operacional: UX final, comportamento, procedimento para admin de plataforma preso. |

### 1.2 Modificar (backend — 8)

| Arquivo | Mudança (resumo) |
|---|---|
| [backend/app/models/usuario.py](backend/app/models/usuario.py) | Adicionar `must_change_password: Mapped[bool]` com `server_default="false"`. |
| [backend/app/schemas/auth.py](backend/app/schemas/auth.py) | Adicionar `must_change_password: bool = False` em `LoginResponse` e `MeResponse`. |
| [backend/app/auth/deps.py](backend/app/auth/deps.py) | Em `get_current_user`: **passa a bloquear flag=true com 403 + `X-Must-Change-Password: true`**. Nova função `get_current_user_no_password_gate` com a mesma lógica de autenticação/tenant **sem** o bloqueio (uso restrito à whitelist). |
| [backend/app/routers/auth.py](backend/app/routers/auth.py) | `login` popula a flag. `me` e `alterar_senha_endpoint` **trocam** `get_current_user` por `get_current_user_no_password_gate`. |
| [backend/app/routers/permissoes.py](backend/app/routers/permissoes.py) | `me` troca `get_current_user` por `get_current_user_no_password_gate`. |
| [backend/app/routers/admin_tenants.py](backend/app/routers/admin_tenants.py) | `admin_me` troca `get_current_user` por `get_current_user_no_password_gate`. |
| [backend/app/services/conta.py](backend/app/services/conta.py) | `alterar_senha`: zera MD5, libera flag, propaga `request` para o `audit_log` (consistência). |
| [backend/app/services/usuario_senha.py](backend/app/services/usuario_senha.py) | `resetar_senha_usuario`: marca flag=true. Payload de audit anexa `marca_must_change_password=True`. |
| [backend/app/services/provisioning_tenant.py](backend/app/services/provisioning_tenant.py) | `provisionar_tenant`: admin inicial nasce com flag=true. |
| [backend/app/routers/usuarios.py](backend/app/routers/usuarios.py) | `create_usuario`: novo usuário nasce com flag=true. |

> **Removido da v1 desta proposta:** edição em `backend/app/auth/perms.py` (`require_permission`), edição em `require_platform_admin`, edição em rotas com `Depends(get_current_user)` direto. **Nenhuma das três é necessária** — o gate em `get_current_user` cobre todos os caminhos automaticamente.

### 1.3 Modificar (frontend — 5)

| Arquivo | Mudança (resumo) |
|---|---|
| [frontend/lib/api.ts](frontend/lib/api.ts) | `MeResponse` e `LoginResponse` ganham `must_change_password: boolean`. Em `request<T>`, interceptar `res.status === 403 && X-Must-Change-Password === "true"` → `window.location.href = "/alterar-senha-obrigatoria"`, **exceto** em `/login`, `/alterar-senha-obrigatoria` e `/cidadao/*`. |
| [frontend/lib/auth.tsx](frontend/lib/auth.tsx) | Em `AuthProvider`: após carregar `/auth/me`, se `user.must_change_password === true`, redireciona para `/alterar-senha-obrigatoria`. **Sem alterar a dependency list do `useEffect` principal** — usar leitura pontual de `window.location.pathname` no momento da decisão. |
| [frontend/middleware.ts](frontend/middleware.ts) | Adicionar `"/alterar-senha-obrigatoria"` à `PUBLIC_PATHS`. |
| [frontend/components/TrocarSenhaCard.tsx](frontend/components/TrocarSenhaCard.tsx) | Prop opcional `onSuccess?: () => void`. Comportamento default preservado. |
| `frontend/app/(app)/usuarios/...` (UI de reset admin) | No modal que exibe `senha_temporaria`, microcopy: *"O usuário deverá alterar esta senha no próximo acesso."* |

### 1.4 Modificar (testes — vitest)

| Arquivo | Mudança |
|---|---|
| [frontend/components/__tests__/TrocarSenhaCard.test.tsx](frontend/components/__tests__/TrocarSenhaCard.test.tsx) | Adicionar 1 teste para o novo prop `onSuccess`. |
| Mocks de `api.me` em testes existentes que usam `useAuth` | Adicionar `must_change_password: false` ao mock. Inventário concreto em §6.4. |

### 1.5 Modificar (docs — 2)

| Arquivo | Mudança |
|---|---|
| [README.md](README.md) | Em "Acesso", explicar que o admin inicial precisa trocar a senha no primeiro acesso. |
| [docs/saas-pr3a-admin-tenants-escopo.md](docs/saas-pr3a-admin-tenants-escopo.md) | Curto adendo no fim: "PR SEC-1: admin inicial nasce com `must_change_password=true`." |

---

## 2. Backend — mudanças (âncoras de identificador, não números de linha)

### 2.1 Migration `0030_must_change_password.py`

```python
"""Adiciona must_change_password em utils.usuario (PR SEC-1).

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-05

Backfill conservador: default FALSE para usuários existentes.
Novos fluxos (provisionamento de tenant, reset administrativo,
criação de usuário pelo admin municipal) marcam TRUE.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema="utils",
    )


def downgrade() -> None:
    op.drop_column("usuario", "must_change_password", schema="utils")
```

**Regras:**
- Não há `UPDATE` no upgrade — o `server_default` garante `false` para os existentes.
- Não tocar em `utils.usuario_externo` (cidadão fora de escopo, D-CIDADAO).

### 2.2 Model `backend/app/models/usuario.py`

Na classe `Usuario`, adicionar (depois de `nivel_acesso_sigilo`):

```python
    # PR SEC-1 — flag de troca obrigatória de senha no próximo acesso.
    # Marcada TRUE em: provisionamento de tenant (admin inicial), reset
    # administrativo, criação de usuário pelo admin municipal.
    # Marcada FALSE em: alteração própria de senha bem-sucedida.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

### 2.3 Schemas `backend/app/schemas/auth.py`

Conteúdo completo do arquivo:

```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario_id: int
    usuario_email: str
    nome: str
    must_change_password: bool = False  # PR SEC-1


class MeResponse(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str | None = None
    id_unidade_trabalho: int | None = None
    must_change_password: bool = False  # PR SEC-1


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=255)
    nova_senha: str = Field(min_length=6, max_length=255)
```

### 2.4 Guard `backend/app/auth/deps.py` — **núcleo da correção**

#### 2.4.1 Refatorar a lógica de busca de usuário em uma função interna

Extrair o miolo do atual `get_current_user` para uma helper interna `_resolve_current_user(...)` que faz: parse Bearer/cookie → decode JWT → checa tenant_id no token vs. middleware → busca `Usuario` no DB → popula `request.state.usuario_id`. **Não** checa `must_change_password`.

```python
async def _resolve_current_user(
    request: Request,
    db: AsyncSession,
) -> Usuario:
    """Lógica original de get_current_user, sem o gate de must_change_password.

    Use APENAS via get_current_user (gate ativo) ou
    get_current_user_no_password_gate (gate desligado, whitelist).
    """
    # [conteúdo atual de get_current_user, sem alterações de lógica]
    ...
```

#### 2.4.2 `get_current_user` passa a aplicar o gate

```python
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """PR SEC-1 — Autentica e exige must_change_password=false.

    Toda rota autenticada de negócio depende disto (direta ou
    indiretamente via require_permission/require_acesso_processo/
    require_platform_admin). Rotas da whitelist usam
    get_current_user_no_password_gate.
    """
    user = await _resolve_current_user(request, db)
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troca de senha obrigatória",
            headers={"X-Must-Change-Password": "true"},
        )
    return user
```

#### 2.4.3 Variante para a whitelist

```python
async def get_current_user_no_password_gate(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """PR SEC-1 — Mesma autenticação de get_current_user, sem o gate.

    Uso restrito às rotas da whitelist (D-WHITELIST-ROTAS):
      - GET  /auth/me
      - POST /auth/alterar-senha
      - GET  /permissoes/me
      - GET  /admin/me

    Qualquer outra rota deve usar get_current_user.
    """
    return await _resolve_current_user(request, db)
```

#### 2.4.4 Por que essa estratégia cobre tudo

| Dep | Cobertura sob o gate em `get_current_user` |
|---|---|
| `Depends(get_current_user)` direto (notificações, audit, busca, anexos, assinaturas leitura, etc.) | bloqueado ✅ |
| `Depends(require_permission(...))` (processos, servicos, dashboard, assinaturas mutativas, usuários, etc.) | bloqueado ✅ — `require_permission` depende de `get_current_user` |
| `Depends(require_acesso_processo)` (vários endpoints de processo) | bloqueado ✅ — depende de `get_current_user` |
| `Depends(require_platform_admin)` (admin SaaS) | bloqueado ✅ — depende de `get_current_user`. Conseqüência: admin de plataforma com flag=true também é bloqueado em `/admin/tenants`. RUNBOOK §7 descreve o procedimento para destravar |
| Rotas da whitelist (`get_current_user_no_password_gate`) | liberadas ✅ |
| `Depends(get_current_cidadao)` | **não afetado** — cidadão fora de escopo (D-CIDADAO) |

#### 2.4.5 `require_platform_admin` — sem edição

Sob a estratégia v2, `require_platform_admin` já é coberto porque depende de `get_current_user`. **Não há edição em `require_platform_admin`.** A v1 propunha essa edição; foi removida.

### 2.5 Router `backend/app/routers/auth.py`

#### 2.5.1 `login` — propagar flag, **sem** bloquear

Na função `login`, a construção do `LoginResponse` no final:

```python
    return LoginResponse(
        access_token=token,
        expires_in=_settings.jwt_ttl_seconds,
        usuario_id=user.id,
        usuario_email=user.email,
        nome=user.nome,
        must_change_password=user.must_change_password,  # PR SEC-1
    )
```

Login **não** muda dependências — segue sem `get_current_user` (autentica por email+senha).

#### 2.5.2 `me` — trocar gate

```python
@router.get("/me", response_model=MeResponse)
async def me(
    user: Usuario = Depends(get_current_user_no_password_gate),  # PR SEC-1
) -> MeResponse:
    return MeResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        cargo=user.cargo,
        id_unidade_trabalho=user.id_unidade_trabalho,
        must_change_password=user.must_change_password,
    )
```

#### 2.5.3 `alterar_senha_endpoint` — trocar gate

```python
@router.post("/alterar-senha", status_code=status.HTTP_204_NO_CONTENT)
async def alterar_senha_endpoint(
    payload: AlterarSenhaRequest,
    request: Request,                                          # PR SEC-1 — D-AUDITORIA
    user: Usuario = Depends(get_current_user_no_password_gate),  # PR SEC-1
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await alterar_senha(
            db,
            usuario=user,
            senha_atual=payload.senha_atual,
            nova_senha=payload.nova_senha,
            request=request,                                   # PR SEC-1 — D-AUDITORIA
        )
    except ContaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

#### 2.5.4 `logout` — sem alteração

`logout` não usa `get_current_user` (só limpa cookie). Não faz parte da whitelist formal; **continua funcionando** porque jamais passou pelo gate.

### 2.6 Router `backend/app/routers/permissoes.py`

Na função `me` (rota `GET /permissoes/me`), trocar dependência:

```python
@router.get("/me", response_model=PermissaoMeResponse)
async def me(
    user: Usuario = Depends(get_current_user_no_password_gate),  # PR SEC-1
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissaoMeResponse:
    ...
```

### 2.7 Router `backend/app/routers/admin_tenants.py`

Na função `admin_me` (rota `GET /admin/me`), trocar dependência:

```python
@router.get("/admin/me", response_model=AdminMeOut)
async def admin_me(
    current: Usuario = Depends(get_current_user_no_password_gate),  # PR SEC-1
) -> AdminMeOut:
    return AdminMeOut(
        email=current.email,
        is_platform_admin=is_platform_admin(current.email),
    )
```

Justificativa: a `Sidebar` e o `PlataformaGate` do frontend chamam `/admin/me` ao montar a área autenticada. Sem essa troca, usuário recém-logado com flag=true receberia 403 com `X-Must-Change-Password: true` em paralelo ao redirect do `AuthProvider` — race + reload completo via `window.location.href`, UX ruim. Whitelistar `/admin/me` elimina o race.

> **Demais rotas em `admin_tenants.py`** (`POST /admin/tenants`, `GET /admin/tenants`, etc.) usam `require_platform_admin` → `get_current_user` → **bloqueadas com flag=true**. Comportamento desejado.

### 2.8 Service `backend/app/services/conta.py`

```python
async def alterar_senha(
    db: AsyncSession,
    *,
    usuario: Usuario,
    senha_atual: str,
    nova_senha: str,
    request: Request | None = None,    # PR SEC-1 — D-AUDITORIA
) -> None:
    ok, _needs_rehash = verify_password(
        senha_atual, bcrypt_hash=usuario.senha_bcrypt, md5_hash=usuario.senha
    )
    if not ok:
        raise ContaError("Senha atual incorreta")
    if len(nova_senha) < 6:
        raise ContaError("A nova senha deve ter ao menos 6 caracteres")

    # PR SEC-1: grava bcrypt, zera MD5 legado, libera must_change_password.
    usuario.senha_bcrypt = hash_password(nova_senha)
    usuario.senha = ""                          # D-ZERAR-MD5-ALTERAR
    usuario.must_change_password = False        # D-ALTERAR-SENHA

    await audit_log(
        db,
        tenant_id=usuario.tenant_id,
        id_usuario=usuario.id,
        acao="usuario.senha_alterada",
        entidade="usuario",
        id_entidade=usuario.id,
        payload={
            "metodo": "bcrypt",
            "limpou_must_change_password": True,
        },
        request=request,                        # PR SEC-1 — D-AUDITORIA
    )
    await db.commit()
```

### 2.9 Service `backend/app/services/usuario_senha.py`

Em `resetar_senha_usuario`, após zerar MD5:

```python
    user.must_change_password = True            # PR SEC-1 — D-RESET-SENHA
```

E no payload do audit log:

```python
        payload={
            "id_usuario_afetado": user.id,
            "afetado_super_usuario": perms_afetado.is_super_usuario,
            "marca_must_change_password": True,    # PR SEC-1
        },
```

**Não tocar** na assinatura/retorno da função — `(usuario, senha_temp)` permanece.

### 2.10 Service `backend/app/services/provisioning_tenant.py`

Na construção do `Usuario` admin, adicionar o campo:

```python
    usuario = Usuario(
        tenant_id=tenant.id,
        nome=admin_nome,
        email=admin_email,
        cpf=admin_cpf,
        senha="",
        senha_bcrypt=hash_password(senha_temp),
        must_change_password=True,             # PR SEC-1 — D-ADMIN-INICIAL
        id_unidade_trabalho=unidade.id,
        ativo=True,
        excluido=False,
        cargo="Administrador",
        app="sistemas",
    )
```

### 2.11 Router `backend/app/routers/usuarios.py`

Em `create_usuario`, adicionar o campo na construção do `Usuario`:

```python
    user = Usuario(
        nome=payload.nome,
        email=payload.email,
        cpf=payload.cpf,
        senha=hash_md5(payload.senha),
        senha_bcrypt=hash_password(payload.senha),
        must_change_password=True,             # PR SEC-1 — D-ADMIN-CRIAR-USUARIO
        id_unidade_trabalho=payload.id_unidade_trabalho,
        cargo=payload.cargo,
        ativo=payload.ativo,
        excluido=False,
        app=get_settings().app_name,
        tenant_id=tenant_id,
    )
```

---

## 3. Frontend — mudanças

### 3.1 Tipos em `frontend/lib/api.ts`

```ts
export interface MeResponse {
  id: number;
  nome: string;
  email: string;
  cargo: string | null;
  id_unidade_trabalho: number | null;
  must_change_password: boolean;   // PR SEC-1
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  usuario_id: number;
  usuario_email: string;
  nome: string;
  must_change_password: boolean;   // PR SEC-1
}
```

### 3.2 Interceptor 403 em `frontend/lib/api.ts`

Na função `request`, antes do bloco `if (!res.ok)`:

```ts
// PR SEC-1 — força redirect quando o backend sinaliza must-change.
// Não redireciona em: tela de login, tela obrigatória, rotas do cidadão.
if (
  res.status === 403 &&
  res.headers.get("X-Must-Change-Password") === "true" &&
  typeof window !== "undefined"
) {
  const here = window.location.pathname;
  const skip =
    here === "/login" ||
    here === "/alterar-senha-obrigatoria" ||
    here.startsWith("/cidadao/");
  if (!skip) {
    window.location.href = "/alterar-senha-obrigatoria";
  }
}
```

A `requestCidadao` **não** recebe este interceptor (cidadão fora de escopo).

### 3.3 Guard em `frontend/lib/auth.tsx`

> **Decisão (corrigida na v2):** **não** adicionar `pathname` à dependency list do `useEffect` principal. Hidratar uma única vez no mount. Ler `window.location.pathname` pontualmente no instante da decisão de redirect.

```tsx
useEffect(() => {
  Promise.all([api.me(), api.permissoes()])
    .then(([u, p]) => {
      setUser(u);
      setPerms(p);
      // PR SEC-1: redireciona uma única vez no mount se a flag estiver
      // ativa. Leitura pontual do pathname — não disparamos a Promise.all
      // novamente a cada navegação interna.
      if (
        u.must_change_password &&
        typeof window !== "undefined" &&
        window.location.pathname !== "/alterar-senha-obrigatoria"
      ) {
        router.replace("/alterar-senha-obrigatoria");
      }
    })
    .catch(() => {
      router.replace("/login");
    })
    .finally(() => setLoading(false));
}, [router]);  // ← apenas router; pathname intencionalmente fora
```

Justificativa: a `request` (lib/api.ts) tem o interceptor 403 + `X-Must-Change-Password: true`. Se a flag for setada **enquanto** a sessão estiver aberta (admin externo reseta a senha do usuário logado), a próxima chamada de API recebe 403 com header → interceptor → redirect. O `AuthProvider` cobre o mount inicial; o interceptor cobre o resto. **Não precisa** rerodar `me`/`permissoes` a cada navegação.

### 3.4 Middleware `frontend/middleware.ts`

```ts
const PUBLIC_PATHS = [
  "/login",
  "/cidadao",
  "/_next",
  "/favicon.ico",
  "/alterar-senha-obrigatoria",   // PR SEC-1
];
```

Página `/alterar-senha-obrigatoria` chama `api.me()` no próprio `useEffect`; sem cookie → 401 → `router.replace("/login")`. Garantir por teste vitest (§6.2).

### 3.5 Componente `frontend/components/TrocarSenhaCard.tsx`

Adicionar prop opcional `onSuccess`:

```tsx
interface Props {
  /**
   * PR SEC-1 — callback chamado após troca bem-sucedida. Usado pela página
   * /alterar-senha-obrigatoria para redirecionar para /home. Default: undefined
   * (mantém comportamento atual de exibir só o toast).
   */
  onSuccess?: () => void;
}

export function TrocarSenhaCard({ onSuccess }: Props = {}) {
  // ... resto inalterado, exceto onSuccess da mutation:
  const m = useMutation({
    mutationFn: () => api.alterarSenha(atual, nova),
    onSuccess: () => {
      toast.success("Senha alterada. Você já pode assinar normalmente.");
      setAtual("");
      setNova("");
      setConfirma("");
      setErr(null);
      onSuccess?.();   // PR SEC-1
    },
    // ...
  });
  // ...
}
```

### 3.6 Nova página `frontend/app/alterar-senha-obrigatoria/page.tsx`

```tsx
"use client";

import { LogOut, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { TrocarSenhaCard } from "@/components/TrocarSenhaCard";
import { api } from "@/lib/api";
import { useBranding } from "@/lib/branding";

/**
 * PR SEC-1 — Tela de troca obrigatória de senha.
 *
 * Fluxo:
 * 1. Verifica /auth/me. Se sem cookie → /login. Se must_change_password=false → /home.
 * 2. Renderiza microcopy + TrocarSenhaCard.
 * 3. Após sucesso → router.replace("/home").
 * 4. Botão "Sair" → api.logout() → /login.
 *
 * Layout próprio (sem sidebar, fora do grupo (app)). Não usa AuthProvider
 * para evitar loop com o guard.
 *
 * Restrição: a página chama EXCLUSIVAMENTE api.me, api.alterarSenha e
 * api.logout. Qualquer outra chamada pode disparar o interceptor 403.
 */
export default function AlterarSenhaObrigatoriaPage() {
  const router = useRouter();
  const branding = useBranding();
  const [verificando, setVerificando] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((me) => {
        if (!me.must_change_password) {
          router.replace("/home");
        } else {
          setVerificando(false);
        }
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function sair() {
    try {
      await api.logout();
    } finally {
      router.replace("/login");
    }
  }

  if (verificando) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-background">
        <p className="text-sm text-foreground-muted">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="w-full max-w-md space-y-6">
        <header className="text-center">
          <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-warning-soft text-warning-soft-foreground">
            <ShieldAlert className="h-6 w-6" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Altere sua senha
          </h1>
          <p className="mt-2 text-sm text-foreground-muted">
            Por segurança, altere sua senha temporária antes de continuar.
          </p>
        </header>

        <TrocarSenhaCard onSuccess={() => router.replace("/home")} />

        <div className="text-center">
          <Button variant="ghost" size="sm" onClick={sair}>
            <LogOut className="mr-1 h-4 w-4" aria-hidden="true" />
            Sair
          </Button>
        </div>

        <p className="text-center text-[11px] text-foreground-subtle">
          {branding?.nome ?? "Aprimora"} — sessão segura
        </p>
      </div>
    </main>
  );
}
```

### 3.7 UI de reset admin (microcopy)

Localizar o modal que exibe `senha_temporaria` em `frontend/app/(app)/usuarios/...`. Acrescentar abaixo da senha:

```tsx
<p className="mt-3 text-xs text-warning-soft-foreground">
  O usuário deverá alterar esta senha no próximo acesso.
</p>
```

Comportamento atual mantido: modal fecha → estado React zera, senha não é persistida (verificado por teste vitest em §6.2).

---

## 4. Plano por commits (ordem corrigida na v2)

A ordem v1 (provisionamento marca flag **antes** do guard armado) criava **janela de exposição**: usuários novos com flag=true existiam, mas o backend ainda não bloqueava rotas de negócio. Ordem corrigida abaixo.

### Commit 1 — `feat(sec1): adiciona coluna must_change_password`

- `backend/alembic/versions/0030_must_change_password.py`
- `backend/app/models/usuario.py`
- `backend/tests/test_must_change_password_modelo.py` (3 testes — §6.1)

Estado do sistema: coluna existe, todos os usuários com flag=false. Nenhum comportamento muda. Seguro para deploy isolado.

Validar: `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head`.

### Commit 2 — `feat(sec1): guard backend + variante whitelist`

- `backend/app/auth/deps.py` (`_resolve_current_user` interno; gate em `get_current_user`; `get_current_user_no_password_gate`)
- `backend/app/routers/auth.py` (`me` e `alterar_senha_endpoint` usam variante)
- `backend/app/routers/permissoes.py` (`me` usa variante)
- `backend/app/routers/admin_tenants.py` (`admin_me` usa variante)
- `backend/tests/test_must_change_password_guard.py` (~15 testes — §6.1)

Estado do sistema: guard armado e auditado, mas como todos os usuários têm flag=false, **ninguém é afetado**. Seguro.

### Commit 3 — `feat(sec1): provisionamento/reset/alterar marcam ou liberam flag`

- `backend/app/services/provisioning_tenant.py`
- `backend/app/services/usuario_senha.py`
- `backend/app/services/conta.py`
- `backend/app/routers/usuarios.py` (`create_usuario`)
- `backend/app/routers/auth.py` (passar `request` para `alterar_senha`)
- `backend/tests/test_must_change_password_provisionamento.py`
- `backend/tests/test_must_change_password_reset.py`
- `backend/tests/test_must_change_password_alterar.py`
- `backend/tests/test_must_change_password_create_usuario.py`

Estado do sistema: a partir daqui, novos admins de tenant, usuários criados e resets futuros marcam `must_change_password=true` — e o guard **já está armado** desde o Commit 2. Sem janela.

### Commit 4 — `feat(sec1): login e /auth/me expõem must_change_password`

- `backend/app/schemas/auth.py`
- `backend/app/routers/auth.py` (popula a flag nas respostas; `me` já está com variante desde Commit 2)
- `backend/tests/test_must_change_password_login.py`

Estado do sistema: clientes (frontend) agora veem a flag, mas até o Commit 5 a UI ainda não age sobre ela. Usuários com flag=true são bloqueados pelo backend (403 + header) — clientes recebem mensagem; sem regressão.

### Commit 5 — `feat(sec1): tela /alterar-senha-obrigatoria + guard frontend`

- `frontend/app/alterar-senha-obrigatoria/page.tsx`
- `frontend/app/alterar-senha-obrigatoria/__tests__/page.test.tsx`
- `frontend/lib/auth.tsx`
- `frontend/lib/api.ts` (tipos + interceptor 403)
- `frontend/middleware.ts`
- `frontend/components/TrocarSenhaCard.tsx` (prop `onSuccess`)
- `frontend/components/__tests__/TrocarSenhaCard.test.tsx` (teste do prop novo)
- Atualizar mocks de `api.me` em testes existentes (§6.4).

### Commit 6 — `feat(sec1): aviso de troca obrigatória no modal de reset`

- `frontend/app/(app)/usuarios/...` (microcopy)
- Teste vitest do modal: verifica microcopy presente; verifica que senha não permanece no DOM após fechar.

### Commit 7 — `test(sec1): smoke E2E + defesa em profundidade`

- `tests-e2e/specs/sec1-must-change.spec.ts` (§6.3 — 4+ tests)

### Commit 8 — `docs(sec1): runbook e operação`

- `docs/sec-pr1-must-change-password-operacao.md`
- `README.md` (parágrafo curto na seção de acesso)
- `docs/saas-pr3a-admin-tenants-escopo.md` (adendo)

**Total: 8 commits.** Cada um é cirúrgico, revogável e validável independente. **Nenhuma janela de exposição** entre commits — o guard entra antes da marcação.

---

## 5. Whitelist final (rotas que precisam funcionar com flag=true)

A whitelist contém apenas **rotas autenticadas** que dependem de `get_current_user` e precisam ser explicitamente liberadas via `get_current_user_no_password_gate`.

| Método | Rota | Origem da dep | Justificativa |
|---|---|---|---|
| GET | `/api/v2/auth/me` | `get_current_user` → trocar para `_no_password_gate` | usuário precisa receber `must_change_password` para o frontend renderizar o guard |
| POST | `/api/v2/auth/alterar-senha` | `get_current_user` → trocar para `_no_password_gate` | única forma de o usuário sair do estado |
| GET | `/api/v2/permissoes/me` | `get_current_user` → trocar para `_no_password_gate` | `AuthProvider` chama em paralelo com `/auth/me` ao montar a área autenticada |
| GET | `/api/v2/admin/me` | `get_current_user` → trocar para `_no_password_gate` | `Sidebar` e `PlataformaGate` chamam ao montar; sem essa rota disponível há race entre interceptor 403 e redirect do `AuthProvider`, causando hard-reload via `window.location.href` |

### Rotas que **não fazem parte da whitelist** (mas continuam funcionando)

Estas não passam pelo gate porque não usam `get_current_user`. Documentadas aqui apenas para evitar confusão em auditoria:

| Método | Rota | Por que não passa pelo gate |
|---|---|---|
| POST | `/api/v2/auth/login` | autentica por email+senha; sem dep de usuário pré-existente |
| POST | `/api/v2/auth/logout` | só limpa cookie; sem dep de usuário |
| GET | `/api/v2/branding/me` | público; sem `get_current_user` |
| GET | `/api/v2/health` | público; sem `get_current_user` |

### Tudo o resto

**Todas as outras rotas autenticadas** (processos, servicos, dashboard, assinaturas, anexos, audit, busca, jobs, manifestantes, modulos, notificacoes, organograma, protocolo, relatorios, tenant, unidades-trabalho, usuarios, workflow, e os endpoints `/admin/tenants` etc.) usam `get_current_user` direta ou indiretamente (`require_permission`, `require_acesso_processo`, `require_platform_admin`) e ficam **automaticamente bloqueadas** com 403 + `X-Must-Change-Password: true` quando o usuário tem `must_change_password=true`.

**Cidadão (`/api/v2/cidadao/*`)** usa `get_current_cidadao` — **não é afetado** (D-CIDADAO).

---

## 6. Testes obrigatórios

### 6.1 Backend (pytest) — 8 arquivos novos

#### `backend/tests/test_must_change_password_modelo.py`
1. `test_default_false_em_insert_sem_campo` — INSERT sem o campo retorna `false`.
2. `test_alembic_upgrade_e_downgrade` — `upgrade head` → coluna existe; `downgrade -1` → coluna some; `upgrade head` novamente OK.
3. `test_backfill_usuarios_existentes` — após upgrade, todos os usuários pré-existentes têm flag `false`.

#### `backend/tests/test_must_change_password_provisionamento.py`
1. `test_provisionar_tenant_cria_admin_must_change_true` — `provisionar_tenant(...)` → `usuario.must_change_password is True`.
2. `test_cli_tenant_create_marca_must_change` — `cli/tenant.py` idem.

#### `backend/tests/test_must_change_password_reset.py`
1. `test_resetar_senha_marca_must_change_true` — `resetar_senha_usuario(...)` → `user.must_change_password is True`.
2. `test_resetar_senha_zera_md5` — `user.senha == ""` após reset.
3. `test_audit_reset_contem_marca_must_change` — payload do `audit_log` tem `marca_must_change_password: True`.
4. `test_audit_reset_nao_contem_senha` — varre o payload e garante ausência da senha temporária.

#### `backend/tests/test_must_change_password_alterar.py`
1. `test_alterar_senha_marca_false` — após `alterar_senha(...)`, `user.must_change_password is False`.
2. `test_alterar_senha_zera_md5` — `user.senha == ""` após troca.
3. `test_audit_alterar_contem_limpou_must_change` — payload tem `limpou_must_change_password: True`.
4. `test_audit_alterar_nao_contem_senha` — varre o payload e garante ausência da nova senha.
5. `test_audit_alterar_passa_request_id` — quando `request` é propagado, o `audit_log` recebe `request_id` no contexto (consistência com `usuario_senha`).

#### `backend/tests/test_must_change_password_create_usuario.py`
1. `test_criar_usuario_pelo_admin_marca_must_change` — `POST /usuarios` → flag=true no novo usuário.

#### `backend/tests/test_must_change_password_login.py`
1. `test_login_must_change_true_retorna_200_com_flag` — usuário com flag=true loga normalmente; resposta carrega `must_change_password=true`.
2. `test_me_retorna_must_change_password` — `GET /auth/me` reflete o estado do DB.
3. `test_login_must_change_false_default` — usuário com flag=false retorna `must_change_password=false`.

#### `backend/tests/test_must_change_password_guard.py` — **núcleo da defesa em profundidade**

Cobertura por camada de dep:

1. `test_guard_403_com_header_x_must_change` — usuário com flag=true → 403 + `X-Must-Change-Password: true`.

   **Whitelist (devem liberar):**
2. `test_guard_libera_auth_me` — `GET /auth/me` retorna 200 com flag=true.
3. `test_guard_libera_alterar_senha` — `POST /auth/alterar-senha` retorna 204 com flag=true (e marca flag=false após).
4. `test_guard_libera_permissoes_me` — `GET /permissoes/me` retorna 200 com flag=true.
5. `test_guard_libera_admin_me` — `GET /admin/me` retorna 200 com flag=true.

   **Não passam pelo gate (devem funcionar mesmo):**
6. `test_guard_branding_me_publico` — `GET /branding/me` retorna 200 (mesmo sem cookie).
7. `test_guard_health_publico` — `GET /health` retorna 200.
8. `test_guard_logout` — `POST /auth/logout` funciona com flag=true.

   **Rotas que usam `require_permission` (cobertas indiretamente):**
9. `test_guard_bloqueia_processos_list` — `GET /processos` com flag=true → 403.
10. `test_guard_bloqueia_servicos_admin` — `GET /servicos` com flag=true → 403.
11. `test_guard_bloqueia_dashboard_kpis` — `GET /dashboard/kpis` com flag=true → 403.
12. `test_guard_bloqueia_assinatura_assinar` — `POST /assinaturas/{id}/assinar` com flag=true → 403 (rota via `require_permission`).
13. `test_guard_bloqueia_workflow_definitions` — `GET /workflow/definitions` com flag=true → 403.
14. `test_guard_bloqueia_usuarios_list` — `GET /usuarios` com flag=true → 403.
15. `test_guard_bloqueia_admin_tenants_list` — `GET /admin/tenants` com flag=true → 403 (rota via `require_platform_admin`).

   **Rotas que usam `get_current_user` DIRETO (cobertas pelo gate em `get_current_user`):**
16. `test_guard_bloqueia_assinatura_recusar` — `POST /solicitacoes-assinatura/{id}/recusar` com flag=true → 403.
17. `test_guard_bloqueia_assinatura_listar_pendentes` — `GET /solicitacoes-assinatura/me/pendentes` → 403.
18. `test_guard_bloqueia_assinatura_validar` — `GET /assinaturas/{id}/validar` → 403.
19. `test_guard_bloqueia_assinatura_evidencias` — `GET /assinaturas/{id}/evidencias` → 403.
20. `test_guard_bloqueia_assinatura_comprovante` — `GET /assinaturas/{id}/comprovante.pdf` → 403.
21. `test_guard_bloqueia_notificacoes_listar` — `GET /notificacoes/me` → 403.
22. `test_guard_bloqueia_notificacoes_preferencias` — `PUT /notificacoes/preferencias` → 403 (crítico — alteração de canal).
23. `test_guard_bloqueia_notificacoes_telefone` — `PUT /notificacoes/telefone` → 403 (crítico — desvio).
24. `test_guard_bloqueia_anexos_download` — `GET /anexos/{id}/download` → 403.
25. `test_guard_bloqueia_audit_list` — `GET /audit` → 403.
26. `test_guard_bloqueia_busca` — `GET /busca?q=teste` → 403.

   **Rotas que usam `require_acesso_processo` (depende de `get_current_user`):**
27. `test_guard_bloqueia_processo_anexos_get` — endpoint de `processos.py` que depende só de `require_acesso_processo` + `require_tenant_id` (sem `require_permission`) → 403.

   **Smoke amplo parametrizado (regressão futura):**
28. `test_rota_negocio_smoke_bloqueada_parametrizado` — pytest `@parametrize` com lista de rotas (1 por router de negócio), todas retornam 403 com flag=true. Detecta routers novos esquecidos.

   **Fluxo completo:**
29. `test_apos_alterar_senha_acessa_processos` — cria usuário com flag=true, alterar-senha (204), acessa `/processos` com 200.
30. `test_usuario_normal_nao_e_afetado` — usuário com flag=false acessa tudo (regressão).

   **Teste genérico de defesa em profundidade:**
31. `test_endpoint_arbitrario_com_get_current_user_direto_bloqueia` — usa uma rota de fixture montada apenas com `Depends(get_current_user)`, verifica que o gate dispara mesmo sem `require_permission` no caminho.

### 6.2 Frontend (vitest) — 2 arquivos novos + atualizações

#### `frontend/app/alterar-senha-obrigatoria/__tests__/page.test.tsx`
1. `test_renderiza_microcopy_obrigatoria` — texto "Por segurança, altere sua senha temporária antes de continuar." está visível.
2. `test_renderiza_card_de_troca` — `TrocarSenhaCard` está presente.
3. `test_renderiza_botao_sair` — botão "Sair" está visível.
4. `test_redireciona_para_home_se_flag_falsa` — `/auth/me` retorna `must_change_password=false` → `router.replace("/home")`.
5. `test_redireciona_para_login_sem_cookie` — `/auth/me` 401 → `router.replace("/login")`.
6. `test_apos_troca_redireciona_para_home` — `api.alterarSenha` resolve → `router.replace("/home")`.
7. `test_botao_sair_chama_logout_e_redireciona` — click no "Sair" → `api.logout` chamado + `router.replace("/login")`.
8. `test_pagina_nao_dispara_chamadas_alem_de_me_alterarsenha_logout` — instrumentar todos os métodos de `api.*` mockados; verificar que `processos`, `dashboard`, `permissoes`, `branding`, `admin.me` etc. NÃO são chamados. Defesa contra interceptor disparar redirect espúrio.

#### `frontend/components/__tests__/TrocarSenhaCard.test.tsx` (extensão)
1. `test_chama_on_success_apos_troca_bem_sucedida` — adicionar 1 teste para o prop `onSuccess`.

#### `frontend/lib/__tests__/auth.test.tsx` (criar)
1. `test_redireciona_para_obrigatoria_se_flag_true` — pathname `/home`, `me.must_change_password=true` → `router.replace("/alterar-senha-obrigatoria")`.
2. `test_nao_redireciona_se_ja_na_obrigatoria` — pathname `/alterar-senha-obrigatoria` → não redireciona.
3. `test_nao_redireciona_se_flag_false` — permanece em `/home`.
4. `test_nao_reexecuta_me_em_navegacao_interna` — montagem inicial chama `api.me` uma vez; mudar `pathname` programaticamente não dispara `api.me` de novo. Defesa contra M-1 da revisão.

#### `frontend/lib/__tests__/api-interceptor.test.tsx` (criar)
1. `test_interceptor_redireciona_em_403_com_header` — 403 + `X-Must-Change-Password: true` em pathname `/home` → `window.location.href` setado para `/alterar-senha-obrigatoria`.
2. `test_interceptor_nao_redireciona_em_login` — pathname `/login` → não redireciona.
3. `test_interceptor_nao_redireciona_em_obrigatoria` — pathname `/alterar-senha-obrigatoria` → não redireciona.
4. `test_interceptor_nao_redireciona_em_cidadao` — pathname `/cidadao/processos/42` → não redireciona.
5. `test_interceptor_nao_redireciona_em_403_sem_header` — 403 sem `X-Must-Change-Password` → não redireciona (erro normal de permissão).

#### Reset admin (microcopy + segurança)
Em `frontend/app/(app)/usuarios/__tests__/reset-senha.test.tsx` (ou local equivalente):
1. `test_modal_reset_mostra_aviso_troca_obrigatoria` — microcopy "O usuário deverá alterar esta senha no próximo acesso." visível.
2. `test_modal_reset_nao_deixa_senha_no_dom_apos_fechar` — captura `senha_temporaria`, fecha modal, varre `document.body.innerHTML` por substring da senha → ausente.

### 6.3 Playwright (E2E) — `tests-e2e/specs/sec1-must-change.spec.ts`

```ts
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

// Reaproveita helpers do ux1-smoke (bridgeApiToNginx, loginAdminInContext, etc.).
// Idealmente extrair para helpers/ comum em um commit futuro.

test.describe.serial("SEC-1 must-change-password", () => {
  // Setup: provisiona tenant via /api/v2/admin/tenants (PLATFORM_ADMIN)
  // OU pré-marca flag=true em usuário existente via SQL direto.
  let userEmail: string;
  let senhaTemp: string;

  test.beforeAll(async ({ browser }) => {
    // Provisiona tenant; captura admin_email e senha_temporaria.
  });

  test("login com senha temporária redireciona para /alterar-senha-obrigatoria",
    async ({ page, context }) => {
      // 1. Login via UI.
      // 2. URL atual é /alterar-senha-obrigatoria.
      // 3. Heading "Altere sua senha" visível.
      // 4. Microcopy "Por segurança, altere sua senha temporária..." visível.
    });

  test("tentativa de acessar /dashboard com flag=true redireciona",
    async ({ page, context }) => {
      // 1. Login com senha temporária.
      // 2. page.goto("/dashboard").
      // 3. Espera redirect para /alterar-senha-obrigatoria.
    });

  test("defesa em profundidade: API de negócio direta retorna 403 + header",
    async ({ context }) => {
      // 1. POST /api/v2/auth/login → cookie aprimora_token.
      // 2. GET /api/v2/processos → 403 + X-Must-Change-Password: true.
      // 3. GET /api/v2/dashboard/kpis → 403 + header.
      // 4. PUT /api/v2/notificacoes/telefone → 403 + header (mutativa crítica).
    });

  test("defesa em profundidade: endpoint de assinatura retorna 403 + header",
    async ({ context }) => {
      // 1. Cookie aprimora_token com flag=true.
      // 2. GET /api/v2/solicitacoes-assinatura/me/pendentes → 403 + header.
      // 3. POST /api/v2/solicitacoes-assinatura/1/recusar → 403 + header
      //    (mesmo que o ID seja inexistente, o gate dispara antes).
    });

  test("após trocar senha, usuário acessa /dashboard normalmente",
    async ({ page, context }) => {
      // 1. Login com senha temporária.
      // 2. Preenche nova senha, confirma, submete.
      // 3. Aguarda redirect para /home.
      // 4. page.goto("/dashboard") → renderiza dashboard executivo (sem redirect).
    });
});
```

### 6.4 Mocks a atualizar em testes existentes

Em todos os testes vitest que mockam `api.me`, adicionar `must_change_password: false`:

Inventário a ser executado **no Commit 5** com:

```bash
grep -rln "api\.me\|me:.*vi\.fn\|MeResponse" frontend/app frontend/components frontend/lib 2>/dev/null
```

Mocks prováveis (lista a confirmar durante a implementação):
- `frontend/app/(app)/dashboard/__tests__/page.test.tsx`
- `frontend/app/(app)/processos/[id]/__tests__/page.test.tsx`
- `frontend/app/(app)/processos/__tests__/page.test.tsx`
- `frontend/app/(app)/servicos/__tests__/page.test.tsx`
- `frontend/app/(app)/usuarios/__tests__/reset-senha.test.tsx`
- `frontend/app/(app)/perfil/...` (se houver)
- `frontend/components/__tests__/*.test.tsx` (testes que envolvem `useAuth`)

**Template:**

```ts
// Antes:
const meMock = { id: 1, nome: "Admin", email: "admin@x", cargo: null, id_unidade_trabalho: null };

// Depois:
const meMock = {
  id: 1, nome: "Admin", email: "admin@x", cargo: null, id_unidade_trabalho: null,
  must_change_password: false,
};
```

Testes que não usam `useAuth` direto provavelmente não precisam atualizar.

---

## 7. RUNBOOK / Operação (documento novo)

`docs/sec-pr1-must-change-password-operacao.md` — esboço completo:

```markdown
# SEC-1 — Must change password (operação)

## O que mudou

A partir do PR SEC-1:
1. O admin inicial criado pelo provisionamento de tenant nasce com
   `must_change_password=true` no banco. A senha temporária continua sendo
   exibida uma única vez ao operador.
2. Quando um admin municipal reseta a senha de outro usuário, a flag também
   é marcada como `true`. O usuário afetado verá a tela obrigatória no
   próximo login.
3. Usuário com a flag ativa **não consegue acessar nenhuma rota de negócio**
   antes de trocar a senha. Apenas: login, `/auth/me`, alterar-senha, logout,
   permissões e branding mínimos.

## Como o usuário troca

1. Login normal em `/login`.
2. Frontend detecta a flag e redireciona para `/alterar-senha-obrigatoria`.
3. Usuário informa senha temporária + nova senha + confirmação.
4. Após sucesso, é levado para `/home` com sessão válida.

## Como o admin reseta a senha de alguém

1. `/usuarios` → seleciona o usuário → "Resetar senha".
2. Modal exibe a senha temporária **uma única vez**.
3. Aviso visível: "O usuário deverá alterar esta senha no próximo acesso."
4. Operador transmite a senha pelo canal seguro institucional.

## Suspeita de senha temporária vazada

1. Admin municipal pode resetar de novo — uma nova senha temporária é
   gerada e a anterior deixa de funcionar.
2. Audit log registra: ator, afetado, evento `usuario.senha_resetada`,
   timestamp, `marca_must_change_password=true`. **A senha nunca é gravada.**
3. Se houver risco de sessão ativa do atacante, desativar o usuário
   (`ativo=false`) invalida a sessão em qualquer rota subsequente.

## Cliente HTTP externo (integração)

Quando uma chamada recebe `403` com `X-Must-Change-Password: true`, o
usuário associado ao token precisa trocar a senha pela UI antes de
chamar qualquer rota de negócio. Clientes externos não devem tentar
resolver isso programaticamente — direcionar o usuário humano à UI.

## Admin de plataforma preso na troca obrigatória (cenário raro)

Cenário: o admin de plataforma (e-mail em `PLATFORM_ADMIN_EMAILS`) também
é um `Usuario` em algum tenant. Se receber `must_change_password=true`
(ex.: criado por provisionamento que admite admins de plataforma como
admins iniciais, ou reset administrativo), ele fica preso na tela
obrigatória — e perde acesso a `/admin/tenants`.

**Procedimento de destrave (controlado e auditado):**

1. Operador DBA autenticado no PostgreSQL com a role privilegiada do
   ambiente (não usar `aprimora_app`).
2. Verificar identidade do admin de plataforma:
   ```sql
   SELECT id, email, must_change_password, tenant_id
   FROM utils.usuario
   WHERE email = '<email_do_admin_plataforma>';
   ```
3. Confirmar com o operador que se trata de admin de plataforma
   legítimo. **Não destravar usuários comuns por essa rota.**
4. Limpar a flag:
   ```sql
   UPDATE utils.usuario
      SET must_change_password = false
    WHERE id = <id_confirmado>
      AND email = '<email_confirmado>';
   ```
5. Registrar ação em ticket interno (não há `audit_log` automático
   para intervenção manual em DB; é responsabilidade operacional
   documentar).
6. Admin de plataforma deve trocar a senha pela UI **assim que
   possível**.

Após o destrave, considerar criar PR futuro que permita reset de senha
do admin de plataforma por outro admin de plataforma autenticado.
```

---

## 8. Critérios de pronto

- [ ] Migration 0030 aplica e desfaz sem erro.
- [ ] Todos os testes pytest novos (~50) passam, incluindo os de defesa em profundidade.
- [ ] Todos os testes vitest novos (~17) passam; mocks existentes atualizados; suíte completa verde.
- [ ] Playwright `sec1-must-change.spec.ts` 5/5 verde.
- [ ] tsc baseline inalterada; zero erros novos.
- [ ] Smoke parametrizado pytest cobre 1 rota por router de negócio (mais 1 router → falha de teste).
- [ ] Audit log não contém senha em **nenhum** dos 3 fluxos (provisionamento, reset, alterar).
- [ ] `must_change_password` aparece **apenas** em `MeResponse` e `LoginResponse` (não em `UsuarioOut` nem em audit log payload com nome enganoso).
- [ ] RUNBOOK escrito e revisado, incluindo procedimento de destrave do admin de plataforma.
- [ ] README atualizado.
- [ ] Nenhuma rota com `Depends(get_current_user)` direto sobrevive sem o gate (cobertura provada pelos testes #16-26 e #28).

---

## 9. Riscos e mitigações (resumo)

| Risco | Mitigação |
|---|---|
| Rota de negócio não coberta pelo gate | Gate em `get_current_user` cobre tudo automaticamente. Smoke parametrizado em pytest detecta routers novos esquecidos |
| Admin SaaS recebe flag involuntariamente | Backfill é `false` por padrão. Pytest modelo #3 garante |
| Admin de plataforma preso | RUNBOOK §7 documenta procedimento de destrave controlado |
| Loop de redirect no frontend | Interceptor 403 ignora `/login`, `/alterar-senha-obrigatoria`, `/cidadao/*`. Vitest #2-5 da seção api-interceptor garante |
| `AuthProvider` re-executa a cada navegação | `useEffect` mantido com `[router]`; pathname lido pontualmente. Vitest auth #4 garante |
| Sessão antiga ignora flag | `get_current_user` lê DB a cada chamada; sem janela |
| Senha em log via Sentry | Audit testes varrem payloads. RequestLogging não loga body. Sentry não captura senha por construção |
| Cidadão cai por engano no guard | `get_current_user` (admin) e `get_current_cidadao` são funções separadas. Cidadão não muda |
| MD5 zerado quebra autenticação legada | `verify_password` prefere bcrypt; após troca/reset, bcrypt está populado |
| `/admin/me` 403 gera race com AuthProvider | `/admin/me` está na whitelist. Vitest api-interceptor #1 cobre o caso geral |
| Sidebar/Sidebar children disparam chamadas em paralelo | Bloqueadas pelo gate, retornam 403 + header → interceptor redireciona. `AuthProvider` faz `router.replace` em paralelo. Comportamento estável (mesmo destino) |
| Página obrigatória dispara chamada inesperada | Vitest page #8 garante que só `me`/`alterarSenha`/`logout` são tocadas |
| Próximo PR de drop MD5 não consegue autenticar usuários antigos | Esses usuários **já vão precisar** rotacionar (assinatura v2 bloqueia MD5). Drop final é PR pós-cutover, fora deste escopo |

---

## 10. Fora de escopo (lembrete)

Não implementar: 2FA, política avançada de complexidade, recuperação por
e-mail, convite por e-mail, expiração periódica, OAuth/gov.br, cidadão,
revogação global de sessões, device management, mudança em assinatura v2,
drop definitivo da coluna MD5, mudança no `min_length=6` da nova senha,
reset de senha de admin de plataforma por outro admin de plataforma
(possível em PR futuro).

---

## 11. Próximo passo

Após aprovação explícita deste documento implementável v2, iniciar pelo
**Commit 1** (migration + modelo + 3 testes pytest de schema). Cada
commit exige autorização individual antes de prosseguir — segue o padrão
das fases A–G do UX-1.
