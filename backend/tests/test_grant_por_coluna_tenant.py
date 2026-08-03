"""SEC-RLS-00D — o runtime municipal não altera coluna de PLATAFORMA.

`aprimora_py.tenant` **não tem RLS** (tabela de plataforma, decisão registrada na
0073). Sem RLS, o `GRANT` é a única coisa entre o papel municipal e a tabela
inteira — e até a migration 0080 `aprimora_app` tinha `UPDATE` de TABELA, ou
seja, as 24 colunas, inclusive `ativo`, `plano`, `slug` e os limites. A migration
troca isso por `GRANT UPDATE (<13 colunas>)`.

## Por que cada negativa tem controle positivo

Em Postgres, negativa por privilégio de COLUNA devolve **exatamente a mesma
frase** da negativa por privilégio de TABELA:

    ERROR:  permission denied for table tenant

(verificado neste banco antes de escrever o arquivo). Então um teste que só
verifica que o `UPDATE` levanta exceção não distingue "o grant por coluna
funcionou" de "o papel perdeu a tabela inteira", "a sessão morreu" ou "a linha
não existe" — os quatro dariam o mesmo verde, e o quarto seria uma REGRESSÃO
grave: `PUT /api/v2/tenants/me` fora do ar para todo município.

Por isso a MESMA sessão, no MESMO tenant, prova antes que consegue gravar
`sigla`; e depois de cada negativa o valor é relido por uma sessão
administrativa, para descartar "levantou exceção MAS gravou".

## Prova por inversão, executada de verdade

Rodado contra o estado anterior à 0080 (o `downgrade` devolve o `UPDATE` de
tabela, e o catálogo volta a mostrar as 24 colunas): **8 vermelhos, 2 verdes.**
As cinco negativas falharam com `DID NOT RAISE` — o `UPDATE` em
`ativo`/`plano`/`slug`/`limite_usuarios` foi aceito, e o município B chegou a ser
desativado pela sessão do município A — e as três guardas de catálogo apontaram
24 colunas concedidas contra 13 esperadas.

Os 2 verdes são exatamente os da seção 3, que medem o que a 0080 **não** tira
(NUP federal no papel municipal, `UPDATE` de tabela no papel de plataforma).
Verdes nos dois estados é o comportamento correto deles.

## O que este arquivo NÃO alcança

Tudo aqui é catálogo (`information_schema`) ou SQL cru, e as três pontas da
guarda de divergência são indexadas por **campo de schema Pydantic**. Coluna que
um caminho municipal suje FORA do payload — o `atualizado_em = utcnow()` depois
do `setattr`, convenção do resto do repositório — é invisível às três, e o
`UPDATE` do ORM (que é o que roda em produção) não é medido aqui.
Essa metade está em `test_pr3b_config_inicial.py`, seção "SEC-RLS-00D": os dois
caminhos municipais rodando pelo ORM sob a fixture `app_session`.
"""
from __future__ import annotations

import re
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.schemas.tenant import TenantInstitucionalUpdate, TenantNupConfigUpdate
from app.services.tenant_config import COLUNAS_MUNICIPAIS_DE_TENANT
from tests.conftest import APP_URL

MIGRATION = "0080_grant_por_coluna_em_tenant.py"

# Colunas de PLATAFORMA: as que decidem entitlement comercial, identidade e
# estado do município. Nenhuma delas pode entrar no grant municipal — nem
# "temporariamente", nem para fazer um teste passar.
#
# Esta lista existe para que a guarda de divergência não seja satisfeita
# ampliando OS DOIS lados. Sem ela, quem quisesse dar `ativo` ao runtime
# municipal bastaria acrescentá-lo à constante do service e à migration, e o
# teste de divergência ficaria verde enquanto a propriedade central do PR
# morria em silêncio.
COLUNAS_DE_PLATAFORMA = frozenset(
    {
        "id",
        "slug",
        "ativo",
        "plano",
        "cnpj",
        "id_cidade",
        "criado_em",
        "limite_usuarios",
        "limite_armazenamento_mb",
    }
)


def _sessionmaker(url: str):
    engine = create_async_engine(url)
    return engine, async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


def _negou_a_tabela(mensagem: str) -> bool:
    """`permission denied for table tenant`, com fronteira de palavra no fim.

    `in` seria frouxo justamente onde não pode ser: casaria também com
    `...table tenant_modulo`, e a negativa passaria verde por causa de um
    `REVOKE` de outra tabela (o da 0079). O `\\b` resolve — depois de `tenant`,
    o `_` de `tenant_modulo` é caractere de palavra.
    """
    return re.search(r"permission denied for table tenant\b", mensagem) is not None


