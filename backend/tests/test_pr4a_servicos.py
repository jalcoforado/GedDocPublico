"""PR 4a — Catálogo de Serviços / Carta de Serviços.

Cobre o serviço de domínio (`services/servico.py`), o gate de permissão `servico`
e a projeção pública. Padrão dos testes: `admin_engine` (ged_user/BYPASSRLS) para
setup + chamadas de serviço; gate via monkeypatch (como em test_pr3b).
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.perms import require_permission
from app.models import Servico, TipoProcesso, Usuario
from app.schemas.servico import ServicoCreate, ServicoUpdate
from app.services import servico as servico_svc
from app.services.permissoes import UserPermissions
from app.services.provisioning_tenant import provisionar_tenant


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pr4a")
    async with _sessionmaker(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura PR4a", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sessionmaker(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


async def _criar_tipo_processo(engine, tenant_id: int) -> int:
    async with _sessionmaker(engine)() as s:
        tp = TipoProcesso(
            tenant_id=tenant_id, tipo_processo="Teste", exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        s.add(tp)
        await s.commit()
        await s.refresh(tp)
        return tp.id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sessionmaker(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.servico WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.especie_documental WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ---------- CRUD básico ----------
async def test_criar_e_editar_servico(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            criado = await servico_svc.criar_servico(
                s, tenant_id=tenant.id,
                payload=ServicoCreate(
                    nome="Certidão de IPTU", slug="certidao-iptu",
                    descricao_curta="Emissão de certidão",
                    documentos_exigidos=[{"nome": "RG", "obrigatorio": True}],
                ),
            )
            assert criado.id and criado.ativo is True and criado.nivel_sigilo_padrao == "ostensivo"
            assert criado.canal_entrada_permitido == "portal"
            assert criado.documentos_exigidos == [{"nome": "RG", "obrigatorio": True, "descricao": None}]

        async with _sessionmaker(admin_engine)() as s:
            editado = await servico_svc.atualizar_servico(
                s, tenant_id=tenant.id, servico_id=criado.id,
                payload=ServicoUpdate(nome="Certidão de IPTU (atualizada)", destaque=True),
            )
            assert editado.nome == "Certidão de IPTU (atualizada)"
            assert editado.destaque is True
            assert editado.atualizado_em is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_ativar_desativar(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            sv = await servico_svc.criar_servico(
                s, tenant_id=tenant.id, payload=ServicoCreate(nome="X", slug="serv-x")
            )
        async with _sessionmaker(admin_engine)() as s:
            d = await servico_svc.set_ativo(s, tenant_id=tenant.id, servico_id=sv.id, ativo=False)
            assert d.ativo is False
        async with _sessionmaker(admin_engine)() as s:
            a = await servico_svc.set_ativo(s, tenant_id=tenant.id, servico_id=sv.id, ativo=True)
            assert a.ativo is True
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- slug ----------
async def test_slug_unico_por_tenant(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            await servico_svc.criar_servico(
                s, tenant_id=tenant.id, payload=ServicoCreate(nome="A", slug="dup-slug")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.criar_servico(
                    s, tenant_id=tenant.id, payload=ServicoCreate(nome="B", slug="dup-slug")
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_mesmo_slug_em_tenants_diferentes_ok(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            sa = await servico_svc.criar_servico(
                s, tenant_id=a.id, payload=ServicoCreate(nome="A", slug="mesmo-slug")
            )
        async with _sessionmaker(admin_engine)() as s:
            sb = await servico_svc.criar_servico(
                s, tenant_id=b.id, payload=ServicoCreate(nome="B", slug="mesmo-slug")
            )
        assert sa.slug == sb.slug and sa.tenant_id != sb.tenant_id
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- cross-tenant + tenant_id imutável ----------
async def test_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            sv = await servico_svc.criar_servico(
                s, tenant_id=a.id, payload=ServicoCreate(nome="A", slug="serv-a")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.obter_servico(s, tenant_id=b.id, servico_id=sv.id)
            assert exc.value.status_code == 404
            with pytest.raises(HTTPException) as exc2:
                await servico_svc.atualizar_servico(
                    s, tenant_id=b.id, servico_id=sv.id, payload=ServicoUpdate(nome="hack")
                )
            assert exc2.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_update_schema_descarta_tenant_id():
    m = ServicoUpdate.model_validate({"nome": "X", "tenant_id": 999, "id": 7, "ativo": False})
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"nome": "X"}
    for proibido in ("tenant_id", "id", "ativo", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


async def test_payload_nao_altera_tenant_id(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            sv = await servico_svc.criar_servico(
                s, tenant_id=tenant.id, payload=ServicoCreate(nome="X", slug="serv-y")
            )
        async with _sessionmaker(admin_engine)() as s:
            # tenant_id no corpo é ignorado pelo schema; serviço permanece no tenant.
            await servico_svc.atualizar_servico(
                s, tenant_id=tenant.id, servico_id=sv.id,
                payload=ServicoUpdate.model_validate({"nome": "Y", "tenant_id": 999999}),
            )
        async with _sessionmaker(admin_engine)() as s:
            row = (await s.execute(select(Servico).where(Servico.id == sv.id))).scalar_one()
            assert row.tenant_id == tenant.id
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- defaults same-tenant ----------
async def test_default_do_tenant_aceito(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        tp = await _criar_tipo_processo(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            sv = await servico_svc.criar_servico(
                s, tenant_id=tenant.id,
                payload=ServicoCreate(
                    nome="X", slug="serv-def",
                    id_unidade_responsavel=uid, id_tipo_processo_padrao=tp,
                ),
            )
            assert sv.id_unidade_responsavel == uid and sv.id_tipo_processo_padrao == tp
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_default_de_outro_tenant_rejeitado(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid_b = await _unidade_id(admin_engine, b.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await servico_svc.criar_servico(
                    s, tenant_id=a.id,
                    payload=ServicoCreate(nome="X", slug="serv-z", id_unidade_responsavel=uid_b),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- documentos_exigidos inválido (422 via schema) ----------
def test_documentos_invalido_rejeitado():
    with pytest.raises(ValidationError):
        ServicoCreate(nome="X", slug="abc", documentos_exigidos="nao-eh-lista")
    with pytest.raises(ValidationError):
        ServicoCreate(nome="X", slug="abc", documentos_exigidos=[{"obrigatorio": True}])  # falta nome


def test_documentos_lista_valida_ok():
    m = ServicoCreate(
        nome="X", slug="abc",
        documentos_exigidos=[{"nome": "RG", "obrigatorio": True, "descricao": "com foto"}],
    )
    assert m.documentos_exigidos[0].nome == "RG"


# ---------- público: só ativos do tenant + projeção segura ----------
async def test_publico_lista_apenas_ativos(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            await servico_svc.criar_servico(
                s, tenant_id=tenant.id, payload=ServicoCreate(nome="Ativo", slug="serv-ativo")
            )
            inativo = await servico_svc.criar_servico(
                s, tenant_id=tenant.id, payload=ServicoCreate(nome="Inativo", slug="serv-inativo")
            )
            await servico_svc.set_ativo(s, tenant_id=tenant.id, servico_id=inativo.id, ativo=False)
        async with _sessionmaker(admin_engine)() as s:
            pub = await servico_svc.listar_publico(s, tenant_id=tenant.id)
        nomes = {p.nome for p in pub}
        assert "Ativo" in nomes and "Inativo" not in nomes
        # projeção pública não expõe campos internos
        campos = pub[0].model_dump().keys()
        for interno in ("id", "tenant_id", "nivel_sigilo_padrao", "canal_entrada_permitido", "ativo", "excluido"):
            assert interno not in campos
        assert pub[0].solicitar_habilitado is False
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- gate de permissão `servico` (monkeypatch) ----------
def _fake_user(uid: int = 9) -> Usuario:
    u = MagicMock(spec=Usuario)
    u.id = uid
    return u


def _patch_load(monkeypatch, perms: UserPermissions) -> None:
    async def fake_load(db, user_id, *, tenant_id):
        return perms

    monkeypatch.setattr("app.auth.perms.load_permissions", fake_load)


async def test_gate_servico_su_bypassa(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]))
    check = require_permission("servico", "inserir")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_gate_servico_nao_su_403(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=False, nivel_valor=5, items=[]))
    check = require_permission("servico", "inserir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
    assert "servico" in exc.value.detail
