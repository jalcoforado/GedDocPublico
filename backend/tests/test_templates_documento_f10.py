"""Modelos de documento — clonar, espécie/setor, destinatário e nº do
documento (fatia F10, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

`id_unidade_trabalho` em `TemplateDocumento` é administração, não precedência
— mesmo padrão de `Marcador` (F5). Não há teste de "unidade sobrepõe tenant"
porque essa cascata foi deliberadamente descartada (ver docstring da
migration 0116).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Assunto, TipoProcesso, Usuario
from app.schemas.minuta import MinutaCreate, TemplateDocumentoCreate
from app.services import minutas as svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("f10-")
    async with _sm(engine)() as s:
        tenant, _senha_temp = await provisionar_tenant(
            s, slug=slug, nome="Pref F10", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(engine)() as s:
        user = (
            await s.execute(select(Usuario).where(Usuario.tenant_id == tenant.id).limit(1))
        ).scalar_one()
        unidade_id = (
            await s.execute(
                text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
                {"t": tenant.id},
            )
        ).scalar_one()
    return tenant, user, unidade_id


async def _criar_processo(engine, tenant_id: int, unidade_id: int) -> int:
    async with _sm(engine)() as s:
        tp = TipoProcesso(
            tenant_id=tenant_id, tipo_processo="Geral",
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(tp)
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant_id, assunto="Minuta F10", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        await s.execute(
            text(
                "INSERT INTO protocolos.manifestante "
                "(tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'Manifestante F10', :cpf, true, false "
                "FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ),
            {"t": tenant_id, "cpf": uuid.uuid4().hex[:11]},
        )
        manifestante_id = (
            await s.execute(
                text("SELECT id FROM protocolos.manifestante WHERE tenant_id=:t LIMIT 1"),
                {"t": tenant_id},
            )
        ).scalar_one()
        processo_id = (
            await s.execute(
                text(
                    "INSERT INTO protocolos.processo "
                    "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                    " virtual, data_hora_abertura, numero_processo, nivel_sigilo, "
                    " externo, migrado, ativo, excluido, canal_entrada) "
                    "VALUES (:t, :a, :m, :u, true, NOW(), :num, 'ostensivo', "
                    "        true, false, true, false, 'portal') RETURNING id"
                ),
                {
                    "t": tenant_id, "a": assunto.id, "m": manifestante_id,
                    "u": unidade_id, "num": f"P{uuid.uuid4().hex[:6].upper()}/2026",
                },
            )
        ).scalar_one()
        await s.commit()
    return processo_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.minuta_historico WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta WHERE tenant_id=:t",
            "DELETE FROM protocolos.template_documento WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest.mark.asyncio
async def test_clonar_template_duplica_com_nome_diferente(admin_engine):
    tenant, user, unidade_id = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            original = await svc.criar_template(
                db, tenant_id=tenant.id, usuario_id=user.id,
                payload=TemplateDocumentoCreate(
                    nome="Ofício padrão", corpo_html="<p>{{processo.numero}}</p>",
                    id_unidade_trabalho=unidade_id,
                ),
            )
        async with _sm(admin_engine)() as db:
            clone = await svc.clonar_template(
                db, tenant_id=tenant.id, template_id=original.id, usuario_id=user.id,
            )
        assert clone.id != original.id
        assert clone.nome == "Ofício padrão (cópia)"
        assert clone.corpo_html == original.corpo_html
        assert clone.id_unidade_trabalho == unidade_id
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_clonar_template_duas_vezes_numera(admin_engine):
    tenant, user, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            original = await svc.criar_template(
                db, tenant_id=tenant.id, usuario_id=user.id,
                payload=TemplateDocumentoCreate(nome="Memorando", corpo_html="<p>x</p>"),
            )
        async with _sm(admin_engine)() as db:
            clone1 = await svc.clonar_template(
                db, tenant_id=tenant.id, template_id=original.id, usuario_id=user.id,
            )
        async with _sm(admin_engine)() as db:
            clone2 = await svc.clonar_template(
                db, tenant_id=tenant.id, template_id=original.id, usuario_id=user.id,
            )
        assert clone1.nome == "Memorando (cópia)"
        assert clone2.nome == "Memorando (cópia 2)"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_listar_templates_filtra_por_unidade(admin_engine):
    tenant, user, unidade_id = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            await svc.criar_template(
                db, tenant_id=tenant.id, usuario_id=user.id,
                payload=TemplateDocumentoCreate(
                    nome="Da unidade", corpo_html="<p>x</p>", id_unidade_trabalho=unidade_id,
                ),
            )
            await svc.criar_template(
                db, tenant_id=tenant.id, usuario_id=user.id,
                payload=TemplateDocumentoCreate(nome="Do tenant", corpo_html="<p>x</p>"),
            )

        async with _sm(admin_engine)() as db:
            so_unidade = await svc.listar_templates(
                db, tenant_id=tenant.id, id_unidade_trabalho=unidade_id,
            )
        assert [t.nome for t in so_unidade] == ["Da unidade"]

        async with _sm(admin_engine)() as db:
            todos = await svc.listar_templates(db, tenant_id=tenant.id)
        assert sorted(t.nome for t in todos) == ["Da unidade", "Do tenant"]
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_build_context_traz_destinatario_e_numero_documento(admin_engine):
    tenant, user, unidade_id = await _provisionar(admin_engine)
    processo_id = await _criar_processo(admin_engine, tenant.id, unidade_id)
    try:
        async with _sm(admin_engine)() as db:
            processo = await svc._obter_processo(
                db, tenant_id=tenant.id, processo_id=processo_id
            )
            from app.services import placeholders as ph

            contexto = await ph.build_context(
                db, tenant_id=tenant.id, processo=processo, usuario=user,
                destinatario="Secretaria de Obras",
            )
        assert contexto["destinatario.nome"] == "Secretaria de Obras"
        assert contexto["documento.numero"] == "1"  # processo sem anexo ainda
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_criar_minuta_resolve_destinatario_e_numero_no_corpo(admin_engine):
    tenant, user, unidade_id = await _provisionar(admin_engine)
    processo_id = await _criar_processo(admin_engine, tenant.id, unidade_id)
    try:
        async with _sm(admin_engine)() as db:
            template = await svc.criar_template(
                db, tenant_id=tenant.id, usuario_id=user.id,
                payload=TemplateDocumentoCreate(
                    nome="Ofício com destinatário",
                    corpo_html="<p>Para: {{destinatario.nome}} — Doc {{documento.numero}}</p>",
                ),
            )
        async with _sm(admin_engine)() as db:
            minuta = await svc.criar_minuta(
                db, tenant_id=tenant.id, processo_id=processo_id, usuario=user,
                payload=MinutaCreate(
                    titulo="Ofício", origem="interno",
                    id_template_origem=template.id,
                    destinatario="Câmara Municipal",
                ),
            )
        assert "Para: Câmara Municipal" in minuta.corpo_html
        assert "Doc 1" in minuta.corpo_html
        assert minuta.destinatario == "Câmara Municipal"
    finally:
        await _cleanup(admin_engine, tenant.id)
