"""Assinatura — registro em audit_log (PR1).

Verifica que os três eventos principais geram entrada de auditoria:
- assinatura.solicitada (solicitar_assinatura)
- assinatura.assinada   (assinar)
- assinatura.cancelada  (cancelar_solicitacao)

Usa admin_engine (BYPASSRLS) — RLS coberto em test_rls_isolation. Catálogos
criados do zero pra rodar em CI contra Postgres limpo.
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import hash_md5
from app.schemas.assinatura import SolicitarAssinaturaRequest
from app.services.assinaturas import (
    cancelar_solicitacao,
    solicitar_assinatura,
)

SENHA = "senha-teste"


async def _setup(s: AsyncSession, tenant_id: int) -> dict[str, int]:
    suf = uuid.uuid4().hex[:8]

    async def _scalar(sql: str, **p) -> int:
        return int((await s.execute(text(sql), p)).scalar_one())

    categoria = await _scalar(
        "INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) "
        "VALUES (:n, 'PF', true, false) RETURNING id",
        n=f"Ass {suf}",
    )
    tipo_manif = await _scalar(
        "INSERT INTO protocolos.tipo_manifestante "
        "(tenant_id, tipo_manifestante, id_categoria, ativo, excluido) "
        "VALUES (:t, :n, :c, true, false) RETURNING id",
        t=tenant_id, n=f"Ass {suf}", c=categoria,
    )
    manifestante = await _scalar(
        "INSERT INTO protocolos.manifestante "
        "(tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
        "VALUES (:t, :tm, :n, true, false) RETURNING id",
        t=tenant_id, tm=tipo_manif, n=f"Ass {suf}",
    )
    unidade = await _scalar(
        "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) "
        "VALUES (:t, :n, false) RETURNING id",
        t=tenant_id, n=f"Unid {suf}",
    )
    tipo_proc = await _scalar(
        "INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) "
        "VALUES (:t, :n, true, false) RETURNING id",
        t=tenant_id, n=f"Tipo {suf}",
    )
    assunto = await _scalar(
        "INSERT INTO protocolos.assunto (tenant_id, assunto, id_tipo_processo, ativo, excluido) "
        "VALUES (:t, :n, :tp, true, false) RETURNING id",
        t=tenant_id, n=f"Assunto {suf}", tp=tipo_proc,
    )
    # Usuário é solicitante E assinante (um usuário pode pedir a própria assinatura).
    usuario = await _scalar(
        "INSERT INTO utils.usuario "
        "(tenant_id, nome, email, senha, cpf, id_unidade_trabalho, ativo, excluido) "
        "VALUES (:t, :n, :e, :senha, :cpf, :u, true, false) RETURNING id",
        t=tenant_id, n=f"Ass {suf}", e=f"{suf}@ass.local",
        senha=hash_md5(SENHA), cpf=uuid.uuid4().hex[:11], u=unidade,
    )
    processo = await _scalar(
        "INSERT INTO protocolos.processo "
        "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
        " numero_processo, virtual, externo, ativo, excluido, migrado, data_hora_abertura) "
        "VALUES (:t, :a, :m, :u, :num, true, false, true, false, false, NOW()) RETURNING id",
        t=tenant_id, a=assunto, m=manifestante, u=unidade, num=f"P{suf}/2026",
    )
    acao = await _scalar(
        "INSERT INTO protocolos.acao "
        "(flag, acao, status_acao, status_movimentacao, ativo, excluido) "
        "VALUES (:flag, 'Abertura', 'aberto', 'aberto', true, false) RETURNING id",
        flag=f"TST_{suf}",
    )
    movimentacao = await _scalar(
        "INSERT INTO protocolos.movimentacao "
        "(tenant_id, id_processo, id_unidade_responsavel, id_acao, data_hora_movimentacao, ativo, excluido) "
        "VALUES (:t, :p, :u, :ac, NOW(), true, false) RETURNING id",
        t=tenant_id, p=processo, u=unidade, ac=acao,
    )
    anexo = await _scalar(
        "INSERT INTO protocolos.anexo "
        "(tenant_id, publico, ativo, excluido, e_doc, descricao, qtd_paginas) "
        "VALUES (:t, true, true, false, :edoc, :desc, 1) RETURNING id",
        t=tenant_id, edoc=f"{suf}.pdf", desc=f"Doc {suf}",
    )
    await _scalar(
        "INSERT INTO protocolos.anexo_processo "
        "(tenant_id, id_processo, id_anexo, id_movimentacao, ativo, excluido, anexo_herdado) "
        "VALUES (:t, :p, :an, :mv, true, false, false) RETURNING id",
        t=tenant_id, p=processo, an=anexo, mv=movimentacao,
    )
    return {
        "categoria": categoria, "tipo_manifestante": tipo_manif,
        "manifestante": manifestante, "unidade": unidade,
        "tipo_processo": tipo_proc, "assunto": assunto, "usuario": usuario,
        "processo": processo, "acao": acao, "movimentacao": movimentacao,
        "anexo": anexo,
    }


@pytest_asyncio.fixture
async def assinatura_env(admin_engine, two_tenants):
    tid, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        ids = await _setup(s, tid)
        await s.commit()

    yield {"tenant_id": tid, **ids}

    async with Session() as s:
        await s.execute(text("DELETE FROM aprimora_py.audit_log WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.assinatura_anexo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.usuario_assinatura WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.solicitacao_assinatura WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo_processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.movimentacao WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.acao WHERE id = :id"), {"id": ids["acao"]})
        await s.execute(text("DELETE FROM utils.usuario WHERE id = :id"), {"id": ids["usuario"]})
        await s.execute(text("DELETE FROM protocolos.assunto WHERE id = :id"), {"id": ids["assunto"]})
        await s.execute(text("DELETE FROM protocolos.tipo_processo WHERE id = :id"), {"id": ids["tipo_processo"]})
        await s.execute(text("DELETE FROM utils.unidade_trabalho WHERE id = :id"), {"id": ids["unidade"]})
        await s.execute(text("DELETE FROM protocolos.manifestante WHERE id = :id"), {"id": ids["manifestante"]})
        await s.execute(text("DELETE FROM protocolos.tipo_manifestante WHERE id = :id"), {"id": ids["tipo_manifestante"]})
        await s.execute(text("DELETE FROM protocolos.categoria WHERE id = :id"), {"id": ids["categoria"]})
        await s.commit()


def _session(admin_engine):
    return async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)()


async def _conta_audit(s: AsyncSession, tenant_id: int, acao: str) -> int:
    return int(
        (await s.execute(
            text(
                "SELECT count(*) FROM aprimora_py.audit_log "
                "WHERE tenant_id = :t AND acao = :a"
            ),
            {"t": tenant_id, "a": acao},
        )).scalar_one()
    )


async def test_solicitar_gera_audit(admin_engine, assinatura_env):
    tid = assinatura_env["tenant_id"]
    uid = assinatura_env["usuario"]
    async with _session(admin_engine) as s:
        await solicitar_assinatura(
            s,
            assinatura_env["processo"],
            SolicitarAssinaturaRequest(
                id_assinantes=[uid], id_anexos=[assinatura_env["anexo"]]
            ),
            tenant_id=tid,
            usuario_id=uid,
            unidade_solicitante_id=assinatura_env["unidade"],
        )
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, tid, "assinatura.solicitada") == 1


# O evento `assinatura.assinada` (com hash + evidências) é coberto em
# test_assinatura_v2.py, que escreve o arquivo no storage e exercita o fluxo v2.


async def test_cancelar_gera_audit(admin_engine, assinatura_env):
    tid = assinatura_env["tenant_id"]
    uid = assinatura_env["usuario"]
    async with _session(admin_engine) as s:
        solic = await solicitar_assinatura(
            s,
            assinatura_env["processo"],
            SolicitarAssinaturaRequest(
                id_assinantes=[uid], id_anexos=[assinatura_env["anexo"]]
            ),
            tenant_id=tid,
            usuario_id=uid,
            unidade_solicitante_id=assinatura_env["unidade"],
        )
        solic_id = solic.id
    async with _session(admin_engine) as s:
        await cancelar_solicitacao(s, solic_id, tenant_id=tid, usuario_id=uid)
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, tid, "assinatura.cancelada") == 1
