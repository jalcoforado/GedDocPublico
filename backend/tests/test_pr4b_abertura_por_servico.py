"""PR 4b — Abertura de protocolo por serviço.

Cobre `obter_servico_solicitavel` (404/409), `abrir_processo_por_servico`
(defaults aplicados, id_servico gravado, rate-limit, auditoria minimizada), o
cálculo de `solicitar_habilitado` e a compatibilidade de processos antigos
(id_servico null). Padrão: admin_engine (ged_user/BYPASSRLS) + serviços de domínio.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Assunto, Processo, Servico, TipoProcesso, UsuarioExterno
from app.schemas.cidadao import AbrirPorServicoRequest, AbrirProcessoCidadaoRequest
from app.schemas.servico import ServicoCreate
from app.services import servico as servico_svc
from app.services.cidadao_processos import (
    CidadaoProcessoError,
    abrir_processo_cidadao,
    abrir_processo_por_servico,
)
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pr4b")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref PR4b", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _criar_assunto(engine, tenant_id: int) -> tuple[int, int]:
    """Cria tipo_processo + assunto. Retorna (id_assunto, id_tipo_processo)."""
    async with _sm(engine)() as s:
        tp = TipoProcesso(tenant_id=tenant_id, tipo_processo="Geral", exige_processo_pai=False, ativo=True, excluido=False)
        s.add(tp)
        await s.flush()
        a = Assunto(tenant_id=tenant_id, assunto="Solicitação geral", id_tipo_processo=tp.id, exige_processo_pai=False, ativo=True, excluido=False)
        s.add(a)
        await s.commit()
        return a.id, tp.id


async def _criar_cidadao(engine, tenant_id: int, cpf: str) -> int:
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id, nome="Maria Cidadã", cpf_cnpj=cpf,
            email="maria@ex.com", ativo=True, excluido=False,
            uid=uuid.uuid4(), data_criacao=datetime.now(), login_govbr=False,
            telefone_whatsapp=False,
        )
        s.add(c)
        await s.commit()
        return c.id


async def _criar_servico(engine, tenant_id: int, **kw) -> Servico:
    async with _sm(engine)() as s:
        return await servico_svc.criar_servico(
            s, tenant_id=tenant_id,
            payload=ServicoCreate(nome=kw.get("nome", "Certidão"), slug=kw.get("slug", _slug("sv-")), **{
                k: v for k, v in kw.items() if k not in ("nome", "slug")
            }),
        )


async def _get_cidadao(engine, cid: int) -> UsuarioExterno:
    async with _sm(engine)() as s:
        return (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            # quebra o ciclo de FK processo↔movimentacao (id_ultima_movimentacao)
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.servico WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_externo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ---------- happy path: defaults aplicados + id_servico gravado ----------
async def test_abre_por_servico_aplica_defaults(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(
            admin_engine, tenant.id, slug="certidao-iptu",
            id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            nivel_sigilo_padrao="interno", canal_entrada_permitido="portal",
        )
        cid = await _criar_cidadao(admin_engine, tenant.id, uuid.uuid4().hex[:11])

        async with _sm(admin_engine)() as s:
            cidadao = (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()
            servico = (await s.execute(select(Servico).where(Servico.id == sv.id))).scalar_one()
            proc = await abrir_processo_por_servico(
                s, cidadao, servico,
                AbrirPorServicoRequest(corpo="Preciso de uma certidão de IPTU."),
                tenant_id=tenant.id,
            )
            pid = proc.id

        async with _sm(admin_engine)() as s:
            p = (await s.execute(select(Processo).where(Processo.id == pid))).scalar_one()
            assert p.id_servico == sv.id
            assert p.id_assunto == id_assunto
            assert p.id_unidade_proprietaria == uid and p.id_local_atual == uid
            assert p.nivel_sigilo == "interno"
            assert p.canal_entrada == "portal"
            assert p.externo is True
            # auditoria minimizada — sem dados pessoais
            audit = (await s.execute(text(
                "SELECT acao, payload::text AS p FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao='processo.aberto_por_servico'"
            ), {"t": tenant.id})).first()
            assert audit is not None
            assert str(sv.id) in audit.p and "portal" in audit.p and "servico" in audit.p
            assert "Maria" not in audit.p and "certidão" not in audit.p.lower()
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- obter_servico_solicitavel: 404 / 409 ----------
async def test_solicitavel_inativo_404(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, slug="serv-inat", id_assunto_padrao=id_assunto, id_unidade_responsavel=uid)
        async with _sm(admin_engine)() as s:
            await servico_svc.set_ativo(s, tenant_id=tenant.id, servico_id=sv.id, ativo=False)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico_solicitavel(s, tenant_id=tenant.id, slug="serv-inat")
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitavel_outro_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, a.id)
        id_assunto, _ = await _criar_assunto(admin_engine, a.id)
        await _criar_servico(admin_engine, a.id, slug="serv-a", id_assunto_padrao=id_assunto, id_unidade_responsavel=uid)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico_solicitavel(s, tenant_id=b.id, slug="serv-a")
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_solicitavel_canal_diferente_409(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        await _criar_servico(admin_engine, tenant.id, slug="serv-balcao", id_assunto_padrao=id_assunto, id_unidade_responsavel=uid, canal_entrada_permitido="balcao")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico_solicitavel(s, tenant_id=tenant.id, slug="serv-balcao")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitavel_sem_assunto_409(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        await _criar_servico(admin_engine, tenant.id, slug="serv-sem-assunto", id_unidade_responsavel=uid)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico_solicitavel(s, tenant_id=tenant.id, slug="serv-sem-assunto")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitavel_sem_unidade_409(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        await _criar_servico(admin_engine, tenant.id, slug="serv-sem-unidade", id_assunto_padrao=id_assunto)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico_solicitavel(s, tenant_id=tenant.id, slug="serv-sem-unidade")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- solicitar_habilitado calculado (projeção pública) ----------
async def test_solicitar_habilitado_calculado(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        await _criar_servico(admin_engine, tenant.id, slug="serv-ok", nome="OK", id_assunto_padrao=id_assunto, id_unidade_responsavel=uid)
        await _criar_servico(admin_engine, tenant.id, slug="serv-bad", nome="Bad")  # sem assunto/unidade
        async with _sm(admin_engine)() as s:
            pub = await servico_svc.listar_publico(s, tenant_id=tenant.id)
        por_nome = {p.nome: p.solicitar_habilitado for p in pub}
        assert por_nome["OK"] is True
        assert por_nome["Bad"] is False
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- rate-limit continua valendo ----------
async def test_rate_limit_continua(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, slug="serv-rl", id_assunto_padrao=id_assunto, id_unidade_responsavel=uid)
        cpf = uuid.uuid4().hex[:11]
        cid = await _criar_cidadao(admin_engine, tenant.id, cpf)
        # 5 aberturas OK, 6ª estoura (RATE_LIMIT_24H=5)
        for _ in range(5):
            async with _sm(admin_engine)() as s:
                cidadao = (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()
                servico = (await s.execute(select(Servico).where(Servico.id == sv.id))).scalar_one()
                await abrir_processo_por_servico(s, cidadao, servico, AbrirPorServicoRequest(corpo="Pedido de teste."), tenant_id=tenant.id)
        async with _sm(admin_engine)() as s:
            cidadao = (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()
            servico = (await s.execute(select(Servico).where(Servico.id == sv.id))).scalar_one()
            with pytest.raises(CidadaoProcessoError):
                await abrir_processo_por_servico(s, cidadao, servico, AbrirPorServicoRequest(corpo="Pedido de teste."), tenant_id=tenant.id)
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- compatibilidade: processo antigo (legado) fica com id_servico null ----------
async def test_legacy_abertura_id_servico_null(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        id_assunto, _ = await _criar_assunto(admin_engine, tenant.id)
        cid = await _criar_cidadao(admin_engine, tenant.id, uuid.uuid4().hex[:11])
        async with _sm(admin_engine)() as s:
            cidadao = (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()
            proc = await abrir_processo_cidadao(
                s, cidadao, AbrirProcessoCidadaoRequest(id_assunto=id_assunto, corpo="Pedido legado de teste."),
                tenant_id=tenant.id,
            )
            assert proc.id_servico is None
    finally:
        await _cleanup(admin_engine, tenant.id)
