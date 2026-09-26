"""Rotas de execução em lote (F4, spec §4.3, §7.6)."""
from __future__ import annotations

import mimetypes
import urllib.parse

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id, require_tenant_slug
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    LoteCriarIn, LoteDetalheOut, LoteParcelaIn, LotePagamentoOut, LotePagamentoParcelaOut,
    LoteProgramarIn, ParcelaOut, RetornoLoteIn,
)
from ..services import pagamentos_lotes as lotes

router = APIRouter(prefix="/pagamentos", tags=["pagamentos-lotes"])


async def _detalhe(db: AsyncSession, *, tenant_id: int, lote_id: int) -> LoteDetalheOut:
    lote = await lotes.obter_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    parcelas = await lotes.parcelas_do_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    return LoteDetalheOut(
        **LotePagamentoOut.model_validate(lote).model_dump(),
        parcelas=[LotePagamentoParcelaOut.model_validate(p) for p in parcelas],
    )


@router.get("/lotes/elegiveis", response_model=list[ParcelaOut])
async def listar_elegiveis(id_conta_pagadora: int | None = None,
                           _: Usuario = Depends(require_permission("pagamento_pagar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await lotes.parcelas_elegiveis_para_lote(
        db, tenant_id=tenant_id, id_conta_pagadora=id_conta_pagadora)


@router.post("/lotes", response_model=LotePagamentoOut, status_code=status.HTTP_201_CREATED)
async def criar_lote(payload: LoteCriarIn,
                     usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    return await lotes.criar_lote(
        db, tenant_id=tenant_id, id_conta_pagadora=payload.id_conta_pagadora,
        parcela_ids=payload.parcela_ids, usuario_id=usuario.id)


@router.get("/lotes", response_model=list[LotePagamentoOut])
async def listar_lotes(situacao: str | None = None,
                       _: Usuario = Depends(require_permission("pagamento_pagar")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return await lotes.listar_lotes(db, tenant_id=tenant_id, situacao=situacao)


@router.get("/lotes/{lote_id}", response_model=LoteDetalheOut)
async def obter_lote(lote_id: int,
                     _: Usuario = Depends(require_permission("pagamento_pagar")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    return await _detalhe(db, tenant_id=tenant_id, lote_id=lote_id)


@router.post("/lotes/{lote_id}/parcelas", response_model=LoteDetalheOut)
async def adicionar_parcela(lote_id: int, payload: LoteParcelaIn,
                            _: Usuario = Depends(require_permission("pagamento_pagar")),
                            tenant_id: int = Depends(require_tenant_id),
                            db: AsyncSession = Depends(get_db)):
    await lotes.adicionar_parcela(
        db, tenant_id=tenant_id, lote_id=lote_id, parcela_id=payload.parcela_id)
    return await _detalhe(db, tenant_id=tenant_id, lote_id=lote_id)


@router.delete("/lotes/{lote_id}/parcelas/{parcela_id}", response_model=LoteDetalheOut)
async def remover_parcela(lote_id: int, parcela_id: int,
                          _: Usuario = Depends(require_permission("pagamento_pagar")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    await lotes.remover_parcela(db, tenant_id=tenant_id, lote_id=lote_id, parcela_id=parcela_id)
    return await _detalhe(db, tenant_id=tenant_id, lote_id=lote_id)


@router.post("/lotes/{lote_id}/cancelar", response_model=LotePagamentoOut)
async def cancelar_lote(lote_id: int,
                        usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    return await lotes.cancelar_lote(db, tenant_id=tenant_id, lote_id=lote_id, usuario_id=usuario.id)


@router.post("/lotes/{lote_id}/programar", response_model=LotePagamentoOut)
async def programar_lote(lote_id: int, payload: LoteProgramarIn,
                         usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return await lotes.programar_lote(
        db, tenant_id=tenant_id, lote_id=lote_id,
        data_programada=payload.data_programada, usuario_id=usuario.id)


@router.post("/lotes/{lote_id}/enviar", response_model=LotePagamentoOut)
async def enviar_lote(lote_id: int,
                      usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return await lotes.enviar_lote(db, tenant_id=tenant_id, lote_id=lote_id, usuario_id=usuario.id)


@router.post("/lotes/{lote_id}/retorno", response_model=LoteDetalheOut)
async def processar_retorno(lote_id: int, payload: RetornoLoteIn,
                            usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                            tenant_id: int = Depends(require_tenant_id),
                            db: AsyncSession = Depends(get_db)):
    await lotes.processar_retorno(
        db, tenant_id=tenant_id, lote_id=lote_id, retornos=payload.retornos,
        usuario_id=usuario.id)
    return await _detalhe(db, tenant_id=tenant_id, lote_id=lote_id)


@router.post("/lotes/{lote_id}/comprovante", response_model=LotePagamentoOut,
            status_code=status.HTTP_201_CREATED)
async def anexar_comprovante(lote_id: int,
                             file: UploadFile = File(...),
                             descricao: str | None = Form(None),
                             usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                             tenant_id: int = Depends(require_tenant_id),
                             tenant_slug: str = Depends(require_tenant_slug),
                             db: AsyncSession = Depends(get_db)):
    return await lotes.anexar_comprovante(
        db, tenant_id=tenant_id, tenant_slug=tenant_slug, lote_id=lote_id,
        usuario_id=usuario.id, file=file, descricao=descricao)


@router.get("/lotes/{lote_id}/comprovante/download")
async def download_comprovante(lote_id: int, inline: bool = False,
                               _: Usuario = Depends(require_permission("pagamento_pagar")),
                               tenant_id: int = Depends(require_tenant_id),
                               tenant_slug: str = Depends(require_tenant_slug),
                               db: AsyncSession = Depends(get_db)):
    path, anexo = await lotes.get_comprovante_path_autorizado(
        db, tenant_id=tenant_id, tenant_slug=tenant_slug, lote_id=lote_id)
    download_name = (anexo.descricao or anexo.e_doc or f"comprovante-{anexo.id}").strip()
    if anexo.e_doc and "." in anexo.e_doc and "." not in download_name:
        download_name += "." + anexo.e_doc.rsplit(".", 1)[1]
    safe_name = urllib.parse.quote(download_name)
    disposition = "inline" if inline else "attachment"
    media_type, _enc = mimetypes.guess_type(anexo.e_doc or "")
    return FileResponse(
        path=str(path), media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{safe_name}"})
