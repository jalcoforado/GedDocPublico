"""PR 4d — Complementação documental formal.

Cobre service layer (solicitar/responder/cancelar/listar/obter_aberta), endpoints
via service, integração com checklist (`complementacao_aberta`), D-RESPOSTA
(cidadão responde sem todos os docs), D-CONCORRENCIA (1 aberta por processo),
D-AUDIT (payloads minimizados sem CPF/nome/mensagem/motivo).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Anexo,
    AnexoProcesso,
    Assunto,
    ComplementacaoDocumental,
    Servico,
    TipoProcesso,
    UsuarioExterno,
)
from app.schemas.cidadao import AbrirPorServicoRequest
from app.schemas.servico import ServicoCreate
from app.services import complementacao_documental as comp_svc
from app.services import servico as servico_svc
from app.services.checklist_documentos import calcular_checklist
from app.services.cidadao_processos import abrir_processo_por_servico
from app.services.complementacao_documental import ComplementacaoError
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pr4d")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref PR4d", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _admin_id(engine, tenant_id: int) -> int:
    """Devolve o id do super-usuário admin do tenant (criado por provisionar)."""
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _criar_assunto(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        tp = TipoProcesso(tenant_id=tenant_id, tipo_processo="Geral", exige_processo_pai=False, ativo=True, excluido=False)
        s.add(tp); await s.flush()
        a = Assunto(tenant_id=tenant_id, assunto="Sol", id_tipo_processo=tp.id, exige_processo_pai=False, ativo=True, excluido=False)
        s.add(a); await s.commit()
        return a.id


async def _criar_cidadao(engine, tenant_id: int, cpf: str | None = None) -> int:
    cpf = cpf or uuid.uuid4().hex[:11]
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id, nome="Maria", cpf_cnpj=cpf, email="m@x", ativo=True,
            excluido=False, uid=uuid.uuid4(), data_criacao=datetime.now(),
            login_govbr=False, telefone_whatsapp=False,
        )
        s.add(c); await s.commit()
        return c.id


async def _abrir_processo(engine, tenant, sv_id: int, cid: int) -> int:
    async with _sm(engine)() as s:
        cidadao = (await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))).scalar_one()
        servico = (await s.execute(select(Servico).where(Servico.id == sv_id))).scalar_one()
        p = await abrir_processo_por_servico(
            s, cidadao, servico, AbrirPorServicoRequest(corpo="Pedido de teste."),
            tenant_id=tenant.id,
        )
        return p.id


async def _movimentacao_id(engine, processo_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id_ultima_movimentacao FROM protocolos.processo WHERE id=:p"),
            {"p": processo_id},
        )).scalar_one())


async def _attach_anexo(engine, tenant_id, processo_id, mov_id, *, key: str | None):
    async with _sm(engine)() as s:
        a = Anexo(tenant_id=tenant_id, ativo=True, excluido=False, publico=True, descricao="doc", documento_exigido_key=key)
        s.add(a); await s.flush()
        ap = AnexoProcesso(tenant_id=tenant_id, id_processo=processo_id, id_anexo=a.id, id_movimentacao=mov_id, ativo=True, excluido=False)
        s.add(ap); await s.commit()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.complementacao_documental WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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


async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def _setup_servico_processo(engine):
    """Helper: cria tenant + serviço (RG/CPF/comp) + cidadão dono + processo aberto."""
    tenant = await _provisionar(engine)
    uid = await _unidade_id(engine, tenant.id)
    id_assunto = await _criar_assunto(engine, tenant.id)
    docs = [
        {"nome": "RG", "obrigatorio": True},
        {"nome": "CPF", "obrigatorio": True},
        {"nome": "Comprovante", "obrigatorio": False},
    ]
    async with _sm(engine)() as s:
        sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
            nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            documentos_exigidos=docs,
        ))
    cid = await _criar_cidadao(engine, tenant.id)
    pid = await _abrir_processo(engine, tenant, sv.id, cid)
    admin_id = await _admin_id(engine, tenant.id)
    return tenant, sv, pid, admin_id


# ============ D-MODELO + solicitar ============

async def test_solicitar_complementacao_ok(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id,
                mensagem="Por favor envie o RG e o CPF.",
                documentos_solicitados_keys=["rg", "cpf"],
            )
            await s.commit()
        assert comp.status == "aberta"
        assert {d["key"] for d in comp.documentos_solicitados} == {"rg", "cpf"}
        assert comp.respondido_em is None and comp.cancelado_em is None

        # audit registrado, sem dados pessoais
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT payload::text AS p FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao='complementacao.solicitada'"
            ), {"t": tenant.id})).first()
        assert row is not None
        assert "rg" in row.p and "cpf" in row.p
        assert "Maria" not in row.p
        assert "envie o RG" not in row.p  # mensagem NÃO no audit
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitar_key_invalida_400(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.solicitar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    id_usuario_solicitante=admin_id, mensagem="m",
                    documentos_solicitados_keys=["nao-existe"],
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitar_processo_sem_servico_400(admin_engine):
    """Processo sem id_servico não permite complementação (não há docs exigidos)."""
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        admin_id = await _admin_id(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'X', '0', true, false FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ), {"t": tenant.id})
            mid = int((await s.execute(text("SELECT id FROM protocolos.manifestante WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one())
            pid = int((await s.execute(text(
                "INSERT INTO protocolos.processo (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                "virtual, data_hora_abertura, numero_processo, nivel_sigilo, externo, migrado, ativo, excluido, canal_entrada) "
                "VALUES (:t, :a, :m, :u, true, NOW(), 'P000777/2026', 'ostensivo', true, false, true, false, 'portal') RETURNING id"
            ), {"t": tenant.id, "a": id_assunto, "m": mid, "u": uid})).scalar_one())
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.solicitar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    id_usuario_solicitante=admin_id, mensagem="m",
                    documentos_solicitados_keys=["x"],
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_solicitar_servico_sem_documentos_400(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        admin_id = await _admin_id(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            ))
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv.id, cid)
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.solicitar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    id_usuario_solicitante=admin_id, mensagem="m",
                    documentos_solicitados_keys=["x"],
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ D-CONCORRENCIA ============

async def test_solicitar_duas_abertas_409(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="primeira",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.solicitar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    id_usuario_solicitante=admin_id, mensagem="segunda",
                    documentos_solicitados_keys=["cpf"],
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ cross-tenant ============

async def test_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, a.id)
        id_assunto = await _criar_assunto(admin_engine, a.id)
        admin_a = await _admin_id(admin_engine, a.id)
        admin_b = await _admin_id(admin_engine, b.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=a.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
                documentos_exigidos=[{"nome": "RG", "obrigatorio": True}],
            ))
        cid = await _criar_cidadao(admin_engine, a.id)
        pid = await _abrir_processo(admin_engine, a, sv.id, cid)
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=a.id, processo_id=pid,
                id_usuario_solicitante=admin_a, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()
        # tenant B tenta tudo → 404 sem vazar existência
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.responder(
                    s, tenant_id=b.id, processo_id=pid, complementacao_id=comp.id,
                )
            assert exc.value.status_code == 404
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.cancelar(
                    s, tenant_id=b.id, processo_id=pid, complementacao_id=comp.id,
                    id_usuario_responsavel=admin_b, motivo=None,
                )
            assert exc.value.status_code == 404
            # listar do tenant B no processo de A → vazio
            rows = await comp_svc.listar(s, tenant_id=b.id, processo_id=pid)
            assert rows == []
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_rls_complementacao_isolada_por_tenant(admin_engine, app_session: AsyncSession):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()

        await _set_tenant(app_session, tenant.id)
        visible = (await app_session.execute(
            text(
                "SELECT id FROM protocolos.complementacao_documental "
                "WHERE id=:id"
            ),
            {"id": comp.id},
        )).scalar_one_or_none()
        assert visible == comp.id

        await app_session.rollback()
        await _set_tenant(app_session, tenant.id + 100000)
        hidden = (await app_session.execute(
            text(
                "SELECT id FROM protocolos.complementacao_documental "
                "WHERE id=:id"
            ),
            {"id": comp.id},
        )).scalar_one_or_none()
        assert hidden is None
    finally:
        await app_session.rollback()
        await _cleanup(admin_engine, tenant.id)


# ============ D-RESPOSTA ============

async def test_responder_aberta_ok(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg", "cpf"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            comp2 = await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        assert comp2.status == "respondida"
        assert comp2.respondido_em is not None

        # audit minimizado
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT payload::text AS p FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao='complementacao.respondida'"
            ), {"t": tenant.id})).first()
        assert row is not None
        assert "portal" in row.p
        assert "Maria" not in row.p
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_responder_sem_todos_docs_ok(admin_engine):
    """D-RESPOSTA: cidadão pode responder mesmo sem anexar todos os docs."""
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg", "cpf"],
            )
            await s.commit()
        # nenhum anexo enviado
        async with _sm(admin_engine)() as s:
            comp2 = await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        assert comp2.status == "respondida"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_responder_respondida_ou_cancelada_409(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.responder(
                    s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ cancelar ============

async def test_cancelar_aberta_ok(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            comp2 = await comp_svc.cancelar(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
                id_usuario_responsavel=admin_id, motivo="enviado por outro canal",
            )
            await s.commit()
        assert comp2.status == "cancelada"
        assert comp2.cancelado_em is not None
        assert comp2.motivo_cancelamento == "enviado por outro canal"

        # audit minimizado — motivo NÃO no audit
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT payload::text AS p FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao='complementacao.cancelada'"
            ), {"t": tenant.id})).first()
        assert row is not None
        assert "outro canal" not in row.p
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_cancelar_nao_aberta_409(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.cancelar(
                    s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
                    id_usuario_responsavel=admin_id, motivo=None,
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_apos_resposta_pode_abrir_nova(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="primeira",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        # nova solicitação no mesmo processo passa
        async with _sm(admin_engine)() as s:
            comp2 = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="segunda",
                documentos_solicitados_keys=["cpf"],
            )
            await s.commit()
        assert comp2.status == "aberta"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ integração com checklist ============

async def test_checklist_traz_complementacao_aberta(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="Envie RG e CPF",
                documentos_solicitados_keys=["rg", "cpf"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        # D-STATUS: status_documental NÃO muda
        assert r.status_documental == "pendente"
        assert r.complementacao_aberta is not None
        assert r.complementacao_aberta.status == "aberta"
        keys = {d.key for d in r.complementacao_aberta.documentos_solicitados}
        assert keys == {"rg", "cpf"}
        # nenhum enviado ainda
        assert all(not d.enviado for d in r.complementacao_aberta.documentos_solicitados)
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_checklist_complementacao_reflete_anexos_enviados(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg", "cpf"],
            )
            await s.commit()
        mid = await _movimentacao_id(admin_engine, pid)
        await _attach_anexo(admin_engine, tenant.id, pid, mid, key="rg")
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        por_key = {d.key: d.enviado for d in r.complementacao_aberta.documentos_solicitados}
        assert por_key == {"rg": True, "cpf": False}
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_checklist_apos_resposta_aberta_none(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=comp.id,
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.complementacao_aberta is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_processo_sem_docs_exigidos_nao_quebra_checklist(admin_engine):
    """Brief: processo sem documentos exigidos não pode receber complementação,
    mas o checklist segue funcionando."""
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            ))
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv.id, cid)
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.status_documental == "sem_documentos_exigidos"
        assert r.complementacao_aberta is None
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ listar ============

async def test_listar_ordena_desc(admin_engine):
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            c1 = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="primeira",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid, complementacao_id=c1.id,
            )
            c2 = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="segunda",
                documentos_solicitados_keys=["cpf"],
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            rows = await comp_svc.listar(s, tenant_id=tenant.id, processo_id=pid)
        assert [r.id for r in rows] == [c2.id, c1.id]  # desc por criado_em
    finally:
        await _cleanup(admin_engine, tenant.id)


# ============ PR 4d-fix — transição atômica ============

async def test_responder_ja_cancelada_409_sem_audit_fantasma(admin_engine):
    """PR 4d-fix: tentar responder uma complementação JÁ cancelada deve
    retornar 409 e NÃO emitir um evento `complementacao.respondida` no audit.
    Garante que a transição atômica não gera dois eventos contraditórios."""
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.cancelar(
                s, tenant_id=tenant.id, processo_id=pid,
                complementacao_id=comp.id,
                id_usuario_responsavel=admin_id, motivo=None,
            )
            await s.commit()

        # Tenta responder a já cancelada → 409
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.responder(
                    s, tenant_id=tenant.id, processo_id=pid,
                    complementacao_id=comp.id,
                )
            assert exc.value.status_code == 409

        # Estado final: cancelada (não foi sobrescrito)
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT status FROM protocolos.complementacao_documental "
                "WHERE id=:i"
            ), {"i": comp.id})).first()
            assert row.status == "cancelada"

            # Audit: 1 solicitada + 1 cancelada; ZERO respondida
            counts = {
                acao: int(n) for acao, n in (await s.execute(text(
                    "SELECT acao, COUNT(*) FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND entidade='complementacao_documental' "
                    "AND id_entidade=:e GROUP BY acao"
                ), {"t": tenant.id, "e": comp.id})).all()
            }
            assert counts.get("complementacao.solicitada") == 1
            assert counts.get("complementacao.cancelada") == 1
            assert counts.get("complementacao.respondida") is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_cancelar_ja_respondida_409_sem_audit_fantasma(admin_engine):
    """PR 4d-fix: tentar cancelar uma complementação JÁ respondida deve
    retornar 409 e NÃO emitir um evento `complementacao.cancelada`."""
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await comp_svc.responder(
                s, tenant_id=tenant.id, processo_id=pid,
                complementacao_id=comp.id,
            )
            await s.commit()

        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.cancelar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    complementacao_id=comp.id,
                    id_usuario_responsavel=admin_id, motivo="tentativa",
                )
            assert exc.value.status_code == 409

        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT status, motivo_cancelamento FROM "
                "protocolos.complementacao_documental WHERE id=:i"
            ), {"i": comp.id})).first()
            assert row.status == "respondida"
            assert row.motivo_cancelamento is None  # não vazou o "tentativa"

            counts = {
                acao: int(n) for acao, n in (await s.execute(text(
                    "SELECT acao, COUNT(*) FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND entidade='complementacao_documental' "
                    "AND id_entidade=:e GROUP BY acao"
                ), {"t": tenant.id, "e": comp.id})).all()
            }
            assert counts.get("complementacao.respondida") == 1
            assert counts.get("complementacao.cancelada") is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_transicao_concorrente_simulada_apenas_uma_prevalece(admin_engine):
    """PR 4d-fix: simula o cenário onde responder e cancelar disparam em
    paralelo. Como ambos usam `UPDATE ... WHERE status='aberta' RETURNING *`,
    apenas a primeira transição prevalece. A segunda, mesmo que tenha lido
    `status='aberta'` antes, recebe 0 linhas no UPDATE e levanta 409 — sem
    audit_log fantasma."""
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            comp = await comp_svc.solicitar(
                s, tenant_id=tenant.id, processo_id=pid,
                id_usuario_solicitante=admin_id, mensagem="m",
                documentos_solicitados_keys=["rg"],
            )
            await s.commit()

        # Sessão A: responder e commita primeiro.
        async with _sm(admin_engine)() as sa:
            await comp_svc.responder(
                sa, tenant_id=tenant.id, processo_id=pid,
                complementacao_id=comp.id,
            )
            await sa.commit()

        # Sessão B: havia visto status='aberta' antes de A commitar, agora
        # tenta cancelar (em transação nova) — UPDATE atômico não acha
        # status='aberta' e devolve 0 linhas → 409.
        async with _sm(admin_engine)() as sb:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.cancelar(
                    sb, tenant_id=tenant.id, processo_id=pid,
                    complementacao_id=comp.id,
                    id_usuario_responsavel=admin_id, motivo=None,
                )
            assert exc.value.status_code == 409

        # Estado final: respondida prevaleceu; só 1 evento de transição.
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT status FROM protocolos.complementacao_documental "
                "WHERE id=:i"
            ), {"i": comp.id})).first()
            assert row.status == "respondida"
            counts = {
                acao: int(n) for acao, n in (await s.execute(text(
                    "SELECT acao, COUNT(*) FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND entidade='complementacao_documental' "
                    "AND id_entidade=:e GROUP BY acao"
                ), {"t": tenant.id, "e": comp.id})).all()
            }
            # Exatamente 1 solicitada + 1 respondida; 0 canceladas.
            assert counts.get("complementacao.solicitada") == 1
            assert counts.get("complementacao.respondida") == 1
            assert counts.get("complementacao.cancelada") is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_transicao_404_distinguida_de_409(admin_engine):
    """PR 4d-fix: UPDATE atômico com fallback distingue 404 (não existe)
    de 409 (existe mas não está aberta)."""
    tenant, sv, pid, admin_id = await _setup_servico_processo(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.responder(
                    s, tenant_id=tenant.id, processo_id=pid,
                    complementacao_id=999999,
                )
            assert exc.value.status_code == 404

            with pytest.raises(ComplementacaoError) as exc:
                await comp_svc.cancelar(
                    s, tenant_id=tenant.id, processo_id=pid,
                    complementacao_id=999999,
                    id_usuario_responsavel=admin_id, motivo=None,
                )
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, tenant.id)
