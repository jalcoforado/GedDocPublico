"""Cota de anexação por processo, por nível de sigilo (fatia F6, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

Por que checar ANTES de gravar: recusar depois de escrever o arquivo no
storage deixaria bytes órfãos no disco sem `Anexo` nenhum apontando pra eles
— o teste de excesso confirma que nada é persistido quando a cota estoura.

Os testes empurram o uso perto do limite por UPDATE direto em
`tamanho_bytes` de um anexo existente, em vez de alocar ~200 MB de conteúdo
de verdade — mais rápido, e o que importa é a soma, não o arquivo em si.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Anexo,
    AnexoProcesso,
    Assunto,
    Manifestante,
    Movimentacao,
    Processo,
    TipoProcesso,
)
from app.services import cota_anexacao
from app.services.anexos import AnexoError, _criar_anexo_from_bytes
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def test_limite_bytes_por_sigilo():
    assert cota_anexacao.limite_bytes("ostensivo") == 200 * 1024 * 1024
    assert cota_anexacao.limite_bytes("interno") == 400 * 1024 * 1024
    assert cota_anexacao.limite_bytes("reservado") == 800 * 1024 * 1024
    assert cota_anexacao.limite_bytes("secreto") == 1200 * 1024 * 1024
    assert cota_anexacao.limite_bytes("ultrassecreto") == 2000 * 1024 * 1024
    # Nível desconhecido cai no piso — conservador, não no teto.
    assert cota_anexacao.limite_bytes("valor-nunca-visto") == 200 * 1024 * 1024


@pytest_asyncio.fixture
async def cen(admin_engine):
    slug = _slug("f6-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F6",
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
        processo.id_ultima_movimentacao = mov.id

        # Anexo pré-existente perto do limite: 200 MB - 500.000 bytes, deixando
        # ~488 KB de folga — o suficiente pra testar a fronteira sem alocar
        # 200 MB de conteúdo de verdade.
        perto_do_limite = 200 * 1024 * 1024 - 500_000
        anexo_existente = Anexo(
            tenant_id=tenant.id,
            publico=True,
            ativo=True,
            excluido=False,
            e_doc=f"{slug}-existente.pdf",
            descricao="Anexo existente",
            tamanho_bytes=perto_do_limite,
        )
        s.add(anexo_existente)
        await s.flush()
        s.add(
            AnexoProcesso(
                tenant_id=tenant.id,
                id_processo=processo.id,
                id_anexo=anexo_existente.id,
                id_movimentacao=mov.id,
                ativo=True,
                excluido=False,
                ordem=1,
            )
        )
        await s.commit()

        dados = {
            "tenant": tenant,
            "processo_id": processo.id,
            "usado_previo": perto_do_limite,
        }

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
async def test_usado_bytes_soma_so_anexo_ativo_e_nao_desentranhado(admin_engine, cen):
    async with _sm(admin_engine)() as s:
        usado = await cota_anexacao.usado_bytes(
            s, cen["processo_id"], cen["tenant"].id
        )
    assert usado == cen["usado_previo"]


@pytest.mark.asyncio
async def test_upload_dentro_da_folga_e_aceito(admin_engine, cen):
    conteudo = b"x" * 100_000  # bem menor que a folga de ~488 KB
    async with _sm(admin_engine)() as s:
        anexo = await _criar_anexo_from_bytes(
            s,
            cen["processo_id"],
            content=conteudo,
            filename="pequeno.txt",
            tenant_id=cen["tenant"].id,
            tenant_slug=cen["tenant"].slug,
            descricao="pequeno",
            id_tipo_anexo=None,
            publico=True,
            usuario_id=None,
        )
        await s.commit()
    assert anexo.id is not None

    async with _sm(admin_engine)() as s:
        usado = await cota_anexacao.usado_bytes(
            s, cen["processo_id"], cen["tenant"].id
        )
    assert usado == cen["usado_previo"] + 100_000


@pytest.mark.asyncio
async def test_upload_alem_da_folga_e_recusado_e_nao_persiste(admin_engine, cen):
    conteudo = b"x" * 900_000  # maior que a folga de ~488 KB
    async with _sm(admin_engine)() as s:
        with pytest.raises(AnexoError, match="[Cc]ota"):
            await _criar_anexo_from_bytes(
                s,
                cen["processo_id"],
                content=conteudo,
                filename="grande.txt",
                tenant_id=cen["tenant"].id,
                tenant_slug=cen["tenant"].slug,
                descricao="grande",
                id_tipo_anexo=None,
                publico=True,
                usuario_id=None,
            )
        await s.rollback()

    # Nada foi persistido — nem a linha, nem (por consequência) o arquivo.
    async with _sm(admin_engine)() as s:
        usado = await cota_anexacao.usado_bytes(
            s, cen["processo_id"], cen["tenant"].id
        )
        restantes = (
            await s.execute(
                select(Anexo.descricao).where(
                    Anexo.tenant_id == cen["tenant"].id,
                    Anexo.descricao == "grande",
                )
            )
        ).scalars().all()
    assert usado == cen["usado_previo"]
    assert restantes == []
