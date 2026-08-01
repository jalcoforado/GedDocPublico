"""Transporte Regulado — routers de Permissionários, Empresas e Veículos regulados.

`permissionarios_router` / `empresas_router` / `veiculos_router` (prefixos
`/transporte-regulado/permissionarios`, `/empresas` e `/veiculos`): CRUD interno,
autenticado + permissão `transporte_regulado`. Mesmo padrão dos routers de `frota`.
Sem portal público nesta etapa.
"""
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
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
)
from ..services import transporte_regulado as tr_svc

permissionarios_router = APIRouter(
    prefix="/transporte-regulado/permissionarios", tags=["transporte-regulado"]
)


@permissionarios_router.get("", response_model=Paginated[PermissionarioOut])
async def list_permissionarios(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PermissionarioOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_permissionarios(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico,
        limit=page_size, offset=offset
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AlvaraOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_alvaras(
        db,
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        permissionario_id=permissionario_id,
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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


# ============================ Documentos de Alvarás ==========================


@alvaras_router.get("/{alvara_id}/documentos", response_model=Paginated[AlvaraDocumentoOut])
async def list_alvara_documentos(
    alvara_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
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
    _: Usuario = Depends(require_permission("transporte_regulado", "visualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AlvaraAuditoriaListResponse:
    """Lista histórico de auditoria de um alvará (trail de mudanças)."""
    eventos = await tr_svc.listar_auditoria_alvara(
        db, tenant_id=tenant_id, alvara_id=alvara_id, limit=limit, offset=offset
    )
    return AlvaraAuditoriaListResponse(eventos=[e for e in eventos])