async def _colunas_concedidas(db: AsyncSession) -> set[str]:
    """Colunas de `aprimora_py.tenant` com `UPDATE` para `aprimora_app`.

    `information_schema.column_privileges` devolve tanto o grant por coluna
    quanto o implicado por um grant de tabela — é por isso que ele serve de
    medida única: antes da 0080 devolvia as 24 colunas.
    """
    linhas = (
        await db.execute(
            text(
                "SELECT column_name FROM information_schema.column_privileges "
                " WHERE table_schema = 'aprimora_py' AND table_name = 'tenant' "
                "   AND grantee = 'aprimora_app' AND privilege_type = 'UPDATE'"
            )
        )
    ).scalars().all()
    return set(linhas)


# ---------------------------------------------------------------------------
# 1. A guarda de divergência — o item mais importante deste arquivo
# ---------------------------------------------------------------------------


async def test_grant_no_banco_espelha_a_fonte_unica_do_service(
    admin_session: AsyncSession,
) -> None:
    """As colunas concedidas no banco == `COLUNAS_MUNICIPAIS_DE_TENANT`.

    Este é o teste que a revisão do `SEC-RLS-00C` pediu nominalmente, e a razão
    de ele existir é o modo de falha, não a simetria: sem ele, acrescentar um
    campo à whitelist do service produziria `permission denied for table tenant`
    em produção **sem nenhuma pista de que a causa é um grant**. O 500 apareceria
    no endpoint de configuração institucional, e quem investigasse leria o
    service — onde está tudo certo — antes de suspeitar do banco.

    A comparação é de três pontas de propósito. Duas (código ↔ banco) pegariam o
    campo esquecido na migration; a terceira (schemas Pydantic ↔ constante) pega
    o caso anterior a esse: campo acrescentado ao `TenantInstitucionalUpdate` ou
    ao `TenantNupConfigUpdate` sem ninguém lembrar da constante. É por ali que a
    divergência começa, porque é o schema que define o que o endpoint aceita.
    """
    dos_schemas = set(TenantInstitucionalUpdate.model_fields) | set(
        TenantNupConfigUpdate.model_fields
    )
    assert dos_schemas == COLUNAS_MUNICIPAIS_DE_TENANT, (
        "`COLUNAS_MUNICIPAIS_DE_TENANT` (services/tenant_config.py) divergiu dos "
        "schemas dos dois endpoints municipais que escrevem em "
        "`aprimora_py.tenant`:\n"
        f"  só nos schemas : {sorted(dos_schemas - COLUNAS_MUNICIPAIS_DE_TENANT)}\n"
        f"  só na constante: {sorted(COLUNAS_MUNICIPAIS_DE_TENANT - dos_schemas)}\n\n"
        "Campo novo em `TenantInstitucionalUpdate`/`TenantNupConfigUpdate` tem de "
        "entrar em `_CAMPOS_INSTITUCIONAIS`/`_CAMPOS_NUP_FEDERAL` **e** virar "
        f"coluna nova no `GRANT UPDATE (...)` — migration {MIGRATION}."
    )

    no_banco = await _colunas_concedidas(admin_session)
    assert no_banco == COLUNAS_MUNICIPAIS_DE_TENANT, (
        "o `GRANT UPDATE (...)` em `aprimora_py.tenant` divergiu de "
        "`COLUNAS_MUNICIPAIS_DE_TENANT`:\n"
        f"  concedidas e não esperadas: {sorted(no_banco - COLUNAS_MUNICIPAIS_DE_TENANT)}\n"
        f"  esperadas e não concedidas: {sorted(COLUNAS_MUNICIPAIS_DE_TENANT - no_banco)}\n\n"
        "**Campo novo na whitelist exige coluna nova no grant, por migration "
        f"nova no modelo de {MIGRATION}.** Sem isso o endpoint municipal passa a "
        "devolver 500 com `permission denied for table tenant` assim que "
        "`APP_DATABASE_URL` estiver definida — e o rastro aponta para o service, "
        "onde não há defeito nenhum. Se a divergência for pelo outro lado "
        "(coluna concedida sem uso), tire-a do grant: privilégio sem caminho de "
        "escrita é exatamente o que este PR fecha.\n"
        "Se este banco não estiver em `head`, rode `alembic upgrade head` antes "
        "de ler a lista acima como defeito de código."
    )
    assert no_banco, (
        "nenhuma coluna concedida — verde vazio não prova nada. Ou a consulta da "
        "guarda quebrou, ou `aprimora_app` perdeu o `UPDATE` inteiro, o que "
        "derruba `PUT /api/v2/tenants/me` para todo município."
    )


