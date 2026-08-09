"""Upload e serving de imagens embutidas no editor rico (Novo Processo,
Templates de Documento, Minutas — todos compartilham o mesmo `RichTextEditor`).

Sem tabela própria de propósito: são recursos referenciados por URL dentro de
um HTML (`corpo`/`corpo_html`), não documentos de processo com trâmite/sigilo
próprios — não há hoje tela de listagem/gestão delas. Nome gerado (uuid4 hex)
evita colisão e serve como o próprio "token" de autorização de leitura: quem
não tiver a URL não adivinha o arquivo. Isolamento de tenant vem do path
(`tenant_editor_imagens_dir`), resolvido sempre a partir do tenant autenticado
da request — nunca de um slug informado pelo cliente.
"""
import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import tenant_editor_imagens_dir

ALLOWED_IMG_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMG_SIZE_MB = 5
_FILENAME_RE = re.compile(r"^[a-f0-9]{32}\.(png|jpe?g|gif|webp)$")


class EditorImagemError(Exception):
    pass


def _ext_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()[:10]


async def salvar_imagem(file: UploadFile, *, tenant_slug: str) -> str:
    """Valida, grava no disco e devolve o nome do arquivo gerado."""
    if not file.filename:
        raise EditorImagemError("Arquivo sem nome")
    ext = _ext_of(file.filename)
    if ext not in ALLOWED_IMG_EXTS:
        raise EditorImagemError(f"Extensão '.{ext}' não permitida — use png, jpg, gif ou webp")

    max_bytes = MAX_IMG_SIZE_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise EditorImagemError(f"Imagem excede {MAX_IMG_SIZE_MB} MB")

    filename = f"{uuid4().hex}.{ext}"
    path = tenant_editor_imagens_dir(tenant_slug) / filename
    path.write_bytes(content)
    return filename


def resolve_imagem_path(tenant_slug: str, filename: str) -> tuple[Path, str] | None:
    """Resolve o path físico + media_type, ou None se o nome for inválido/inexistente.

    O regex de `filename` é a defesa contra path traversal — só aceita o
    formato exato que `salvar_imagem` gera.
    """
    if not _FILENAME_RE.match(filename):
        return None
    path = tenant_editor_imagens_dir(tenant_slug) / filename
    if not path.is_file():
        return None
    media_type, _enc = mimetypes.guess_type(filename)
    return path, media_type or "application/octet-stream"
