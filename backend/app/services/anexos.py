"""Upload, download e soft-delete de anexos vinculados a processos.

Storage (Fase 14): por tenant em `{tenants_storage_root}/{slug}/anexos/`.
Para anexos legacy (pré Fase 14) que estão em `{uploads_dir}/`, o
`resolve_anexo_path` faz fallback de leitura.

Nome do arquivo no disco: `{anexo_id}.{ext}` — guardado no campo `e_doc`
(unique constraint). O vínculo `protocolos.anexo_processo` requer
`id_movimentacao`; usamos `id_ultima_movimentacao` do processo.
"""
import hashlib

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings, resolve_anexo_path, tenant_anexos_dir
from ..models import Anexo, AnexoProcesso, AssinaturaAnexo, Processo


class AnexoError(Exception):
    pass


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
    tenant_id: int,
    tenant_slug: str,
    descricao: str | None,
    id_tipo_anexo: int | None,
    publico: bool,
    usuario_id: int | None,
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
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise AnexoError("Processo não encontrado")
    if not processo.ativo:
        raise AnexoError("Processo inativo — não permite anexos")
    if processo.id_ultima_movimentacao is None:
        raise AnexoError("Processo sem movimentação — abra-o antes de anexar")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AnexoError(f"Arquivo excede {settings.max_upload_size_mb} MB")

    qtd_paginas = None
    if ext == "pdf":
        try:
            qtd_paginas = content.count(b"/Type /Page") or None
        except Exception:
            qtd_paginas = None

    anexo = Anexo(
        tenant_id=tenant_id,
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        descricao=(descricao or file.filename)[:512],
        qtd_paginas=qtd_paginas,
    )
    db.add(anexo)
    await db.flush()

    e_doc = f"{anexo.id}.{ext}"
    anexo.e_doc = e_doc

    # Storage por tenant (Fase 14).
    path = tenant_anexos_dir(tenant_slug) / e_doc
    path.write_bytes(content)

    next_ordem = (
        await db.execute(
            select(func.coalesce(func.max(AnexoProcesso.ordem), 0) + 1).where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one()

    db.add(
        AnexoProcesso(
            tenant_id=tenant_id,
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
    db: AsyncSession,
    anexo_id: int,
    *,
    tenant_id: int,
    tenant_slug: str,
):
    anexo = (
        await db.execute(
            select(Anexo).where(
                Anexo.id == anexo_id,
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")
    if not anexo.e_doc:
        raise AnexoError("Anexo sem arquivo físico associado")
    path = resolve_anexo_path(tenant_slug, anexo.e_doc)
    if path is None:
        raise AnexoError(f"Arquivo {anexo.e_doc} não está no storage")
    return anexo, path


async def anexo_esta_assinado(
    db: AsyncSession, anexo_id: int, *, tenant_id: int
) -> bool:
    """True se há assinatura concluída (`status='assinada'`) sobre o anexo —
    inclui o legado, cujo backfill marcou `status='assinada'` quando assinado."""
    achou = (
        await db.execute(
            select(AssinaturaAnexo.id).where(
                AssinaturaAnexo.id_anexo == anexo_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.status == "assinada",
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).first()
    return achou is not None


async def hash_anexo(
    db: AsyncSession, anexo_id: int, *, tenant_id: int, tenant_slug: str
) -> tuple[str, str]:
    """SHA-256 do conteúdo exato do anexo no disco. Retorna (hex, 'sha256')."""
    _anexo, path = await get_anexo_path(
        db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
    )
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest(), "sha256"


async def delete_anexo(
    db: AsyncSession, processo_id: int, anexo_id: int, *, tenant_id: int
) -> None:
    """Soft delete: marca anexo + vínculo como excluído. Mantém arquivo físico."""
    # Imutabilidade (Assinatura v2): anexo assinado não pode ser removido.
    if await anexo_esta_assinado(db, anexo_id, tenant_id=tenant_id):
        raise AnexoError(
            "Anexo possui assinatura e não pode ser excluído. "
            "Gere uma nova versão do documento se precisar alterá-lo."
        )
    anexo = (
        await db.execute(
            select(Anexo).where(
                Anexo.id == anexo_id,
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")

    vinculo = (
        await db.execute(
            select(AnexoProcesso).where(
                AnexoProcesso.id_anexo == anexo_id,
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
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
