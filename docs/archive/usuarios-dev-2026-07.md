# Usuários e senhas — ambiente LOCAL / DEV

> **Status:** PARADO · **Autoridade sobre:** nada — ver docs/acessos-teste-local.md, que é mantido.
> **Última verificação:** 2026-07-18 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](docs/INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

> **Não use como referência do estado atual.** Sem alteração desde a data
> acima; o sistema mudou bastante desde então. Fica por valor histórico.


> ⚠️ **AMBIENTE LOCAL / DEV — NÃO USAR EM PRODUÇÃO.**
> Todas as credenciais abaixo são *seeds* de desenvolvimento versionados no
> repositório (`backend/app/cli/seed_demo.py`, `docs/acessos-teste-local.md`).
> Nenhum dado corresponde a usuário/sistema real. Não substituir por credenciais
> reais; senhas de produção jamais devem ser commitadas.

URL do sistema: `http://localhost:8090` (login servidor em `/login`, cidadão em `/cidadao/login`).

---

## Tenant `sobral` (tenant 1) — ambiente que usamos no dia a dia

| Papel | E-mail / CPF | Senha | Login | Obs. |
|---|---|---|---|---|
| **Super Usuário** (vê tudo, pode tudo) | `admin@local.test` | `admin123` | `/login` | ID 2 · "Usuário Local" |
| Usuário **sem permissões** (testar guardas/403) | `semperm@local.test` | `semperm123` | `/login` | ID 6 |
| **Cidadão** de teste | CPF `12345678901` | `cidadao123` | `/cidadao/login` | ID 1 · "Cidadao Teste" |

---

## Tenant `demo` — seed de apresentação (só existe se rodar `python -m app.cli.seed_demo`)

Todos com a mesma senha: **`Demo@12345`** · domínio `@demo.test` · login em `/login`.

| Papel | E-mail | Nome |
|---|---|---|
| Admin | `admin@demo.test` | Admin Demo |
| Servidor (Obras) | `ana.obras@demo.test` | Ana Costa |
| Servidor (Protocolo) | `bruno.protocolo@demo.test` | Bruno Lima |
| Servidor (Meio Ambiente) | `carla.ambiente@demo.test` | Carla Souza |

---

## Login via API (curl)

```bash
# Servidor / admin
curl -s -X POST http://localhost:8090/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.test","senha":"admin123"}'

# Cidadão
curl -s -X POST http://localhost:8090/api/v2/cidadao/login \
  -H "Content-Type: application/json" \
  -d '{"cpf_cnpj":"12345678901","senha":"cidadao123"}'
```

---

## Notas

- O tenant padrão em `localhost` é o **sobral** (`default_tenant_slug` em `backend/app/config.py`); por isso `admin@local.test` loga direto em `localhost:8090`.
- Os usuários **demo** só existem se o seed de apresentação tiver sido executado no banco; os do **sobral** vêm no seed base.
- Hoje os usuários **não** são forçados a trocar senha no 1º acesso (o fluxo SEC-1 `must_change_password` ainda não foi implementado). Quando entrar, este arquivo precisa ser revisitado.
- Documento de referência mais completo (roteiros de teste, portas, cidadão adicional): [docs/acessos-teste-local.md](docs/acessos-teste-local.md).