async def test_o_update_de_tabela_inteira_nao_esta_mais_de_pe(
    admin_session: AsyncSession,
) -> None:
    """`role_table_grants` não pode mais mostrar `UPDATE` para `aprimora_app`.

    Privilégio de TABELA e de COLUNA são entradas de ACL **distintas** em
    Postgres, e a de tabela é a mais ampla. Um `GRANT UPDATE (col, ...)` aplicado
    sem o `REVOKE UPDATE ON <tabela>` deixa o antigo valendo: o
    `column_privileges` continuaria devolvendo as 24 colunas e a migration não
    teria feito nada. Este teste é a metade que o de divergência não cobre — ele
    mede a ACL de tabela, não a de coluna.

    Controle positivo embutido: `SELECT` continua de tabela inteira, o que prova
    que a consulta enxerga privilégios deste papel nesta tabela. Sem ele, um
    `WHERE` errado devolveria zero linhas e o teste passaria por engano.
    """
    privilegios = set(
        (
            await admin_session.execute(
                text(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    " WHERE table_schema = 'aprimora_py' AND table_name = 'tenant' "
                    "   AND grantee = 'aprimora_app'"
                )
            )
        ).scalars().all()
    )
    assert "SELECT" in privilegios, (
        "CONTROLE POSITIVO falhou: `aprimora_app` não tem nem `SELECT` de tabela "
        "em `aprimora_py.tenant`. Ou a consulta desta guarda está errada, ou o "
        "papel perdeu a leitura — e sem leitura o `TenantMiddleware` não resolve "
        "tenant nenhum."
    )
    assert "UPDATE" not in privilegios, (
        "`aprimora_app` ainda tem `UPDATE` de TABELA INTEIRA em "
        "`aprimora_py.tenant`. O `GRANT UPDATE (colunas)` NÃO substitui o de "
        "tabela — são ACLs distintas, e a de tabela vence. Falta o "
        f"`REVOKE UPDATE ON aprimora_py.tenant FROM aprimora_app` (ver {MIGRATION})."
    )


async def test_coluna_de_plataforma_nunca_entra_no_grant_municipal(
    admin_session: AsyncSession,
) -> None:
    """Denylist explícita — a guarda de divergência sozinha não basta.

    A comparação de conjuntos do primeiro teste é satisfeita ampliando os DOIS
    lados: quem quisesse dar `ativo` ao runtime municipal bastaria acrescentá-lo
    à constante do service e à migration, e tudo ficaria verde enquanto a
    propriedade central do PR morria. Aqui a lista de proibidas é escrita à mão,
    e alterá-la é uma edição que aparece na revisão.
    """
    concedidas = await _colunas_concedidas(admin_session)
    intrusas = sorted(concedidas & COLUNAS_DE_PLATAFORMA)
    assert not intrusas, (
        f"colunas de PLATAFORMA no grant do papel municipal: {intrusas}.\n\n"
        "`aprimora_py.tenant` não tem RLS: com `UPDATE` nessas colunas, um "
        "defeito de service ou uma injeção no runtime municipal eleva o próprio "
        "`plano`/`limite_*`, reativa um município suspenso ou **desativa outro "
        "município**. Quem edita essas colunas é `aprimora_platform`, por "
        "`PUT /api/v2/admin/tenants/{id}` e `POST .../ativar`.\n"
        "Se um caminho municipal legítimo passou a precisar de uma delas, isso é "
        "decisão de arquitetura — não relaxe esta lista sem registrar a razão."
    )


