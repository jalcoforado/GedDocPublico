"""Transporte Regulado P3.1 — Documentos de Alvarás.

Cobre criação, leitura, atualização e exclusão de documentos anexados a alvarás
com isolamento RLS tenant-scoped, validação de FK para alvará, e soft-delete.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraDocumentoCreate,
    AlvaraDocumentoUpdate,
    PermissionarioCreate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("alvdoc")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Alv Doc", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


async def _permissionario(admin_engine, tenant_id):
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome="Permissionário", cpf=_cpf(), tipo_servico="taxi",
            ),
        )


async def _alvara(admin_engine, tenant_id):
    perm = await _permissionario(admin_engine, tenant_id)
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_alvara(
            s, tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=f"ALV-{uuid.uuid4().hex[:8].upper()}",
                data_validade=datetime.utcnow().date() + timedelta(days=365),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )


# ========================= Testes de Documentos =============================


@pytest.mark.asyncio
async def test_alvara_documento_criar_basico(admin_engine):
    """Criar documento de alvará com tipo e arquivo."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="contrato",
                arquivo="contrato_2026.pdf",
            ),
        )

    assert doc.id is not None
    assert doc.tenant_id == tenant.id
    assert doc.id_alvara == alvara.id
    assert doc.tipo_documento == "contrato"
    assert doc.arquivo == "contrato_2026.pdf"
    assert doc.excluido is False


@pytest.mark.asyncio
async def test_alvara_documento_criar_com_observacoes(admin_engine):
    """Criar documento com observações opcionais."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="comprovante_endereco",
                arquivo="comprovante.pdf",
                observacoes="Endereço da empresa verificado",
            ),
        )

    assert doc.observacoes == "Endereço da empresa verificado"


@pytest.mark.asyncio
async def test_alvara_documento_criar_alvara_nao_existe(admin_engine):
    """Criar documento para alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.criar_alvara_documento(
                s, tenant_id=tenant.id, alvara_id=99999,
                payload=AlvaraDocumentoCreate(
                    tipo_documento="contrato",
                    arquivo="doc.pdf",
                ),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_obter_basico(admin_engine):
    """Obter documento por ID."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="procuracao",
                arquivo="procuracao.pdf",
            ),
        )
        doc_id = doc.id

        obtido = await tr_svc.obter_alvara_documento(s, tenant_id=tenant.id, documento_id=doc_id)

    assert obtido.id == doc_id
    assert obtido.tipo_documento == "procuracao"


@pytest.mark.asyncio
async def test_alvara_documento_obter_nao_existe(admin_engine):
    """Obter documento inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara_documento(s, tenant_id=tenant.id, documento_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_obter_excluido(admin_engine):
    """Obter documento soft-deletado retorna 404."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="contrato",
                arquivo="doc.pdf",
            ),
        )
        doc_id = doc.id

        # Soft-delete
        await tr_svc.excluir_alvara_documento(s, tenant_id=tenant.id, documento_id=doc_id)

        # Tentar obter
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara_documento(s, tenant_id=tenant.id, documento_id=doc_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_listar_basico(admin_engine):
    """Listar documentos de um alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc1 = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(tipo_documento="contrato", arquivo="a.pdf"),
        )

        doc2 = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(tipo_documento="procuracao", arquivo="b.pdf"),
        )

        docs, _ = await tr_svc.listar_alvara_documentos(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(docs) == 2
    # Ordenado por criado_em DESC (mais recente primeiro)
    assert docs[0].id == doc2.id
    assert docs[1].id == doc1.id


@pytest.mark.asyncio
async def test_alvara_documento_listar_vazio(admin_engine):
    """Listar documentos de alvará sem documentos retorna vazio."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        docs, _ = await tr_svc.listar_alvara_documentos(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(docs) == 0


@pytest.mark.asyncio
async def test_alvara_documento_listar_ignora_excluidos(admin_engine):
    """Listar documentos ignora soft-deletados."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc1 = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(tipo_documento="contrato", arquivo="a.pdf"),
        )

        doc2 = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(tipo_documento="procuracao", arquivo="b.pdf"),
        )

        # Soft-delete doc1
        await tr_svc.excluir_alvara_documento(s, tenant_id=tenant.id, documento_id=doc1.id)

        docs, _ = await tr_svc.listar_alvara_documentos(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(docs) == 1
    assert docs[0].id == doc2.id


@pytest.mark.asyncio
async def test_alvara_documento_atualizar_basico(admin_engine):
    """Atualizar documentos de alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="contrato",
                arquivo="old.pdf",
            ),
        )

        atualizado = await tr_svc.atualizar_alvara_documento(
            s, tenant_id=tenant.id, documento_id=doc.id,
            payload=AlvaraDocumentoUpdate(arquivo="new.pdf"),
        )

    assert atualizado.arquivo == "new.pdf"
    assert atualizado.tipo_documento == "contrato"  # Não alterado


@pytest.mark.asyncio
async def test_alvara_documento_atualizar_observacoes(admin_engine):
    """Atualizar observações de documento."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="contrato",
                arquivo="doc.pdf",
                observacoes="Versão 1",
            ),
        )

        atualizado = await tr_svc.atualizar_alvara_documento(
            s, tenant_id=tenant.id, documento_id=doc.id,
            payload=AlvaraDocumentoUpdate(observacoes="Versão 2 atualizada"),
        )

    assert atualizado.observacoes == "Versão 2 atualizada"


@pytest.mark.asyncio
async def test_alvara_documento_atualizar_nao_existe(admin_engine):
    """Atualizar documento inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.atualizar_alvara_documento(
                s, tenant_id=tenant.id, documento_id=99999,
                payload=AlvaraDocumentoUpdate(arquivo="new.pdf"),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_excluir_basico(admin_engine):
    """Soft-delete documento de alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraDocumentoCreate(
                tipo_documento="contrato",
                arquivo="doc.pdf",
            ),
        )
        doc_id = doc.id

        # Excluir
        await tr_svc.excluir_alvara_documento(s, tenant_id=tenant.id, documento_id=doc_id)

        # Verificar que está marcado como excluído
        with pytest.raises(HTTPException):
            await tr_svc.obter_alvara_documento(s, tenant_id=tenant.id, documento_id=doc_id)


@pytest.mark.asyncio
async def test_alvara_documento_excluir_nao_existe(admin_engine):
    """Excluir documento inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.excluir_alvara_documento(s, tenant_id=tenant.id, documento_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_rls_cross_tenant(admin_engine):
    """RLS: Documento de um tenant não visível em outro."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    alvara1 = await _alvara(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_alvara_documento(
            s, tenant_id=tenant1.id, alvara_id=alvara1.id,
            payload=AlvaraDocumentoCreate(tipo_documento="contrato", arquivo="doc.pdf"),
        )
        doc_id = doc.id

    # Tentar acessar como tenant2
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara_documento(s, tenant_id=tenant2.id, documento_id=doc_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_documento_listar_alvara_nao_existe(admin_engine):
    """Listar documentos de alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.listar_alvara_documentos(s, tenant_id=tenant.id, alvara_id=99999)

    assert exc.value.status_code == 404
