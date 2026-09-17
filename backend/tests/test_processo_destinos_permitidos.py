"""Destinos permitidos no encaminhamento (fatia F3, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.
Spec: `docs/superpowers/specs/2026-08-28-reuniao-as-is-to-be-design.md` §7.2.

O que cada grupo de testes existe para pegar
--------------------------------------------
**A invariante que importa mais que qualquer caso isolado**: o conjunto que
`destinos_permitidos` devolve como "permitido" e o veredito que
`validar_acao_strict(acao="encaminhar")` dá para CADA unidade daquele
conjunto (e de fora dele) têm de concordar. As duas funções foram escritas
pra compartilhar a mesma leitura do DSL (`_instance_strict_ativa`) — um teste
que só checasse `destinos_permitidos` isoladamente não pegaria as duas
divergindo se alguém editar uma sem lembrar da outra, e é exatamente essa
divergência que reintroduziria o defeito original: o combo oferece uma
unidade que o `encaminhar` real recusa.

**Usuário comum.** O bypass de SU em `auth/perms.py` retorna antes de olhar
`action` — mesmo motivo do `test_processo_responsavel.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
    WorkflowDefinition,
    WorkflowInstance,
)
from app.services.acoes_processo import _get_processo
from app.services.workflow_integration import (
    destinos_permitidos,
    validar_acao_strict,
)
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cria_usuario_comum(session, tenant_id: int, *, unidade_id: int) -> int:
    """Cópia do helper de `test_processo_responsavel.py` — mesma razão lá."""
    sistema_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
            ),
            {"app": APP},
        )
    ).scalar_one()
    nivel_id = (
        await session.execute(
            text("SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1")
        )
    ).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (
            await session.execute(
                text(
                    "INSERT INTO utils.nivel (nivel, valor, excluido) "
                    "VALUES ('Operacional', 1, false) RETURNING id"
                )
            )
        ).scalar_one()
    transacao_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.transacao WHERE codigo = 'processo' "
                "AND excluido = false LIMIT 1"
            )
        )
    ).scalar_one()
    uid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo,
                                   id_unidade_trabalho)
        VALUES (:t, 'Operador', :email, '', :cpf, true, false, :app,
                'ultrassecreto', :u)
        RETURNING id
    """
            ),
            {
                "t": tenant_id,
                "email": f"op-{uuid.uuid4().hex[:8]}@f3.test",
                "cpf": uuid.uuid4().hex[:11],
                "app": APP,
                "u": unidade_id,
            },
        )
    ).scalar_one()
    gid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo F3', false) RETURNING id
    """
            ),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id},
        )
    ).scalar_one()
    await session.execute(
        text(
            """
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """
        ),
        {"t": tenant_id, "u": uid, "g": gid, "app": APP},
    )
    await session.execute(
        text(
            """
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """
        ),
        {"t": tenant_id, "g": gid, "tr": transacao_id},
    )
    return uid


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Tenant com unidades A (origem), B e C (destinos possíveis), um processo."""
    slug = _slug("f3-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F3",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )

    async with _sm(admin_engine)() as s:
        tipo_unidade = (
            await s.execute(
                text(
                    "SELECT id_tipo_unidade_trabalho FROM utils.unidade_trabalho "
                    "WHERE tenant_id=:t ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        id_tipo_manif = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()

        def _un(nome: str) -> UnidadeTrabalho:
            return UnidadeTrabalho(
                tenant_id=tenant.id,
                unidade_trabalho=nome,
                id_tipo_unidade_trabalho=tipo_unidade,
                excluido=False,
            )

        a, b, c = _un("A"), _un("B"), _un("C")
        s.add_all([a, b, c])
        await s.flush()

        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral", exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manif, nome="Maria",
            ativo=True, excluido=False,
        )
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        operador = await _cria_usuario_comum(s, tenant.id, unidade_id=a.id)

        p = Processo(
            tenant_id=tenant.id,
            id_assunto=assunto.id,
            virtual=True,
            data_hora_abertura=datetime.now(),
            numero_processo=f"{slug}-p1",
            id_unidade_proprietaria=a.id,
            id_manifestante=manif.id,
            id_local_atual=a.id,
            nivel_sigilo="ostensivo",
            ativo=True,
            excluido=False,
        )
        s.add(p)
        await s.flush()
        await s.commit()

        dados = {
            "tenant": tenant,
            "unidades": {"a": a.id, "b": b.id, "c": c.id},
            "operador": operador,
            "processo_id": p.id,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.workflow_transicao_log WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.workflow_instance WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.workflow_definition WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": dados["tenant"].id})
        await s.commit()


async def _workflow(
    session,
    tenant_id: int,
    processo_id: int,
    *,
    strict: bool,
    estados: list[dict[str, Any]],
    transicoes: list[dict[str, Any]],
    estado_atual: str,
) -> WorkflowInstance:
    wf = WorkflowDefinition(
        tenant_id=tenant_id,
        slug=f"wf-{uuid.uuid4().hex[:8]}",
        nome="Teste F3",
        versao=1,
        ativo=True,
        dsl={"strict": strict, "estados": estados, "transicoes": transicoes},
        criado_em=datetime.now(),
    )
    session.add(wf)
    await session.flush()
    inst = WorkflowInstance(
        tenant_id=tenant_id,
        id_workflow_definition=wf.id,
        id_processo=processo_id,
        entidade_tipo="processo",
        entidade_id=processo_id,
        estado_atual=estado_atual,
        ativa=True,
        iniciada_em=datetime.now(),
    )
    session.add(inst)
    await session.flush()
    return inst


# ---------------------------------------------------------------------------
# `destinos_permitidos` isolado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_instance_ativa_libera_tudo(admin_engine, cen):
    """Sem workflow, o comportamento é o de hoje: sem restrição."""
    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ids, motivo = await destinos_permitidos(s, processo)
    assert ids is None
    assert motivo is None


@pytest.mark.asyncio
async def test_workflow_nao_strict_libera_tudo(admin_engine, cen):
    async with _sm(admin_engine)() as s:
        await _workflow(
            s, cen["tenant"].id, cen["processo_id"],
            strict=False,
            estados=[{"slug": "aberto"}, {"slug": "em_b", "id_unidade_responsavel": cen["unidades"]["b"]}],
            transicoes=[{"de": "aberto", "para": "em_b", "evento": "manual"}],
            estado_atual="aberto",
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ids, motivo = await destinos_permitidos(s, processo)
    assert ids is None
    assert motivo is None


@pytest.mark.asyncio
async def test_transicao_sem_unidade_fixa_libera_tudo(admin_engine, cen):
    """Estado destino sem `id_unidade_responsavel` é "livre" — nenhuma restrição."""
    async with _sm(admin_engine)() as s:
        await _workflow(
            s, cen["tenant"].id, cen["processo_id"],
            strict=True,
            estados=[{"slug": "aberto"}, {"slug": "em_qualquer"}],
            transicoes=[{"de": "aberto", "para": "em_qualquer", "evento": "manual"}],
            estado_atual="aberto",
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ids, motivo = await destinos_permitidos(s, processo)
    assert ids is None
    assert motivo is None


@pytest.mark.asyncio
async def test_restringe_ao_conjunto_das_transicoes_candidatas(admin_engine, cen):
    b, c = cen["unidades"]["b"], cen["unidades"]["c"]
    async with _sm(admin_engine)() as s:
        await _workflow(
            s, cen["tenant"].id, cen["processo_id"],
            strict=True,
            estados=[
                {"slug": "aberto"},
                {"slug": "em_b", "id_unidade_responsavel": b},
                {"slug": "em_c", "id_unidade_responsavel": c},
            ],
            transicoes=[
                {"de": "aberto", "para": "em_b", "evento": "manual"},
                {"de": "aberto", "para": "em_c", "evento": "encaminhamento"},
            ],
            estado_atual="aberto",
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ids, motivo = await destinos_permitidos(s, processo)
    assert ids == sorted([b, c])
    assert motivo is not None

    # A invariante: o que este endpoint promete bate com o que `encaminhar`
    # de fato aceita — para cada id no conjunto, e para um de fora dele.
    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ok_b, _ = await validar_acao_strict(
            s, processo, acao="encaminhar", id_unidade_destino=b
        )
        ok_c, _ = await validar_acao_strict(
            s, processo, acao="encaminhar", id_unidade_destino=c
        )
        ok_a, _ = await validar_acao_strict(
            s, processo, acao="encaminhar", id_unidade_destino=cen["unidades"]["a"]
        )
    assert ok_b is True
    assert ok_c is True
    assert ok_a is False


@pytest.mark.asyncio
async def test_estado_sem_transicao_manual_nao_permite_nada(admin_engine, cen):
    """Sem candidata alguma, a lista é VAZIA — não "tudo liberado".

    Essa distinção é a correção do defeito original: devolver `None` aqui
    faria a tela oferecer todas as unidades de novo, e `encaminhar` recusaria
    qualquer uma delas — exatamente o "escolhe e é barrado depois".
    """
    async with _sm(admin_engine)() as s:
        await _workflow(
            s, cen["tenant"].id, cen["processo_id"],
            strict=True,
            estados=[{"slug": "finalizado", "final": True}],
            transicoes=[],
            estado_atual="finalizado",
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        processo = await _get_processo(s, cen["processo_id"], cen["tenant"].id)
        ids, motivo = await destinos_permitidos(s, processo)
    assert ids == []
    assert motivo is not None


# ---------------------------------------------------------------------------
# HTTP, usuário comum
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_usuario_comum_ve_lista_restrita(admin_engine, cen):
    b, c = cen["unidades"]["b"], cen["unidades"]["c"]
    async with _sm(admin_engine)() as s:
        await _workflow(
            s, cen["tenant"].id, cen["processo_id"],
            strict=True,
            estados=[
                {"slug": "aberto"},
                {"slug": "em_b", "id_unidade_responsavel": b},
            ],
            transicoes=[{"de": "aberto", "para": "em_b", "evento": "manual"}],
            estado_atual="aberto",
        )
        await s.commit()

    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == cen["operador"]))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            f"/api/v2/processos/{cen['processo_id']}/destinos-permitidos"
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["restrito"] is True
        assert body["ids_unidade"] == [b]
        assert body["motivo"]


@pytest.mark.asyncio
async def test_http_usuario_comum_sem_workflow_ve_lista_livre(admin_engine, cen):
    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == cen["operador"]))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            f"/api/v2/processos/{cen['processo_id']}/destinos-permitidos"
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["restrito"] is False
        assert body["ids_unidade"] is None
