"""Diagnóstico de permissões (item 1.0.7) — CLI de leitura.

Por que uma CLI de diagnóstico merece teste: ela é feita para ser rodada
**no dia em que algo já está errado**, por alguém sob pressão. Uma que estoura
com `UndefinedColumnError` nesse momento é pior do que não existir — some a
informação e some a confiança na ferramenta. Escrevendo esta CLI eu errei duas
colunas (`aprimora_py.tenant.excluido`, que não existe) e só descobri rodando;
estes testes fixam o contrato com o schema real.

O outro risco que eles cobrem é o oposto do falso alarme: um diagnóstico que
**nunca acusa nada** parece tranquilizador e não é. Por isso todo teste de
"não acusou" vem em par com um de "acusou quando devia".
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.diagnostico_permissoes import TRANSACOES_0074, diagnosticar
from app.config import get_settings
from app.services.provisioning_tenant import provisionar_tenant

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def tenant_com_grupos(admin_engine):
    """Tenant com um grupo SU e um grupo não-SU sem nenhuma das 9."""
    slug = f"diag-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Diag", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )

    async with _sm(admin_engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app = :a AND excluido = false LIMIT 1"
        ), {"a": APP})).scalar_one())
        # get-or-create do nível operacional: o bootstrap garante SÓ o valor 0.
        # Assumir que o nível 1 existe foi exatamente a causa do item 1.0.65 —
        # passava aqui por herança do legado e estourava em banco limpo.
        nivel_op = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_op is None:
            nivel_op = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"
            ))).scalar_one()
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, 'Operacional Diag', false) RETURNING id
        """), {"t": tenant.id, "n": nivel_op, "s": sistema_id})).scalar_one())
        await s.commit()

    yield {"tenant": tenant, "slug": slug, "grupo_nao_su": gid}

    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant.id})
        await s.commit()


@pytest.mark.asyncio
async def test_a_cli_roda_contra_o_schema_real(tenant_com_grupos, capsys) -> None:
    """Contrato com o schema. Este teste existe porque a primeira versão
    estourava em `aprimora_py.tenant.excluido` — coluna que não existe."""
    codigo = await diagnosticar(tenant_com_grupos["slug"])
    assert codigo == 0
    saida = capsys.readouterr().out
    assert "Diagnóstico de permissões por grupo" in saida
    assert tenant_com_grupos["slug"] in saida


@pytest.mark.asyncio
async def test_acusa_grupo_nao_su_sem_as_9(tenant_com_grupos, capsys) -> None:
    """O caso que o item 1.0.7 descreve."""
    await diagnosticar(tenant_com_grupos["slug"])
    saida = capsys.readouterr().out
    assert "Operacional Diag" in saida
    assert "NÃO-SU" in saida
    assert "Faltam 9 das 9" in saida
    for codigo in TRANSACOES_0074:
        assert codigo in saida


@pytest.mark.asyncio
async def test_para_de_acusar_quando_as_9_sao_concedidas(
    admin_engine, tenant_com_grupos, capsys
) -> None:
    """Controle contra alarme permanente.

    Sem este par, o teste acima passaria com um diagnóstico que imprime
    "Faltam 9 das 9" incondicionalmente — e um aviso que nunca some é
    indistinguível de ruído: em pouco tempo ninguém lê.
    """
    async with _sm(admin_engine)() as s:
        for codigo in TRANSACOES_0074:
            tid = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo = :c "
                "AND excluido = false LIMIT 1"
            ), {"c": codigo})).scalar_one_or_none()
            if tid is None:
                pytest.skip(f"transação '{codigo}' não existe neste catálogo")
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar,
                     excluir, excluido)
                VALUES (:t, :g, :tr, false, false, false, false)
            """), {
                "t": tenant_com_grupos["tenant"].id,
                "g": tenant_com_grupos["grupo_nao_su"],
                "tr": tid,
            })
        await s.commit()

    await diagnosticar(tenant_com_grupos["slug"])
    saida = capsys.readouterr().out
    assert "tem as 9 da 0074" in saida
    assert "Faltam" not in saida


@pytest.mark.asyncio
async def test_super_usuario_nao_e_acusado(tenant_com_grupos, capsys) -> None:
    """SU passa por `sistema_transacao`, não por `grupo_transacao`.

    Acusar o grupo de administradores de "faltam 9 transações" seria falso
    alarme na linha mais visível do relatório — e é o erro fácil de cometer,
    porque a query de `grupo_transacao` de fato não devolve nada para ele.
    """
    await diagnosticar(tenant_com_grupos["slug"])
    saida = capsys.readouterr().out
    linhas_su = [ln for ln in saida.splitlines() if "SUPER-USUÁRIO" in ln]
    assert linhas_su, "nenhum grupo SU no relatório — o tenant deveria ter um"
    for ln in linhas_su:
        assert "Faltam" not in ln


@pytest.mark.asyncio
async def test_tenant_inexistente_falha_alto(capsys) -> None:
    """Slug errado tem de gritar, não devolver relatório vazio.

    Um relatório vazio para um slug digitado errado lê-se como "está tudo
    certo" — a pior resposta possível para uma ferramenta de diagnóstico.
    """
    with pytest.raises(SystemExit) as exc:
        await diagnosticar(f"nao-existe-{uuid.uuid4().hex[:8]}")
    assert exc.value.code == 2
