"""`services/editor_imagens.py` — upload e serving de imagens do editor rico.

Sem tabela própria (ver docstring do módulo) — a superfície de teste é
validação de extensão/tamanho no upload e a defesa de path traversal na
resolução de leitura.
"""
import io
import shutil
import uuid

import pytest
from fastapi import UploadFile

from app.config import tenant_editor_imagens_dir
from app.services.editor_imagens import (
    EditorImagemError,
    resolve_imagem_path,
    salvar_imagem,
)

_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
)


@pytest.fixture
def tenant_slug():
    slug = f"test-editor-img-{uuid.uuid4().hex[:8]}"
    yield slug
    shutil.rmtree(tenant_editor_imagens_dir(slug), ignore_errors=True)


@pytest.mark.asyncio
async def test_salvar_imagem_grava_e_devolve_nome_gerado(tenant_slug):
    f = UploadFile(filename="brasao.png", file=io.BytesIO(_PNG_1X1))
    filename = await salvar_imagem(f, tenant_slug=tenant_slug)

    assert filename.endswith(".png")
    assert (tenant_editor_imagens_dir(tenant_slug) / filename).is_file()
    # Nome gerado (uuid4 hex), não o nome original do upload.
    assert filename != "brasao.png"


@pytest.mark.asyncio
async def test_salvar_imagem_rejeita_extensao_nao_permitida(tenant_slug):
    f = UploadFile(filename="script.svg", file=io.BytesIO(b"<svg></svg>"))
    with pytest.raises(EditorImagemError, match="não permitida"):
        await salvar_imagem(f, tenant_slug=tenant_slug)


@pytest.mark.asyncio
async def test_salvar_imagem_rejeita_arquivo_grande_demais(tenant_slug, monkeypatch):
    import app.services.editor_imagens as mod

    monkeypatch.setattr(mod, "MAX_IMG_SIZE_MB", 0)  # qualquer coisa já excede
    f = UploadFile(filename="foto.png", file=io.BytesIO(_PNG_1X1))
    with pytest.raises(EditorImagemError, match="excede"):
        await salvar_imagem(f, tenant_slug=tenant_slug)


@pytest.mark.asyncio
async def test_resolve_imagem_path_encontra_arquivo_salvo(tenant_slug):
    f = UploadFile(filename="foto.png", file=io.BytesIO(_PNG_1X1))
    filename = await salvar_imagem(f, tenant_slug=tenant_slug)

    resolved = resolve_imagem_path(tenant_slug, filename)
    assert resolved is not None
    path, media_type = resolved
    assert path.read_bytes() == _PNG_1X1
    assert media_type == "image/png"


def test_resolve_imagem_path_bloqueia_path_traversal(tenant_slug):
    for tentativa in (
        "../../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "a" * 32 + ".png/../../etc/passwd",
        "naoeuuidvalido.png",
    ):
        assert resolve_imagem_path(tenant_slug, tentativa) is None


def test_resolve_imagem_path_none_se_nao_existe(tenant_slug):
    nome_valido_mas_inexistente = "f" * 32 + ".png"
    assert resolve_imagem_path(tenant_slug, nome_valido_mas_inexistente) is None
