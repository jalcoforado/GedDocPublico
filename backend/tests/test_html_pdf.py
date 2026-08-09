"""`services/html_pdf.py` — inlining de imagem local + bloqueio de rede (SSRF).

Cobertura nova: o módulo não tinha nenhum teste antes desta suíte. O caso de
"data: URI passa pelo url_fetcher e é bloqueado por engano" foi um bug real
encontrado ao testar manualmente o template de Ofício com brasão — o
`url_fetcher` customizado bloqueava QUALQUER url, inclusive `data:`, que não é
rede nenhuma. `test_data_uri_nao_e_bloqueada_pelo_url_fetcher` é a regressão
dele.
"""
import base64
import uuid

import pytest

from app.config import tenant_editor_imagens_dir
from app.services.html_pdf import _inline_imagens, _raise_no_remote, html_to_pdf_bytes

# PNG 1x1 válido (gerado via PIL — hex à mão já causou "Truncated File Read").
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
)


@pytest.fixture
def tenant_slug():
    slug = f"test-html-pdf-{uuid.uuid4().hex[:8]}"
    yield slug
    # tenant_editor_imagens_dir cria o diretório on-demand; limpa o que criamos.
    import shutil

    shutil.rmtree(tenant_editor_imagens_dir(slug), ignore_errors=True)


def test_inline_imagens_troca_por_data_uri(tenant_slug):
    path = tenant_editor_imagens_dir(tenant_slug) / "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"
    path.write_bytes(_PNG_1X1)

    html = '<img src="/api/v2/editor-imagens/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png" alt="x">'
    out = _inline_imagens(html, tenant_slug)

    assert "data:image/png;base64," in out
    assert base64.b64encode(_PNG_1X1).decode("ascii") in out
    assert "/api/v2/editor-imagens/" not in out


def test_inline_imagens_arquivo_ausente_mantem_src_original(tenant_slug):
    html = '<img src="/api/v2/editor-imagens/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png" alt="x">'
    out = _inline_imagens(html, tenant_slug)
    assert out == html


def test_data_uri_nao_e_bloqueada_pelo_url_fetcher(tenant_slug):
    """Regressão: `_raise_no_remote` bloqueava `data:` URI por engano — a
    imagem inlined nunca aparecia no PDF (WeasyPrint captura o erro e só
    omite a imagem, sem propagar exceção — por isso o bug não "quebrava"
    nada visivelmente, só sumia com a imagem)."""
    path = tenant_editor_imagens_dir(tenant_slug) / "cccccccccccccccccccccccccccccccc.png"
    path.write_bytes(_PNG_1X1)

    html = '<p>Texto</p><img src="/api/v2/editor-imagens/cccccccccccccccccccccccccccccccc.png" alt="x">'
    pdf = html_to_pdf_bytes(html, tenant_slug=tenant_slug)

    assert pdf.startswith(b"%PDF")
    # Sem tenant_slug, _inline_imagens nunca roda: o PDF sai bem menor (sem a
    # imagem embutida em base64) — diferença de tamanho é o teste indireto de
    # que a imagem REALMENTE entrou no documento.
    pdf_sem_imagem = html_to_pdf_bytes("<p>Texto</p>")
    assert len(pdf) > len(pdf_sem_imagem) + len(_PNG_1X1) // 2


def test_raise_no_remote_bloqueia_url_externa():
    """SSRF: testado direto na função, não via `html_to_pdf_bytes` — o
    WeasyPrint CAPTURA a exceção do `url_fetcher` e só loga (não propaga,
    confirmado empiricamente), então observar o PDF final não provaria nada
    sobre o bloqueio ter acontecido."""
    with pytest.raises(ValueError):
        _raise_no_remote("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ValueError):
        _raise_no_remote("https://example.com/logo.png")


def test_raise_no_remote_permite_data_uri():
    """O desvio que corrige a regressão: `data:` não é rede, tem que passar."""
    result = _raise_no_remote(
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR"
        "42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    assert isinstance(result, dict)


def test_html_to_pdf_bytes_sem_tenant_slug_ignora_inlining():
    """Chamador que nunca produz `<img>` (ordem de pagamento) não muda de
    comportamento: sem `tenant_slug`, nada tenta resolver imagem nenhuma."""
    pdf = html_to_pdf_bytes("<p>Ordem de pagamento sem imagem</p>", titulo="Teste")
    assert pdf.startswith(b"%PDF")
