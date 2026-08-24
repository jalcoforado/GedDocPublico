"""Transporte Regulado — routers de Permissionários, Empresas e Veículos regulados.

`permissionarios_router` / `empresas_router` / `veiculos_router` (prefixos
`/transporte-regulado/permissionarios`, `/empresas` e `/veiculos`): CRUD interno,
autenticado + permissão `transporte_regulado`. Mesmo padrão dos routers de `frota`.
Sem portal público nesta etapa.
"""
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_cidadao, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import (
    Empresa,
    OcorrenciaTipo,
    Permissionario,
    RecadastramentoNotificacao,
    Usuario,
    UsuarioExterno,
    VeiculoRegulado,
)
from ..services import notificacoes
from ..services.notificacoes import Destinatario
from ..schemas.common import Paginated
from ..schemas.transporte_regulado import (
    EmpresaCreate,
    EmpresaOut,
    EmpresaUpdate,
    PermissionarioCreate,
    PermissionarioOut,
    PermissionarioUpdate,
    VeiculoReguladoCreate,
    VeiculoReguladoOut,
    VeiculoReguladoUpdate,
    VeiculoDocumentoCreate,
    VeiculoDocumentoOut,
    VeiculoDocumentoUpdate,
    VeiculoAvaliacaoCreate,
    VeiculoAvaliacaoOut,
    VeiculoAvaliacaoUpdate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaOut,
    VeiculoVistoriaUpdate,
    VeiculoVistoriaRenovarInput,
    AlvaraCreate,
    AlvaraOut,
    AlvaraUpdate,
    AlvaraRenovarInput,
    AlvaraRevogar,
    PontoCreate,
    PontoOut,
    PontoUpdate,
    PontoMapaOut,
    PontoOcupacaoOut,
    PontoOcuparInput,
    PontoLiberarInput,
    AlvaraDocumentoCreate,
    AlvaraDocumentoOut,
    AlvaraDocumentoUpdate,
    AlvaraResponsavelCreate,
    AlvaraResponsavelOut,
    AlvaraVeiculoCreate,
    AlvaraVeiculoOut,
    AlvaraAuditoriaListResponse,
    AlvaraRelatorioListResponse,
    AlvaraRelatorioItem,
    AlvaraKPIsResponse,
    RecadastramentoAjustePrazo,
    RecadastramentoCicloCreate,
    RecadastramentoCicloOut,
    RecadastramentoCicloUpdate,
    RecadastramentoConvocacaoOut,
    RecadastramentoGeracaoOut,
    RecadastramentoDecisaoInput,
    RecadastramentoDecisaoOut,
    RecadastramentoFaltososOut,
    RecadastramentoNotificacaoResultadoOut,
    RecadastramentoNotificarInput,
    RecadastramentoItemCreate,
    RecadastramentoItemOut,
    RecadastramentoItemUpdate,
    RecadastramentoMarcarInput,
    RecadastramentoSituacaoAtendimentoOut,
    LinhaCreate,
    LinhaUpdate,
    LinhaOut,
    LinhaParadaOut,
    LinhaHorarioOut,
    LinhaParadaCreate,
    LinhaParadaUpdate,
    LinhaParadasOrdemInput,
    LinhaHorarioCreate,
    OcorrenciaTipoCreate,
    OcorrenciaTipoUpdate,
    OcorrenciaTipoOut,
    OcorrenciaCreate,
    OcorrenciaOut,
    OcorrenciaAndamentoOut,
    OcorrenciaAnotarInput,
    OcorrenciaVincularInput,
    OcorrenciaDecidirInput,
    DenunciaCidadaoCreate,
    DenunciaCidadaoOut,
    WorkflowEntidadeOut,
)
from ..services import transporte_regulado as tr_svc

logger = logging.getLogger("transporte_regulado")

permissionarios_router = APIRouter(
    prefix="/transporte-regulado/permissionarios", tags=["transporte-regulado"]
)


