"""Apensamento de processos — validação anti-ciclo (Fase P6).

Cobre cenários críticos do service:
- Apensar A em B funciona e denormaliza ``id_processo_pai``.
- Bloqueios: self-apensar, filho já apensado, processo inativo/inexistente.
- Ciclos: direto (A→B, depois B→A) e indireto (A→B→C, depois C→A).
- Desapensar libera o filho para novo vínculo.

Usa ``admin_engine`` (ged_user, BYPASSRLS) — RLS já foi coberto em
``test_rls_isolation.py``. Foco aqui é a lógica recursiva.

A fixture cria toda a hierarquia de catálogos do zero (categoria,
tipo_manifestante, manifestante, tipo_processo, assunto, unidade,
usuário) para não depender de seed externo — assim roda em CI contra
Postgres limpo.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Processo
from app.services.apensamento import ApensamentoError, apensar, desapensar


async def _setup_catalogs(
    s: AsyncSession, tenant_id: int
) -> dict[str, int]:
    """Cria FKs mínimas para abrir processo. Retorna ids."""
    suffix = uuid.uuid4().hex[:8]

    categoria_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) "
                    "VALUES (:nome, 'PF', true, false) RETURNING id"
                ),
                {"nome": f"Test {suffix}"},
            )
        ).scalar_one()
    )

    tipo_manif_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO protocolos.tipo_manifestante "
                    "(tenant_id, tipo_manifestante, id_categoria, ativo, excluido) "
                    "VALUES (:tid, :nome, :cat, true, false) RETURNING id"
                ),
                {"tid": tenant_id, "nome": f"Test {suffix}", "cat": categoria_id},
            )
        ).scalar_one()
    )

    manifestante_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO protocolos.manifestante "
                    "(tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
                    "VALUES (:tid, :tm, :nome, true, false) RETURNING id"
                ),
                {"tid": tenant_id, "tm": tipo_manif_id, "nome": f"Bot {suffix}"},
            )
        ).scalar_one()
    )

    unidade_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO utils.unidade_trabalho "
                    "(tenant_id, unidade_trabalho, excluido) "
                    "VALUES (:tid, :nome, false) RETURNING id"
                ),
                {"tid": tenant_id, "nome": f"Unidade {suffix}"},
            )
        ).scalar_one()
    )

    tipo_proc_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO protocolos.tipo_processo "
                    "(tenant_id, tipo_processo, ativo, excluido) "
                    "VALUES (:tid, :nome, true, false) RETURNING id"
                ),
                {"tid": tenant_id, "nome": f"Tipo {suffix}"},
            )
        ).scalar_one()
    )

    assunto_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO protocolos.assunto "
                    "(tenant_id, assunto, id_tipo_processo, ativo, excluido) "
                    "VALUES (:tid, :nome, :tp, true, false) RETURNING id"
                ),
                {"tid": tenant_id, "nome": f"Assunto {suffix}", "tp": tipo_proc_id},
            )
        ).scalar_one()
    )

    usuario_id = int(
        (
            await s.execute(
                text(
                    "INSERT INTO utils.usuario "
                    "(tenant_id, nome, email, senha, cpf, ativo, excluido) "
                    "VALUES (:tid, :nome, :email, 'x', :cpf, true, false) "
                    "RETURNING id"
                ),
                {
                    "tid": tenant_id,
                    "nome": f"Test {suffix}",
                    "email": f"{suffix}@test.local",
                    "cpf": uuid.uuid4().hex[:11],
                },
            )
        ).scalar_one()
    )

    return {
        "categoria": categoria_id,
        "tipo_manifestante": tipo_manif_id,
        "manifestante": manifestante_id,
        "unidade": unidade_id,
        "tipo_processo": tipo_proc_id,
        "assunto": assunto_id,
        "usuario": usuario_id,
    }


async def _cleanup_catalogs(
    s: AsyncSession, tenant_id: int, ids: dict[str, int]
) -> None:
    """Limpa catálogos criados por _setup_catalogs em ordem reversa de FK."""
    await s.execute(
        text("DELETE FROM utils.usuario WHERE id = :id"), {"id": ids["usuario"]}
    )
    await s.execute(
        text("DELETE FROM protocolos.assunto WHERE id = :id"),
        {"id": ids["assunto"]},
    )
    await s.execute(
        text("DELETE FROM protocolos.tipo_processo WHERE id = :id"),
        {"id": ids["tipo_processo"]},
    )
    await s.execute(
        text("DELETE FROM utils.unidade_trabalho WHERE id = :id"),
        {"id": ids["unidade"]},
    )
    await s.execute(
        text("DELETE FROM protocolos.manifestante WHERE id = :id"),
        {"id": ids["manifestante"]},
    )
    await s.execute(
        text("DELETE FROM protocolos.tipo_manifestante WHERE id = :id"),
        {"id": ids["tipo_manifestante"]},
    )
    await s.execute(
        text("DELETE FROM protocolos.categoria WHERE id = :id"),
        {"id": ids["categoria"]},
    )


@pytest_asyncio.fixture
async def processos_apensaveis(admin_engine, two_tenants):
    """Cria tudo do zero num tenant temp: catálogos + 3 processos.

    Retorna dict ``{tenant_id, usuario_id, processos: [id1, id2, id3]}``.
    """
    tid_a, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    processo_ids: list[int] = []
    async with Session() as s:
        cat = await _setup_catalogs(s, tid_a)
        for _ in range(3):
            res = await s.execute(
                text(
                    """
                    INSERT INTO protocolos.processo
                        (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                         virtual, publico, externo, ativo, excluido, migrado)
                    VALUES
                        (:tid, :assunto, :manif, :unid,
                         true, true, false, true, false, false)
                    RETURNING id
                    """
                ),
                {
                    "tid": tid_a,
                    "assunto": cat["assunto"],
                    "manif": cat["manifestante"],
                    "unid": cat["unidade"],
                },
            )
            processo_ids.append(int(res.scalar_one()))
        await s.commit()

    yield {
        "tenant_id": tid_a,
        "usuario_id": cat["usuario"],
        "processos": processo_ids,
    }

    # Teardown: dependências de processo primeiro, depois processos,
    # depois catálogos. two_tenants cuida do tenant.
    async with Session() as s:
        await s.execute(
            text(
                "DELETE FROM aprimora_py.audit_log "
                "WHERE entidade = 'processo' AND id_entidade = ANY(:ids)"
            ),
            {"ids": processo_ids},
        )
        await s.execute(
            text(
                "DELETE FROM protocolos.processo_apensamento "
                "WHERE id_processo_apensado = ANY(:ids) "
                "   OR id_processo_principal = ANY(:ids)"
            ),
            {"ids": processo_ids},
        )
        await s.execute(
            text(
                "UPDATE protocolos.processo SET id_processo_pai = NULL "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": processo_ids},
        )
        await s.execute(
            text("DELETE FROM protocolos.processo WHERE id = ANY(:ids)"),
            {"ids": processo_ids},
        )
        await _cleanup_catalogs(s, tid_a, cat)
        await s.commit()


async def _session(admin_engine, tenant_id: int) -> AsyncSession:
    """Cria session pronta pra uso pelo service (com tenant_id no info)."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    session.info["tenant_id"] = tenant_id
    return session


