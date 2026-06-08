"""Frota Pública — router do cadastro de Veículos (fundação).

`router` (prefix `/frota/veiculos`): CRUD interno, autenticado + permissão
`frota`. Mesmo padrão de `routers/servico.py`. Sem portal público nesta etapa.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.frota import (
    MotoristaCreate,
    MotoristaOut,
    MotoristaUpdate,
    SolicitacaoVeiculoCreate,
    SolicitacaoVeiculoDesignar,
    SolicitacaoVeiculoOut,
    SolicitacaoVeiculoRegistrarRetorno,
    SolicitacaoVeiculoRegistrarSaida,
    SolicitacaoVeiculoRejeitar,
    SolicitacaoVeiculoUpdate,
    VeiculoCreate,
    VeiculoDocumentoAlertas,
    VeiculoDocumentoCreate,
    VeiculoDocumentoOut,
    VeiculoDocumentoUpdate,
    VeiculoOut,
    VeiculoUpdate,
)
from ..services import frota as frota_svc

router = APIRouter(prefix="/frota/veiculos", tags=["frota"])


@router.get("", response_model=list[VeiculoOut])
async def list_veiculos(
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoOut]:
    rows = await frota_svc.listar_veiculos(db, tenant_id=tenant_id)
    return [VeiculoOut.model_validate(r) for r in rows]


@router.get("/{veiculo_id}", response_model=VeiculoOut)
async def get_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoOut:
    veiculo = await frota_svc.obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    return VeiculoOut.model_validate(veiculo)


@router.post("", response_model=VeiculoOut, status_code=status.HTTP_201_CREATED)
async def create_veiculo(
    payload: VeiculoCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoOut:
    veiculo = await frota_svc.criar_veiculo(db, tenant_id=tenant_id, payload=payload)
    return VeiculoOut.model_validate(veiculo)


@router.put("/{veiculo_id}", response_model=VeiculoOut)
async def update_veiculo(
    veiculo_id: int,
    payload: VeiculoUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoOut:
    veiculo = await frota_svc.atualizar_veiculo(
        db, tenant_id=tenant_id, veiculo_id=veiculo_id, payload=payload
    )
    return VeiculoOut.model_validate(veiculo)


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)


# --- Documentos do Veículo (PR Frota-6, permissão `frota`) -------------------
# Listagem/criação aninhadas ao veículo; detalhe/edição/remoção/alertas em
# `documentos_router` (/frota/documentos-veiculo).
@router.get("/{veiculo_id}/documentos", response_model=list[VeiculoDocumentoOut])
async def list_documentos_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoDocumentoOut]:
    rows = await frota_svc.listar_documentos_veiculo(
        db, tenant_id=tenant_id, id_veiculo=veiculo_id
    )
    return [VeiculoDocumentoOut.model_validate(r) for r in rows]


@router.post(
    "/{veiculo_id}/documentos",
    response_model=VeiculoDocumentoOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_documento_veiculo(
    veiculo_id: int,
    payload: VeiculoDocumentoCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await frota_svc.criar_documento(
        db, tenant_id=tenant_id, id_veiculo=veiculo_id, payload=payload
    )
    return VeiculoDocumentoOut.model_validate(doc)


# --- Motoristas / Condutores (permissão `frota`) ----------------------------
motoristas_router = APIRouter(prefix="/frota/motoristas", tags=["frota"])


@motoristas_router.get("", response_model=list[MotoristaOut])
async def list_motoristas(
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[MotoristaOut]:
    rows = await frota_svc.listar_motoristas(db, tenant_id=tenant_id)
    return [MotoristaOut.model_validate(r) for r in rows]


@motoristas_router.get("/{motorista_id}", response_model=MotoristaOut)
async def get_motorista(
    motorista_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MotoristaOut:
    motorista = await frota_svc.obter_motorista(
        db, tenant_id=tenant_id, motorista_id=motorista_id
    )
    return MotoristaOut.model_validate(motorista)


@motoristas_router.post("", response_model=MotoristaOut, status_code=status.HTTP_201_CREATED)
async def create_motorista(
    payload: MotoristaCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MotoristaOut:
    motorista = await frota_svc.criar_motorista(db, tenant_id=tenant_id, payload=payload)
    return MotoristaOut.model_validate(motorista)


@motoristas_router.put("/{motorista_id}", response_model=MotoristaOut)
async def update_motorista(
    motorista_id: int,
    payload: MotoristaUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MotoristaOut:
    motorista = await frota_svc.atualizar_motorista(
        db, tenant_id=tenant_id, motorista_id=motorista_id, payload=payload
    )
    return MotoristaOut.model_validate(motorista)


@motoristas_router.post("/{motorista_id}/inativar", response_model=MotoristaOut)
async def inativar_motorista(
    motorista_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MotoristaOut:
    motorista = await frota_svc.set_situacao_motorista(
        db, tenant_id=tenant_id, motorista_id=motorista_id, situacao="inativo"
    )
    return MotoristaOut.model_validate(motorista)


@motoristas_router.post("/{motorista_id}/reativar", response_model=MotoristaOut)
async def reativar_motorista(
    motorista_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MotoristaOut:
    motorista = await frota_svc.set_situacao_motorista(
        db, tenant_id=tenant_id, motorista_id=motorista_id, situacao="ativo"
    )
    return MotoristaOut.model_validate(motorista)


@motoristas_router.delete("/{motorista_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_motorista(
    motorista_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_motorista(db, tenant_id=tenant_id, motorista_id=motorista_id)


# --- Solicitações de Veículo (permissão `frota`) ----------------------------
solicitacoes_router = APIRouter(prefix="/frota/solicitacoes", tags=["frota"])


@solicitacoes_router.get("", response_model=list[SolicitacaoVeiculoOut])
async def list_solicitacoes(
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[SolicitacaoVeiculoOut]:
    rows = await frota_svc.listar_solicitacoes(db, tenant_id=tenant_id)
    return [SolicitacaoVeiculoOut.model_validate(r) for r in rows]


@solicitacoes_router.get("/{solicitacao_id}", response_model=SolicitacaoVeiculoOut)
async def get_solicitacao(
    solicitacao_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.obter_solicitacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post(
    "", response_model=SolicitacaoVeiculoOut, status_code=status.HTTP_201_CREATED
)
async def create_solicitacao(
    payload: SolicitacaoVeiculoCreate,
    usuario: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    # id_usuario_solicitante vem SEMPRE do usuário autenticado (server-side).
    sol = await frota_svc.criar_solicitacao(
        db, tenant_id=tenant_id, id_usuario_solicitante=usuario.id, payload=payload
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.put("/{solicitacao_id}", response_model=SolicitacaoVeiculoOut)
async def update_solicitacao(
    solicitacao_id: int,
    payload: SolicitacaoVeiculoUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.atualizar_solicitacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id, payload=payload
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post("/{solicitacao_id}/aprovar", response_model=SolicitacaoVeiculoOut)
async def aprovar_solicitacao(
    solicitacao_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.aprovar_solicitacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post("/{solicitacao_id}/rejeitar", response_model=SolicitacaoVeiculoOut)
async def rejeitar_solicitacao(
    solicitacao_id: int,
    payload: SolicitacaoVeiculoRejeitar,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.rejeitar_solicitacao(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        justificativa=payload.justificativa_rejeicao,
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post("/{solicitacao_id}/cancelar", response_model=SolicitacaoVeiculoOut)
async def cancelar_solicitacao(
    solicitacao_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.cancelar_solicitacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post("/{solicitacao_id}/designar", response_model=SolicitacaoVeiculoOut)
async def designar_solicitacao(
    solicitacao_id: int,
    payload: SolicitacaoVeiculoDesignar,
    usuario: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    # id_usuario_designador vem SEMPRE do usuário autenticado (server-side).
    sol = await frota_svc.designar_solicitacao(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        id_usuario_designador=usuario.id,
        payload=payload,
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post(
    "/{solicitacao_id}/limpar-designacao", response_model=SolicitacaoVeiculoOut
)
async def limpar_designacao(
    solicitacao_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    sol = await frota_svc.limpar_designacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post(
    "/{solicitacao_id}/registrar-saida", response_model=SolicitacaoVeiculoOut
)
async def registrar_saida(
    solicitacao_id: int,
    payload: SolicitacaoVeiculoRegistrarSaida,
    usuario: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    # id_usuario_registro_saida vem SEMPRE do usuário autenticado (server-side).
    sol = await frota_svc.registrar_saida(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        id_usuario_registro=usuario.id,
        payload=payload,
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.post(
    "/{solicitacao_id}/registrar-retorno", response_model=SolicitacaoVeiculoOut
)
async def registrar_retorno(
    solicitacao_id: int,
    payload: SolicitacaoVeiculoRegistrarRetorno,
    usuario: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoVeiculoOut:
    # id_usuario_registro_retorno vem SEMPRE do usuário autenticado (server-side).
    sol = await frota_svc.registrar_retorno(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        id_usuario_registro=usuario.id,
        payload=payload,
    )
    return SolicitacaoVeiculoOut.model_validate(sol)


@solicitacoes_router.delete("/{solicitacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_solicitacao(
    solicitacao_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_solicitacao(
        db, tenant_id=tenant_id, solicitacao_id=solicitacao_id
    )


# --- Documentos do Veículo: detalhe / edição / remoção / alertas -------------
documentos_router = APIRouter(prefix="/frota/documentos-veiculo", tags=["frota"])


# `alertas` é declarada ANTES de `/{documento_id}` (evita conflito de rota).
@documentos_router.get("/alertas", response_model=VeiculoDocumentoAlertas)
async def alertas_documentos(
    dias: int = 30,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoAlertas:
    dias = max(0, min(dias, 365))  # clamp defensivo
    grupos = await frota_svc.listar_alertas_documentos(
        db, tenant_id=tenant_id, dias=dias
    )
    return VeiculoDocumentoAlertas(
        dias=dias,
        vencidos=[VeiculoDocumentoOut.model_validate(d) for d in grupos["vencidos"]],
        a_vencer=[VeiculoDocumentoOut.model_validate(d) for d in grupos["a_vencer"]],
    )


@documentos_router.get("/{documento_id}", response_model=VeiculoDocumentoOut)
async def get_documento(
    documento_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await frota_svc.obter_documento(
        db, tenant_id=tenant_id, documento_id=documento_id
    )
    return VeiculoDocumentoOut.model_validate(doc)


@documentos_router.put("/{documento_id}", response_model=VeiculoDocumentoOut)
async def update_documento(
    documento_id: int,
    payload: VeiculoDocumentoUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoDocumentoOut:
    doc = await frota_svc.atualizar_documento(
        db, tenant_id=tenant_id, documento_id=documento_id, payload=payload
    )
    return VeiculoDocumentoOut.model_validate(doc)


@documentos_router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_documento(
    documento_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_documento(
        db, tenant_id=tenant_id, documento_id=documento_id
    )
