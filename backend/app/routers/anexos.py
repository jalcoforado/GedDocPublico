import mimetypes
import urllib.parse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models import AnexoProcesso, Processo, Usuario
from ..schemas.processo import AnexoNoProcesso
from ..services.anexos import (
    AnexoError,
    delete_anexo,
    get_anexo_path,
    upload_anexo,
)
from ..services.pdf_carimbo import CarimboError, carimbar_anexo_com_cache, invalidate_cache

router = APIRouter(tags=["anexos"])


@router.post(
    "/processos/{processo_id}/anexos",
    response_model=AnexoNoProcesso,
    status_code=status.HTTP_201_CREATED,
)
async def upload_endpoint(
    processo_id: int,
    file: UploadFile = File(...),
    descricao: str | None = Form(None),
    id_tipo_anexo: int | None = Form(None),
    publico: bool = Form(True),
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> AnexoNoProcesso:
    try:
        anexo = await upload_anexo(
            db,
            processo_id,
            file,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            descricao=descricao,
            id_tipo_anexo=id_tipo_anexo,
            publico=publico,
            usuario_id=current.id,
        )
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AnexoNoProcesso(
        id=anexo.id,
        descricao=anexo.descricao,
        publico=anexo.publico,
        qtd_paginas=anexo.qtd_paginas,
        e_doc=anexo.e_doc,
        tipo_anexo=None,
    )


@router.get(
    "/anexos/{anexo_id}/download",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def download_endpoint(
    anexo_id: int,
    inline: bool = Query(False, description="Quando true, serve o arquivo inline (para iframe/visualizador)"),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
):
    try:
        anexo, path = await get_anexo_path(
            db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    download_name = (anexo.descricao or anexo.e_doc or f"anexo-{anexo.id}").strip()
    if anexo.e_doc and "." in anexo.e_doc and "." not in download_name:
        download_name += "." + anexo.e_doc.rsplit(".", 1)[1]
    safe_name = urllib.parse.quote(download_name)
    disposition = "inline" if inline else "attachment"

    media_type, _enc = mimetypes.guess_type(anexo.e_doc or "")
    return FileResponse(
        path=str(path),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{safe_name}"},
    )


@router.delete(
    "/processos/{processo_id}/anexos/{anexo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_endpoint(
    processo_id: int,
    anexo_id: int,
    _: Usuario = Depends(require_permission("processo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_anexo(db, processo_id, anexo_id, tenant_id=tenant_id)
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    invalidate_cache(anexo_id, tenant_slug=tenant_slug)


@router.get(
    "/anexos/{anexo_id}/carimbado.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def carimbado_endpoint(
    anexo_id: int,
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
):
    try:
        anexo, source_path = await get_anexo_path(
            db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if not anexo.e_doc or not anexo.e_doc.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Carimbamento disponível apenas para anexos PDF",
        )

    row = (
        await db.execute(
            select(Processo.numero_processo)
            .join(AnexoProcesso, AnexoProcesso.id_processo == Processo.id)
            .where(
                AnexoProcesso.id_anexo == anexo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
                Processo.tenant_id == tenant_id,
            )
        )
    ).first()
    numero_processo = row[0] if row else "—"

    try:
        carimbado_path = carimbar_anexo_com_cache(
            anexo_id=anexo_id,
            source_pdf_path=source_path,
            numero_processo=numero_processo,
            e_doc=anexo.e_doc,
            tenant_slug=tenant_slug,
        )
    except CarimboError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    download_name = (anexo.descricao or anexo.e_doc).strip()
    if "." not in download_name:
        download_name += ".pdf"
    if not download_name.lower().endswith(".pdf"):
        download_name = download_name.rsplit(".", 1)[0] + "-carimbado.pdf"
    else:
        download_name = download_name[:-4] + "-carimbado.pdf"
    safe_name = urllib.parse.quote(download_name)
    disposition = "inline" if inline else "attachment"

    return FileResponse(
        path=str(carimbado_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{safe_name}"},
    )
