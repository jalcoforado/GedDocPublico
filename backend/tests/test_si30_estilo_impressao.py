"""SI-30 — a pré-visualização da minuta usa o MESMO CSS do PDF final.

O endpoint devolve o `CSS_DOCUMENTO` do `html_pdf` e, desde o SI-53, o papel
timbrado da prefeitura (só por isso lê o banco: o nome e o brasão são do
tenant). O que se trava aqui é que ele é exatamente o estilo com que
`html_to_pdf_bytes` imprime (uma fonte só), e que a rota não é engolida por
`/{template_id}`.
"""
from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.models import Tenant
from app.routers.minutas import estilo_impressao, templates_router
from app.services import html_pdf
from app.services.papel_timbrado import papel_timbrado


async def test_endpoint_devolve_o_css_do_pdf(admin_session):
    tenant = (
        await admin_session.execute(
            select(Tenant).where(Tenant.slug == get_settings().default_tenant_slug)
        )
    ).scalar_one()
    r = await estilo_impressao(_=None, tenant_id=tenant.id, db=admin_session)
    timbre = papel_timbrado(tenant)
    assert r == {
        "css": html_pdf.CSS_DOCUMENTO,
        "css_tela": html_pdf.CSS_PRE_VISUALIZACAO,
        "cabecalho_html": timbre.cabecalho_html(),
        "rodape_html": timbre.rodape_html(),
    }
    # A moldura da tela não é o documento: nada dela pode ir para o PDF.
    assert ".folha" not in html_pdf.CSS_DOCUMENTO
    # É o mesmo objeto que o PDF usa, não uma cópia que pode divergir.
    assert html_pdf.CSS_DOCUMENTO is html_pdf._CSS
    assert "doc-titulo" in r["css"] and "@page" in r["css"]


def test_rota_vem_antes_da_rota_de_id():
    """`GET /templates-documento/estilo-impressao` declarada depois de
    `/{template_id}` cairia nela e responderia 422 ("id não é inteiro")."""
    caminhos = [getattr(r, "path", "") for r in templates_router.routes]
    estilo = caminhos.index("/templates-documento/estilo-impressao")
    por_id = caminhos.index("/templates-documento/{template_id}")
    assert estilo < por_id


def test_marca_de_campo_do_modelo_so_na_tela():
    """SI-31: na prévia do MODELO o `{{campo}}` é marcado como campo — estilo
    da tela, nunca do PDF."""
    assert "mark.campo-modelo" in html_pdf.CSS_PRE_VISUALIZACAO
    assert "campo-modelo" not in html_pdf.CSS_DOCUMENTO
