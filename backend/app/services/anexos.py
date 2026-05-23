"""Upload, download e soft-delete de anexos vinculados a processos.

Storage: filesystem do container (volume Docker), pasta `UPLOADS_DIR`.
Nome do arquivo no disco: `{anexo_id}.{ext}` — guardado no campo `e_doc`
da tabela (que tem unique constraint, garantindo 1-pra-1).

O vínculo `protocolos.anexo_processo` requer `id_movimentacao`. Para
simplificar (e seguir o padrão do PHP), usamos a `id_ultima_movimentacao`
do processo — o anexo "pertence" à movimentação corrente.
"""
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Anexo, AnexoProcesso, Processo


class AnexoError(Exception):
    pass


# Extensões aceitas + um MIME-lista mínima (fast-path)
ALLOWED_EXTS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
}


def _ext_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()[:10]


async def upload_anexo(
    db: AsyncSession,
    processo_id: int,
    file: UploadFile,
    *,
    descricao: str | None,
    id_tipo_anexo: int | None,
    publico: bool,
    usuario_id: int,
) -> Anexo:
    settings = get_settings()

    if not file.filename:
        raise AnexoError("Arquivo sem nome")
    ext = _ext_of(file.filename)
    if ext not in ALLOWED_EXTS:
        raise AnexoError(f"Extensão '.{ext}' não permitida")

    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id, Processo.excluido.is_(False)
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise AnexoError("Processo não encontrado")
    if not processo.ativo:
        raise AnexoError("Processo inativo — não permite anexos")
    if processo.id_ultima_movimentacao is None:
        raise AnexoError("Processo sem movimentação — abra-o antes de anexar")

    # Lê o conteúdo (com cap de tamanho).
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AnexoError(f"Arquivo excede {settings.max_upload_size_mb} MB")

    # Conta páginas pra PDF (best-effort: ignora erros).
    qtd_paginas = None
    if ext == "pdf":
        try:
            qtd_paginas = content.count(b"/Type /Page") or None
        except Exception:
            qtd_paginas = None

    # 1. Cria registro do anexo para obter o id.
    anexo = Anexo(
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        descricao=(descricao or file.filename)[:512],
        qtd_paginas=qtd_paginas,
    )
    db.add(anexo)
    await db.flush()  # popula anexo.id

    # 2. Define e_doc (com a extensão) e salva o arquivo.
    e_doc = f"{anexo.id}.{ext}"
    anexo.e_doc = e_doc

    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    path = uploads_dir / e_doc
    path.write_bytes(content)

    # 3. Próxima ordem dentro do processo.
    next_ordem = (
        await db.execute(
            select(func.coalesce(func.max(AnexoProcesso.ordem), 0) + 1).where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one()

    # 4. Vínculo anexo↔processo (na última movimentação corrente).
    db.add(
        AnexoProcesso(
            id_processo=processo_id,
            id_anexo=anexo.id,
            id_movimentacao=processo.id_ultima_movimentacao,
            id_usuario=usuario_id,
            ordem=next_ordem,
            ativo=True,
            excluido=False,
            anexo_herdado=False,
        )
    )

    await db.commit()
    await db.refresh(anexo)
    return anexo


async def get_anexo_path(
    db: AsyncSession, anexo_id: int
) -> tuple[Anexo, Path]:
    settings = get_settings()
    anexo = (
        await db.execute(
            select(Anexo).where(
                Anexo.id == anexo_id,
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")
    if not anexo.e_doc:
        raise AnexoError("Anexo sem arquivo físico associado")
    path = Path(settings.uploads_dir) / anexo.e_doc
    if not path.exists():
        raise AnexoError(f"Arquivo {anexo.e_doc} não está no storage")
    return anexo, path


async def delete_anexo(
    db: AsyncSession, processo_id: int, anexo_id: int
) -> None:
    """Soft delete: marca anexo + vínculo como excluído. Mantém arquivo físico."""
    anexo = (
        await db.execute(
            select(Anexo).where(Anexo.id == anexo_id, Anexo.excluido.is_(False))
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")

    vinculo = (
        await db.execute(
            select(AnexoProcesso).where(
                AnexoProcesso.id_anexo == anexo_id,
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if vinculo is None:
        raise AnexoError("Anexo não está vinculado a este processo")

    anexo.excluido = True
    anexo.ativo = False
    vinculo.excluido = True
    await db.commit()
