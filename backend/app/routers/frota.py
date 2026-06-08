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
    AbastecimentoResumo,
    VeiculoAbastecimentoCreate,
    VeiculoAbastecimentoOut,
    VeiculoAbastecimentoUpdate,
    VeiculoCreate,
    VeiculoDocumentoAlertas,
    VeiculoDocumentoCreate,
    VeiculoDocumentoOut,
    VeiculoDocumentoUpdate,
    VeiculoManutencaoConcluir,
    VeiculoManutencaoCreate,
    VeiculoManutencaoOut,
    VeiculoManutencaoUpdate,
    VeiculoOut,
    VeiculoUpdate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaOut,
    VeiculoVistoriaUpdate,
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


# --- Manutenção de Veículos (permissão `frota`) -----------------------------
manutencoes_router = APIRouter(prefix="/frota/manutencoes", tags=["frota"])


@manutencoes_router.get("", response_model=list[VeiculoManutencaoOut])
async def list_manutencoes(
    id_veiculo: int | None = None,
    status_filtro: str | None = None,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoManutencaoOut]:
    rows = await frota_svc.listar_manutencoes(
        db, tenant_id=tenant_id, id_veiculo=id_veiculo, status_filtro=status_filtro
    )
    return [VeiculoManutencaoOut.model_validate(r) for r in rows]


@manutencoes_router.get("/{manutencao_id}", response_model=VeiculoManutencaoOut)
async def get_manutencao(
    manutencao_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.obter_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.post(
    "", response_model=VeiculoManutencaoOut, status_code=status.HTTP_201_CREATED
)
async def create_manutencao(
    payload: VeiculoManutencaoCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.criar_manutencao(
        db, tenant_id=tenant_id, id_veiculo=payload.id_veiculo, payload=payload
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.put("/{manutencao_id}", response_model=VeiculoManutencaoOut)
async def update_manutencao(
    manutencao_id: int,
    payload: VeiculoManutencaoUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.atualizar_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id, payload=payload
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.post("/{manutencao_id}/iniciar", response_model=VeiculoManutencaoOut)
async def iniciar_manutencao(
    manutencao_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.iniciar_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.post("/{manutencao_id}/concluir", response_model=VeiculoManutencaoOut)
async def concluir_manutencao(
    manutencao_id: int,
    payload: VeiculoManutencaoConcluir,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.concluir_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id, payload=payload
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.post("/{manutencao_id}/cancelar", response_model=VeiculoManutencaoOut)
async def cancelar_manutencao(
    manutencao_id: int,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoManutencaoOut:
    m = await frota_svc.cancelar_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id
    )
    return VeiculoManutencaoOut.model_validate(m)


@manutencoes_router.delete("/{manutencao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manutencao(
    manutencao_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_manutencao(
        db, tenant_id=tenant_id, manutencao_id=manutencao_id
    )


# --- Abastecimentos de Veículos (permissão `frota`) -------------------------
abastecimentos_router = APIRouter(prefix="/frota/abastecimentos", tags=["frota"])


@abastecimentos_router.get("", response_model=list[VeiculoAbastecimentoOut])
async def list_abastecimentos(
    id_veiculo: int | None = None,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoAbastecimentoOut]:
    rows = await frota_svc.listar_abastecimentos(
        db, tenant_id=tenant_id, id_veiculo=id_veiculo
    )
    return [VeiculoAbastecimentoOut.model_validate(r) for r in rows]


# `resumo` declarado ANTES de `/{abastecimento_id}` (evita conflito de rota).
@abastecimentos_router.get("/resumo", response_model=AbastecimentoResumo)
async def resumo_abastecimentos(
    id_veiculo: int | None = None,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AbastecimentoResumo:
    dados = await frota_svc.resumo_abastecimentos(
        db, tenant_id=tenant_id, id_veiculo=id_veiculo
    )
    return AbastecimentoResumo(**dados)


@abastecimentos_router.get("/{abastecimento_id}", response_model=VeiculoAbastecimentoOut)
async def get_abastecimento(
    abastecimento_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAbastecimentoOut:
    a = await frota_svc.obter_abastecimento(
        db, tenant_id=tenant_id, abastecimento_id=abastecimento_id
    )
    return VeiculoAbastecimentoOut.model_validate(a)


@abastecimentos_router.post(
    "", response_model=VeiculoAbastecimentoOut, status_code=status.HTTP_201_CREATED
)
async def create_abastecimento(
    payload: VeiculoAbastecimentoCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAbastecimentoOut:
    a = await frota_svc.criar_abastecimento(
        db, tenant_id=tenant_id, id_veiculo=payload.id_veiculo, payload=payload
    )
    return VeiculoAbastecimentoOut.model_validate(a)


@abastecimentos_router.put("/{abastecimento_id}", response_model=VeiculoAbastecimentoOut)
async def update_abastecimento(
    abastecimento_id: int,
    payload: VeiculoAbastecimentoUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoAbastecimentoOut:
    a = await frota_svc.atualizar_abastecimento(
        db, tenant_id=tenant_id, abastecimento_id=abastecimento_id, payload=payload
    )
    return VeiculoAbastecimentoOut.model_validate(a)


@abastecimentos_router.delete(
    "/{abastecimento_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_abastecimento(
    abastecimento_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_abastecimento(
        db, tenant_id=tenant_id, abastecimento_id=abastecimento_id
    )


# --- Vistorias / Checklist (permissão `frota`) ------------------------------
vistorias_router = APIRouter(prefix="/frota/vistorias", tags=["frota"])


@vistorias_router.get("", response_model=list[VeiculoVistoriaOut])
async def list_vistorias(
    id_veiculo: int | None = None,
    resultado: str | None = None,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[VeiculoVistoriaOut]:
    rows = await frota_svc.listar_vistorias(
        db, tenant_id=tenant_id, id_veiculo=id_veiculo, resultado=resultado
    )
    return [VeiculoVistoriaOut.model_validate(r) for r in rows]


@vistorias_router.get("/{vistoria_id}", response_model=VeiculoVistoriaOut)
async def get_vistoria(
    vistoria_id: int,
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await frota_svc.obter_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
    return VeiculoVistoriaOut.model_validate(v)


@vistorias_router.post(
    "", response_model=VeiculoVistoriaOut, status_code=status.HTTP_201_CREATED
)
async def create_vistoria(
    payload: VeiculoVistoriaCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await frota_svc.criar_vistoria(
        db, tenant_id=tenant_id, id_veiculo=payload.id_veiculo, payload=payload
    )
    return VeiculoVistoriaOut.model_validate(v)


@vistorias_router.put("/{vistoria_id}", response_model=VeiculoVistoriaOut)
async def update_vistoria(
    vistoria_id: int,
    payload: VeiculoVistoriaUpdate,
    _: Usuario = Depends(require_permission("frota", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> VeiculoVistoriaOut:
    v = await frota_svc.atualizar_vistoria(
        db, tenant_id=tenant_id, vistoria_id=vistoria_id, payload=payload
    )
    return VeiculoVistoriaOut.model_validate(v)


@vistorias_router.delete("/{vistoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vistoria(
    vistoria_id: int,
    _: Usuario = Depends(require_permission("frota", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await frota_svc.excluir_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
