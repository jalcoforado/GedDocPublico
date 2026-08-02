"""SEC-RLS-00B — os papéis mínimos de runtime, medidos no banco.

Companheiro de `test_rls_bypass_caracterizacao.py`: lá se **mede** o achado
F-12; aqui se **trava** o que a migration 0078 passou a garantir.

Quatro propriedades, e nenhuma delas é afirmação de catálogo sozinha — as três
que poderiam passar por acidente têm controle positivo explícito:

1. nenhum papel de runtime é `SUPERUSER` nem tem `BYPASSRLS`;
2. sob `aprimora_app`, **toda** tabela tenanted responde a uma consulta com
   contexto de tenant — é a guarda que teria pego os 20 policies de
   `transporte_regulado` apontando para uma GUC inexistente;
3. sob `aprimora_app`, tenant A não alcança dado de tenant B — em várias
   tabelas, de schemas diferentes, com o controle positivo de que A alcança o
   PRÓPRIO dado;
4. `aprimora_app` não faz DDL; `aprimora_migrator` faz.

Prova por inversão, executada durante a implementação (não é retórica):
com `alembic downgrade -1` — isto é, com a 0078 desfeita — a propriedade 2
fica **vermelha** em 7 tabelas de `transporte_regulado`
(`permission denied for table alvara` e
`unrecognized configuration parameter "app.current_tenant_id"`), e o teste 4
de `aprimora_migrator` falha porque o papel não existe. Só depois disso o
verde do `upgrade` significa alguma coisa.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import APP_URL, MIGRATOR_URL, WORKER_URL

# Os papéis que um PROCESSO de runtime pode usar. `ged_user` está fora de
# propósito: ele é o legado que o `SEC-RLS-ROLLOUT` vai aposentar, e o teste
# `test_rls_bypass_caracterizacao.py` já registra que ele tem bypass.
PAPEIS_DE_RUNTIME = (
    "aprimora_app",
    "aprimora_worker",
    "aprimora_platform",
    "aprimora_migrator",
)

SCHEMAS_NEGOCIO = (
    "aprimora_py",
    "frota",
    "pagamentos",
    "protocolos",
    "transporte_regulado",
    "utils",
)

# Tabelas usadas na prova de isolamento, uma por schema onde dá para inserir
# uma linha sem arrastar meia dúzia de FKs. `transporte_regulado.alvara` está
# aqui porque era uma das quatro tabelas SEM NENHUM grant para `aprimora_app`
# (inventário §4): antes da 0078, o INSERT do controle positivo morria com
# `permission denied for table alvara`.
#
# Cada entrada: (tabela, colunas extras, SQL dos valores extras).
TABELAS_ISOLAMENTO: tuple[tuple[str, str, str], ...] = (
    ("protocolos.tipo_anexo", "tipo_anexo, excluido", "'{marca}', false"),
    # `placa` é varchar(8) — daí o `{curta}` em vez do `{marca}`.
    ("frota.veiculo", "placa", "'{curta}'"),
    ("pagamentos.tag_prioridade", "nome", "'{marca}'"),
    (
        "transporte_regulado.alvara",
        "numero_alvara, tipo_servico, criado_em",
        "'{marca}', 'taxi', NOW()",
    ),
)


def _sessionmaker(url: str):
    engine = create_async_engine(url)
    return engine, async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


# --------------------------------------------------------------------------
# 1. Varredura de pg_roles
# --------------------------------------------------------------------------


async def test_nenhum_papel_de_runtime_e_superuser_nem_tem_bypassrls(
    admin_session: AsyncSession,
) -> None:
    """ADR-016 §2.3/§9.1, em forma executável.

    Cobre os quatro papéis de uma vez em vez de um teste por papel: papel novo
    criado sem os atributos certos aparece aqui como ausente
    (`faltando`), e papel afrouxado aparece como violação. Um teste por papel
    deixaria o quinto papel — o que alguém criar amanhã — sem cobertura
    nenhuma.
    """
    linhas = (
        await admin_session.execute(
            text(
                "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = ANY(:papeis)"
            ),
            {"papeis": list(PAPEIS_DE_RUNTIME)},
        )
    ).all()
    encontrados = {nome for nome, _s, _b in linhas}
    faltando = set(PAPEIS_DE_RUNTIME) - encontrados
    assert not faltando, (
        f"papéis de runtime que NÃO existem no banco: {sorted(faltando)}. "
        "As migrations 0076 (aprimora_platform) e 0078 (worker/migrator) "
        "criam todos — este banco está desatualizado ou alguém deu DROP ROLE."
    )

    violacoes = [
        f"{nome}(rolsuper={s}, rolbypassrls={b})"
        for nome, s, b in linhas
        if s or b
    ]
    assert not violacoes, (
        f"papéis de runtime com privilégio proibido: {violacoes}. "
        "Nenhum papel de runtime pode ser SUPERUSER nem ter BYPASSRLS, e "
        "restaurar o bypass para 'destravar' uma policy é explicitamente "
        "proibido (ADR-016 §9.1)."
    )


# --------------------------------------------------------------------------
# 2. Toda tabela tenanted responde sob o papel da aplicação
# --------------------------------------------------------------------------


async def test_toda_tabela_com_rls_responde_sob_aprimora_app(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """A guarda que teria pego `transporte_regulado` antes de ele chegar a main.

    Para CADA tabela com RLS nos seis schemas de negócio, roda um
    `SELECT count(*)` sob `aprimora_app` com `app.tenant_id` instalado. Não se
    afirma nada sobre o resultado — o que se afirma é que a consulta
    **responde**.

    Os dois defeitos que isso pega são justamente os que o inventário mediu e
    que nenhum teste de service pegaria, porque nenhum deles é erro de lógica:

    - grant faltando  → `permission denied for table ...`
    - GUC errada/sem `true` → `unrecognized configuration parameter ...`

    Uma tabela nova que chegue sem o `GRANT` do boilerplate reprova aqui, no
    PR que a introduziu, e não meses depois no primeiro cliente sem bypass.
    """
    tid_a, _tid_b = two_tenants

    tabelas = [
        f"{s}.{t}"
        for s, t in (
            await admin_session.execute(
                text(
                    "SELECT n.nspname, c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relkind = 'r' AND c.relrowsecurity "
                    "AND n.nspname = ANY(:schemas) ORDER BY 1, 2"
                ),
                {"schemas": list(SCHEMAS_NEGOCIO)},
            )
        ).all()
    ]
    assert len(tabelas) > 50, (
        f"a consulta do catálogo devolveu só {len(tabelas)} tabelas com RLS — "
        "o inventário mediu 87. A guarda quebrou; conserte a consulta antes de "
        "confiar no verde."
    )

    engine, Session = _sessionmaker(APP_URL)
    erros: list[str] = []
    try:
        for tabela in tabelas:
            async with Session() as s:
                try:
                    await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
                    await s.execute(text(f"SELECT count(*) FROM {tabela}"))
                except Exception as e:  # noqa: BLE001 — queremos a lista inteira
                    erros.append(f"{tabela}: {type(e).__name__}: {e}".split("\n")[0])
                finally:
                    await s.rollback()
    finally:
        await engine.dispose()

    assert not erros, (
        "tabelas com RLS inacessíveis para `aprimora_app` mesmo com "
        "`app.tenant_id` instalado:\n  " + "\n  ".join(erros)
    )


# --------------------------------------------------------------------------
# 3. Isolamento cross-tenant, com controle positivo
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tabela,colunas,valores", TABELAS_ISOLAMENTO)
async def test_tenant_a_nao_alcanca_dado_de_tenant_b(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
    tabela: str,
    colunas: str,
    valores: str,
) -> None:
    """A propriedade central do PR, tabela a tabela.

    O CONTROLE POSITIVO não é enfeite: `SELECT` que devolve zero linhas é
    indistinguível entre "a RLS isolou" e "a tabela está quebrada, sem grant,
    ou a GUC não foi instalada". Sem provar antes que a linha do PRÓPRIO
    tenant aparece, este teste passaria verde num banco em que `aprimora_app`
    não enxerga absolutamente nada — que é o oposto do que se quer.
    """
    tid_a, tid_b = two_tenants
    sufixo = uuid.uuid4().hex[:8]
    marca = f"rls00b-{sufixo}"

    ins = text(
        f"INSERT INTO {tabela} (tenant_id, {colunas}) "
        f"VALUES (:t, {valores.format(marca=marca, curta=sufixo)}) RETURNING id"
    )
    id_a = int((await admin_session.execute(ins, {"t": tid_a})).scalar_one())
    id_b = int((await admin_session.execute(ins, {"t": tid_b})).scalar_one())
    await admin_session.commit()

    engine, Session = _sessionmaker(APP_URL)
    try:
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            vistos = [
                int(x)
                for x in (
                    await s.execute(
                        text(f"SELECT id FROM {tabela} WHERE id IN (:a, :b)"),
                        {"a": id_a, "b": id_b},
                    )
                ).scalars()
            ]
            await s.rollback()
    finally:
        await engine.dispose()
        await admin_session.execute(
            text(f"DELETE FROM {tabela} WHERE id IN (:a, :b)"),
            {"a": id_a, "b": id_b},
        )
        await admin_session.commit()

    assert id_a in vistos, (
        f"CONTROLE POSITIVO falhou em {tabela}: `aprimora_app` não enxerga a "
        "linha do PRÓPRIO tenant. Isso é grant ou policy quebrada, não "
        "isolamento — e sem isso a asserção seguinte não prova nada."
    )
    assert id_b not in vistos, (
        f"VAZAMENTO em {tabela}: com `app.tenant_id` do tenant A, "
        "`aprimora_app` enxergou a linha do tenant B."
    )


# --------------------------------------------------------------------------
# 4. Quem pode DDL
# --------------------------------------------------------------------------


async def test_aprimora_app_nao_consegue_ddl() -> None:
    """O papel da API não cria tabela em schema nenhum.

    É o que separa "runtime" de "migração": `entrypoint.sh` roda
    `alembic upgrade head` com a credencial da API, e enquanto essa credencial
    for `ged_user` ninguém percebe. Quando deixar de ser, a migration tem de
    rodar por `aprimora_migrator` — e este teste é o que documenta que a
    separação existe de fato no banco, não só na intenção.
    """
    engine, Session = _sessionmaker(APP_URL)
    try:
        async with Session() as s:
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text("CREATE TABLE aprimora_py.ddl_proibido_rls00b (id int)")
                )
            await s.rollback()
    finally:
        await engine.dispose()
    msg = str(exc.value).lower()
    assert "permission denied" in msg, (
        f"esperava `permission denied for schema`; recebi: {msg}"
    )


async def test_aprimora_migrator_consegue_ddl() -> None:
    """Controle positivo do teste acima.

    Sem ele, `test_aprimora_app_nao_consegue_ddl` continuaria verde num banco
    em que NINGUÉM cria tabela — e a conclusão "a separação de papéis
    funciona" seria falsa.
    """
    nome = f"aprimora_py.ddl_ok_rls00b_{uuid.uuid4().hex[:8]}"
    engine, Session = _sessionmaker(MIGRATOR_URL)
    try:
        async with Session() as s:
            await s.execute(text(f"CREATE TABLE {nome} (id int)"))
            await s.execute(text(f"DROP TABLE {nome}"))
            await s.commit()
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------
# 5. O worker escreve só onde foi autorizado
# --------------------------------------------------------------------------


async def test_worker_le_o_dominio_mas_so_escreve_no_enumerado(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """`aprimora_worker` tem `SELECT` amplo e escrita enumerada (0078).

    A parte que importa é a segunda: o worker NÃO pode inserir numa tabela de
    negócio qualquer. Se puder, o "grants mínimos por task" virou um
    `GRANT ALL` com nome bonito.

    Controle positivo: escrever em `aprimora_py.job`, que é a tabela que as
    tasks de fato gravam.
    """
    tid_a, _ = two_tenants
    sufixo = uuid.uuid4().hex[:8]
    usuario_id = int(
        (
            await admin_session.execute(
                text(
                    "INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf) "
                    "VALUES (:t, 'Worker RLS', :e, '', :c) RETURNING id"
                ),
                {"t": tid_a, "e": f"worker-{sufixo}@rls00b.test", "c": sufixo + "000"},
            )
        ).scalar_one()
    )
    await admin_session.commit()

    engine, Session = _sessionmaker(WORKER_URL)
    try:
        # --- leitura: o worker precisa ler o domínio para montar relatório ---
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            await s.execute(text("SELECT count(*) FROM protocolos.processo"))
            await s.rollback()

        # --- CONTROLE POSITIVO: escreve onde foi autorizado ---
        # `aprimora_py.job.id_usuario` é NOT NULL com FK para `utils.usuario`,
        # então o job precisa de um dono no mesmo tenant.
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            job_id = int(
                (
                    await s.execute(
                        text(
                            "INSERT INTO aprimora_py.job "
                            "(tenant_id, tipo, id_usuario, status) "
                            "VALUES (:t, 'limpeza', :u, 'pendente') RETURNING id"
                        ),
                        {"t": tid_a, "u": usuario_id},
                    )
                ).scalar_one()
            )
            assert job_id > 0
            # `limpar_jobs_antigos` apaga job vencido — é o único DELETE do
            # worker, e faz parte do contrato.
            await s.execute(
                text("DELETE FROM aprimora_py.job WHERE id = :i"), {"i": job_id}
            )
            await s.commit()

        # --- negativo: tabela de negócio fora da lista ---
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text(
                        "INSERT INTO protocolos.tipo_anexo "
                        "(tenant_id, tipo_anexo, excluido) "
                        "VALUES (:t, 'worker-nao-deveria', false)"
                    ),
                    {"t": tid_a},
                )
            await s.rollback()
    finally:
        await engine.dispose()
        await admin_session.execute(
            text("DELETE FROM utils.usuario WHERE id = :i"), {"i": usuario_id}
        )
        await admin_session.commit()

    msg = str(exc.value).lower()
    assert "permission denied" in msg, (
        "esperava `permission denied` ao worker inserir em "
        f"protocolos.tipo_anexo; recebi: {msg}"
    )