# ---------------------------------------------------------------------------
# 2. A propriedade medida no SQL, com controle positivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coluna", "sql_valor"),
    [
        ("ativo", "false"),
        ("plano", "'enterprise'"),
        ("slug", "'sequestrado'"),
        ("limite_usuarios", "999999"),
    ],
)
async def test_aprimora_app_nao_altera_coluna_de_plataforma(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
    coluna: str,
    sql_valor: str,
) -> None:
    """Quatro colunas, quatro ataques distintos — e um controle positivo antes.

    - `ativo = false` no próprio tenant: auto-suspensão (irrelevante) ou, com o
      `WHERE` errado, suspensão de outro município (ver o teste seguinte).
    - `plano = 'enterprise'` e `limite_usuarios`: entitlement comercial, o que a
      frase "cadastro institucional, não entitlement" da 0079 descrevia mal.
    - `slug`: o `TenantMiddleware` resolve o tenant pelo subdomínio contra esta
      coluna. Trocá-la sequestra o endereço de outro município.
    """
    tid_a, _tid_b = two_tenants
    marca = f"SEC00D{uuid.uuid4().hex[:2]}"

    engine, Session = _sessionmaker(APP_URL)
    try:
        # --- controle positivo: a MESMA sessão grava coluna institucional ---
        async with Session() as s:
            await s.execute(
                text("UPDATE aprimora_py.tenant SET sigla = :v WHERE id = :t"),
                {"v": marca, "t": tid_a},
            )
            await s.commit()

        confere = (
            await admin_session.execute(
                text("SELECT sigla FROM aprimora_py.tenant WHERE id = :t"),
                {"t": tid_a},
            )
        ).scalar_one()
        await admin_session.rollback()
        assert confere == marca, (
            "CONTROLE POSITIVO falhou: `aprimora_app` não consegue gravar `sigla` "
            "no próprio tenant. Sem esta metade, a negativa abaixo passaria verde "
            "num banco em que o papel perdeu a tabela inteira — e aí quem quebrou "
            "não foi o atacante, foi o PR: `PUT /api/v2/tenants/me` estaria fora "
            "do ar para todo município."
        )

        # --- a negativa ------------------------------------------------------
        antes = (
            await admin_session.execute(
                text(f"SELECT {coluna} FROM aprimora_py.tenant WHERE id = :t"),
                {"t": tid_a},
            )
        ).scalar_one()
        await admin_session.rollback()

        async with Session() as s:
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text(
                        f"UPDATE aprimora_py.tenant SET {coluna} = {sql_valor} "
                        " WHERE id = :t"
                    ),
                    {"t": tid_a},
                )
            await s.rollback()
    finally:
        await engine.dispose()

    assert _negou_a_tabela(str(exc.value).lower()), (
        f"esperava `permission denied for table tenant` ao gravar `{coluna}`; "
        f"recebi: {exc.value}\n\n"
        "A mensagem é conferida por extenso porque qualquer outra exceção (FK, "
        "CHECK, conexão caída) daria o mesmo `pytest.raises` verde sem provar "
        "que o grant por coluna está de pé."
    )

    depois = (
        await admin_session.execute(
            text(f"SELECT {coluna} FROM aprimora_py.tenant WHERE id = :t"),
            {"t": tid_a},
        )
    ).scalar_one()
    assert depois == antes, (
        f"`{coluna}` mudou de {antes!r} para {depois!r} — o UPDATE levantou "
        "exceção MAS gravou. Investigue antes de qualquer outra coisa."
    )


