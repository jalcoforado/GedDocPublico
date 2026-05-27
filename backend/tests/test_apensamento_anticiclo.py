"""Apensamento de processos — validação anti-ciclo (Fase P6).

Cobre cenários críticos do service:
- Apensar A em B funciona e denormaliza ``id_processo_pai``.
- Bloqueios: self-apensar, filho já apensado, processo inativo/inexistente.
- Ciclos: direto (A→B, depois B→A) e indireto (A→B→C, depois C→A).
- Desapensar libera o filho para novo vínculo.

Usa ``admin_engine`` (ged_user, BYPASSRLS) — RLS já foi coberto em
``test_rls_isolation.py``. Foco aqui é a lógica recursiva.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Processo
from app.services.apensamento import ApensamentoError, apensar, desapensar


# Catálogos de seed do tenant Sobral (id=1) — confirmados no smoke.
TENANT_SOBRAL = 1
ID_ASSUNTO = 1
ID_MANIFESTANTE = 1
ID_UNIDADE = 3
ID_USUARIO_ADMIN = 2  # admin@local.test


@pytest_asyncio.fixture
async def processos_apensaveis(admin_engine):
    """Cria 3 processos temporários no tenant Sobral apontando para FKs de
    seed. Retorna ``(tenant_id, [id_p1, id_p2, id_p3])`` e limpa no teardown.

    Insere SQL direto pra não precisar setup de Acao/Movimentacao do fluxo
    completo de abertura. O service de apensamento só lê ``Processo``.
    """
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    created_ids: list[int] = []
    async with Session() as s:
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
                    "tid": TENANT_SOBRAL,
                    "assunto": ID_ASSUNTO,
                    "manif": ID_MANIFESTANTE,
                    "unid": ID_UNIDADE,
                },
            )
            created_ids.append(int(res.scalar_one()))
        await s.commit()

    yield (TENANT_SOBRAL, created_ids)

    # Teardown: limpa audit + apensamentos + processos (ordem importa por FK).
    async with Session() as s:
        await s.execute(
            text(
                "DELETE FROM aprimora_py.audit_log "
                "WHERE entidade = 'processo' AND id_entidade = ANY(:ids)"
            ),
            {"ids": created_ids},
        )
        await s.execute(
            text(
                "DELETE FROM protocolos.processo_apensamento "
                "WHERE id_processo_apensado = ANY(:ids) "
                "   OR id_processo_principal = ANY(:ids)"
            ),
            {"ids": created_ids},
        )
        # Limpa id_processo_pai antes do delete (auto-ref FK)
        await s.execute(
            text(
                "UPDATE protocolos.processo SET id_processo_pai = NULL "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": created_ids},
        )
        await s.execute(
            text("DELETE FROM protocolos.processo WHERE id = ANY(:ids)"),
            {"ids": created_ids},
        )
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
    tid, [a, b, _c] = processos_apensaveis
    async with await _session(admin_engine, tid) as s:
        result = await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
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
    tid, [a, _b, _c] = processos_apensaveis
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="apensado a si mesmo"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=a,
                id_processo_principal=a,
                motivo="x",
            )


async def test_apensar_filho_ja_apensado_bloqueado(
    admin_engine, processos_apensaveis
):
    tid, [a, b, c] = processos_apensaveis
    # Setup: A→B
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
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
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=a,
                id_processo_principal=c,
                motivo="second",
            )


async def test_apensar_processo_inexistente_bloqueado(
    admin_engine, processos_apensaveis
):
    tid, [a, _b, _c] = processos_apensaveis
    INEXISTENTE = 999_999_999
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="não encontrado"):
            await apensar(
                s,
                tenant_id=tid,
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=INEXISTENTE,
                id_processo_principal=a,
                motivo="x",
            )


# -------- ciclos --------


async def test_ciclo_direto_bloqueado(admin_engine, processos_apensaveis):
    """A→B; depois B→A deve falhar (B é descendente de A na cadeia A→B,
    então tornar B filho de A criaria ciclo)."""
    tid, [a, b, _c] = processos_apensaveis
    # Setup: A→B (A vira filho, B vira pai)
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
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
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=b,
                id_processo_principal=a,
                motivo="step2",
            )


async def test_ciclo_indireto_bloqueado(admin_engine, processos_apensaveis):
    """A→B (B é pai de A); C→A (A é pai de C → cadeia C→A→B); depois B→C
    fecha o ciclo: walk de C→A→B encontra filho B → erro."""
    tid, [a, b, c] = processos_apensaveis

    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="A em B",
        )
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
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
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=b,
                id_processo_principal=c,
                motivo="B em C",
            )


# -------- desapensar --------


async def test_desapensar_libera_novo_vinculo(admin_engine, processos_apensaveis):
    tid, [a, b, c] = processos_apensaveis
    # A→B
    async with await _session(admin_engine, tid) as s:
        await apensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
            id_processo_apensado=a,
            id_processo_principal=b,
            motivo="first",
        )

    # Desapensar A
    async with await _session(admin_engine, tid) as s:
        apens = await desapensar(
            s,
            tenant_id=tid,
            usuario_id=ID_USUARIO_ADMIN,
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
            usuario_id=ID_USUARIO_ADMIN,
            id_processo_apensado=a,
            id_processo_principal=c,
            motivo="second",
        )
        assert result.id_processo_principal == c


async def test_desapensar_processo_sem_vinculo_bloqueado(
    admin_engine, processos_apensaveis
):
    tid, [a, _b, _c] = processos_apensaveis
    async with await _session(admin_engine, tid) as s:
        with pytest.raises(ApensamentoError, match="não está apensado"):
            await desapensar(
                s,
                tenant_id=tid,
                usuario_id=ID_USUARIO_ADMIN,
                id_processo_apensado=a,
                motivo="x",
            )
