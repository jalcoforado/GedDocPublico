"""Transporte Regulado — routers de Permissionários, Empresas e Veículos regulados.

`permissionarios_router` / `empresas_router` / `veiculos_router` (prefixos
`/transporte-regulado/permissionarios`, `/empresas` e `/veiculos`): CRUD interno,
autenticado + permissão `transporte_regulado`. Mesmo padrão dos routers de `frota`.
Sem portal público nesta etapa.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
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
)
from ..services import transporte_regulado as tr_svc

permissionarios_router = APIRouter(
    prefix="/transporte-regulado/permissionarios", tags=["transporte-regulado"]
)


@permissionarios_router.get("", response_model=list[PermissionarioOut])
async def list_permissionarios(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionarioOut]:
    rows = await tr_svc.listar_permissionarios(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico
    )
    return [PermissionarioOut.model_validate(r) for r in rows]


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


@empresas_router.get("", response_model=list[EmpresaOut])
async def list_empresas(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    q: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[EmpresaOut]:
    rows = await tr_svc.listar_empresas(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico, q=q
    )
    return [EmpresaOut.model_validate(r) for r in rows]


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


@veiculos_router.get("", response_model=list[VeiculoReguladoOut])
async def list_veiculos(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    id_empresa: int | None = None,
    q: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoReguladoOut]:
    rows = await tr_svc.listar_veiculos(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico,
        id_permissionario=id_permissionario, id_empresa=id_empresa, q=q,
    )
    return [VeiculoReguladoOut.model_validate(r) for r in rows]


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


@documentos_router.get("", response_model=list[VeiculoDocumentoOut])
async def list_documentos(
    veiculo_id: int,
    tipo_documento: str | None = None,
    situacao: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoDocumentoOut]:
    rows = await tr_svc.listar_documentos(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        tipo_documento=tipo_documento,
        situacao=situacao,
    )
    return [VeiculoDocumentoOut.model_validate(r) for r in rows]


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


@avaliacoes_router.get("", response_model=list[VeiculoAvaliacaoOut])
async def list_avaliacoes(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoAvaliacaoOut]:
    rows = await tr_svc.listar_avaliacoes(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id
    )
    return [VeiculoAvaliacaoOut.model_validate(r) for r in rows]


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


@vistorias_router.get("", response_model=list[VeiculoVistoriaOut])
async def list_vistorias(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoVistoriaOut]:
    rows = await tr_svc.listar_vistorias(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id
    )
    return [VeiculoVistoriaOut.model_validate(r) for r in rows]


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


@vistorias_router.get("/vencidas", response_model=list[VeiculoVistoriaOut])
async def list_vistorias_vencidas(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoVistoriaOut]:
    rows = await tr_svc.listar_vistorias_vencidas(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id
    )
    return [VeiculoVistoriaOut.model_validate(r) for r in rows]


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


@alvaras_router.get("", response_model=list[AlvaraOut])
async def list_alvaras(
    empresa_id: int | None = None,
    permissionario_id: int | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[AlvaraOut]:
    rows = await tr_svc.listar_alvaras(
        db,
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        permissionario_id=permissionario_id,
    )
    return [AlvaraOut.model_validate(r) for r in rows]


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


@alvaras_router.get("/vencidos", response_model=list[AlvaraOut])
async def list_alvaras_vencidos(
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[AlvaraOut]:
    """Lista alvarás vencidos (data_validade <= hoje) do tenant."""
    return await tr_svc.listar_alvaras_vencidos(db, tenant_id=tenant_id)


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
