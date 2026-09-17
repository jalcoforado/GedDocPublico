"""Numeração de documento e de página do processo (fatia F8, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

Por que isto importa: hoje só o PDF consolidado (`pdf_montagem.py`) sabia em
que página cada anexo cai, e só depois de gerado. Citar "fls. 70" num
despacho exigia montar o PDF inteiro antes. `_load_anexos` agora expõe a
mesma numeração na listagem — mas como estimativa sobre `Anexo.qtd_paginas`
(calculado no upload, não relido aqui), não uma nova leitura de arquivo.

O caso que mais importa: anexo NÃO-PDF não conta para a página do processo
(pdf_montagem também o pula), mas CONTA para `documento_numero` (é um
documento do processo, só não entra no PDF consolidado).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models import (
    Anexo,
    AnexoProcesso,
    Assunto,
    Manifestante,
    Movimentacao,
    Processo,
    TipoProcesso,
)
from app.services.processos import _load_anexos
from app.services.provisioning_tenant import provisionar_tenant

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def cen(admin_engine):
    slug = _slug("f8-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F8",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )

    async with _sm(admin_engine)() as s:
        unidade_id = (
            await s.execute(
                text(
                    "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
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
        id_acao_abertura = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.acao WHERE flag='ABERTURA' "
                    "AND excluido=false LIMIT 1"
                )
            )
        ).scalar_one()

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

        processo = Processo(
            tenant_id=tenant.id,
            id_assunto=assunto.id,
            virtual=True,
            data_hora_abertura=datetime.now(),
            numero_processo=f"{slug}-p1",
            id_unidade_proprietaria=unidade_id,
            id_manifestante=manif.id,
            id_local_atual=unidade_id,
            nivel_sigilo="ostensivo",
            ativo=True,
            excluido=False,
        )
        s.add(processo)
        await s.flush()

        mov = Movimentacao(
            tenant_id=tenant.id,
            id_processo=processo.id,
            id_unidade_responsavel=unidade_id,
            id_acao=id_acao_abertura,
            data_hora_movimentacao=datetime.now(),
            ativo=True,
            excluido=False,
        )
        s.add(mov)
        await s.flush()

        # Três documentos, em ordem: PDF de 5 páginas, um DOCX (não conta
        # página do processo), e outro PDF de 3 páginas. `e_doc` é único
        # GLOBALMENTE (`anexo_e_doc_key`, sem tenant_id) — precisa do slug
        # pra não colidir com outro teste ou tenant residual do banco de dev.
        anexos_spec = [
            (f"{slug}-a.pdf", 5),
            (f"{slug}-b.docx", None),
            (f"{slug}-c.pdf", 3),
        ]
        anexo_ids: list[int] = []
        for i, (e_doc, qtd) in enumerate(anexos_spec, start=1):
            a = Anexo(
                tenant_id=tenant.id,
                publico=True,
                ativo=True,
                excluido=False,
                e_doc=e_doc,
                descricao=f"Documento {i}",
                qtd_paginas=qtd,
            )
            s.add(a)
            await s.flush()
            ap = AnexoProcesso(
                tenant_id=tenant.id,
                id_processo=processo.id,
                id_anexo=a.id,
                id_movimentacao=mov.id,
                ativo=True,
                excluido=False,
                ordem=i,
            )
            s.add(ap)
            anexo_ids.append(a.id)
        await s.commit()

        dados = {"tenant": tenant, "processo_id": processo.id, "anexo_ids": anexo_ids}

    yield dados

    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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


@pytest.mark.asyncio
async def test_numeracao_conta_todo_documento_mas_pagina_so_pdf(admin_engine, cen):
    async with _sm(admin_engine)() as s:
        anexos = await _load_anexos(s, cen["processo_id"], cen["tenant"].id)

    assert [a.documento_numero for a in anexos] == [1, 2, 3]
    # Capa = 1 página. a.pdf (5 pág) termina em 1+5=6. b.docx não conta.
    # c.pdf (3 pág) termina em 6+3=9.
    assert anexos[0].pagina_processo == 6
    assert anexos[1].pagina_processo is None
    assert anexos[2].pagina_processo == 9


@pytest.mark.asyncio
async def test_pdf_sem_qtd_paginas_conhecida_nao_avanca_nem_quebra(admin_engine, cen):
    """Upload que falhou o cálculo (`qtd_paginas=None`) não impede a listagem
    — só deixa a estimativa daquele documento em diante mais conservadora."""
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE protocolos.anexo SET qtd_paginas=NULL WHERE id=:id"),
            {"id": cen["anexo_ids"][0]},
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        anexos = await _load_anexos(s, cen["processo_id"], cen["tenant"].id)

    assert anexos[0].pagina_processo is None  # PDF, mas sem contagem
    assert anexos[2].pagina_processo == 4  # capa(1) + c.pdf(3), a.pdf não somou