async def _id_processo_pai(session: AsyncSession, processo_id: int) -> int | None:
    res = await session.execute(
        select(Processo.id_processo_pai).where(Processo.id == processo_id)
    )
    return res.scalar_one_or_none()


# -------- happy path --------


async def test_apensar_denormaliza_id_processo_pai(
    admin_engine, processos_apensaveis
):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, b, _c = processos_apensaveis["processos"]
    async with await _session(admin_engine, tid) as s:
        result = await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="smoke",
        )
        assert result.id_processo_apensado == a
        assert result.id_processo_principal == b
        assert result.desapensado_em is None

    # Confirma denormalização: a.id_processo_pai == b
    async with await _session(admin_engine, tid) as s:
        assert await _id_processo_pai(s, a) == b


# -------- bloqueios diretos --------


async def test_apensar_em_si_mesmo_bloqueado(admin_engine, processos_apensaveis):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, _b, _c = processos_apensaveis["processos"]
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="apensado a si mesmo"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=a,
                id_processo_principal=a,
                motivo="x",
            )


async def test_apensar_filho_ja_apensado_bloqueado(
    admin_engine, processos_apensaveis
):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, b, c = processos_apensaveis["processos"]
    # Setup: A→B
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="first",
        )

    # Tentar A→C: A já tem parent → erro
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="já está apensado"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=a,
                id_processo_principal=c,
                motivo="second",
            )


