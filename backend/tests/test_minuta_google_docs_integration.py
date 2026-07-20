"""Testes para Google Docs integration (PR-F).

Testes de modelo Minuta: campos Google, validações básicas.
"""
from __future__ import annotations

from app.models.minuta import Minuta


def test_minuta_google_doc_fields():
    """Minuta pode armazenar campos Google Docs."""
    minuta = Minuta(
        tenant_id=1,
        id_processo=100,
        titulo="Despacho via Google",
        origem="google",
        status="rascunho",
        versao=1,
        google_doc_id="abc-123-def",
        google_doc_url="https://docs.google.com/document/d/abc-123-def/edit",
        ativo=True,
        excluido=False,
    )

    assert minuta.google_doc_id == "abc-123-def"
    assert minuta.google_doc_url == "https://docs.google.com/document/d/abc-123-def/edit"
    assert minuta.origem == "google"


def test_minuta_origem_interno():
    """Minuta origem=interno não exige Google Doc URL."""
    minuta = Minuta(
        tenant_id=1,
        id_processo=100,
        titulo="Despacho Interno",
        origem="interno",
        status="rascunho",
        versao=1,
        corpo_html="<p>Conteúdo</p>",
        ativo=True,
        excluido=False,
    )

    assert minuta.origem == "interno"
    assert minuta.google_doc_id is None
    assert minuta.google_doc_url is None
