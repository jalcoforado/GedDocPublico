"""Caracterização do achado **F-12** — o runtime conecta com `BYPASSRLS`.

Este arquivo **mede**, não conserta. Ele existe para transformar em teste
executável a afirmação de ADR-016 §1.7 e §9.1: a aplicação conecta no Postgres
como `ged_user` (`SUPERUSER`, `BYPASSRLS`), de modo que a RLS descrita no
invariante 10 do spec como "última barreira de isolamento de tenant" está
**inerte no runtime**.

Por que provar por **inversão** e não por afirmação de catálogo: um teste que
apenas checasse `rolbypassrls = true` em `pg_roles` provaria a *configuração*, e
passaria verde mesmo num mundo em que a RLS estivesse funcionando. O que
interessa é a **consequência** — a diferença de resultado da MESMA consulta,
com o MESMO `app.tenant_id`, sob os dois papéis:

- `ged_user`  (BYPASSRLS)   → enxerga e grava linha de tenant alheio;
- `aprimora_app` (NOBYPASSRLS) → não enxerga e não consegue gravar.

Tabela alvo: `protocolos.tipo_anexo`. Escolhida porque tem `relrowsecurity` e
`relforcerowsecurity` verdadeiros (conferido em `pg_class`), schema simples (só
`tenant_id` NOT NULL, sem FK obrigatória) e já é limpa pela fixture
`two_tenants` no teardown.

Inventário completo do que depende do bypass:
`docs/architecture/security/rls-bypass-inventory.md`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

TABELA_ALVO = "protocolos.tipo_anexo"

# Schemas cobertos pela guarda estrutural. São os schemas cujas tabelas são
# criadas pelas nossas migrations com o boilerplate de RLS descrito no CLAUDE.md.
SCHEMAS_COM_BOILERPLATE_RLS = ("aprimora_py", "frota")

# Tabelas que TÊM coluna `tenant_id` nesses schemas e ainda assim NÃO têm RLS,
# por decisão registrada. Cada entrada precisa da razão escrita — sem razão, a
# entrada não entra aqui e a guarda reprova.
ALLOWLIST_SEM_RLS: dict[str, str] = {
    "aprimora_py.tenant_modulo": (
        "Tabela de PLATAFORMA, não de negócio. A contratação de módulo é escrita "
        "pelo platform admin operando sobre OUTROS tenants — uma policy de "
        "`app.tenant_id` barraria justamente o caso de uso. Decisão registrada no "
        "CLAUDE.md (seção 'Modularização') e na migration 0073."
    ),
}


async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    """`SET LOCAL` na transação corrente — mesma semântica do listener
    `after_begin` de `app/database.py`."""
    await session.execute(text(f"SET LOCAL app.tenant_id = '{int(tenant_id)}'"))


async def _insere_tipo_anexo(
    session: AsyncSession, *, tenant_id: int, nome: str
) -> int:
    res = await session.execute(
        text(
            f"INSERT INTO {TABELA_ALVO} (tenant_id, tipo_anexo, excluido) "
            "VALUES (:tid, :nome, false) RETURNING id"
        ),
        {"tid": tenant_id, "nome": nome},
    )
    return int(res.scalar_one())


async def _ids_visiveis(
    session: AsyncSession, id_a: int, id_b: int
) -> list[int]:
    res = await session.execute(
        text(f"SELECT id FROM {TABELA_ALVO} WHERE id IN (:a, :b) ORDER BY id"),
        {"a": id_a, "b": id_b},
    )
    return [int(r) for r in res.scalars().all()]


# --------------------------------------------------------------------------
# 1. O bypass, provado por diferença de resultado observável (LEITURA)
# --------------------------------------------------------------------------


async def test_leitura_ged_user_ve_linha_de_outro_tenant_e_aprimora_app_nao(
    admin_session: AsyncSession,
    app_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """MESMO SELECT, MESMO `app.tenant_id` (tenant A), dois papéis.

    Com `ged_user` a linha do tenant B aparece; com `aprimora_app` não. A
    diferença é o achado F-12: no runtime a RLS não filtra nada.
    """
    tid_a, tid_b = two_tenants

    # Setup como ged_user: uma linha em cada tenant.
    id_a = await _insere_tipo_anexo(admin_session, tenant_id=tid_a, nome="f12-A")
    id_b = await _insere_tipo_anexo(admin_session, tenant_id=tid_b, nome="f12-B")
    await admin_session.commit()

    # --- papel do RUNTIME (ged_user, BYPASSRLS), posando de tenant A ---
    await _set_tenant(admin_session, tid_a)
    vistos_por_ged_user = await _ids_visiveis(admin_session, id_a, id_b)
    await admin_session.rollback()

    # --- papel sujeito a RLS (aprimora_app), mesmo tenant A ---
    await _set_tenant(app_session, tid_a)
    vistos_por_aprimora_app = await _ids_visiveis(app_session, id_a, id_b)
    await app_session.rollback()

    assert id_b in vistos_por_ged_user, (
        "F-12 parece ter sido corrigido: com `SET LOCAL app.tenant_id` do tenant A, "
        f"`ged_user` NÃO enxergou a linha do tenant B em {TABELA_ALVO}. "
        "Se o runtime deixou de ter BYPASSRLS, atualize este arquivo junto com "
        "docs/architecture/security/rls-bypass-inventory.md."
    )
    assert id_b not in vistos_por_aprimora_app, (
        "A RLS não está isolando nem sob `aprimora_app` — a policy de "
        f"{TABELA_ALVO} está quebrada. Isto é falha de isolamento, não medição."
    )
    assert id_a in vistos_por_aprimora_app, (
        "`aprimora_app` deveria enxergar a linha do PRÓPRIO tenant; se não "
        "enxerga, o problema é grant ou policy, não bypass."
    )
    # A frase que resume o achado, em forma de asserção:
    assert vistos_por_ged_user != vistos_por_aprimora_app, (
        "Os dois papéis devolveram o mesmo conjunto — não há bypass observável "
        "e este teste deixou de caracterizar coisa alguma."
    )


# --------------------------------------------------------------------------
# 2. O bypass na ESCRITA — o lado que corrompe dado, não só vaza
# --------------------------------------------------------------------------


async def test_escrita_ged_user_grava_em_tenant_alheio_e_aprimora_app_e_barrado(
    admin_session: AsyncSession,
    app_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """Posando de tenant A, gravar linha com `tenant_id` de B.

    `ged_user` consegue (o `WITH CHECK` não é avaliado); `aprimora_app` leva
    erro de policy. É o mesmo bypass, no caminho de escrita.
    """
    tid_a, tid_b = two_tenants

    # --- papel do RUNTIME: posando de A, grava em B ---
    await _set_tenant(admin_session, tid_a)
    id_intruso = await _insere_tipo_anexo(
        admin_session, tenant_id=tid_b, nome="f12-cross-tenant"
    )
    await admin_session.commit()

    dono = (
        await admin_session.execute(
            text(f"SELECT tenant_id FROM {TABELA_ALVO} WHERE id = :id"),
            {"id": id_intruso},
        )
    ).scalar_one()
    assert int(dono) == tid_b, (
        "F-12 parece ter sido corrigido: `ged_user` não conseguiu gravar linha "
        "de tenant alheio. Atualize este arquivo e o inventário."
    )

    # --- papel sujeito a RLS: a mesma escrita é barrada ---
    await _set_tenant(app_session, tid_a)
    with pytest.raises(DBAPIError) as exc:
        await _insere_tipo_anexo(
            app_session, tenant_id=tid_b, nome="f12-cross-tenant-app"
        )
        await app_session.commit()
    await app_session.rollback()
    msg = str(exc.value).lower()
    assert "row-level security" in msg or "policy" in msg, (
        f"esperava erro de policy sob `aprimora_app`; recebi: {msg}"
    )


# --------------------------------------------------------------------------
# 3. Guardas
# --------------------------------------------------------------------------


async def test_aprimora_app_nao_tem_superuser_nem_bypassrls(
    admin_session: AsyncSession,
) -> None:
    """Guarda contra regressão de provisionamento.

    Se alguém "consertar" uma falha de RLS dando `BYPASSRLS` a `aprimora_app`,
    todos os testes de isolamento deste repositório passam a passar por engano.
    ADR-016 §9.1 proíbe explicitamente esse atalho.
    """
    linha = (
        await admin_session.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'aprimora_app'"
            )
        )
    ).one_or_none()
    assert linha is not None, "papel `aprimora_app` não existe neste banco"
    rolsuper, rolbypassrls = linha
    assert rolsuper is False, "`aprimora_app` não pode ser SUPERUSER"
    assert rolbypassrls is False, (
        "`aprimora_app` recebeu BYPASSRLS — restaurar bypass como atalho é "
        "proibido (ADR-016 §9.1). Sem isso, todo teste de RLS passa por engano."
    )


async def test_papel_do_runtime_hoje_tem_bypassrls(
    admin_session: AsyncSession,
) -> None:
    """Caracteriza F-12 na configuração efetiva desta execução.

    Lê o papel de `app.database.engine` (isto é, o `DATABASE_URL` que o processo
    de fato usa) e confirma no catálogo que ele tem `BYPASSRLS`.

    **Este teste é feito para falhar quando F-12 for corrigido.** Ele falha
    também na execução deliberada da suíte com `DATABASE_URL` apontando para
    `aprimora_app` — e essa falha é o resultado esperado da medição descrita no
    inventário, não um defeito.
    """
    from app.database import engine

    papel = engine.url.username
    assert papel, "não consegui extrair o papel de `DATABASE_URL`"

    linha = (
        await admin_session.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"
            ),
            {"r": papel},
        )
    ).one_or_none()
    assert linha is not None, f"papel `{papel}` do DATABASE_URL não existe no banco"
    rolsuper, rolbypassrls = linha
    assert rolbypassrls is True, (
        f"o runtime conecta como `{papel}`, que NÃO tem BYPASSRLS "
        f"(rolsuper={rolsuper}). Se isso é a correção de F-12, remova este teste "
        "de caracterização e feche o achado no inventário."
    )


async def test_tabelas_tenanted_tem_rls_habilitada_e_forcada(
    admin_session: AsyncSession,
) -> None:
    """Guarda estrutural: em `aprimora_py.*` e `frota.*`, toda tabela com coluna
    `tenant_id` tem `ENABLE` **e** `FORCE ROW LEVEL SECURITY`, ou consta da
    allowlist acima com razão escrita.

    `FORCE` importa porque sem ele o **dono** da tabela continua contornando as
    policies — e hoje o dono de tudo é `ged_user`. Uma tabela com `ENABLE` e sem
    `FORCE` fica protegida contra `aprimora_app` e desprotegida contra o papel
    que o runtime usa.
    """
    rows = (
        await admin_session.execute(
            text(
                """
                SELECT n.nspname || '.' || c.relname AS tabela,
                       c.relrowsecurity,
                       c.relforcerowsecurity
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                  JOIN information_schema.columns col
                    ON col.table_schema = n.nspname
                   AND col.table_name = c.relname
                   AND col.column_name = 'tenant_id'
                 WHERE c.relkind = 'r'
                   AND n.nspname = ANY(:schemas)
                 ORDER BY 1
                """
            ),
            {"schemas": list(SCHEMAS_COM_BOILERPLATE_RLS)},
        )
    ).all()
    assert rows, (
        "nenhuma tabela tenanted encontrada em "
        f"{SCHEMAS_COM_BOILERPLATE_RLS} — a consulta da guarda quebrou"
    )

    faltando = [
        tabela
        for tabela, rls, forcada in rows
        if not (rls and forcada) and tabela not in ALLOWLIST_SEM_RLS
    ]
    assert not faltando, (
        "tabelas com coluna `tenant_id` sem RLS habilitada E forçada: "
        f"{faltando}. Ou adicione o boilerplate de RLS na migration, ou "
        "declare a tabela em ALLOWLIST_SEM_RLS com a razão escrita."
    )

    # A allowlist não pode envelhecer sem que ninguém perceba: se a tabela ganhou
    # RLS, a entrada tem de sair daqui.
    estado = {tabela: (rls, forcada) for tabela, rls, forcada in rows}
    obsoletas = [
        t for t in ALLOWLIST_SEM_RLS if estado.get(t) == (True, True)
    ]
    assert not obsoletas, (
        f"entradas da allowlist já têm RLS habilitada e forçada: {obsoletas}. "
        "Remova-as da ALLOWLIST_SEM_RLS."
    )
