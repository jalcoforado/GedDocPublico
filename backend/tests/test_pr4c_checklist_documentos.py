"""PR 4c — Checklist documental, vínculo anexo↔documento exigido e auditoria.

Cobre `calcular_checklist`, a extensão de `upload_anexo` (key opcional +
validação), a normalização estável de `ServicoDocumento.key` em
criar/atualizar_servico, anexos antigos (key=NULL) e a auditoria minimizada.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Anexo, AnexoProcesso, Assunto, Servico, TipoProcesso, UsuarioExterno
from app.schemas.cidadao import AbrirPorServicoRequest
from app.schemas.servico import ServicoCreate, ServicoUpdate
from app.services import servico as servico_svc
from app.services.anexos import AnexoError, upload_anexo
from app.services.audit import log as audit_log
from app.services.checklist_documentos import calcular_checklist
from app.services.cidadao_processos import abrir_processo_por_servico
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pr4c")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref PR4c", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _criar_assunto(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        tp = TipoProcesso(tenant_id=tenant_id, tipo_processo="Geral", exige_processo_pai=False, ativo=True, excluido=False)
        s.add(tp); await s.flush()
        a = Assunto(tenant_id=tenant_id, assunto="Sol", id_tipo_processo=tp.id, exige_processo_pai=False, ativo=True, excluido=False)
        s.add(a); await s.commit()
        return a.id


async def _criar_cidadao(engine, tenant_id: int, cpf: str) -> int:
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
        p = await abrir_processo_por_servico(s, cidadao, servico, AbrirPorServicoRequest(corpo="Pedido de teste."), tenant_id=tenant.id)
        return p.id


async def _movimentacao_id(engine, processo_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(text("SELECT id_ultima_movimentacao FROM protocolos.processo WHERE id=:p"), {"p": processo_id})).scalar_one())


async def _attach_anexo(engine, tenant_id, processo_id, mov_id, key: str | None):
    """Cria Anexo+AnexoProcesso via ORM, com documento_exigido_key opcional."""
    async with _sm(engine)() as s:
        a = Anexo(tenant_id=tenant_id, ativo=True, excluido=False, publico=True, descricao="doc", documento_exigido_key=key)
        s.add(a); await s.flush()
        ap = AnexoProcesso(tenant_id=tenant_id, id_processo=processo_id, id_anexo=a.id, id_movimentacao=mov_id, ativo=True, excluido=False)
        s.add(ap); await s.commit()
        return a.id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
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


# ---------- normalização (unit, sem DB) ----------
def test_normalizar_gera_key_e_preserva_existente():
    from app.services.servico import _normalizar_documentos_exigidos
    docs = [
        {"nome": "Documento de identificação", "obrigatorio": True},
        {"key": "comprovante-residencia", "nome": "Comprovante mudou", "obrigatorio": False},
    ]
    out = _normalizar_documentos_exigidos(docs)
    assert out[0]["key"] == "documento-de-identificacao"
    assert out[1]["key"] == "comprovante-residencia"  # preservada


def test_normalizar_colisao_sufixa():
    from app.services.servico import _normalizar_documentos_exigidos
    docs = [{"nome": "Documento X"}, {"nome": "Documento X"}]
    out = _normalizar_documentos_exigidos(docs)
    assert {d["key"] for d in out} == {"documento-x", "documento-x-2"}


# ---------- checklist: sem_documentos_exigidos ----------
async def test_checklist_processo_sem_id_servico(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        # Cria um processo legado (sem id_servico) via SQL direto.
        async with _sm(admin_engine)() as s:
            uid = await _unidade_id(admin_engine, tenant.id)
            id_assunto = await _criar_assunto(admin_engine, tenant.id)
            # manifestante mínimo
            await s.execute(text(
                "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'Teste', '00000000000', true, false FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ), {"t": tenant.id})
            mid = int((await s.execute(text("SELECT id FROM protocolos.manifestante WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one())
            pid = int((await s.execute(text(
                "INSERT INTO protocolos.processo (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                "virtual, data_hora_abertura, numero_processo, nivel_sigilo, externo, migrado, ativo, excluido, canal_entrada) "
                "VALUES (:t, :a, :m, :u, true, NOW(), 'P000999/2026', 'ostensivo', true, false, true, false, 'portal') RETURNING id"
            ), {"t": tenant.id, "a": id_assunto, "m": mid, "u": uid})).scalar_one())
            await s.commit()
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.id_servico is None
        assert r.status_documental == "sem_documentos_exigidos"
        assert r.itens == []
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_checklist_servico_sem_documentos(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            ))
        cid = await _criar_cidadao(admin_engine, tenant.id, uuid.uuid4().hex[:11])
        pid = await _abrir_processo(admin_engine, tenant, sv.id, cid)
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.status_documental == "sem_documentos_exigidos"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- checklist: pendente / parcial / completo + opcionais ----------
async def test_status_pendente_parcial_completo(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        docs = [
            {"nome": "RG", "obrigatorio": True},
            {"nome": "CPF", "obrigatorio": True},
            {"nome": "Opcional", "obrigatorio": False},
        ]
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
                documentos_exigidos=docs,
            ))
        cid = await _criar_cidadao(admin_engine, tenant.id, uuid.uuid4().hex[:11])
        pid = await _abrir_processo(admin_engine, tenant, sv.id, cid)
        mid = await _movimentacao_id(admin_engine, pid)

        # 0/2 → pendente
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.status_documental == "pendente"
        assert r.obrigatorios_total == 2 and r.obrigatorios_enviados == 0

        # 1/2 → parcial (anexa só o RG)
        await _attach_anexo(admin_engine, tenant.id, pid, mid, key="rg")
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.status_documental == "parcial"
        assert r.obrigatorios_enviados == 1

        # 2/2 → completo (opcional não importa)
        await _attach_anexo(admin_engine, tenant.id, pid, mid, key="cpf")
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        assert r.status_documental == "completo"
        # itens trazem `enviado` por key
        por_key = {i.key: i.enviado for i in r.itens}
        assert por_key == {"rg": True, "cpf": True, "opcional": False}
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- cross-tenant 404 ----------
async def test_checklist_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, a.id)
        id_assunto = await _criar_assunto(admin_engine, a.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=a.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            ))
        cid = await _criar_cidadao(admin_engine, a.id, uuid.uuid4().hex[:11])
        pid = await _abrir_processo(admin_engine, a, sv.id, cid)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await calcular_checklist(s, processo_id=pid, tenant_id=b.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- upload com key (válida/inválida/sem serviço) ----------
async def _setup_upload(admin_engine):
    tenant = await _provisionar(admin_engine)
    uid = await _unidade_id(admin_engine, tenant.id)
    id_assunto = await _criar_assunto(admin_engine, tenant.id)
    async with _sm(admin_engine)() as s:
        sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
            nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
            documentos_exigidos=[{"nome": "RG", "obrigatorio": True}],
        ))
    cid = await _criar_cidadao(admin_engine, tenant.id, uuid.uuid4().hex[:11])
    pid = await _abrir_processo(admin_engine, tenant, sv.id, cid)
    return tenant, sv, pid


def _fake_file(name="rg.pdf", content=b"%PDF-1.4 fake"):
    return UploadFile(filename=name, file=io.BytesIO(content))


async def test_upload_com_key_valida_persiste_e_checklist_enviado(admin_engine):
    tenant, sv, pid = await _setup_upload(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            anexo = await upload_anexo(
                s, pid, _fake_file(),
                tenant_id=tenant.id, tenant_slug=tenant.slug,
                descricao="meu rg", id_tipo_anexo=None, publico=True, usuario_id=None,
                documento_exigido_key="rg",
            )
            aid = anexo.id

        async with _sm(admin_engine)() as s:
            row = (await s.execute(select(Anexo).where(Anexo.id == aid))).scalar_one()
            assert row.documento_exigido_key == "rg"
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        por_key = {i.key: i.enviado for i in r.itens}
        assert por_key.get("rg") is True
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_upload_com_key_invalida_400(admin_engine):
    tenant, sv, pid = await _setup_upload(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(AnexoError):
                await upload_anexo(
                    s, pid, _fake_file(),
                    tenant_id=tenant.id, tenant_slug=tenant.slug,
                    descricao=None, id_tipo_anexo=None, publico=True, usuario_id=None,
                    documento_exigido_key="nao-existe",
                )
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_upload_key_em_processo_sem_servico_400(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        # Cria processo SEM servico via SQL direto (legado).
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'X', '0', true, false FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ), {"t": tenant.id})
            mid = int((await s.execute(text("SELECT id FROM protocolos.manifestante WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one())
            # processo + movimentacao (precisa ter id_ultima_movimentacao p/ upload_anexo aceitar)
            pid = int((await s.execute(text(
                "INSERT INTO protocolos.processo (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                "virtual, data_hora_abertura, numero_processo, nivel_sigilo, externo, migrado, ativo, excluido, canal_entrada) "
                "VALUES (:t, :a, :m, :u, true, NOW(), 'P000998/2026', 'ostensivo', true, false, true, false, 'portal') RETURNING id"
            ), {"t": tenant.id, "a": id_assunto, "m": mid, "u": uid})).scalar_one())
            mvid = int((await s.execute(text(
                "INSERT INTO protocolos.movimentacao (tenant_id, id_processo, id_unidade_responsavel, id_acao, data_hora_movimentacao, ativo, excluido) "
                "SELECT :t, :p, :u, id, NOW(), true, false FROM protocolos.acao WHERE flag='ABERTURA' LIMIT 1 RETURNING id"
            ), {"t": tenant.id, "p": pid, "u": uid})).scalar_one())
            await s.execute(text("UPDATE protocolos.processo SET id_ultima_movimentacao=:m WHERE id=:p"), {"m": mvid, "p": pid})
            await s.commit()

        async with _sm(admin_engine)() as s:
            with pytest.raises(AnexoError):
                await upload_anexo(
                    s, pid, _fake_file(),
                    tenant_id=tenant.id, tenant_slug=tenant.slug,
                    descricao=None, id_tipo_anexo=None, publico=True, usuario_id=None,
                    documento_exigido_key="qualquer",
                )
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- anexo antigo (key NULL) continua funcionando ----------
async def test_anexo_antigo_key_null_nao_quebra(admin_engine):
    tenant, sv, pid = await _setup_upload(admin_engine)
    try:
        mid = await _movimentacao_id(admin_engine, pid)
        await _attach_anexo(admin_engine, tenant.id, pid, mid, key=None)  # legado
        async with _sm(admin_engine)() as s:
            r = await calcular_checklist(s, processo_id=pid, tenant_id=tenant.id)
        # anexo NULL não aparece nos itens (não está vinculado), mas não quebra
        assert r.status_documental == "pendente"
        assert r.itens[0].enviado is False
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- atualizar_servico preserva key existente ----------
async def test_atualizar_preserva_key_existente(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_assunto = await _criar_assunto(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            sv = await servico_svc.criar_servico(s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"), id_assunto_padrao=id_assunto, id_unidade_responsavel=uid,
                documentos_exigidos=[{"nome": "RG", "obrigatorio": True}],
            ))
            assert sv.documentos_exigidos[0]["key"] == "rg"
        # admin edita o nome do item — preserva a key
        async with _sm(admin_engine)() as s:
            sv2 = await servico_svc.atualizar_servico(
                s, tenant_id=tenant.id, servico_id=sv.id,
                payload=ServicoUpdate(documentos_exigidos=[
                    {"key": "rg", "nome": "Documento RG (atualizado)", "obrigatorio": True}
                ]),
            )
            assert sv2.documentos_exigidos[0]["key"] == "rg"
            assert "atualizado" in sv2.documentos_exigidos[0]["nome"]
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- auditoria minimizada ----------
async def test_audit_minimizado_sem_dados_pessoais(admin_engine):
    tenant, sv, pid = await _setup_upload(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            anexo = await upload_anexo(
                s, pid, _fake_file(name="confidencial-do-cidadao.pdf"),
                tenant_id=tenant.id, tenant_slug=tenant.slug,
                descricao=None, id_tipo_anexo=None, publico=True, usuario_id=None,
                documento_exigido_key="rg",
            )
            # mesma audit_log emitida pelo router /cidadao/.../anexos
            await audit_log(
                s, tenant_id=tenant.id, id_usuario=None,
                acao="anexo.enviado_cidadao", entidade="anexo", id_entidade=anexo.id,
                payload={"id_processo": pid, "documento_exigido_key": "rg", "canal": "portal"},
            )
            await s.commit()

        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT payload::text AS p FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao='anexo.enviado_cidadao'"
            ), {"t": tenant.id})).first()
        assert row is not None
        assert "rg" in row.p and "portal" in row.p
        # NÃO deve conter dados pessoais / nome do arquivo / nome do cidadão
        assert "Maria" not in row.p
        assert "confidencial" not in row.p
    finally:
        await _cleanup(admin_engine, tenant.id)
