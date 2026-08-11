"""`services/pdf_montagem.py` — PDF completo do processo (capa + anexos).

Regressão real: `gerar_processo_completo_pdf` procurava o arquivo do anexo em
`settings.uploads_dir` (caminho legado, achatado) mesmo depois da Fase 14 ter
migrado o storage pra `tenant_anexos_dir(tenant_slug)` — todo anexo criado
desde então era silenciosamente OMITIDO do "PDF completo" (sem erro nenhum,
o PDF só saía com a capa). Achado testando manualmente com minutas
finalizadas em PDF que nunca apareciam no processo materializado.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from pypdf import PdfReader, PdfWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings, tenant_anexos_dir
from app.routers.processos import get_processo_detail
from app.services.pdf_montagem import gerar_processo_completo_pdf


def _pdf_valido() -> bytes:
    """PDF mínimo de 1 página válido — o bastante pra PdfReader não recusar."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _sessao(admin_engine):
    return async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)()


async def _catalogos(s: AsyncSession, tenant_id: int) -> dict[str, int]:
    sfx = uuid.uuid4().hex[:8]
    categoria = int((await s.execute(text(
        "INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) "
        "VALUES (:n, 'PF', true, false) RETURNING id"
    ), {"n": f"PdfMont {sfx}"})).scalar_one())
    tipo_manif = int((await s.execute(text(
        "INSERT INTO protocolos.tipo_manifestante "
        "(tenant_id, tipo_manifestante, id_categoria, ativo, excluido) "
        "VALUES (:t, :n, :c, true, false) RETURNING id"
    ), {"t": tenant_id, "n": f"PdfMont {sfx}", "c": categoria})).scalar_one())
    manifestante = int((await s.execute(text(
        "INSERT INTO protocolos.manifestante "
        "(tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
        "VALUES (:t, :tm, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "tm": tipo_manif, "n": f"PdfMont {sfx}"})).scalar_one())
    unidade = int((await s.execute(text(
        "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) "
        "VALUES (:t, :n, false) RETURNING id"
    ), {"t": tenant_id, "n": f"PdfMont {sfx}"})).scalar_one())
    tipo_proc = int((await s.execute(text(
        "INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) "
        "VALUES (:t, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "n": f"PdfMont {sfx}"})).scalar_one())
    assunto = int((await s.execute(text(
        "INSERT INTO protocolos.assunto "
        "(tenant_id, id_tipo_processo, assunto, ativo, excluido) "
        "VALUES (:t, :tp, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "tp": tipo_proc, "n": f"PdfMont {sfx}"})).scalar_one())
    return {
        "categoria": categoria,
        "manifestante": manifestante,
        "unidade": unidade,
        "assunto": assunto,
    }


async def _processo(s: AsyncSession, tenant_id: int, cat: dict) -> int:
    return int((await s.execute(text(
        """
        INSERT INTO protocolos.processo
            (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
             numero_processo, nivel_sigilo, virtual, externo, ativo, excluido,
             migrado, data_hora_abertura)
        VALUES (:t, :a, :m, :u, :n, 'ostensivo', true, false, true, false, false, NOW())
        RETURNING id
        """
    ), {
        "t": tenant_id, "a": cat["assunto"], "m": cat["manifestante"],
        "u": cat["unidade"], "n": f"PM{uuid.uuid4().hex[:6]}/2026",
    })).scalar_one())


async def _anexo_pdf(
    s: AsyncSession, tenant_id: int, tenant_slug: str, processo_id: int, unidade_id: int,
) -> int:
    movimentacao = int((await s.execute(text(
        "INSERT INTO protocolos.movimentacao "
        "(tenant_id, id_processo, id_unidade_responsavel, id_acao, "
        " data_hora_movimentacao, ativo, excluido) "
        "SELECT :t, :p, :u, id, NOW(), true, false "
        "FROM protocolos.acao WHERE flag = 'ABERTURA' LIMIT 1 RETURNING id"
    ), {"t": tenant_id, "p": processo_id, "u": unidade_id})).scalar_one())
    anexo_id = int((await s.execute(text(
        "INSERT INTO protocolos.anexo "
        "(tenant_id, publico, ativo, excluido, descricao) "
        "VALUES (:t, true, true, false, 'anexo pdf de teste') RETURNING id"
    ), {"t": tenant_id})).scalar_one())
    e_doc = f"{anexo_id}.pdf"
    await s.execute(text(
        "UPDATE protocolos.anexo SET e_doc = :e WHERE id = :i"
    ), {"e": e_doc, "i": anexo_id})
    await s.execute(text(
        "INSERT INTO protocolos.anexo_processo "
        "(tenant_id, id_processo, id_anexo, id_movimentacao, ordem, ativo, "
        " excluido, anexo_herdado) "
        "VALUES (:t, :p, :a, :m, 1, true, false, false)"
    ), {"t": tenant_id, "p": processo_id, "a": anexo_id, "m": movimentacao})
    # Storage por tenant (Fase 14) — é aqui que _criar_anexo_from_bytes grava
    # de verdade; é o caminho que a regressão não procurava.
    destino = tenant_anexos_dir(tenant_slug) / e_doc
    destino.write_bytes(_pdf_valido())
    return anexo_id


@pytest_asyncio.fixture
async def ambiente(admin_engine, two_tenants):
    tid, _outro = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        slug = (await s.execute(text(
            "SELECT slug FROM aprimora_py.tenant WHERE id = :t"
        ), {"t": tid})).scalar_one()
        cat = await _catalogos(s, tid)
        processo_id = await _processo(s, tid, cat)
        anexo_id = await _anexo_pdf(s, tid, slug, processo_id, cat["unidade"])
        await s.commit()

    yield {"tenant_id": tid, "tenant_slug": slug, "processo_id": processo_id, "anexo_id": anexo_id}

    # Movimentação/processo seguram o tenant por FK — sem apagá-los aqui, o
    # teardown do `two_tenants` estoura com ForeignKeyViolationError longe
    # da causa (mesma armadilha documentada em test_guarda_anexo_sigiloso.py).
    async with Session() as s:
        await s.execute(text("DELETE FROM protocolos.anexo_processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.movimentacao WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.assunto WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.tipo_processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM utils.unidade_trabalho WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.manifestante WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.tipo_manifestante WHERE tenant_id = :t"), {"t": tid})
        # categoria é catálogo global (sem tenant_id) — limpa por id.
        await s.execute(text("DELETE FROM protocolos.categoria WHERE id = :i"), {"i": cat["categoria"]})
        await s.commit()


@pytest.mark.asyncio
async def test_completo_pdf_inclui_anexo_do_storage_por_tenant(admin_engine, ambiente):
    """Regressão principal: anexo gravado em tenant_anexos_dir (o caminho real
    desde a Fase 14) tem que aparecer no PDF completo, não só a capa."""
    a = ambiente
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as db:
        detail = await get_processo_detail(db, a["processo_id"], tenant_id=a["tenant_id"])

    capa_only = gerar_processo_completo_pdf(
        detail.model_copy(update={"anexos": []}), tenant_slug=a["tenant_slug"]
    )
    completo = gerar_processo_completo_pdf(detail, tenant_slug=a["tenant_slug"])

    paginas_capa = len(PdfReader(io.BytesIO(capa_only)).pages)
    paginas_completo = len(PdfReader(io.BytesIO(completo)).pages)

    assert paginas_completo > paginas_capa, (
        "o anexo do storage por tenant não entrou no PDF completo — "
        f"capa sozinha tem {paginas_capa} página(s), completo tem {paginas_completo}"
    )


@pytest.mark.asyncio
async def test_completo_pdf_usa_fallback_legacy_se_nao_achar_no_tenant(admin_engine, ambiente):
    """`resolve_anexo_path` cai pro path legado (uploads_dir/e_doc) quando o
    arquivo não está no storage por tenant — cobre anexo pré-Fase 14."""
    a = ambiente
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as db:
        detail = await get_processo_detail(db, a["processo_id"], tenant_id=a["tenant_id"])

    # Remove do storage por tenant e recria só no path legado.
    e_doc = f"{a['anexo_id']}.pdf"
    (tenant_anexos_dir(a["tenant_slug"]) / e_doc).unlink()
    legacy_dir = Path(get_settings().uploads_dir)
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = legacy_dir / e_doc
    legacy_path.write_bytes(_pdf_valido())
    try:
        completo = gerar_processo_completo_pdf(detail, tenant_slug=a["tenant_slug"])
        paginas = len(PdfReader(io.BytesIO(completo)).pages)
        assert paginas > 1, "fallback legado não encontrou o anexo"
    finally:
        legacy_path.unlink(missing_ok=True)
