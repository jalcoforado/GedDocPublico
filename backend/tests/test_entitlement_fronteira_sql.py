"""SEC-RLS-00C — a fronteira de entitlement, medida no SQL.

O que este arquivo trava: **o runtime municipal não contrata módulo.** Até a
migration 0079 a fronteira estava fechada no HTTP (`require_platform_admin`) e
aberta no SQL — `aprimora_app` tinha `INSERT` em `aprimora_py.tenant_modulo`, e
essa tabela **não tem RLS** por decisão registrada, de modo que o `GRANT` era a
única coisa entre um defeito de service e uma contratação forjada.

**Por que cada teste tem controle positivo.** Um teste que só verifica que um
`INSERT` levanta exceção não distingue "o `REVOKE` funcionou" de "a tabela não
existe", "o papel não conecta" ou "a conexão caiu" — os três dariam o mesmo
verde. Nos PRs anteriores desta família, todos os defeitos graves foram testes
que passavam pelo motivo errado. Aqui, antes de cada negativa, a MESMA sessão
prova que faz algo equivalente, e outra sessão prova que a linha negada é de
fato inserível por quem deve inseri-la. As mensagens de erro são conferidas por
extenso pelo mesmo motivo.

**Prova por inversão, executada de verdade durante a implementação.** Não basta
`alembic downgrade -1`: o `downgrade()` da 0079 devolve só o `INSERT` em
`tenant_modulo` (o de `tenant` nunca foi concedido por migration — veio do
`GRANT`-cobertor do bootstrap). A reconstrução fiel do estado anterior foi
`downgrade -1` **mais** `GRANT INSERT ON aprimora_py.tenant TO aprimora_app`.
Com isso, os três testes de negativa ficaram **vermelhos**, e com a mensagem
certa — `DID NOT RAISE`, isto é, o `INSERT` foi aceito e a contratação forjada
apareceu no banco. `test_aprimora_app_continua_gravando_a_propria_trilha`
permaneceu verde, como tem de ser: ele mede um grant que a 0079 não toca.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import APP_URL


def _sessionmaker(url: str):
    engine = create_async_engine(url)
    return engine, async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


async def _um_modulo_contratavel(session: AsyncSession) -> int:
    modulo_id = (
        await session.execute(
            text(
                "SELECT id FROM aprimora_py.modulo "
                " WHERE contratavel = true AND ativo = true ORDER BY ordem LIMIT 1"
            )
        )
    ).scalar_one_or_none()
    assert modulo_id is not None, (
        "não há módulo contratável no catálogo — sem ele o controle positivo "
        "deste arquivo não roda e a negativa não prova nada. Rode "
        "`python -m app.cli.seed_bootstrap`."
    )
    return int(modulo_id)


# ---------------------------------------------------------------------------
# 1. tenant_modulo — a brecha que este PR fecha
# ---------------------------------------------------------------------------


async def test_aprimora_app_nao_contrata_modulo(
    admin_session: AsyncSession,
    platform_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """`aprimora_app` não insere em `aprimora_py.tenant_modulo`.

    Três etapas, nesta ordem, e as duas primeiras existem para que a terceira
    signifique alguma coisa:

    1. **Controle positivo do papel**: a mesma sessão de `aprimora_app` LÊ
       `tenant_modulo` e ESCREVE numa tabela de negócio. Se o papel não
       conectasse, ou o schema não existisse, isto falharia aqui.
    2. **Controle positivo da linha**: `aprimora_platform` insere exatamente a
       linha que vai ser negada, e ela aparece no banco. Descarta que a negativa
       venha de FK, `NOT NULL`, constraint ou catálogo vazio.
    3. **A negativa**, com a mensagem conferida: tem de ser
       `permission denied for table tenant_modulo`, e não um erro qualquer.
    """
    tid_a, tid_b = two_tenants
    modulo_id = await _um_modulo_contratavel(admin_session)
    marca = uuid.uuid4().hex[:8]

    engine, Session = _sessionmaker(APP_URL)
    try:
        # --- 1. controle positivo do papel ---------------------------------
        async with Session() as s:
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.tenant_modulo "
                    " WHERE tenant_id = :t"
                ),
                {"t": tid_a},
            )
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            await s.execute(
                text(
                    "INSERT INTO protocolos.tipo_anexo "
                    "(tenant_id, tipo_anexo, excluido) VALUES (:t, :n, false)"
                ),
                {"t": tid_a, "n": f"sec00c-{marca}"},
            )
            # Rollback: o que interessa é que o INSERT foi ACEITO. Deixá-lo
            # commitado só criaria lixo para o teardown de `two_tenants`.
            await s.rollback()

        # --- 2. controle positivo da linha ---------------------------------
        vinculo_id = int(
            (
                await platform_session.execute(
                    text(
                        "INSERT INTO aprimora_py.tenant_modulo "
                        "(tenant_id, id_modulo) VALUES (:t, :m) RETURNING id"
                    ),
                    {"t": tid_b, "m": modulo_id},
                )
            ).scalar_one()
        )
        await platform_session.commit()
        assert vinculo_id > 0, (
            "`aprimora_platform` não conseguiu contratar. O papel de plataforma "
            "PRECISA conseguir — senão o provisionamento inteiro está quebrado e "
            "a negativa abaixo seria sobre uma tabela inutilizável."
        )

        # --- 3. a negativa -------------------------------------------------
        async with Session() as s:
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text(
                        "INSERT INTO aprimora_py.tenant_modulo "
                        "(tenant_id, id_modulo) VALUES (:t, :m)"
                    ),
                    {"t": tid_a, "m": modulo_id},
                )
            await s.rollback()
    finally:
        await engine.dispose()
        await admin_session.execute(
            text("DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await admin_session.commit()

    msg = str(exc.value).lower()
    assert "permission denied for table tenant_modulo" in msg, (
        f"esperava `permission denied for table tenant_modulo`; recebi: {msg}\n\n"
        "A mensagem é conferida por extenso de propósito: qualquer outra exceção "
        "(FK, NOT NULL, conexão caída) daria o mesmo `pytest.raises` verde sem "
        "provar que o REVOKE da 0079 está de pé."
    )

    vazou = (
        await admin_session.execute(
            text(
                "SELECT id FROM aprimora_py.tenant_modulo "
                " WHERE tenant_id = :t AND id_modulo = :m"
            ),
            {"t": tid_a, "m": modulo_id},
        )
    ).scalar_one_or_none()
    assert vazou is None, (
        "a contratação forjada existe no banco — o INSERT levantou exceção MAS "
        "gravou. Investigue antes de qualquer outra coisa."
    )


# ---------------------------------------------------------------------------
# 2. tenant — criar município também é ato de plataforma
# ---------------------------------------------------------------------------


async def test_aprimora_app_nao_cria_tenant(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """`aprimora_app` não insere em `aprimora_py.tenant`.

    Controle positivo na MESMA sessão e na MESMA tabela, que é o mais forte que
    existe aqui: o papel continua lendo e ATUALIZANDO a linha do tenant. O
    `UPDATE` fica de propósito — a configuração institucional
    (`services/tenant_config`) é editada pelo admin do município. Só o `INSERT`
    saiu. Sem esta metade o teste passaria igual num banco em que `aprimora_app`
    perdeu a tabela inteira, e a revogação teria sido um cobertor em vez de
    cirurgia.
    """
    tid_a, _tid_b = two_tenants
    slug = f"sec00c-negado-{uuid.uuid4().hex[:8]}"

    engine, Session = _sessionmaker(APP_URL)
    try:
        # --- controle positivo: SELECT e UPDATE continuam ------------------
        async with Session() as s:
            await s.execute(
                text("UPDATE aprimora_py.tenant SET sigla = :v WHERE id = :t"),
                {"v": "SEC00C", "t": tid_a},
            )
            await s.commit()

        async with Session() as s:
            depois = (
                await s.execute(
                    text("SELECT sigla FROM aprimora_py.tenant WHERE id = :t"),
                    {"t": tid_a},
                )
            ).scalar_one()
        assert depois == "SEC00C", (
            "CONTROLE POSITIVO falhou: `aprimora_app` não consegue atualizar a "
            "configuração institucional do próprio tenant. Esse UPDATE tem de "
            "continuar — quem o perde é o admin do município, não a plataforma."
        )

        # --- a negativa ----------------------------------------------------
        async with Session() as s:
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text(
                        "INSERT INTO aprimora_py.tenant "
                        "(slug, nome, ativo, plano, criado_em) "
                        "VALUES (:s, 'Forjado', true, 'basico', NOW())"
                    ),
                    {"s": slug},
                )
            await s.rollback()
    finally:
        await engine.dispose()

    msg = str(exc.value).lower()
    assert "permission denied for table tenant" in msg, (
        f"esperava `permission denied for table tenant`; recebi: {msg}"
    )

    sobrou = (
        await admin_session.execute(
            text("SELECT id FROM aprimora_py.tenant WHERE slug = :s"), {"s": slug}
        )
    ).scalar_one_or_none()
    assert sobrou is None, (
        f"o tenant '{slug}' existe no banco — o INSERT levantou exceção MAS "
        "gravou. Investigue antes de qualquer outra coisa."
    )


# ---------------------------------------------------------------------------
# 3. O que a 0079 deliberadamente NÃO tirou
# ---------------------------------------------------------------------------


async def test_aprimora_app_continua_gravando_a_propria_trilha(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """`INSERT` em `aprimora_py.audit_log` FICA — e o teste diz por quê.

    A revogação da 0079 é cirúrgica: entitlement, e só. A trilha municipal é
    escrita pelo próprio município a cada mutação (`services/audit.py`, chamado
    de dezenas de rotas) e a tabela **tem** RLS FORCE, então existe segunda
    barreira: o papel municipal só grava dentro do tenant da sessão. É isso que
    torna esse grant diferente do de `tenant_modulo`, que não tem RLS nenhuma —
    e as duas metades são verificadas aqui.

    Este teste existe para reprovar a revogação "por garantia" que alguém
    tentaria acrescentar depois: sem ele, tirar esse `INSERT` passaria em todo o
    resto do arquivo e derrubaria a aplicação em produção.
    """
    tid_a, tid_b = two_tenants

    engine, Session = _sessionmaker(APP_URL)
    try:
        # --- controle positivo: grava a própria trilha ---------------------
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            await s.execute(
                text(
                    # `tenant_id` é integer e `id_entidade` é bigint: reusar o
                    # MESMO bind nos dois faz o asyncpg deduzir tipos
                    # conflitantes e recusar o prepare. Dois binds distintos.
                    "INSERT INTO aprimora_py.audit_log "
                    "(tenant_id, acao, entidade, id_entidade, criado_em) "
                    "VALUES (:t, 'sec00c.teste', 'tenant', :ent, NOW())"
                ),
                {"t": tid_a, "ent": tid_a},
            )
            await s.commit()

        gravou = (
            await admin_session.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.audit_log "
                    " WHERE tenant_id = :t AND acao = 'sec00c.teste'"
                ),
                {"t": tid_a},
            )
        ).scalar_one()
        assert gravou == 1, (
            "CONTROLE POSITIVO falhou: `aprimora_app` não grava a própria "
            "trilha. Se este grant foi revogado, a aplicação inteira parou de "
            "auditar."
        )

        # --- a segunda barreira: RLS nega a trilha de OUTRO tenant ---------
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text(
                        "INSERT INTO aprimora_py.audit_log "
                        "(tenant_id, acao, entidade, id_entidade, criado_em) "
                        "VALUES (:outro, 'sec00c.vazamento', 'tenant', :ent, NOW())"
                    ),
                    {"outro": tid_b, "ent": tid_b},
                )
            await s.rollback()
    finally:
        await engine.dispose()
        await admin_session.execute(
            text("DELETE FROM aprimora_py.audit_log WHERE tenant_id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await admin_session.commit()

    assert "row-level security" in str(exc.value).lower(), (
        "esperava a policy `WITH CHECK` negando a gravação cross-tenant na "
        f"trilha; recebi: {exc.value}"
    )


# ---------------------------------------------------------------------------
# 4. A mesma propriedade, um nível acima: pelo serviço
# ---------------------------------------------------------------------------


async def test_provisionamento_na_sessao_municipal_falha_alto_e_nao_deixa_tenant(
    admin_session: AsyncSession,
    app_session: AsyncSession,
) -> None:
    """`provisionar_tenant` sem sessão de plataforma, sob `aprimora_app`, para.

    Esta é a metade em CÓDIGO da propriedade que os testes acima medem em SQL, e
    é o que justifica o `db_plataforma=None` continuar existindo na assinatura:
    o parâmetro opcional não é um contorno, porque o banco não deixa. Sob uma
    credencial administrativa (`ged_user`, `aprimora_migrator`) o mesmo `None`
    funciona — é o que a CLI, os seeds e o resto da suíte usam.

    Verifica também que **nada** ficou para trás: como o ato de plataforma é
    atômico em si, o `permission denied` não deixa nem tenant nem contratação.
    """
    from app.services.provisioning_tenant import provisionar_tenant

    slug = f"sec00c-app-{uuid.uuid4().hex[:8]}"
    with pytest.raises((ProgrammingError, DBAPIError)) as exc:
        await provisionar_tenant(
            app_session,
            slug=slug,
            nome="Não deveria existir",
            admin_email=f"{slug}@teste.test",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
        )
    await app_session.rollback()

    assert "permission denied for table tenant" in str(exc.value).lower(), (
        "esperava o INSERT em `aprimora_py.tenant` ser negado ao papel "
        f"municipal; recebi: {exc.value}"
    )

    sobrou = (
        await admin_session.execute(
            text("SELECT id FROM aprimora_py.tenant WHERE slug = :s"), {"s": slug}
        )
    ).scalar_one_or_none()
    assert sobrou is None, f"o tenant '{slug}' ficou no banco depois da negativa"