async def test_aprimora_app_nao_desativa_outro_municipio(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """O caso que dói: negação de serviço cross-tenant com um `UPDATE`.

    A tabela não tem RLS, então o `WHERE id = <outro>` não é filtrado por
    ninguém — a barreira de hoje é o `WHERE Tenant.id == tenant_id` escrito à
    mão dentro do service, que um defeito ou uma injeção contorna. Com o grant
    por coluna, o banco recusa antes de olhar o `WHERE`.

    Controle positivo: a mesma sessão altera `sigla` do MESMO tenant alheio e
    consegue. É deliberado que consiga — a 0080 fecha *coluna*, não *linha*; a
    fronteira por linha é o filtro do service, e é outro problema (item 1.0.8 do
    backlog). Sem esta metade, o verde abaixo poderia vir de a linha B não
    existir.
    """
    tid_a, tid_b = two_tenants
    engine, Session = _sessionmaker(APP_URL)
    try:
        async with Session() as s:
            await s.execute(
                text("UPDATE aprimora_py.tenant SET sigla = 'SEC00DB' WHERE id = :t"),
                {"t": tid_b},
            )
            await s.commit()

        alcancou = (
            await admin_session.execute(
                text("SELECT sigla FROM aprimora_py.tenant WHERE id = :t"),
                {"t": tid_b},
            )
        ).scalar_one()
        await admin_session.rollback()
        assert alcancou == "SEC00DB", (
            "CONTROLE POSITIVO falhou: a sessão do tenant A nem alcança a LINHA "
            "do tenant B. Então a negativa abaixo não prova nada sobre coluna — "
            "prova que a linha sumiu ou que o papel perdeu a tabela."
        )

        async with Session() as s:
            with pytest.raises((ProgrammingError, DBAPIError)) as exc:
                await s.execute(
                    text("UPDATE aprimora_py.tenant SET ativo = false WHERE id = :t"),
                    {"t": tid_b},
                )
            await s.rollback()
    finally:
        await engine.dispose()

    assert _negou_a_tabela(str(exc.value).lower()), (
        f"esperava `permission denied for table tenant`; recebi: {exc.value}"
    )

    ainda_ativo = (
        await admin_session.execute(
            text("SELECT ativo FROM aprimora_py.tenant WHERE id = :t"), {"t": tid_b}
        )
    ).scalar_one()
    assert ainda_ativo is True, (
        "o município B foi DESATIVADO pelo runtime municipal do tenant A. O "
        "UPDATE levantou exceção MAS gravou — pare tudo e investigue."
    )


# ---------------------------------------------------------------------------
# 3. O que a 0080 deliberadamente NÃO tira
# ---------------------------------------------------------------------------


async def test_aprimora_app_continua_configurando_nup_federal(
    admin_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """`codigo_orgao_nup` e `usar_nup_federal` FICAM no grant municipal.

    São o segundo caminho de escrita municipal em `aprimora_py.tenant`
    (`routers/tenant.py::update_nup_config`, por `PUT /tenants/me/nup-config`) e
    **não passam pela whitelist de `tenant_config`** — quem derivasse a lista de
    colunas só de `_CAMPOS_INSTITUCIONAIS` deixaria esse endpoint devolvendo 500
    no dia do `SEC-RLS-ROLLOUT`.

    Este teste existe para reprovar o estreitamento "por garantia" que alguém
    tentaria depois: sem ele, tirar essas duas colunas passaria em todo o resto
    do arquivo e só apareceria em produção.
    """
    tid_a, _ = two_tenants
    engine, Session = _sessionmaker(APP_URL)
    try:
        async with Session() as s:
            await s.execute(
                text(
                    "UPDATE aprimora_py.tenant "
                    "   SET codigo_orgao_nup = '54321', usar_nup_federal = true "
                    " WHERE id = :t"
                ),
                {"t": tid_a},
            )
            await s.commit()
    finally:
        await engine.dispose()

    codigo, flag = (
        await admin_session.execute(
            text(
                "SELECT codigo_orgao_nup, usar_nup_federal "
                "  FROM aprimora_py.tenant WHERE id = :t"
            ),
            {"t": tid_a},
        )
    ).one()
    assert (codigo, flag) == ("54321", True), (
        "`aprimora_app` não consegue gravar a configuração de NUP federal. "
        "`PUT /api/v2/tenants/me/nup-config` está fora do ar — acrescente "
        f"`codigo_orgao_nup` e `usar_nup_federal` ao grant da {MIGRATION}."
    )


async def test_aprimora_platform_mantem_update_de_tabela_inteira(
    admin_session: AsyncSession,
    platform_session: AsyncSession,
    two_tenants: tuple[int, int],
) -> None:
    """O papel de plataforma continua ativando e desativando município.

    A 0080 estreita só `aprimora_app`. Se alguém "padronizasse" o grant por
    coluna para `aprimora_platform` também, `POST /admin/tenants/{id}/desativar`
    e `python -m app.cli.tenant deactivate` parariam — e nenhum outro teste deste
    arquivo notaria, porque todos medem o papel municipal.
    """
    tid_a, _ = two_tenants
    await platform_session.execute(
        text(
            "UPDATE aprimora_py.tenant SET ativo = false, plano = 'enterprise' "
            " WHERE id = :t"
        ),
        {"t": tid_a},
    )
    await platform_session.commit()

    ativo, plano = (
        await admin_session.execute(
            text("SELECT ativo, plano FROM aprimora_py.tenant WHERE id = :t"),
            {"t": tid_a},
        )
    ).one()
    assert (ativo, plano) == (False, "enterprise"), (
        "`aprimora_platform` perdeu o `UPDATE` em colunas de plataforma. "
        "Suspender município e mudar plano são operações DELE — a 0080 estreita "
        "apenas `aprimora_app`."
    )