async def test_apensar_processo_inexistente_bloqueado(
    admin_engine, processos_apensaveis
):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, _b, _c = processos_apensaveis["processos"]
    INEXISTENTE = 999_999_999
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="não encontrado"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=INEXISTENTE,
                id_processo_principal=a,
                motivo="x",
            )


# -------- ciclos --------


async def test_ciclo_direto_bloqueado(admin_engine, processos_apensaveis):
    """A→B; depois B→A deve falhar (B é descendente de A na cadeia A→B,
    então tornar B filho de A criaria ciclo)."""
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, b, _c = processos_apensaveis["processos"]
    # Setup: A→B (A vira filho, B vira pai)
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="step1",
        )

    # Tentar B→A: B é o root, mas A é descendente dele (não, A é filho dele)
    # filho=B, pai=A. Walk: cur=A. visitados={A}. A==B? não. Sobe A.parent=B.
    # cur=B. B==filho(B)? sim → ciclo
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="ciclo"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=b,
                id_processo_principal=a,
                motivo="step2",
            )


async def test_ciclo_indireto_bloqueado(admin_engine, processos_apensaveis):
    """A→B (B é pai de A); C→A (A é pai de C → cadeia C→A→B); depois B→C
    fecha o ciclo: walk de C→A→B encontra filho B → erro."""
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, b, c = processos_apensaveis["processos"]

    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="A em B",
        )
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=c,
            id_processo_principal=a,
            motivo="C em A",
        )

    # Agora tentar B em C — B.parent é None, OK. Walk a partir de C:
    # cur=C → visitados {C}, !=B. Sobe C.parent=A → cur=A, !=B. Sobe A.parent=B
    # → cur=B == filho(B) → ciclo.
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="ciclo"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=b,
                id_processo_principal=c,
                motivo="B em C",
            )


# -------- desapensar --------


async def test_desapensar_libera_novo_vinculo(admin_engine, processos_apensaveis):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, b, c = processos_apensaveis["processos"]
    # A→B
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="first",
        )

    # Desapensar A
    async with await _session(admin_engine, tid) as s:
        apens = await desapensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            motivo="desfazer",
        )
        assert apens.desapensado_em is not None
        assert apens.motivo_desapensamento == "desfazer"

    # Pointer limpou
    async with await _session(admin_engine, tid) as s:
        assert await _id_processo_pai(s, a) is None

    # Agora A→C funciona
    async with await _session(admin_engine, tid) as s:
        result = await apensar(
            s,
            tenant_id=tid,
            usuario_id=uid,
            id_processo_apensado=a,
            id_processo_principal=c,
            motivo="second",
        )
        assert result.id_processo_principal == c


async def test_desapensar_processo_sem_vinculo_bloqueado(
    admin_engine, processos_apensaveis
):
    tid = processos_apensaveis["tenant_id"]
    uid = processos_apensaveis["usuario_id"]
    a, _b, _c = processos_apensaveis["processos"]
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="não está apensado"):
            await desapensar(
                s,
                tenant_id=tid,
                usuario_id=uid,
                id_processo_apensado=a,
                motivo="x",
            )