@permissionarios_router.get("", response_model=Paginated[PermissionarioOut])
async def list_permissionarios(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    q: str | None = Query(None, description="Busca por nome ou CPF (substring)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PermissionarioOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_permissionarios(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico,
        q=q, limit=page_size, offset=offset
    )
    return Paginated(
        items=[PermissionarioOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@permissionarios_router.get("/{permissionario_id}", response_model=PermissionarioOut)
async def get_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.obter_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "", response_model=PermissionarioOut, status_code=status.HTTP_201_CREATED
)
async def create_permissionario(
    payload: PermissionarioCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.criar_permissionario(db, tenant_id=tenant_id, payload=payload)
    return PermissionarioOut.model_validate(p)


@permissionarios_router.put("/{permissionario_id}", response_model=PermissionarioOut)
async def update_permissionario(
    permissionario_id: int,
    payload: PermissionarioUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.atualizar_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, payload=payload
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/inativar", response_model=PermissionarioOut
)
async def inativar_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="inativo"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/reativar", response_model=PermissionarioOut
)
async def reativar_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="ativo"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/suspender", response_model=PermissionarioOut
)
async def suspender_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="suspenso"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.delete(
    "/{permissionario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )


# ============================ Empresas ======================================
empresas_router = APIRouter(
    prefix="/transporte-regulado/empresas", tags=["transporte-regulado"]
)


@empresas_router.get("", response_model=Paginated[EmpresaOut])
async def list_empresas(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[EmpresaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_empresas(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico, q=q,
        limit=page_size, offset=offset
    )
    return Paginated(
        items=[EmpresaOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@empresas_router.get("/{empresa_id}", response_model=EmpresaOut)
async def get_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.obter_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
    return EmpresaOut.model_validate(e)


@empresas_router.post(
    "", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED
)
async def create_empresa(
    payload: EmpresaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.criar_empresa(db, tenant_id=tenant_id, payload=payload)
    return EmpresaOut.model_validate(e)


@empresas_router.put("/{empresa_id}", response_model=EmpresaOut)
async def update_empresa(
    empresa_id: int,
    payload: EmpresaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.atualizar_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, payload=payload
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/inativar", response_model=EmpresaOut)
async def inativar_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="inativa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/reativar", response_model=EmpresaOut)
async def reativar_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="ativa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/suspender", response_model=EmpresaOut)
async def suspender_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="suspensa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)


# ============================ Veículos regulados ============================
veiculos_router = APIRouter(
    prefix="/transporte-regulado/veiculos", tags=["transporte-regulado"]
)


@veiculos_router.get("", response_model=Paginated[VeiculoReguladoOut])
async def list_veiculos(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    id_empresa: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[VeiculoReguladoOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_veiculos(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico,
        id_permissionario=id_permissionario, id_empresa=id_empresa, q=q,
        limit=page_size, offset=offset
    )
    return Paginated(
        items=[VeiculoReguladoOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@veiculos_router.get("/{veiculo_id}", response_model=VeiculoReguladoOut)
async def get_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.post(
    "", response_model=VeiculoReguladoOut, status_code=status.HTTP_201_CREATED
)
async def create_veiculo(
    payload: VeiculoReguladoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.criar_veiculo(db, tenant_id=tenant_id, payload=payload)
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.put("/{veiculo_id}", response_model=VeiculoReguladoOut)
async def update_veiculo(
    veiculo_id: int,
    payload: VeiculoReguladoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.atualizar_veiculo(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, payload=payload
    )
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.post("/{veiculo_id}/inativar", response_model=VeiculoReguladoOut)
async def inativar_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.set_situacao_veiculo(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, situacao="inativo"
    )
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.post("/{veiculo_id}/reativar", response_model=VeiculoReguladoOut)
async def reativar_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.set_situacao_veiculo(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, situacao="ativo"
    )
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.post("/{veiculo_id}/suspender", response_model=VeiculoReguladoOut)
async def suspender_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoReguladoOut:
    v = await tr_svc.set_situacao_veiculo(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, situacao="suspenso"
    )
    return VeiculoReguladoOut.model_validate(v)


@veiculos_router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)


# ============================ Documentos Veículo ==============================
documentos_router = APIRouter(
    prefix="/transporte-regulado/veiculos/{veiculo_id}/documentos",
    tags=["transporte-regulado-documentos"],
)


@documentos_router.get("", response_model=Paginated[VeiculoDocumentoOut])
async def list_documentos(
    veiculo_id: int,
    tipo_documento: str | None = None,
    situacao: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[VeiculoDocumentoOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_documentos(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        tipo_documento=tipo_documento,
        situacao=situacao,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[VeiculoDocumentoOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@documentos_router.post(
    "", response_model=VeiculoDocumentoOut, status_code=status.HTTP_201_CREATED
)
async def create_documento(
    veiculo_id: int,
    payload: VeiculoDocumentoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await tr_svc.criar_documento(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, payload=payload
    )
    return VeiculoDocumentoOut.model_validate(doc)


@documentos_router.get("/{documento_id}", response_model=VeiculoDocumentoOut)
async def get_documento(
    veiculo_id: int,
    documento_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await tr_svc.obter_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    return VeiculoDocumentoOut.model_validate(doc)


@documentos_router.put("/{documento_id}", response_model=VeiculoDocumentoOut)
async def update_documento(
    veiculo_id: int,
    documento_id: int,
    payload: VeiculoDocumentoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await tr_svc.atualizar_documento(
        db, tenant_id=tenant_id, documento_id=documento_id, payload=payload
    )
    return VeiculoDocumentoOut.model_validate(doc)


@documentos_router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_documento(
    veiculo_id: int,
    documento_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_documento(db, tenant_id=tenant_id, documento_id=documento_id)


# ============================ Avaliações Veículo ==============================
avaliacoes_router = APIRouter(
    prefix="/transporte-regulado/veiculos/{veiculo_id}/avaliacoes",
    tags=["transporte-regulado-avaliacoes"],
)


@avaliacoes_router.get("", response_model=Paginated[VeiculoAvaliacaoOut])
async def list_avaliacoes(
    veiculo_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[VeiculoAvaliacaoOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_avaliacoes(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, limit=page_size, offset=offset
    )
    return Paginated(
        items=[VeiculoAvaliacaoOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@avaliacoes_router.post(
    "", response_model=VeiculoAvaliacaoOut, status_code=status.HTTP_201_CREATED
)
async def create_avaliacao(
    veiculo_id: int,
    payload: VeiculoAvaliacaoCreate,
    usuario: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAvaliacaoOut:
    av = await tr_svc.criar_avaliacao(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        usuario_id=usuario.id,
        payload=payload,
    )
    return VeiculoAvaliacaoOut.model_validate(av)


@avaliacoes_router.get("/{avaliacao_id}", response_model=VeiculoAvaliacaoOut)
async def get_avaliacao(
    veiculo_id: int,
    avaliacao_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAvaliacaoOut:
    av = await tr_svc.obter_avaliacao(db, tenant_id=tenant_id, avaliacao_id=avaliacao_id)
    return VeiculoAvaliacaoOut.model_validate(av)


@avaliacoes_router.put("/{avaliacao_id}", response_model=VeiculoAvaliacaoOut)
async def update_avaliacao(
    veiculo_id: int,
    avaliacao_id: int,
    payload: VeiculoAvaliacaoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAvaliacaoOut:
    av = await tr_svc.atualizar_avaliacao(
        db, tenant_id=tenant_id, avaliacao_id=avaliacao_id, payload=payload
    )
    return VeiculoAvaliacaoOut.model_validate(av)


@avaliacoes_router.delete("/{avaliacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avaliacao(
    veiculo_id: int,
    avaliacao_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_avaliacao(db, tenant_id=tenant_id, avaliacao_id=avaliacao_id)


# ============================ Vistorias Veículo ===============================
vistorias_router = APIRouter(
    prefix="/transporte-regulado/veiculos/{veiculo_id}/vistorias",
    tags=["transporte-regulado-vistorias"],
)


@vistorias_router.get("", response_model=Paginated[VeiculoVistoriaOut])
async def list_vistorias(
    veiculo_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[VeiculoVistoriaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_vistorias(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, limit=page_size, offset=offset
    )
    return Paginated(
        items=[VeiculoVistoriaOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@vistorias_router.post(
    "", response_model=VeiculoVistoriaOut, status_code=status.HTTP_201_CREATED
)
async def create_vistoria(
    veiculo_id: int,
    payload: VeiculoVistoriaCreate,
    usuario: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await tr_svc.criar_vistoria(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        auditor_id=usuario.id,
        payload=payload,
    )
    return VeiculoVistoriaOut.model_validate(v)


# ORDEM IMPORTA: precisa vir antes de `/{vistoria_id}`. O FastAPI casa rotas na
# ordem de declaração, e `/{vistoria_id}: int` engole "vencidas" e devolve 422.
# Travado por test_http_vencidas_nao_e_engolida_por_vistoria_id.
@vistorias_router.get("/vencidas", response_model=Paginated[VeiculoVistoriaOut])
async def list_vistorias_vencidas(
    veiculo_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[VeiculoVistoriaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_vistorias_vencidas(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, limit=page_size, offset=offset
    )
    return Paginated(
        items=[VeiculoVistoriaOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@vistorias_router.get("/{vistoria_id}", response_model=VeiculoVistoriaOut)
async def get_vistoria(
    veiculo_id: int,
    vistoria_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await tr_svc.obter_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
    return VeiculoVistoriaOut.model_validate(v)


@vistorias_router.put("/{vistoria_id}", response_model=VeiculoVistoriaOut)
async def update_vistoria(
    veiculo_id: int,
    vistoria_id: int,
    payload: VeiculoVistoriaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await tr_svc.atualizar_vistoria(
        db, tenant_id=tenant_id, vistoria_id=vistoria_id, payload=payload
    )
    return VeiculoVistoriaOut.model_validate(v)


@vistorias_router.delete("/{vistoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vistoria(
    veiculo_id: int,
    vistoria_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)


@vistorias_router.post(
    "/{vistoria_id}/renovar",
    response_model=VeiculoVistoriaOut,
    status_code=status.HTTP_201_CREATED,
)
async def renovar_vistoria(
    veiculo_id: int,
    vistoria_id: int,
    payload: VeiculoVistoriaRenovarInput,
    usuario: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await tr_svc.renovar_vistoria(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        vistoria_id=vistoria_id,
        auditor_id=usuario.id,
        payload=payload,
    )
    return VeiculoVistoriaOut.model_validate(v)


# ================================ Alvarás (P2) ================================

alvaras_router = APIRouter(
    prefix="/transporte-regulado/alvaras", tags=["transporte-regulado"]
)


@alvaras_router.get("", response_model=Paginated[AlvaraOut])
async def list_alvaras(
    empresa_id: int | None = None,
    permissionario_id: int | None = None,
    q: str | None = Query(None, description="Busca por número do alvará (substring)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraOut]:
    # `q` é do SERVIDOR de propósito. A tela filtrava no cliente sobre a página
    # já truncada em `page_size`, então busca por número que estivesse fora da
    # primeira página devolvia "nada encontrado" com o registro no banco.
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_alvaras(
        db,
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        permissionario_id=permissionario_id,
        q=q,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[AlvaraOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ORDEM IMPORTA: estas rotas de segmento literal precisam vir antes de
# `/{alvara_id}`. O FastAPI casa na ordem de declaração, e a paramétrica engole
# "vencidos" e "relatorio", devolvendo 422 sem chegar no handler.
# Travado por tests/test_guarda_ordem_rotas.py.
@alvaras_router.get("/vencidos", response_model=Paginated[AlvaraOut])
async def list_alvaras_vencidos(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraOut]:
    """Lista alvarás vencidos (data_validade <= hoje) do tenant."""
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_alvaras_vencidos(db, tenant_id=tenant_id, limit=page_size, offset=offset)
    return Paginated(
        items=[AlvaraOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@alvaras_router.get("/relatorio", response_model=AlvaraRelatorioListResponse)
async def listar_relatorio(
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraRelatorioListResponse:
    """Lista alvarás com KPIs para relatório.

    Filtros opcionais:
    - tipo_servico: filtrar por tipo de serviço
    - id_permissionario: filtrar por permissionário
    - status: filtrar por status (ativo, vencido, a_renovar_30d, indefinido)
    """
    alvaras, total = await tr_svc.listar_relatorio_alvaras(
        db,
        tenant_id=tenant_id,
        tipo_servico=tipo_servico,
        id_permissionario=id_permissionario,
        status_filtro=status,
        limit=limit,
        offset=offset,
    )
    return AlvaraRelatorioListResponse(
        alvaras=[AlvaraRelatorioItem.model_validate(a) for a in alvaras],
        total=total,
        limit=limit,
        offset=offset,
    )


@alvaras_router.get("/{alvara_id}", response_model=AlvaraOut)
async def get_alvara(
    alvara_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraOut:
    a = await tr_svc.obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)
    return AlvaraOut.model_validate(a)


@alvaras_router.post("", response_model=AlvaraOut, status_code=status.HTTP_201_CREATED)
async def create_alvara(
    payload: AlvaraCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraOut:
    a = await tr_svc.criar_alvara(db, tenant_id=tenant_id, payload=payload)
    return AlvaraOut.model_validate(a)


@alvaras_router.put("/{alvara_id}", response_model=AlvaraOut)
async def update_alvara(
    alvara_id: int,
    payload: AlvaraUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraOut:
    a = await tr_svc.atualizar_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id, payload=payload
    )
    return AlvaraOut.model_validate(a)


@alvaras_router.delete("/{alvara_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alvara(
    alvara_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)


# ============================ Relatório (P4.3) ================================


@alvaras_router.get("/relatorio/kpis", response_model=AlvaraKPIsResponse)
async def obter_kpis_relatorio(
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraKPIsResponse:
    """Retorna KPIs agregados de alvarás (total, ativos, vencidos, a_renovar_30d, indefinidos)."""
    kpis = await tr_svc.obter_kpis_agregados(db, tenant_id=tenant_id)
    return AlvaraKPIsResponse(**kpis)


@alvaras_router.get("/relatorio/export/csv")
async def exportar_relatorio_csv(
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    status: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Exporta relatório de alvarás em formato CSV (streaming — sem carregar tudo em RAM)."""
    async def csv_generator():
        # Header do CSV
        header = "id,numero_alvara,tipo_servico,id_permissionario,id_empresa,data_inicio,data_validade,criado_em,status,dias_para_vencimento\r\n"
        yield header

        # Fetch em batches de 500 para evitar RAM picos
        offset = 0
        batch_size = 500
        while True:
            alvaras, _ = await tr_svc.listar_relatorio_alvaras(
                db,
                tenant_id=tenant_id,
                tipo_servico=tipo_servico,
                id_permissionario=id_permissionario,
                status_filtro=status,
                limit=batch_size,
                offset=offset,
            )
            if not alvaras:
                break

            # Converter batch para CSV linhas (escape valores com quote se necessário)
            import csv
            for alvara in alvaras:
                # Usar CSV writer para escape correto
                row_str = tr_svc.format_csv_row(alvara)
                yield row_str

            offset += batch_size

    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alvaras_relatorio.csv"},
    )


@alvaras_router.post("/{alvara_id}/renovar", response_model=AlvaraOut)
async def renovate_alvara(
    alvara_id: int,
    payload: AlvaraRenovarInput,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraOut:
    """Renova um alvará vencido — cria novo alvará atrelado ao anterior via renovado_de."""
    return await tr_svc.renovar_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id, payload=payload)


@alvaras_router.post("/{alvara_id}/revogar", response_model=AlvaraOut)
async def revogar_alvara(
    alvara_id: int,
    payload: AlvaraRevogar,
    usuario: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraOut:
    """Revoga um alvará vigente (P8 D2) — motivo obrigatório."""
    a = await tr_svc.revogar_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id,
        motivo=payload.motivo, usuario_id=usuario.id,
    )
    return AlvaraOut.model_validate(a)


# ============================ Documentos de Alvarás ==========================


@alvaras_router.get("/{alvara_id}/documentos", response_model=Paginated[AlvaraDocumentoOut])
async def list_alvara_documentos(
    alvara_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraDocumentoOut]:
    """Lista documentos de um alvará."""
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_alvara_documentos(
        db, tenant_id=tenant_id, alvara_id=alvara_id, limit=page_size, offset=offset
    )
    return Paginated(
        items=[AlvaraDocumentoOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@alvaras_router.post(
    "/{alvara_id}/documentos", response_model=AlvaraDocumentoOut, status_code=status.HTTP_201_CREATED
)
async def create_alvara_documento(
    alvara_id: int,
    payload: AlvaraDocumentoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraDocumentoOut:
    """Cria documento anexado a um alvará."""
    return await tr_svc.criar_alvara_documento(
        db, tenant_id=tenant_id, alvara_id=alvara_id, payload=payload
    )


@alvaras_router.get("/{alvara_id}/documentos/{documento_id}", response_model=AlvaraDocumentoOut)
async def get_alvara_documento(
    alvara_id: int,
    documento_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraDocumentoOut:
    """Obtém um documento de alvará."""
    return await tr_svc.obter_alvara_documento(db, tenant_id=tenant_id, documento_id=documento_id)


@alvaras_router.put("/{alvara_id}/documentos/{documento_id}", response_model=AlvaraDocumentoOut)
async def update_alvara_documento(
    alvara_id: int,
    documento_id: int,
    payload: AlvaraDocumentoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraDocumentoOut:
    """Atualiza documento de um alvará."""
    return await tr_svc.atualizar_alvara_documento(
        db, tenant_id=tenant_id, documento_id=documento_id, payload=payload
    )


@alvaras_router.delete("/{alvara_id}/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alvara_documento(
    alvara_id: int,
    documento_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-deleta um documento de alvará."""
    await tr_svc.excluir_alvara_documento(db, tenant_id=tenant_id, documento_id=documento_id)


# ============================ Responsáveis de Alvarás ==========================


@alvaras_router.get("/{alvara_id}/responsaveis", response_model=Paginated[AlvaraResponsavelOut])
async def list_alvara_responsaveis(
    alvara_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraResponsavelOut]:
    """Lista responsáveis de um alvará."""
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_responsaveis(
        db, tenant_id=tenant_id, alvara_id=alvara_id, limit=page_size, offset=offset
    )
    return Paginated(
        items=[AlvaraResponsavelOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@alvaras_router.post(
    "/{alvara_id}/responsaveis", response_model=AlvaraResponsavelOut, status_code=status.HTTP_201_CREATED
)
async def add_alvara_responsavel(
    alvara_id: int,
    payload: AlvaraResponsavelCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraResponsavelOut:
    """Adiciona usuário como responsável por um alvará."""
    return await tr_svc.adicionar_responsavel(
        db, tenant_id=tenant_id, alvara_id=alvara_id, payload=payload
    )


@alvaras_router.get("/{alvara_id}/responsaveis/{responsavel_id}", response_model=AlvaraResponsavelOut)
async def get_alvara_responsavel(
    alvara_id: int,
    responsavel_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraResponsavelOut:
    """Obtém um responsável de um alvará."""
    return await tr_svc.obter_responsavel(db, tenant_id=tenant_id, responsavel_id=responsavel_id)


@alvaras_router.delete("/{alvara_id}/responsaveis/{responsavel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alvara_responsavel(
    alvara_id: int,
    responsavel_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-deleta um responsável de um alvará."""
    await tr_svc.remover_responsavel(db, tenant_id=tenant_id, responsavel_id=responsavel_id)


# ============================ Veículos do Alvará (P4) ========================
@alvaras_router.post("/{alvara_id}/veiculos", response_model=AlvaraVeiculoOut, status_code=status.HTTP_201_CREATED)
async def vincular_veiculo_alvara(
    alvara_id: int,
    payload: AlvaraVeiculoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraVeiculoOut:
    """Vincula um veículo a um alvará."""
    av = await tr_svc.vincular_veiculo_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id, veiculo_id=payload.id_veiculo
    )
    return AlvaraVeiculoOut.model_validate(av)


@alvaras_router.delete("/{alvara_id}/veiculos/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desvincular_veiculo_alvara(
    alvara_id: int,
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Desvincula um veículo de um alvará."""
    await tr_svc.desvincular_veiculo_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id, veiculo_id=veiculo_id
    )


@alvaras_router.get("/{alvara_id}/veiculos", response_model=Paginated[AlvaraVeiculoOut])
async def listar_veiculos_alvara(
    alvara_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraVeiculoOut]:
    """Lista veículos vinculados a um alvará."""
    offset = (page - 1) * page_size
    avs, total = await tr_svc.listar_veiculos_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id, limit=page_size, offset=offset)
    return Paginated(
        items=[AlvaraVeiculoOut.model_validate(av) for av in avs],
        total=total,
        page=page,
        page_size=page_size,
    )


@alvaras_router.get("/veiculos/{veiculo_id}/alvaras", response_model=Paginated[AlvaraVeiculoOut])
async def listar_alvaras_veiculo(
    veiculo_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraVeiculoOut]:
    """Lista alvarás vinculados a um veículo."""
    offset = (page - 1) * page_size
    avs, total = await tr_svc.listar_alvaras_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id, limit=page_size, offset=offset)
    return Paginated(
        items=[AlvaraVeiculoOut.model_validate(av) for av in avs],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================ Auditoria de Alvará (P4) ========================
@alvaras_router.get("/{alvara_id}/auditoria", response_model=AlvaraAuditoriaListResponse)
async def listar_auditoria_alvara(
    alvara_id: int,
    limit: int = 50,
    offset: int = 0,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraAuditoriaListResponse:
    """Lista histórico de auditoria de um alvará (trail de mudanças)."""
    eventos = await tr_svc.listar_auditoria_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id, limit=limit, offset=offset
    )
    return AlvaraAuditoriaListResponse(eventos=[e for e in eventos])


# ========================= Recadastramento (P5.1) =========================
#
# Recadastramento não é renovação de alvará: renovação trata do documento de
# operação, recadastramento de o titular continuar elegível.
#
# Todos os endpoints passam por `require_permission("transporte_regulado")`,
# que é também o gate de contratação do módulo — transação de módulo não
# contratado entra no conjunto de bloqueados ANTES do bypass de super-usuário.
# Leitura sem `action`; escrita com `inserir`/`atualizar`/`excluir`. Nunca
# `"visualizar"`: não é uma `Action` válida e vira 500 para usuário comum.

recadastramento_router = APIRouter(
    prefix="/transporte-regulado/recadastramento", tags=["transporte-regulado"]
)


@recadastramento_router.get("/ciclos", response_model=Paginated[RecadastramentoCicloOut])
async def list_ciclos_recadastramento(
    situacao: str | None = None,
    q: str | None = Query(None, description="Busca por nome do ciclo (substring)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[RecadastramentoCicloOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_ciclos(
        db, tenant_id=tenant_id, situacao=situacao, q=q, limit=page_size, offset=offset
    )
    return Paginated(
        items=[RecadastramentoCicloOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@recadastramento_router.post(
    "/ciclos",
    response_model=RecadastramentoCicloOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ciclo_recadastramento(
    payload: RecadastramentoCicloCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoCicloOut:
    ciclo = await tr_svc.criar_ciclo(db, tenant_id=tenant_id, payload=payload)
    return RecadastramentoCicloOut.model_validate(ciclo)


@recadastramento_router.get(
    "/ciclos/{ciclo_id}", response_model=RecadastramentoCicloOut
)
async def get_ciclo_recadastramento(
    ciclo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoCicloOut:
    ciclo = await tr_svc.obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    return RecadastramentoCicloOut.model_validate(ciclo)


@recadastramento_router.put(
    "/ciclos/{ciclo_id}", response_model=RecadastramentoCicloOut
)
async def update_ciclo_recadastramento(
    ciclo_id: int,
    payload: RecadastramentoCicloUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoCicloOut:
    ciclo = await tr_svc.atualizar_ciclo(
        db, tenant_id=tenant_id, ciclo_id=ciclo_id, payload=payload
    )
    return RecadastramentoCicloOut.model_validate(ciclo)


@recadastramento_router.delete(
    "/ciclos/{ciclo_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_ciclo_recadastramento(
    ciclo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@recadastramento_router.post(
    "/ciclos/{ciclo_id}/gerar-convocacoes", response_model=RecadastramentoGeracaoOut
)
async def gerar_convocacoes_do_ciclo(
    ciclo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoGeracaoOut:
    """Ato explícito, não efeito de criar o ciclo: separar as duas coisas dá ao
    operador a chance de conferir janela e critério antes de comprometer prazos.
    Idempotente — rodar de novo alcança quem entrou depois, sem duplicar."""
    resultado = await tr_svc.gerar_convocacoes(
        db, tenant_id=tenant_id, ciclo_id=ciclo_id
    )
    return RecadastramentoGeracaoOut(**resultado)


@recadastramento_router.get(
    "/ciclos/{ciclo_id}/convocacoes",
    response_model=Paginated[RecadastramentoConvocacaoOut],
)
async def list_convocacoes_do_ciclo(
    ciclo_id: int,
    tipo: str | None = Query(None, description="permissionario | empresa"),
    q: str | None = Query(
        None, description="Busca por nome do permissionário ou razão social"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[RecadastramentoConvocacaoOut]:
    # `q` e `page` são do SERVIDOR. Filtrar no cliente sobre a página truncada
    # faz a tela afirmar que um registro não existe — foi o defeito que a fatia
    # anterior consertou na busca de alvarás.
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_convocacoes(
        db,
        tenant_id=tenant_id,
        ciclo_id=ciclo_id,
        tipo=tipo,
        q=q,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[RecadastramentoConvocacaoOut(**r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@recadastramento_router.put(
    "/convocacoes/{convocacao_id}/prazo",
    response_model=RecadastramentoConvocacaoOut,
)
async def ajustar_prazo_da_convocacao(
    convocacao_id: int,
    payload: RecadastramentoAjustePrazo,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoConvocacaoOut:
    """Justificativa obrigatória: sem ela o ajuste vira favor invisível.
    `ajustado_por` vem do token, nunca do payload."""
    conv = await tr_svc.ajustar_prazo(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        payload=payload,
        usuario_id=usuario.id,
    )
    return RecadastramentoConvocacaoOut(
        id=conv.id,
        id_ciclo=conv.id_ciclo,
        id_permissionario=conv.id_permissionario,
        id_empresa=conv.id_empresa,
        tipo_regulado="permissionario" if conv.id_permissionario else "empresa",
        nome_regulado=await tr_svc.nome_do_regulado(
            db, tenant_id=tenant_id, conv=conv
        ),
        prazo=conv.prazo,
        prazo_original=conv.prazo_original,
        ajustado=conv.ajustado_em is not None,
        ajuste_justificativa=conv.ajuste_justificativa,
        ajustado_por=conv.ajustado_por,
        ajustado_em=conv.ajustado_em,
        situacao=conv.situacao,
        criado_em=conv.criado_em,
    )


# =================== Recadastramento — atendimento (P5.2) ==================
#
# ORDEM IMPORTA: `/itens` e `/itens/{item_id}` são segmentos literais irmãos de
# `/ciclos/{ciclo_id}`, e vêm declarados no mesmo router do recadastramento.
# Não há colisão porque os prefixos diferem (`/itens` × `/ciclos`), mas a
# vizinhança é a mesma que já engoliu três rotas neste arquivo — por isso os
# literais vêm primeiro e `tests/test_guarda_ordem_rotas.py` varre a app.


@recadastramento_router.get(
    "/itens", response_model=Paginated[RecadastramentoItemOut]
)
async def list_itens_recadastramento(
    apenas_ativos: bool = False,
    aplica_a: str | None = Query(None, description="permissionario | empresa | ambos"),
    q: str | None = Query(None, description="Busca por descrição (substring)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[RecadastramentoItemOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_itens_recadastramento(
        db,
        tenant_id=tenant_id,
        apenas_ativos=apenas_ativos,
        aplica_a=aplica_a,
        q=q,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[RecadastramentoItemOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@recadastramento_router.post(
    "/itens",
    response_model=RecadastramentoItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_recadastramento(
    payload: RecadastramentoItemCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoItemOut:
    item = await tr_svc.criar_item_recadastramento(
        db, tenant_id=tenant_id, payload=payload
    )
    return RecadastramentoItemOut.model_validate(item)


@recadastramento_router.get(
    "/itens/{item_id}", response_model=RecadastramentoItemOut
)
async def get_item_recadastramento(
    item_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoItemOut:
    item = await tr_svc.obter_item_recadastramento(
        db, tenant_id=tenant_id, item_id=item_id
    )
    return RecadastramentoItemOut.model_validate(item)


@recadastramento_router.put(
    "/itens/{item_id}", response_model=RecadastramentoItemOut
)
async def update_item_recadastramento(
    item_id: int,
    payload: RecadastramentoItemUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoItemOut:
    item = await tr_svc.atualizar_item_recadastramento(
        db, tenant_id=tenant_id, item_id=item_id, payload=payload
    )
    return RecadastramentoItemOut.model_validate(item)


@recadastramento_router.delete(
    "/itens/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_item_recadastramento(
    item_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_item_recadastramento(
        db, tenant_id=tenant_id, item_id=item_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@recadastramento_router.get(
    "/convocacoes/{convocacao_id}/atendimento",
    response_model=RecadastramentoSituacaoAtendimentoOut,
)
async def get_atendimento(
    convocacao_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoSituacaoAtendimentoOut:
    """A ficha inteira numa chamada: checklist, vistorias e o PORQUÊ de o botão
    de deferir estar ou não habilitado. Um booleano solto viraria botão
    desabilitado sem explicação."""
    dados = await tr_svc.situacao_atendimento(
        db, tenant_id=tenant_id, convocacao_id=convocacao_id
    )
    return RecadastramentoSituacaoAtendimentoOut(**dados)


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/itens/{item_id}/marcar",
    response_model=RecadastramentoSituacaoAtendimentoOut,
)
async def marcar_item(
    convocacao_id: int,
    item_id: int,
    payload: RecadastramentoMarcarInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoSituacaoAtendimentoOut:
    """Devolve a ficha inteira, não a marca criada: depois de marcar, o que a
    tela precisa saber é se o botão de deferir mudou de estado."""
    await tr_svc.marcar_item_recadastramento(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        item_id=item_id,
        payload=payload,
        usuario_id=usuario.id,
    )
    dados = await tr_svc.situacao_atendimento(
        db, tenant_id=tenant_id, convocacao_id=convocacao_id
    )
    return RecadastramentoSituacaoAtendimentoOut(**dados)


@recadastramento_router.get(
    "/convocacoes/{convocacao_id}/decisoes",
    response_model=list[RecadastramentoDecisaoOut],
)
async def list_decisoes(
    convocacao_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[RecadastramentoDecisaoOut]:
    """Lista curta e sem paginação de propósito: são poucas decisões por
    convocação, e o histórico só faz sentido inteiro."""
    linhas = await tr_svc.listar_decisoes(
        db, tenant_id=tenant_id, convocacao_id=convocacao_id
    )
    return [RecadastramentoDecisaoOut.model_validate(d) for d in linhas]


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/deferir",
    response_model=RecadastramentoDecisaoOut,
)
async def deferir_convocacao(
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoDecisaoOut:
    """409 se faltar item obrigatório ou vistoria. O autor vem do token."""
    d = await tr_svc.decidir_recadastramento(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        tipo="deferimento",
        payload=payload,
        usuario_id=usuario.id,
    )
    return RecadastramentoDecisaoOut.model_validate(d)


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/indeferir",
    response_model=RecadastramentoDecisaoOut,
)
async def indeferir_convocacao(
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoDecisaoOut:
    """**NÃO exige completude**, ao contrário do deferimento. Indeferir por
    falta de documento é o caso real do balcão."""
    d = await tr_svc.decidir_recadastramento(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        tipo="indeferimento",
        payload=payload,
        usuario_id=usuario.id,
    )
    return RecadastramentoDecisaoOut.model_validate(d)


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/reabrir",
    response_model=RecadastramentoDecisaoOut,
)
async def reabrir_convocacao(
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoDecisaoOut:
    """Existe para que um deferimento errado não vire `UPDATE` manual em
    produção."""
    d = await tr_svc.reabrir_recadastramento(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        payload=payload,
        usuario_id=usuario.id,
    )
    return RecadastramentoDecisaoOut.model_validate(d)


# ==================================================================== P5.3


@recadastramento_router.get(
    "/ciclos/{ciclo_id}/faltosos",
    response_model=RecadastramentoFaltososOut,
)
async def relatorio_faltosos(
    ciclo_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoFaltososOut:
    """Quem perdeu o prazo e ainda não foi atendido.

    `hoje` não é parâmetro do endpoint de propósito: a data é do servidor.
    Aceitá-la da tela deixaria o relatório de faltosos depender do relógio do
    posto de atendimento.
    """
    dados = await tr_svc.listar_faltosos(
        db, tenant_id=tenant_id, ciclo_id=ciclo_id, limit=limit, offset=offset
    )
    return RecadastramentoFaltososOut.model_validate(dados)


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/suspender",
    response_model=RecadastramentoDecisaoOut,
)
async def suspender_convocacao(
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoDecisaoOut:
    """Ato humano, com parecer. Atinge SÓ a convocação — não muda a situação do
    regulado nem mexe em alvará."""
    d = await tr_svc.suspender_convocacao(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        payload=payload,
        usuario_id=usuario.id,
    )

    # Fase C2: e-mail ao TITULAR da convocação, com o PARECER no corpo — aqui
    # o destinatário é o próprio suspenso, diferente do e-mail neutro do job
    # (`notificar_recadastramento`). Sempre depois do commit acima, mesmo
    # padrão pós-commit do `POST /{id}/decidir` de ocorrências (P7): falha de
    # e-mail NUNCA desfaz o ato, que já está persistido.
    try:
        conv = await tr_svc.obter_convocacao(
            db, tenant_id=tenant_id, convocacao_id=convocacao_id
        )
        _nome, email, _telefone = await tr_svc.contato_do_regulado(
            db, tenant_id=tenant_id, conv=conv
        )
        if email:
            criadas = await notificacoes.enviar(
                db,
                tenant_id=tenant_id,
                destinatarios=[Destinatario(email=email)],
                canais=["email"],
                tipo="recadastramento.suspensao",
                titulo="Recadastramento suspenso",
                mensagem=(
                    "Sua convocação de recadastramento foi suspensa. "
                    f"Parecer: {d.parecer} "
                    "Para voltar a renovar seu alvará, procure a prefeitura "
                    "para reativação."
                ),
                link_url="/m/transporte/recadastramento",
                payload={"id_convocacao": convocacao_id, "gatilho": "suspensao"},
            )
            if criadas:
                db.add(
                    RecadastramentoNotificacao(
                        tenant_id=tenant_id,
                        id_convocacao=convocacao_id,
                        id_notificacao=criadas[0].id,
                        id_usuario=usuario.id,
                        gatilho="suspensao",
                        criado_em=datetime.utcnow(),
                    )
                )
                await db.commit()
        else:
            logger.info(
                "Suspensão da convocação %s sem e-mail do titular — sem aviso",
                convocacao_id,
            )
    except Exception:
        # Sessão pode ter sido envenenada por falha DB-level dentro do
        # `enviar` — sem o rollback, qualquer leitura seguinte estoura 500
        # mesmo com a suspensão já commitada com sucesso.
        await db.rollback()
        logger.exception(
            "Falha ao notificar suspensão da convocação %s", convocacao_id
        )

    return RecadastramentoDecisaoOut.model_validate(d)


@recadastramento_router.post(
    "/convocacoes/{convocacao_id}/reativar",
    response_model=RecadastramentoDecisaoOut,
)
async def reativar_convocacao(
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RecadastramentoDecisaoOut:
    """Desfaz a suspensão. É o deferimento do recurso, e o parecer é o
    julgamento — por isso não há entidade separada de recurso."""
    d = await tr_svc.reativar_convocacao(
        db,
        tenant_id=tenant_id,
        convocacao_id=convocacao_id,
        payload=payload,
        usuario_id=usuario.id,
    )

    # Fase C2: mesmo desenho pós-commit da suspensão acima — e-mail ao
    # titular, com o parecer (julgamento do recurso) no corpo, informando o
    # desbloqueio da renovação.
    try:
        conv = await tr_svc.obter_convocacao(
            db, tenant_id=tenant_id, convocacao_id=convocacao_id
        )
        _nome, email, _telefone = await tr_svc.contato_do_regulado(
            db, tenant_id=tenant_id, conv=conv
        )
        if email:
            criadas = await notificacoes.enviar(
                db,
                tenant_id=tenant_id,
                destinatarios=[Destinatario(email=email)],
                canais=["email"],
                tipo="recadastramento.reativacao",
                titulo="Recadastramento reativado",
                mensagem=(
                    "Sua convocação de recadastramento foi reativada. "
                    f"Parecer: {d.parecer} "
                    "A renovação do seu alvará está liberada novamente."
                ),
                link_url="/m/transporte/recadastramento",
                payload={"id_convocacao": convocacao_id, "gatilho": "reativacao"},
            )
            if criadas:
                db.add(
                    RecadastramentoNotificacao(
                        tenant_id=tenant_id,
                        id_convocacao=convocacao_id,
                        id_notificacao=criadas[0].id,
                        id_usuario=usuario.id,
                        gatilho="reativacao",
                        criado_em=datetime.utcnow(),
                    )
                )
                await db.commit()
        else:
            logger.info(
                "Reativação da convocação %s sem e-mail do titular — sem aviso",
                convocacao_id,
            )
    except Exception:
        await db.rollback()
        logger.exception(
            "Falha ao notificar reativação da convocação %s", convocacao_id
        )

    return RecadastramentoDecisaoOut.model_validate(d)


@recadastramento_router.post(
    "/ciclos/{ciclo_id}/notificar",
    response_model=list[RecadastramentoNotificacaoResultadoOut],
)
async def notificar_faltosos(
    ciclo_id: int,
    payload: RecadastramentoNotificarInput,
    usuario: Usuario = Depends(
        require_permission("transporte_regulado", "atualizar")
    ),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[RecadastramentoNotificacaoResultadoOut]:
    """Aviso em lote. Devolve o resultado POR item: cadastro sem contato volta
    como `sem_contato` e não derruba o resto do lote."""
    resultados = await tr_svc.notificar_faltosos(
        db,
        tenant_id=tenant_id,
        ciclo_id=ciclo_id,
        convocacao_ids=payload.convocacao_ids,
        usuario_id=usuario.id,
    )
    return [
        RecadastramentoNotificacaoResultadoOut.model_validate(r) for r in resultados
    ]


# ============================================================ P6: pontos e vagas

pontos_router = APIRouter(
    prefix="/transporte-regulado/pontos", tags=["transporte-regulado"]
)


def _ponto_out(ponto, ocupadas: int) -> PontoOut:
    saida = PontoOut.model_validate(ponto)
    saida.vagas_ocupadas = ocupadas
    return saida


@pontos_router.get("", response_model=Paginated[PontoOut])
async def list_pontos(
    q: str | None = Query(None, description="Busca por nome do ponto (substring)"),
    tipo_servico: str | None = None,
    situacao: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PontoOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_pontos(
        db,
        tenant_id=tenant_id,
        q=q,
        tipo_servico=tipo_servico,
        situacao=situacao,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[_ponto_out(p, n) for p, n in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@pontos_router.post("", response_model=PontoOut, status_code=status.HTTP_201_CREATED)
async def create_ponto(
    payload: PontoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoOut:
    ponto = await tr_svc.criar_ponto(db, tenant_id=tenant_id, payload=payload)
    await db.commit()
    await db.refresh(ponto)
    return _ponto_out(ponto, 0)


# ATENÇÃO à ordem: as rotas de segmento literal (`/{id}/mapa`, `/{id}/ocupacoes`)
# vêm depois de `/{ponto_id}` mas NÃO conflitam, porque o literal está no
# segundo segmento. O que não pode acontecer é uma rota como `/vagas-livres`
# depois de `/{ponto_id}` — o FastAPI casa na ordem de declaração e a
# paramétrica engoliria a literal, devolvendo 422 sem chegar ao handler. Isso
# aconteceu TRÊS vezes neste arquivo; `tests/test_guarda_ordem_rotas.py` varre a
# aplicação inteira e reprova.
@pontos_router.get("/{ponto_id}", response_model=PontoOut)
async def get_ponto(
    ponto_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoOut:
    ponto, ocupadas = await tr_svc.obter_ponto(
        db, tenant_id=tenant_id, ponto_id=ponto_id
    )
    return _ponto_out(ponto, ocupadas)


@pontos_router.put("/{ponto_id}", response_model=PontoOut)
async def update_ponto(
    ponto_id: int,
    payload: PontoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoOut:
    ponto = await tr_svc.atualizar_ponto(
        db, tenant_id=tenant_id, ponto_id=ponto_id, payload=payload
    )
    await db.commit()
    _, ocupadas = await tr_svc.obter_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    return _ponto_out(ponto, ocupadas)


@pontos_router.delete("/{ponto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ponto(
    ponto_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@pontos_router.get("/{ponto_id}/mapa", response_model=PontoMapaOut)
async def get_mapa_de_vagas(
    ponto_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoMapaOut:
    return PontoMapaOut.model_validate(
        await tr_svc.mapa_de_vagas(db, tenant_id=tenant_id, ponto_id=ponto_id)
    )


@pontos_router.get(
    "/{ponto_id}/ocupacoes", response_model=Paginated[PontoOcupacaoOut]
)
async def list_ocupacoes(
    ponto_id: int,
    apenas_vigentes: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PontoOcupacaoOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_ocupacoes(
        db,
        tenant_id=tenant_id,
        ponto_id=ponto_id,
        apenas_vigentes=apenas_vigentes,
        limit=page_size,
        offset=offset,
    )
    return Paginated(
        items=[PontoOcupacaoOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@pontos_router.post(
    "/{ponto_id}/ocupacoes",
    response_model=PontoOcupacaoOut,
    status_code=status.HTTP_201_CREATED,
)
async def ocupar_vaga(
    ponto_id: int,
    payload: PontoOcuparInput,
    # `atualizar` e não `inserir`: ocupar uma vaga não cria um cadastro novo,
    # muda o estado de um ponto existente. Quem pode remanejar vaga é quem
    # administra o ponto.
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoOcupacaoOut:
    ocupacao = await tr_svc.ocupar_vaga(
        db, tenant_id=tenant_id, ponto_id=ponto_id, payload=payload
    )
    await db.commit()
    await db.refresh(ocupacao)
    return PontoOcupacaoOut.model_validate(ocupacao)


@pontos_router.post(
    "/{ponto_id}/ocupacoes/{ocupacao_id}/liberar", response_model=PontoOcupacaoOut
)
async def liberar_vaga(
    ponto_id: int,
    ocupacao_id: int,
    payload: PontoLiberarInput,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PontoOcupacaoOut:
    ocupacao = await tr_svc.liberar_vaga(
        db,
        tenant_id=tenant_id,
        ponto_id=ponto_id,
        ocupacao_id=ocupacao_id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(ocupacao)
    return PontoOcupacaoOut.model_validate(ocupacao)


linhas_router = APIRouter(
    prefix="/transporte-regulado/linhas", tags=["transporte-regulado"]
)


async def _linha_out(db, linha, *, com_filhas: bool, tenant_id: int) -> LinhaOut:
    saida = LinhaOut.model_validate(linha)
    if linha.id_empresa is not None:
        emp = await db.get(Empresa, linha.id_empresa)
        saida.operador_nome = emp.razao_social if emp else None
    elif linha.id_permissionario is not None:
        perm = await db.get(Permissionario, linha.id_permissionario)
        saida.operador_nome = perm.nome if perm else None
    horarios = await tr_svc.listar_horarios(
        db, tenant_id=tenant_id, linha_id=linha.id
    )
    saida.total_horarios = len(horarios)
    if com_filhas:
        saida.horarios = [LinhaHorarioOut.model_validate(h) for h in horarios]
        saida.paradas = [
            LinhaParadaOut.model_validate(p)
            for p in await tr_svc.listar_paradas(
                db, tenant_id=tenant_id, linha_id=linha.id
            )
        ]
    return saida


@linhas_router.get("", response_model=Paginated[LinhaOut])
async def list_linhas(
    q: str | None = Query(None, description="Busca por nome ou código (substring)"),
    tipo_servico: str | None = None,
    situacao: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[LinhaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_linhas(
        db, tenant_id=tenant_id, q=q, tipo_servico=tipo_servico,
        situacao=situacao, limit=page_size, offset=offset,
    )
    # Resolução em LOTE (3 queries fixas, não uma por linha): a listagem não
    # precisa dos filhos (`com_filhas=False`), só de operador_nome/total_horarios.
    linha_ids = [l.id for l in rows]
    empresa_ids = [l.id_empresa for l in rows if l.id_empresa is not None]
    permissionario_ids = [
        l.id_permissionario for l in rows if l.id_permissionario is not None
    ]
    horarios_por_linha, empresas, permissionarios = (
        await tr_svc.contar_horarios_por_linhas(
            db, tenant_id=tenant_id, linha_ids=linha_ids
        ),
        await tr_svc.nomes_empresas(db, tenant_id=tenant_id, empresa_ids=empresa_ids),
        await tr_svc.nomes_permissionarios(
            db, tenant_id=tenant_id, permissionario_ids=permissionario_ids
        ),
    )
    items = []
    for l in rows:
        saida = LinhaOut.model_validate(l)
        if l.id_empresa is not None:
            saida.operador_nome = empresas.get(l.id_empresa)
        elif l.id_permissionario is not None:
            saida.operador_nome = permissionarios.get(l.id_permissionario)
        saida.total_horarios = horarios_por_linha.get(l.id, 0)
        items.append(saida)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@linhas_router.post("", response_model=LinhaOut, status_code=status.HTTP_201_CREATED)
async def create_linha(
    payload: LinhaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.criar_linha(db, tenant_id=tenant_id, payload=payload)
    await db.commit()
    await db.refresh(linha)
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.get("/{linha_id}", response_model=LinhaOut)
async def get_linha(
    linha_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.put("/{linha_id}", response_model=LinhaOut)
async def update_linha(
    linha_id: int,
    payload: LinhaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.atualizar_linha(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.delete("/{linha_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_linha(
    linha_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@linhas_router.post(
    "/{linha_id}/paradas",
    response_model=LinhaParadaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_parada(
    linha_id: int,
    payload: LinhaParadaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaParadaOut:
    parada = await tr_svc.criar_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return LinhaParadaOut.model_validate(parada)


# ATENÇÃO à ordem: `/paradas/ordem` é literal irmã de `/paradas/{parada_id}` e
# TEM de vir antes — a paramétrica engoliria a literal com 422 sem chegar ao
# handler. Esse defeito já ocorreu TRÊS vezes neste arquivo;
# `tests/test_guarda_ordem_rotas.py` varre e reprova.
@linhas_router.put("/{linha_id}/paradas/ordem", response_model=list[LinhaParadaOut])
async def reordenar_paradas(
    linha_id: int,
    payload: LinhaParadasOrdemInput,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[LinhaParadaOut]:
    paradas = await tr_svc.reordenar_paradas(
        db, tenant_id=tenant_id, linha_id=linha_id, ids=payload.ids
    )
    await db.commit()
    return [LinhaParadaOut.model_validate(p) for p in paradas]


@linhas_router.put("/{linha_id}/paradas/{parada_id}", response_model=LinhaParadaOut)
async def update_parada(
    linha_id: int,
    parada_id: int,
    payload: LinhaParadaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaParadaOut:
    parada = await tr_svc.atualizar_parada(
        db, tenant_id=tenant_id, linha_id=linha_id,
        parada_id=parada_id, payload=payload,
    )
    await db.commit()
    return LinhaParadaOut.model_validate(parada)


@linhas_router.delete(
    "/{linha_id}/paradas/{parada_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_parada(
    linha_id: int,
    parada_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@linhas_router.post(
    "/{linha_id}/horarios",
    response_model=LinhaHorarioOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_horario(
    linha_id: int,
    payload: LinhaHorarioCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaHorarioOut:
    horario = await tr_svc.criar_horario(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return LinhaHorarioOut.model_validate(horario)


@linhas_router.delete(
    "/{linha_id}/horarios/{horario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_horario(
    linha_id: int,
    horario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_horario(
        db, tenant_id=tenant_id, linha_id=linha_id, horario_id=horario_id
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


ocorrencias_router = APIRouter(
    prefix="/transporte-regulado/ocorrencias", tags=["transporte-regulado"]
)


async def _ocorrencia_out(
    db, oc, *, com_trilha: bool, tenant_id: int
) -> OcorrenciaOut:
    saida = OcorrenciaOut.model_validate(oc)

    tipo = await db.get(OcorrenciaTipo, oc.id_tipo)
    saida.tipo_nome = tipo.nome if tipo else None

    partes: list[str] = []
    if oc.id_permissionario is not None:
        perm = await db.get(Permissionario, oc.id_permissionario)
        if perm and perm.nome:
            partes.append(perm.nome)
    if oc.id_empresa is not None:
        emp = await db.get(Empresa, oc.id_empresa)
        if emp and emp.razao_social:
            partes.append(emp.razao_social)
    if oc.id_veiculo is not None:
        veic = await db.get(VeiculoRegulado, oc.id_veiculo)
        if veic and veic.placa:
            partes.append(veic.placa)
    saida.alvo_resumo = " - ".join(partes) if partes else None

    if com_trilha:
        andamentos = await tr_svc.listar_andamentos(
            db, tenant_id=tenant_id, ocorrencia_id=oc.id
        )
        itens = []
        for a in andamentos:
            item = OcorrenciaAndamentoOut.model_validate(a)
            if a.id_usuario is not None:
                usuario = await db.get(Usuario, a.id_usuario)
                item.usuario_nome = usuario.nome if usuario else None
            itens.append(item)
        saida.andamentos = itens

    return saida


# `/tipos*` e literal irma de `/{ocorrencia_id}` - declarada ANTES. Defeito
# recorrente neste arquivo (parametrica engolindo literal -> 422);
# `tests/test_guarda_ordem_rotas.py` reprova.
@ocorrencias_router.get("/tipos", response_model=list[OcorrenciaTipoOut])
async def list_ocorrencia_tipos(
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[OcorrenciaTipoOut]:
    tipos = await tr_svc.listar_tipos_ocorrencia(db, tenant_id=tenant_id)
    return [OcorrenciaTipoOut.model_validate(t) for t in tipos]


@ocorrencias_router.post(
    "/tipos", response_model=OcorrenciaTipoOut, status_code=status.HTTP_201_CREATED
)
async def create_ocorrencia_tipo(
    payload: OcorrenciaTipoCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaTipoOut:
    tipo = await tr_svc.criar_tipo_ocorrencia(db, tenant_id=tenant_id, payload=payload)
    await db.commit()
    return OcorrenciaTipoOut.model_validate(tipo)


@ocorrencias_router.put("/tipos/{tipo_id}", response_model=OcorrenciaTipoOut)
async def update_ocorrencia_tipo(
    tipo_id: int,
    payload: OcorrenciaTipoUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaTipoOut:
    tipo = await tr_svc.atualizar_tipo_ocorrencia(
        db, tenant_id=tenant_id, tipo_id=tipo_id, payload=payload
    )
    await db.commit()
    return OcorrenciaTipoOut.model_validate(tipo)


@ocorrencias_router.delete(
    "/tipos/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_ocorrencia_tipo(
    tipo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_tipo_ocorrencia(db, tenant_id=tenant_id, tipo_id=tipo_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@ocorrencias_router.get("", response_model=Paginated[OcorrenciaOut])
async def list_ocorrencias(
    q: str | None = Query(None, description="Busca por descricao ou referencia (substring)"),
    situacao: str | None = None,
    origem: str | None = None,
    id_tipo: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[OcorrenciaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_ocorrencias(
        db, tenant_id=tenant_id, q=q, situacao=situacao, origem=origem,
        id_tipo=id_tipo, limit=page_size, offset=offset,
    )
    return Paginated(
        items=[
            await _ocorrencia_out(db, oc, com_trilha=False, tenant_id=tenant_id)
            for oc in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@ocorrencias_router.post(
    "", response_model=OcorrenciaOut, status_code=status.HTTP_201_CREATED
)
async def create_ocorrencia(
    payload: OcorrenciaCreate,
    user: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.registrar_ocorrencia(
        db, tenant_id=tenant_id, payload=payload, id_usuario=user.id,
    )
    await db.commit()
    await db.refresh(ocorrencia)
    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.get("/{ocorrencia_id}", response_model=OcorrenciaOut)
async def get_ocorrencia(
    ocorrencia_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.obter_ocorrencia(
        db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id
    )
    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.post("/{ocorrencia_id}/apurar", response_model=OcorrenciaOut)
async def apurar_ocorrencia(
    ocorrencia_id: int,
    user: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.iniciar_apuracao(
        db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id, id_usuario=user.id,
    )
    await db.commit()
    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.post("/{ocorrencia_id}/anotar", response_model=OcorrenciaOut)
async def anotar_ocorrencia(
    ocorrencia_id: int,
    payload: OcorrenciaAnotarInput,
    user: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.anotar_ocorrencia(
        db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id,
        parecer=payload.parecer, id_usuario=user.id,
    )
    await db.commit()
    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.post("/{ocorrencia_id}/vincular-alvo", response_model=OcorrenciaOut)
async def vincular_alvo_ocorrencia(
    ocorrencia_id: int,
    payload: OcorrenciaVincularInput,
    user: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.vincular_alvo_ocorrencia(
        db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id,
        id_permissionario=payload.id_permissionario,
        id_empresa=payload.id_empresa,
        id_veiculo=payload.id_veiculo,
        id_usuario=user.id,
    )
    await db.commit()
    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.post("/{ocorrencia_id}/decidir", response_model=OcorrenciaOut)
async def decidir_ocorrencia(
    ocorrencia_id: int,
    payload: OcorrenciaDecidirInput,
    user: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OcorrenciaOut:
    ocorrencia = await tr_svc.decidir_ocorrencia(
        db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id,
        resultado=payload.resultado, parecer=payload.parecer, id_usuario=user.id,
    )
    await db.commit()

    # P7.2: notifica o cidadão que registrou a denúncia — SEMPRE depois do
    # commit da decisão, nunca antes. `enviar` faz commit próprio; falha de
    # e-mail (SMTP fora, cidadão sem e-mail já filtrado abaixo, driver com
    # erro) NUNCA desfaz a decisão, que já está persistida.
    if ocorrencia.id_cidadao:
        try:
            cidadao_denunciante = await db.get(UsuarioExterno, ocorrencia.id_cidadao)
            if cidadao_denunciante and cidadao_denunciante.email:
                await notificacoes.enviar(
                    db, tenant_id=tenant_id,
                    destinatarios=[Destinatario(email=cidadao_denunciante.email)],
                    canais=["email"],
                    tipo="denuncia_decidida",
                    titulo="Sua denúncia foi analisada",
                    mensagem=(
                        f"A denúncia nº {ocorrencia.id} foi analisada. "
                        "Acompanhe a situação no portal do cidadão."
                    ),
                    link_url="/cidadao/denuncias",
                )
        except Exception:
            # Sessão pode ter sido envenenada por falha DB-level dentro do
            # `enviar` (ex.: erro ao gravar log de notificação) — sem o
            # rollback, o SELECT do `_ocorrencia_out` logo abaixo estoura
            # 500 mesmo com a decisão já commitada com sucesso.
            await db.rollback()
            logger.exception(
                "Falha ao notificar cidadão da decisão da ocorrência %s",
                ocorrencia.id,
            )

    return await _ocorrencia_out(db, ocorrencia, com_trilha=True, tenant_id=tenant_id)


@ocorrencias_router.delete(
    "/{ocorrencia_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_ocorrencia(
    ocorrencia_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------- P7.2: realm cidadão (denúncias)
#
# Outro realm: `get_current_cidadao` + `require_tenant_id`, NUNCA
# `require_permission` — não há transação municipal nem grupo/nível aqui.
# A saída usa `DenunciaCidadaoOut`, schema fechado, sem trilha/parecer/alvo.

cidadao_denuncias_router = APIRouter(prefix="/cidadao/denuncias", tags=["cidadao"])


@cidadao_denuncias_router.get("/tipos", response_model=list[OcorrenciaTipoOut])
async def listar_tipos_denuncia_cidadao(
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[OcorrenciaTipoOut]:
    tipos = await tr_svc.listar_tipos_ocorrencia(db, tenant_id=tenant_id)
    return [OcorrenciaTipoOut.model_validate(t) for t in tipos if t.ativo]


@cidadao_denuncias_router.post(
    "", response_model=DenunciaCidadaoOut, status_code=status.HTTP_201_CREATED
)
async def registrar_denuncia_cidadao_endpoint(
    payload: DenunciaCidadaoCreate,
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> DenunciaCidadaoOut:
    ocorrencia = await tr_svc.registrar_denuncia_cidadao(
        db, tenant_id=tenant_id, cidadao=cidadao, payload=payload,
    )
    await db.commit()
    await db.refresh(ocorrencia)
    tipo = await db.get(OcorrenciaTipo, ocorrencia.id_tipo)
    saida = DenunciaCidadaoOut.model_validate(ocorrencia)
    saida.tipo_nome = tipo.nome if tipo else None
    return saida


@cidadao_denuncias_router.get("", response_model=list[DenunciaCidadaoOut])
async def listar_minhas_denuncias_endpoint(
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[DenunciaCidadaoOut]:
    ocorrencias = await tr_svc.listar_denuncias_do_cidadao(
        db, tenant_id=tenant_id, id_cidadao=cidadao.id,
    )
    return [DenunciaCidadaoOut.model_validate(oc) for oc in ocorrencias]


# ============================================================================
# Painel de workflow (P8 D3, Task 6) — leitura só, entidade polimórfica.
# ============================================================================

workflow_router = APIRouter(
    prefix="/transporte-regulado/workflow", tags=["transporte-regulado"]
)


@workflow_router.get(
    "/{entidade_tipo}/{entidade_id}", response_model=WorkflowEntidadeOut
)
async def get_workflow_de_entidade(
    entidade_tipo: Literal["ocorrencia", "alvara", "convocacao"],
    entidade_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> WorkflowEntidadeOut:
    """Autorização antes de resolver: carrega a entidade (404 cross-tenant/
    inexistente) ANTES de tocar a `WorkflowInstance` — mesma disciplina do
    guard de anexo sigiloso, sem o sigilo (ocorrência/alvará/convocação não
    têm `nivel_sigilo`; tenant+excluido basta)."""
    if entidade_tipo == "ocorrencia":
        await tr_svc.obter_ocorrencia(
            db, tenant_id=tenant_id, ocorrencia_id=entidade_id
        )
    elif entidade_tipo == "alvara":
        await tr_svc.obter_alvara(db, tenant_id=tenant_id, alvara_id=entidade_id)
    else:
        await tr_svc.obter_convocacao(
            db, tenant_id=tenant_id, convocacao_id=entidade_id
        )

    dados = await tr_svc.obter_workflow_de_entidade(
        db, tenant_id=tenant_id, entidade_tipo=entidade_tipo, entidade_id=entidade_id,
    )
    return WorkflowEntidadeOut(**dados)
