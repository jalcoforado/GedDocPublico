from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Encaminhamento as _Encaminhamento
from ..models import Prioridade as _Prio
from ..models import UnidadeTrabalho as _UT
from ..models import Usuario
from ..schemas.common import Paginated
from ..schemas.processo import (
    CancelarEncaminhamentoRequest,
    EncaminharRequest,
    EncaminhamentoOut as _EncaminhamentoOut,
    ProcessoCreate,
    ProcessoDetail,
    ProcessoListItem,
)
from ..services.abertura_processo import AberturaError, abrir_processo
from ..services.acoes_processo import (
    AcaoError,
    cancelar_encaminhamento,
    encaminhar,
    receber,
)
from ..services.pdf_capa import gerar_capa_pdf
from ..services.pdf_comprovante import gerar_comprovante_pdf
from ..services.pdf_etiqueta import gerar_etiqueta_pdf
from ..services.pdf_montagem import gerar_processo_completo_pdf
from ..services.processos import get_processo_detail, list_processos

router = APIRouter(prefix="/processos", tags=["processos"])


@router.get("", response_model=Paginated[ProcessoListItem])
async def list_endpoint(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Busca em número, manifestante, assunto"),
    id_assunto: int | None = None,
    id_manifestante: int | None = None,
    id_unidade: int | None = Query(None, description="Filtra unidade proprietária ou local atual"),
    apenas_ativos: bool = False,
    desde: datetime | None = None,
    ate: datetime | None = None,
) -> Paginated[ProcessoListItem]:
    items, total = await list_processos(
        db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        q=q,
        id_assunto=id_assunto,
        id_manifestante=id_manifestante,
        id_unidade=id_unidade,
        apenas_ativos=apenas_ativos,
        desde=desde,
        ate=ate,
    )
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{processo_id}", response_model=ProcessoDetail)
async def detail_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


@router.post("", response_model=ProcessoDetail, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: ProcessoCreate,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    try:
        processo = await abrir_processo(db, payload, tenant_id=tenant_id, usuario_id=current.id)
    except AberturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_processo_detail(db, processo.id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Processo criado mas não recuperado")
    return detail


@router.get("/{processo_id}/trail")
async def get_trail(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Sequência de unidades visitadas pelo processo (caminho percorrido).

    Útil pra mini-organograma com highlight das visitadas + setas entre.
    """
    from ..services.processo_trail import trail as build_trail

    return await build_trail(db, processo_id=processo_id, tenant_id=tenant_id)


@router.post("/{processo_id}/encaminhamentos", response_model=ProcessoDetail)
async def encaminhar_endpoint(
    processo_id: int,
    payload: EncaminharRequest,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    try:
        await encaminhar(db, processo_id, payload, tenant_id=tenant_id, usuario_id=current.id)
    except AcaoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


@router.post("/{processo_id}/receber", response_model=ProcessoDetail)
async def receber_endpoint(
    processo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    try:
        await receber(db, processo_id, tenant_id=tenant_id, usuario_id=current.id)
    except AcaoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


def _pdf_response(pdf_bytes: bytes, *, inline: bool, fname: str) -> Response:
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


@router.get("/{processo_id}/capa.pdf")
async def capa_pdf_endpoint(
    processo_id: int,
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_capa_pdf(detail)
    fname = f"capa-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get("/{processo_id}/etiqueta-unica.pdf")
async def etiqueta_unica_pdf(
    processo_id: int,
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_etiqueta_pdf(detail, dupla=False)
    fname = f"etiqueta-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get("/{processo_id}/completo.pdf")
async def completo_pdf_endpoint(
    processo_id: int,
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_processo_completo_pdf(detail)
    fname = f"processo-completo-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get("/{processo_id}/etiqueta-dupla.pdf")
async def etiqueta_dupla_pdf(
    processo_id: int,
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_etiqueta_pdf(detail, dupla=True)
    fname = f"etiquetas-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get("/encaminhamentos/{encaminhamento_id}/comprovante.pdf")
async def comprovante_pdf_endpoint(
    encaminhamento_id: int,
    tipo: str = Query("envio", pattern="^(envio|recebimento)$"),
    inline: bool = Query(True),
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Carrega encaminhamento + nomes via JOIN explícito.
    from sqlalchemy.orm import aliased
    UOrig = aliased(_UT, name="u_orig")
    UDest = aliased(_UT, name="u_dest")
    row = (
        await db.execute(
            _select(_Encaminhamento, UOrig, UDest, _Prio)
            .join(UOrig, UOrig.id == _Encaminhamento.id_unidade_origem, isouter=True)
            .join(UDest, UDest.id == _Encaminhamento.id_unidade_destino)
            .join(_Prio, _Prio.id == _Encaminhamento.id_prioridade, isouter=True)
            .where(
                _Encaminhamento.id == encaminhamento_id,
                _Encaminhamento.tenant_id == tenant_id,
                _Encaminhamento.excluido.is_(False),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaminhamento não encontrado")

    enc, uo, ud, prio = row
    detail = await get_processo_detail(db, enc.id_processo, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")

    if tipo == "recebimento" and not enc.recebido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Encaminhamento ainda não foi recebido")

    enc_out = _EncaminhamentoOut(
        id=enc.id,
        unidade_origem=uo.unidade_trabalho if uo else None,
        unidade_destino=ud.unidade_trabalho,
        prioridade=prio.prioridade if prio else None,
        quantidade_folhas=enc.quantidade_folhas,
        data_prazo=enc.data_prazo,
        recebido=enc.recebido,
        data_hora_recebimento=enc.data_hora_recebimento,
        cancelado=enc.cancelado,
    )

    pdf_bytes = gerar_comprovante_pdf(
        detail, enc_out, tipo=tipo, operador_nome=current.nome,  # type: ignore[arg-type]
    )
    fname = f"comprovante-{tipo}-enc{enc.id}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.post("/encaminhamentos/{encaminhamento_id}/cancelar", response_model=ProcessoDetail)
async def cancelar_encaminhamento_endpoint(
    encaminhamento_id: int,
    payload: CancelarEncaminhamentoRequest,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    try:
        enc = await cancelar_encaminhamento(
            db, encaminhamento_id, payload, tenant_id=tenant_id, usuario_id=current.id
        )
    except AcaoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_processo_detail(db, enc.id_processo, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail
