from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Encaminhamento as _Encaminhamento
from ..models import Prioridade as _Prio
from ..models import UnidadeTrabalho as _UT
from ..models import Usuario
from ..schemas.common import Paginated
from ..schemas.checklist_documentos import ChecklistDocumentosResponse
from ..schemas.complementacao_documental import (
    CancelarComplementacaoRequest,
    ComplementacaoOut,
    SolicitarComplementacaoRequest,
)
from ..schemas.processo import (
    CancelarEncaminhamentoRequest,
    ClassificarSigiloRequest,
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
from ..services.checklist_documentos import calcular_checklist
from ..services import complementacao_documental as _comp_svc
from ..services.complementacao_documental import ComplementacaoError
from ..services.processos import get_processo_detail, list_processos
from ..schemas.ccd import TemporalidadeOut
from ..services.temporalidade import calcular_temporalidade

# Fase P6 — Apensamento, Desentranhamento, Volumes
from ..models import (
    Anexo as _AnexoP6,
    AnexoProcesso as _AnexoProcessoP6,
    Manifestante as _ManifestanteP6,
    Processo as _ProcessoP6,
    ProcessoApensamento as _ApensP6,
    ProcessoVolume as _VolP6,
)
from ..schemas.apensamento import (
    ApensamentoOut,
    ApensarRequest,
    DesapensarRequest,
    DesentranhamentoOut,
    DesentranhamentoRequest,
    ProcessoApensadoItem,
    VolumeCreate,
    VolumeOut,
    VolumeUpdate,
)
from ..services.apensamento import (
    ApensamentoError,
    apensar as _apensar_svc,
    desapensar as _desapensar_svc,
)
from ..services.desentranhamento import (
    DesentranhamentoError,
    desentranhar_anexo as _desentranhar_svc,
)
from ..services.pdf_termos import (
    gerar_termo_apensamento,
    gerar_termo_desapensamento,
    gerar_termo_desentranhamento,
)
from ..services.volumes import (
    VolumeError,
    atualizar_volume as _vol_update,
    criar_volume as _vol_create,
    deletar_volume as _vol_delete,
)

router = APIRouter(prefix="/processos", tags=["processos"])


async def _is_super(db: AsyncSession, user: Usuario, tenant_id: int) -> bool:
    from ..services.permissoes import load_permissions

    perms = await load_permissions(db, user.id, tenant_id=tenant_id)
    return perms.is_super_usuario


async def _niveis_acesso(
    db: AsyncSession, user: Usuario, tenant_id: int
) -> list[str] | None:
    """Níveis de sigilo que o usuário alcança. None = super-usuário (tudo)."""
    from ..services.sigilo import niveis_permitidos

    if await _is_super(db, user, tenant_id):
        return None
    return niveis_permitidos(user.nivel_acesso_sigilo)


async def acesso_niveis_dep(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[str] | None:
    return await _niveis_acesso(db, user, tenant_id)


async def require_acesso_processo(
    processo_id: int,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Bloqueia (404) acesso a processo acima da credencial do servidor.

    404 em vez de 403 pra não vazar a existência de processo sigiloso.
    """
    # Delega ao helper reaproveitável de sigilo (mesma lógica de acesso a
    # processo usada também pelos endpoints de assinatura).
    from ..services.sigilo import SigiloAcessoError, assert_acesso_processo

    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=processo_id, usuario=user
        )
    except SigiloAcessoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )


@router.get(
    "",
    response_model=Paginated[ProcessoListItem],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_endpoint(
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
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
        niveis_permitidos=niveis,
    )
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{processo_id}",
    response_model=ProcessoDetail,
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def detail_endpoint(
    processo_id: int,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
) -> ProcessoDetail:
    detail = await get_processo_detail(
        db, processo_id, tenant_id=tenant_id, niveis_permitidos=niveis
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


@router.get(
    "/{processo_id}/checklist-documentos",
    response_model=ChecklistDocumentosResponse,
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def checklist_documentos_servidor(
    processo_id: int,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ChecklistDocumentosResponse:
    """PR 4c — checklist documental read-only do processo (servidor)."""
    return await calcular_checklist(db, processo_id=processo_id, tenant_id=tenant_id)


# PR 4d — Complementação documental formal ===================================

@router.post(
    "/{processo_id}/complementacoes",
    response_model=ComplementacaoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_acesso_processo)],
)
async def solicitar_complementacao(
    processo_id: int,
    payload: SolicitarComplementacaoRequest,
    tenant_id: int = Depends(require_tenant_id),
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    db: AsyncSession = Depends(get_db),
) -> ComplementacaoOut:
    """PR 4d — servidor abre solicitação formal de complementação documental."""
    try:
        comp = await _comp_svc.solicitar(
            db,
            tenant_id=tenant_id,
            processo_id=processo_id,
            id_usuario_solicitante=current.id,
            mensagem=payload.mensagem,
            documentos_solicitados_keys=payload.documentos_solicitados,
        )
    except ComplementacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    out = await _comp_svc.montar_out(db, comp)
    await db.commit()
    return out


@router.get(
    "/{processo_id}/complementacoes",
    response_model=list[ComplementacaoOut],
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def listar_complementacoes_servidor(
    processo_id: int,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[ComplementacaoOut]:
    """PR 4d — histórico de complementações do processo (desc por criado_em)."""
    try:
        return await _comp_svc.listar_out(
            db, tenant_id=tenant_id, processo_id=processo_id
        )
    except ComplementacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/{processo_id}/complementacoes/{complementacao_id}/cancelar",
    response_model=ComplementacaoOut,
    dependencies=[Depends(require_acesso_processo)],
)
async def cancelar_complementacao(
    processo_id: int,
    complementacao_id: int,
    payload: CancelarComplementacaoRequest,
    tenant_id: int = Depends(require_tenant_id),
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    db: AsyncSession = Depends(get_db),
) -> ComplementacaoOut:
    """PR 4d — servidor cancela complementação aberta."""
    try:
        comp = await _comp_svc.cancelar(
            db,
            tenant_id=tenant_id,
            processo_id=processo_id,
            complementacao_id=complementacao_id,
            id_usuario_responsavel=current.id,
            motivo=payload.motivo,
        )
    except ComplementacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    out = await _comp_svc.montar_out(db, comp)
    await db.commit()
    return out


@router.post(
    "/{processo_id}/classificar-sigilo",
    response_model=ProcessoDetail,
    dependencies=[Depends(require_acesso_processo)],
)
async def classificar_sigilo_endpoint(
    processo_id: int,
    payload: ClassificarSigiloRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    from ..services.sigilo import SigiloError, classificar_processo

    is_super = await _is_super(db, current, tenant_id)
    try:
        await classificar_processo(
            db,
            tenant_id=tenant_id,
            processo_id=processo_id,
            nivel=payload.nivel,
            usuario_id=current.id,
            credencial_usuario=current.nivel_acesso_sigilo,
            is_super=is_super,
            fundamento_legal=payload.fundamento_legal,
            autoridade=payload.autoridade,
            prazo_anos=payload.prazo_anos,
        )
    except SigiloError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


@router.post("", response_model=ProcessoDetail, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: ProcessoCreate,
    current: Usuario = Depends(require_permission("processo", "inserir")),
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


@router.get(
    "/{processo_id}/trail",
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
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


@router.get(
    "/{processo_id}/temporalidade",
    response_model=TemporalidadeOut,
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def temporalidade_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """P4 — calcula temporalidade documental do processo via regra TTD."""
    try:
        return await calcular_temporalidade(db, processo_id, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e


@router.post(
    "/{processo_id}/encaminhamentos",
    response_model=ProcessoDetail,
    dependencies=[Depends(require_acesso_processo)],
)
async def encaminhar_endpoint(
    processo_id: int,
    payload: EncaminharRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    is_super = await _is_super(db, current, tenant_id)
    try:
        await encaminhar(
            db,
            processo_id,
            payload,
            tenant_id=tenant_id,
            usuario_id=current.id,
            is_super_usuario=is_super,
        )
    except AcaoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return detail


@router.post(
    "/{processo_id}/receber",
    response_model=ProcessoDetail,
    dependencies=[Depends(require_acesso_processo)],
)
async def receber_endpoint(
    processo_id: int,
    override_motivo: str | None = None,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoDetail:
    is_super = await _is_super(db, current, tenant_id)
    try:
        await receber(
            db,
            processo_id,
            tenant_id=tenant_id,
            usuario_id=current.id,
            is_super_usuario=is_super,
            override_motivo=override_motivo,
        )
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


@router.get(
    "/{processo_id}/capa.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def capa_pdf_endpoint(
    processo_id: int,
    inline: bool = Query(True),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
):
    detail = await get_processo_detail(
        db, processo_id, tenant_id=tenant_id, niveis_permitidos=niveis
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_capa_pdf(detail)
    fname = f"capa-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get(
    "/{processo_id}/etiqueta-unica.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def etiqueta_unica_pdf(
    processo_id: int,
    inline: bool = Query(True),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
):
    detail = await get_processo_detail(
        db, processo_id, tenant_id=tenant_id, niveis_permitidos=niveis
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_etiqueta_pdf(detail, dupla=False)
    fname = f"etiqueta-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get(
    "/{processo_id}/completo.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def completo_pdf_endpoint(
    processo_id: int,
    inline: bool = Query(True),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
):
    detail = await get_processo_detail(
        db, processo_id, tenant_id=tenant_id, niveis_permitidos=niveis
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_processo_completo_pdf(detail)
    fname = f"processo-completo-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get(
    "/{processo_id}/etiqueta-dupla.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def etiqueta_dupla_pdf(
    processo_id: int,
    inline: bool = Query(True),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
):
    detail = await get_processo_detail(
        db, processo_id, tenant_id=tenant_id, niveis_permitidos=niveis
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    pdf_bytes = gerar_etiqueta_pdf(detail, dupla=True)
    fname = f"etiquetas-{detail.numero_processo.replace('/', '_')}.pdf"
    return _pdf_response(pdf_bytes, inline=inline, fname=fname)


@router.get(
    "/encaminhamentos/{encaminhamento_id}/comprovante.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def comprovante_pdf_endpoint(
    encaminhamento_id: int,
    tipo: str = Query("envio", pattern="^(envio|recebimento)$"),
    inline: bool = Query(True),
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
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
    detail = await get_processo_detail(
        db, enc.id_processo, tenant_id=tenant_id, niveis_permitidos=niveis
    )
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
    current: Usuario = Depends(require_permission("processo", "atualizar")),
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


# =============================================================================
#  P6 — APENSAMENTO
# =============================================================================

async def _hydrate_apensamento(
    db: AsyncSession, apens: _ApensP6
) -> ApensamentoOut:
    """Resolve nomes para o ApensamentoOut."""
    nums = (
        await db.execute(
            _select(_ProcessoP6.id, _ProcessoP6.numero_processo).where(
                _ProcessoP6.id.in_(
                    [apens.id_processo_apensado, apens.id_processo_principal]
                )
            )
        )
    ).all()
    num_por_id = {r.id: r.numero_processo for r in nums}

    user_ids = [uid for uid in [apens.id_usuario, apens.id_usuario_desapensamento] if uid]
    user_rows = (
        await db.execute(
            _select(Usuario.id, Usuario.nome).where(Usuario.id.in_(user_ids))
        )
    ).all() if user_ids else []
    user_por_id = {r.id: r.nome for r in user_rows}

    return ApensamentoOut(
        id=apens.id,
        id_processo_apensado=apens.id_processo_apensado,
        id_processo_principal=apens.id_processo_principal,
        id_usuario=apens.id_usuario,
        motivo=apens.motivo,
        criado_em=apens.criado_em,
        desapensado_em=apens.desapensado_em,
        id_usuario_desapensamento=apens.id_usuario_desapensamento,
        motivo_desapensamento=apens.motivo_desapensamento,
        numero_processo_apensado=num_por_id.get(apens.id_processo_apensado),
        numero_processo_principal=num_por_id.get(apens.id_processo_principal),
        usuario_nome=user_por_id.get(apens.id_usuario),
        usuario_desapensamento_nome=user_por_id.get(apens.id_usuario_desapensamento)
        if apens.id_usuario_desapensamento
        else None,
        ativo=apens.desapensado_em is None,
    )


@router.post(
    "/{processo_id}/apensar",
    response_model=ApensamentoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_acesso_processo)],
)
async def apensar_endpoint(
    processo_id: int,
    payload: ApensarRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        apens = await _apensar_svc(
            db,
            tenant_id=tenant_id,
            usuario_id=current.id,
            id_processo_apensado=processo_id,
            id_processo_principal=payload.id_processo_principal,
            motivo=payload.motivo,
        )
    except ApensamentoError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _hydrate_apensamento(db, apens)


@router.post(
    "/{processo_id}/desapensar",
    response_model=ApensamentoOut,
    dependencies=[Depends(require_acesso_processo)],
)
async def desapensar_endpoint(
    processo_id: int,
    payload: DesapensarRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        apens = await _desapensar_svc(
            db,
            tenant_id=tenant_id,
            usuario_id=current.id,
            id_processo_apensado=processo_id,
            motivo=payload.motivo,
        )
    except ApensamentoError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _hydrate_apensamento(db, apens)


@router.get(
    "/{processo_id}/apensamentos",
    response_model=list[ApensamentoOut],
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def list_apensamentos_endpoint(
    processo_id: int,
    apenas_ativos: bool = False,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Histórico (ou apenas vínculos ativos) onde o processo é filho OU pai."""
    stmt = _select(_ApensP6).where(
        _ApensP6.tenant_id == tenant_id,
        (_ApensP6.id_processo_apensado == processo_id)
        | (_ApensP6.id_processo_principal == processo_id),
    )
    if apenas_ativos:
        stmt = stmt.where(_ApensP6.desapensado_em.is_(None))
    stmt = stmt.order_by(_ApensP6.criado_em.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [await _hydrate_apensamento(db, a) for a in rows]


@router.get(
    "/{processo_id}/apensados",
    response_model=list[ProcessoApensadoItem],
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def list_processos_apensados_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista os processos atualmente apensados a este (este é o pai).

    Retorna filhos ativos (desapensado_em IS NULL) com dados enriquecidos.
    """
    stmt = (
        _select(_ApensP6, _ProcessoP6, _ManifestanteP6.nome)
        .join(_ProcessoP6, _ProcessoP6.id == _ApensP6.id_processo_apensado)
        .join(_ManifestanteP6, _ManifestanteP6.id == _ProcessoP6.id_manifestante, isouter=True)
        .where(
            _ApensP6.tenant_id == tenant_id,
            _ApensP6.id_processo_principal == processo_id,
            _ApensP6.desapensado_em.is_(None),
        )
        .order_by(_ApensP6.criado_em.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        ProcessoApensadoItem(
            id_apensamento=a.id,
            id_processo=p.id,
            numero_processo=p.numero_processo,
            nup=p.nup,
            manifestante=manif,
            apensado_em=a.criado_em,
            motivo=a.motivo,
        )
        for a, p, manif in rows
    ]


@router.get(
    "/apensamentos/{apensamento_id}/termo.pdf",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def termo_apensamento_pdf(
    apensamento_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Termo de apensamento (ou desapensamento, conforme estado do registro).

    Se ``desapensado_em`` está preenchido → termo de desapensamento.
    Caso contrário → termo de apensamento ativo.
    """
    apens = (
        await db.execute(
            _select(_ApensP6).where(
                _ApensP6.id == apensamento_id, _ApensP6.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if apens is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apensamento não encontrado")

    # Carrega ambos processos + nome do operador
    rows = (
        await db.execute(
            _select(_ProcessoP6).where(
                _ProcessoP6.id.in_(
                    [apens.id_processo_apensado, apens.id_processo_principal]
                )
            )
        )
    ).scalars().all()
    p_por_id = {p.id: p for p in rows}
    pa = p_por_id.get(apens.id_processo_apensado)
    pp = p_por_id.get(apens.id_processo_principal)
    if pa is None or pp is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Inconsistência ao carregar processos")

    manif_rows = (
        await db.execute(
            _select(_ManifestanteP6.id, _ManifestanteP6.nome).where(
                _ManifestanteP6.id.in_([pa.id_manifestante, pp.id_manifestante])
            )
        )
    ).all()
    manif_por_id = {r.id: r.nome for r in manif_rows}

    operador = (
        await db.execute(_select(Usuario.nome).where(Usuario.id == apens.id_usuario))
    ).scalar_one_or_none()

    if apens.desapensado_em is not None:
        op_desap = (
            await db.execute(
                _select(Usuario.nome).where(
                    Usuario.id == apens.id_usuario_desapensamento
                )
            )
        ).scalar_one_or_none() if apens.id_usuario_desapensamento else None
        pdf = gerar_termo_desapensamento(
            numero_processo_apensado=pa.numero_processo,
            numero_processo_principal=pp.numero_processo,
            nup_apensado=pa.nup,
            nup_principal=pp.nup,
            motivo_apensamento=apens.motivo,
            motivo_desapensamento=apens.motivo_desapensamento or "—",
            data_apensamento=apens.criado_em,
            data_desapensamento=apens.desapensado_em,
            operador_nome=op_desap or operador,
            processo_id=pa.id,
        )
        tipo_arq = "desapensamento"
    else:
        pdf = gerar_termo_apensamento(
            numero_processo_apensado=pa.numero_processo,
            numero_processo_principal=pp.numero_processo,
            nup_apensado=pa.nup,
            nup_principal=pp.nup,
            manifestante_apensado=manif_por_id.get(pa.id_manifestante),
            manifestante_principal=manif_por_id.get(pp.id_manifestante),
            motivo=apens.motivo,
            data_apensamento=apens.criado_em,
            operador_nome=operador,
            processo_id=pa.id,
        )
        tipo_arq = "apensamento"

    fname = f"termo-{tipo_arq}-{pa.numero_processo.replace('/', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# =============================================================================
#  P6 — DESENTRANHAMENTO
# =============================================================================


@router.post(
    "/{processo_id}/anexos/{anexo_processo_id}/desentranhar",
    response_model=DesentranhamentoOut,
    dependencies=[Depends(require_acesso_processo)],
)
async def desentranhar_anexo_endpoint(
    processo_id: int,
    anexo_processo_id: int,
    payload: DesentranhamentoRequest,
    current: Usuario = Depends(require_permission("processo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        ap = await _desentranhar_svc(
            db,
            tenant_id=tenant_id,
            usuario_id=current.id,
            processo_id=processo_id,
            anexo_processo_id=anexo_processo_id,
            motivo=payload.motivo,
            autoridade=payload.autoridade,
        )
    except DesentranhamentoError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    anexo = (
        await db.execute(_select(_AnexoP6).where(_AnexoP6.id == ap.id_anexo))
    ).scalar_one_or_none()
    return DesentranhamentoOut(
        id_anexo_processo=ap.id,
        id_anexo=ap.id_anexo,
        descricao_anexo=anexo.descricao if anexo else None,
        desentranhado_em=ap.desentranhado_em,  # type: ignore[arg-type]
        motivo=ap.motivo_desentranhamento or "",
        autoridade=ap.autoridade_desentranhamento or "",
        usuario_nome=current.nome,
    )


@router.get(
    "/{processo_id}/anexos/{anexo_processo_id}/termo-desentranhamento.pdf",
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def termo_desentranhamento_pdf(
    processo_id: int,
    anexo_processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    ap = (
        await db.execute(
            _select(_AnexoProcessoP6).where(
                _AnexoProcessoP6.id == anexo_processo_id,
                _AnexoProcessoP6.id_processo == processo_id,
                _AnexoProcessoP6.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if ap is None or ap.desentranhado_em is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anexo desentranhado não encontrado")

    p = (
        await db.execute(_select(_ProcessoP6).where(_ProcessoP6.id == processo_id))
    ).scalar_one()
    anexo = (
        await db.execute(_select(_AnexoP6).where(_AnexoP6.id == ap.id_anexo))
    ).scalar_one_or_none()
    operador = (
        await db.execute(
            _select(Usuario.nome).where(Usuario.id == ap.id_usuario_desentranhamento)
        )
    ).scalar_one_or_none() if ap.id_usuario_desentranhamento else None

    pdf = gerar_termo_desentranhamento(
        numero_processo=p.numero_processo,
        nup=p.nup,
        descricao_anexo=anexo.descricao if anexo else None,
        motivo=ap.motivo_desentranhamento or "—",
        autoridade=ap.autoridade_desentranhamento or "—",
        data_desentranhamento=ap.desentranhado_em,
        operador_nome=operador,
        processo_id=p.id,
        anexo_processo_id=ap.id,
    )
    fname = f"termo-desentranhamento-{p.numero_processo.replace('/', '_')}-anexo{ap.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# =============================================================================
#  P6 — VOLUMES
# =============================================================================


async def _vol_hydrate(db: AsyncSession, vol: _VolP6) -> VolumeOut:
    nome = (
        await db.execute(_select(Usuario.nome).where(Usuario.id == vol.id_usuario))
    ).scalar_one_or_none()
    return VolumeOut(
        id=vol.id,
        id_processo=vol.id_processo,
        numero=vol.numero,
        pagina_inicial=vol.pagina_inicial,
        pagina_final=vol.pagina_final,
        observacao=vol.observacao,
        id_usuario=vol.id_usuario,
        criado_em=vol.criado_em,
        usuario_nome=nome,
    )


@router.get(
    "/{processo_id}/volumes",
    response_model=list[VolumeOut],
    dependencies=[Depends(require_acesso_processo), Depends(require_modulo("protocolo"))],
)
async def list_volumes_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            _select(_VolP6)
            .where(
                _VolP6.tenant_id == tenant_id, _VolP6.id_processo == processo_id
            )
            .order_by(_VolP6.numero)
        )
    ).scalars().all()
    return [await _vol_hydrate(db, v) for v in rows]


@router.post(
    "/{processo_id}/volumes",
    response_model=VolumeOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_acesso_processo)],
)
async def create_volume_endpoint(
    processo_id: int,
    payload: VolumeCreate,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        vol = await _vol_create(
            db,
            tenant_id=tenant_id,
            usuario_id=current.id,
            processo_id=processo_id,
            payload=payload,
        )
    except VolumeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _vol_hydrate(db, vol)


@router.put("/volumes/{volume_id}", response_model=VolumeOut)
async def update_volume_endpoint(
    volume_id: int,
    payload: VolumeUpdate,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        vol = await _vol_update(
            db, tenant_id=tenant_id, volume_id=volume_id, payload=payload
        )
    except VolumeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _vol_hydrate(db, vol)


@router.delete("/volumes/{volume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volume_endpoint(
    volume_id: int,
    current: Usuario = Depends(require_permission("processo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        await _vol_delete(
            db, tenant_id=tenant_id, usuario_id=current.id, volume_id=volume_id
        )
    except VolumeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
