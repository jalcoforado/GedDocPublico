"""SI-53 — modelo padrão da prefeitura e papel timbrado nos documentos.

Duas partes:

1. **Modelo padrão** (`template_documento.padrao`, migration 0143): no máximo
   um por prefeitura; marcar um desmarca o anterior; modelo inativo ou
   excluído não fica padrão. O `seed_itaitinga --parte documento` cria o de
   Itaitinga sem tomar o lugar de um padrão escolhido na tela.
2. **Papel timbrado** (`services/papel_timbrado.py`): brasão e nome no topo,
   rodapé fixo, no PDF do documento redigido — e só nele; os PDFs de
   pagamentos não pedem timbre e não mudam.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_itaitinga import MODELO_PADRAO_NOME, _aplicar_documento
from app.models import TemplateDocumento, Tenant
from app.schemas.minuta import TemplateDocumentoCreate, TemplateDocumentoUpdate
from app.services import minutas as svc
from app.services.html_pdf import html_to_pdf_bytes
from app.services.papel_timbrado import papel_timbrado


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def tenant_id(admin_engine):
    slug = f"si53-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text(
                    "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
                    "VALUES (:slug, 'Prefeitura SI-53', true, 'basico', :now) RETURNING id"
                ),
                {"slug": slug, "now": datetime.now()},
            )
        ).scalar_one()
        await s.commit()
    yield tid
    async with _sm(admin_engine)() as s:
        await s.execute(text("SET lock_timeout = '15s'"))
        await s.execute(
            text("DELETE FROM protocolos.template_documento WHERE tenant_id = :t"), {"t": tid}
        )
        await s.execute(text("DELETE FROM aprimora_py.tenant WHERE id = :t"), {"t": tid})
        await s.commit()


async def _criar(engine, tid: int, nome: str, **extra) -> TemplateDocumento:
    async with _sm(engine)() as db:
        return await svc.criar_template(
            db, tenant_id=tid, usuario_id=None,
            payload=TemplateDocumentoCreate(nome=nome, corpo_html="<p>x</p>", **extra),
        )


async def _padroes(engine, tid: int) -> list[str]:
    async with _sm(engine)() as db:
        return list(
            (
                await db.execute(
                    select(TemplateDocumento.nome).where(
                        TemplateDocumento.tenant_id == tid,
                        TemplateDocumento.padrao.is_(True),
                    )
                )
            ).scalars()
        )


# ---------------------------------------------------------------- padrão ----


@pytest.mark.asyncio
async def test_marcar_padrao_desmarca_o_anterior(admin_engine, tenant_id):
    await _criar(admin_engine, tenant_id, "Ofício", padrao=True)
    b = await _criar(admin_engine, tenant_id, "Despacho")
    assert await _padroes(admin_engine, tenant_id) == ["Ofício"]

    async with _sm(admin_engine)() as db:
        await svc.atualizar_template(
            db, tenant_id=tenant_id, template_id=b.id,
            payload=TemplateDocumentoUpdate(padrao=True),
        )
    assert await _padroes(admin_engine, tenant_id) == ["Despacho"]

    # Criar já marcado também desmarca.
    await _criar(admin_engine, tenant_id, "Memorando", padrao=True)
    assert await _padroes(admin_engine, tenant_id) == ["Memorando"]


@pytest.mark.asyncio
async def test_modelo_inativo_nao_pode_ser_padrao(admin_engine, tenant_id):
    with pytest.raises(HTTPException) as e:
        await _criar(admin_engine, tenant_id, "Inativo", padrao=True, ativo=False)
    assert e.value.status_code == 409

    t = await _criar(admin_engine, tenant_id, "Ativo", padrao=True)
    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await svc.atualizar_template(
                db, tenant_id=tenant_id, template_id=t.id,
                payload=TemplateDocumentoUpdate(padrao=True, ativo=False),
            )
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_desativar_ou_excluir_o_padrao_tira_a_marca(admin_engine, tenant_id):
    a = await _criar(admin_engine, tenant_id, "A", padrao=True)
    async with _sm(admin_engine)() as db:
        await svc.atualizar_template(
            db, tenant_id=tenant_id, template_id=a.id,
            payload=TemplateDocumentoUpdate(ativo=False),
        )
    assert await _padroes(admin_engine, tenant_id) == []

    b = await _criar(admin_engine, tenant_id, "B", padrao=True)
    async with _sm(admin_engine)() as db:
        await svc.excluir_template(db, tenant_id=tenant_id, template_id=b.id)
    assert await _padroes(admin_engine, tenant_id) == []


@pytest.mark.asyncio
async def test_clone_do_padrao_nao_nasce_padrao(admin_engine, tenant_id):
    a = await _criar(admin_engine, tenant_id, "A", padrao=True)
    async with _sm(admin_engine)() as db:
        clone = await svc.clonar_template(
            db, tenant_id=tenant_id, template_id=a.id, usuario_id=None
        )
    assert clone.padrao is False
    assert await _padroes(admin_engine, tenant_id) == ["A"]


@pytest.mark.asyncio
async def test_banco_recusa_dois_padroes_na_mesma_prefeitura(admin_engine, tenant_id):
    """O service desmarca antes; o índice único parcial (0143) é a rede."""
    await _criar(admin_engine, tenant_id, "A", padrao=True)
    async with _sm(admin_engine)() as db:
        db.add(TemplateDocumento(
            tenant_id=tenant_id, nome="B", corpo_html="<p>x</p>", ativo=True,
            padrao=True, criado_em=datetime.utcnow(),
        ))
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_padrao_de_outra_prefeitura_nao_interfere(admin_engine, tenant_id, two_tenants):
    outro, _ = two_tenants
    await _criar(admin_engine, tenant_id, "Daqui", padrao=True)
    async with _sm(admin_engine)() as db:
        await svc.criar_template(
            db, tenant_id=outro, usuario_id=None,
            payload=TemplateDocumentoCreate(nome="De lá", corpo_html="<p>x</p>", padrao=True),
        )
    try:
        assert await _padroes(admin_engine, tenant_id) == ["Daqui"]
        assert await _padroes(admin_engine, outro) == ["De lá"]
    finally:
        async with _sm(admin_engine)() as db:
            await db.execute(
                text("DELETE FROM protocolos.template_documento WHERE tenant_id = :t"),
                {"t": outro},
            )
            await db.commit()


# ------------------------------------------------------------------ seed ----


@pytest.mark.asyncio
async def test_seed_cria_o_modelo_de_itaitinga_como_padrao_e_e_idempotente(
    admin_engine, tenant_id
):
    async with _sm(admin_engine)() as db:
        r1 = await _aplicar_documento(db, tenant_id)
    async with _sm(admin_engine)() as db:
        r2 = await _aplicar_documento(db, tenant_id)
    assert r1["modelo_criado"] and r1["modelo_marcado_como_padrao"]
    assert not r2["modelo_criado"]
    assert await _padroes(admin_engine, tenant_id) == [MODELO_PADRAO_NOME]


@pytest.mark.asyncio
async def test_seed_nao_toma_o_lugar_do_padrao_escolhido_na_tela(admin_engine, tenant_id):
    await _criar(admin_engine, tenant_id, "Escolhido pela prefeitura", padrao=True)
    async with _sm(admin_engine)() as db:
        r = await _aplicar_documento(db, tenant_id)
    assert r["modelo_criado"] and not r["modelo_marcado_como_padrao"]
    assert await _padroes(admin_engine, tenant_id) == ["Escolhido pela prefeitura"]


# --------------------------------------------------------- papel timbrado ----


def _tenant(**campos) -> Tenant:
    return Tenant(nome="Prefeitura de Itaitinga", **campos)


def test_timbre_le_o_brasao_do_disco_e_monta_o_rodape():
    pt = papel_timbrado(_tenant(
        logo_url="/brand/itaitinga-brasao.png",
        endereco="Av. Cel. Virgílio Távora, 1710",
        telefone_institucional="(85) 3513-2002",
        site_oficial="https://www.itaitinga.ce.gov.br/",
    ))
    assert pt.brasao_data_uri and pt.brasao_data_uri.startswith("data:image/png;base64,")
    assert 'class="timbre-brasao"' in pt.cabecalho_html()
    assert "Prefeitura de Itaitinga" in pt.cabecalho_html()
    assert pt.linhas_rodape == (
        "Av. Cel. Virgílio Távora, 1710", "(85) 3513-2002", "www.itaitinga.ce.gov.br",
    )


@pytest.mark.parametrize("logo_url", [
    None,
    "/brand/nao-existe.png",
    "/brand/../../config.py",
    "/brand/sub/itaitinga-brasao.png",
    "https://exemplo.com/brand/itaitinga-brasao.png",
])
def test_timbre_sem_brasao_valido_sai_so_com_o_nome(logo_url):
    pt = papel_timbrado(_tenant(logo_url=logo_url))
    assert pt.brasao_data_uri is None
    assert "<img" not in pt.cabecalho_html()
    assert "Prefeitura de Itaitinga" in pt.cabecalho_html()
    assert pt.rodape_html() == ""


def test_nome_da_prefeitura_e_escapado():
    pt = papel_timbrado(Tenant(nome="<script>x</script>"))
    assert "<script>" not in pt.cabecalho_html()


def _texto(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_com_timbre_tem_nome_e_rodape_em_toda_pagina():
    pt = papel_timbrado(_tenant(
        logo_url="/brand/itaitinga-brasao.png", telefone_institucional="(85) 3513-2002",
    ))
    corpo = "<p>" + "Texto longo do despacho. " * 900 + "</p>"
    pdf = html_to_pdf_bytes(corpo, titulo="Despacho", timbre=pt)
    paginas = PdfReader(io.BytesIO(pdf)).pages
    assert len(paginas) > 1
    assert "PREFEITURA DE ITAITINGA" in paginas[0].extract_text()
    assert all("(85) 3513-2002" in p.extract_text() for p in paginas)
    # Brasão embutido como imagem (nenhum fetch: veio em data:).
    assert len(paginas[0].images) == 1


def test_pdf_sem_timbre_nao_muda():
    """Ordem de pagamento e exportações não passam `timbre`."""
    pdf = html_to_pdf_bytes("<p>Linha</p>", titulo="Ordem de Pagamento 1")
    texto = _texto(pdf)
    assert "PREFEITURA" not in texto.upper()
    assert "Ordem de Pagamento 1" in texto
