# SEC-1 follow-up — `must_change_password` no `PUT /usuarios/{id}`

> Documento **somente de escopo**. Nada será implementado sem autorização.
> SEC-1 publicado em `origin/main` até o commit `0488e3f` (test(sec): cobre
> fluxo obrigatório de troca de senha).

## 1. Dívida endereçada

Quando um admin altera a senha de outro usuário pelo endpoint genérico de
edição (`PUT /usuarios/{id}`), o usuário **deveria** ser obrigado a trocá-la no
próximo acesso (mesma regra que vale para `POST /usuarios` e
`POST /usuarios/{id}/resetar-senha`). Hoje **não é**: a edição grava a senha
nova, mas não toca em `must_change_password` e ainda mantém o MD5 legado.

## 2. Estado atual auditado (com referências)

### 2.1. O endpoint **realmente** aceita troca de senha

[backend/app/routers/usuarios.py:168-212](backend/app/routers/usuarios.py#L168-L212) — `PUT /usuarios/{id}`:

```python
data = payload.model_dump(exclude_unset=True)
if "senha" in data and data["senha"]:
    plain = data["senha"]
    data["senha"] = hash_md5(plain)
    data["senha_bcrypt"] = hash_password(plain)
elif "senha" in data:
    data.pop("senha")
...
for k, v in data.items():
    setattr(user, k, v)
await db.commit()
```

Comportamento observado:

- ✅ Aceita o campo `senha` no payload.
- ✅ Grava `senha_bcrypt` correto.
- ❌ **Continua gravando o MD5 legado** — diferente do reset, que zera MD5.
- ❌ **Não marca `must_change_password=true`**.
- ❌ **Não emite registro no audit_log** (a edição genérica de usuário não é
  auditada hoje; reset é).
- ✅ Autorização: `require_permission("usuario", "atualizar")` (mesma do reset)
  — sem essa permissão retorna 403.
- ✅ Cross-tenant bloqueado por `_get_usuario_or_404` em
  [usuarios.py:73-87](backend/app/routers/usuarios.py#L73-L87) (404 quando o
  alvo não pertence ao `tenant_id` da request).

### 2.2. Schema

[backend/app/schemas/usuario.py:18-27](backend/app/schemas/usuario.py#L18-L27) — `UsuarioUpdate.senha: str | None`. Não há
campo novo a criar.

### 2.3. Service `usuario_senha` (referência de “como deve ser”)

[backend/app/services/usuario_senha.py:30-81](backend/app/services/usuario_senha.py#L30-L81) já cobre, no fluxo de reset, exatamente o que falta no
PUT:

- `user.senha_bcrypt = hash_password(senha)`
- `user.senha = ""` (zera MD5 legado)
- `user.must_change_password = True`
- chamada a `audit_log(...)` com `acao="usuario.senha_resetada"`, marcando se
  o afetado é super-usuário e **sem** colocar a senha no payload.

### 2.4. Frontend — UI de edição **já tem** campo de senha

[frontend/app/(app)/usuarios/page.tsx:378-389](frontend/app/(app)/usuarios/page.tsx#L378-L389):

```tsx
<Label htmlFor="senha" required={!editing}>
  {editing ? "Nova senha (vazio = manter)" : "Senha"}
</Label>
<PasswordInput ... />
```

Copy atual diz apenas “Nova senha (vazio = manter)”. **Não avisa** que
preencher força troca no próximo acesso. O `submit()` em
[page.tsx:135-147](frontend/app/(app)/usuarios/page.tsx#L135-L147) já
remove `senha` do payload quando vazia.

### 2.5. Testes existentes

- Backend: `backend/tests/` **não tem** nenhum teste para `PUT /usuarios/{id}`.
- Frontend: `frontend/app/(app)/usuarios/__tests__/reset-senha.test.tsx` cobre
  reset; **não há** teste do dialog de edição.
- Playwright: nenhum spec específico desse caminho.

## 3. Regra desejada (alvo do follow-up)

Quando `PUT /usuarios/{id}` for chamado com `senha` preenchida:

1. Gravar `senha_bcrypt = hash_password(senha)` (já faz).
2. **Zerar `senha` (MD5 legado) para `""`** — paridade com reset e com `POST`
   (Commit 3 do SEC-1).
3. **Marcar `user.must_change_password = True`** — regra principal do
   follow-up.
4. **Auditar** o evento (`acao="usuario.senha_alterada_por_admin"` ou nome
   equivalente — a definir no PR). Payload mínimo, **sem a senha** e **sem o
   hash**: `{ "id_usuario_afetado": user.id, "afetado_super_usuario": bool,
   "must_change_password_set": True, "via": "put_usuarios" }`.
5. Quando o ator alterar a **própria** senha via PUT (`current.id == usuario_id`),
   **não** marcar `must_change_password` (auto-serviço de admin não deve se
   bloquear). Em prol da clareza, recomendar à UI usar `POST /auth/alterar-senha`
   para esse caso; mas se PUT for chamado, o backend trata como exceção
   documentada.
6. Nunca retornar a senha. `UsuarioDetail` (resposta atual) não inclui senha —
   ok como está; cobrir com asserção no teste.

Se decidirmos **proibir** alteração de senha por PUT e canalizar tudo via
reset (rota mais explícita, audit forte, senha temporária), essa é uma opção
mais conservadora; ver §7.

## 4. Autorização / segurança (sem mudança)

Já garantido pelo código atual — confirmar nos testes:

- Sem permissão `usuario.atualizar` → 403. (já)
- Alvo de outro tenant → 404, sem vazar existência. (já)
- Usuário comum tentando alterar outro usuário → 403 via gate de permissão. (já)
- Audit_log **não** carrega a senha em claro nem o hash. (regra do PR; coberto
  em teste).
- Senha nunca retorna na response. (regra do PR; coberto em teste).

## 5. Frontend

Ajustes mínimos no dialog de edição em
[usuarios/page.tsx:378-389](frontend/app/(app)/usuarios/page.tsx#L378-L389):

- Copy do label/help: substituir “Nova senha (vazio = manter)” por algo como
  “Nova senha (vazio = manter; se preenchida, o usuário será obrigado a
  trocá-la no próximo acesso)”.
- Após salvar com senha preenchida, o `toast` poderia trocar de
  “Alterações salvas.” para algo como “Alterações salvas. Usuário deverá
  trocar a senha no próximo acesso.” quando a request tiver enviado `senha`.
- Não criar campo novo. Não exibir a senha pós-salvar (já não exibe).

Decisão alternativa: **remover** o campo de senha do dialog e direcionar a UI
para usar exclusivamente o botão “Resetar senha”. Reduz superfície a manter,
remove um caminho redundante. Detalhe em §7.

## 6. Testes esperados

### 6.1. Backend (pytest, primeiro arquivo `tests/test_usuarios_update.py`)

1. Admin altera senha via PUT → `must_change_password` vira `true`, `senha`
   (MD5) é `""`, `senha_bcrypt` confere com `verify_password`.
2. Login com a nova senha funciona; chamada seguinte a rota protegida devolve
   403 + `X-Must-Change-Password=true` (cobertura cruzada com SEC-1).
3. Audit_log contém um registro com a ação correta e payload sem `senha`/`hash`.
4. PUT alterando **outro** campo (ex.: `cargo`) sem `senha` **não** mexe na
   flag e **não** gera audit_log dessa natureza.
5. Cross-tenant → 404; flag não muda.
6. Sem permissão → 403; flag não muda.
7. Ator alterando a própria senha (`current.id == usuario_id`) — flag **não**
   é marcada (caminho de exceção descrito em §3.5).

### 6.2. Frontend (vitest)

- Edição com `senha` preenchida envia `senha` no payload (já implícito; cobrir).
- Edição com `senha` vazia **não** envia o campo (já implementado; cobrir
  regressão em `usuarios/__tests__/edicao.test.tsx` ou similar).
- Copy do campo informa troca obrigatória.

### 6.3. Playwright (opcional, se baixo custo)

- Estender o spec `sec-must-change-password.spec.ts` com um caso onde a
  troca é feita via PUT do admin (em vez de POST /usuarios criando flagged):
  flag deve subir e o redirect do guard SEC-1 deve disparar igual.

## 7. Decisões em aberto (para alinhamento antes de implementar)

1. **Manter PUT como caminho válido de troca de senha** *(recomendado: sim)*
   ou **canalizar tudo para `POST /usuarios/{id}/resetar-senha`** removendo o
   campo de senha do PUT? Manter é menos intrusivo e preserva o fluxo atual da
   UI; canalizar simplifica a superfície e dá um único ponto de auditoria.
2. **Auto-serviço de admin via PUT em si mesmo** (§3.5) — ratificar a exceção
   ou exigir que admin troque a própria senha **somente** via
   `/auth/alterar-senha`?
3. **Nome da ação no audit_log**: `usuario.senha_alterada_por_admin` vs
   `usuario.senha_alterada` com discriminador `via` no payload.
4. **Copy do dialog** — texto final do aviso.

## 8. Fora de escopo (reafirmado)

- Política de complexidade de senha.
- MFA.
- E-mail / WhatsApp / qualquer canal de notificação.
- Expiração de sessão.
- Portal cidadão (D-CIDADAO).
- Mudança ampla de RBAC.
- Qualquer alteração no SEC-1 já publicado fora do escopo deste follow-up.

## 9. Estimativa grosseira de impacto

- Backend: 1 endpoint alterado (~15 linhas), 1 service opcionalmente, 1 arquivo
  de testes novo (~7 cenários).
- Frontend: 1 dialog (copy + 1-2 linhas), 1 teste novo (~3 cenários).
- Playwright: 0 ou 1 spec extra.
- Migrations: **nenhuma** (coluna já existe).
- Doc: 1 nota curta no `RUNBOOK.md` sob a seção SEC-1 mencionando o
  comportamento do PUT.

---

**Próximo passo após este doc**: aguardar autorização para implementar com a
decisão de §7.1 definida.
