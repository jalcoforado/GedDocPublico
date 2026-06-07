"""Frota — serviço de domínio do cadastro de Veículos (fundação).

Tudo tenant-scoped, mesmo padrão de `services/servico.py`:
- `tenant_id` vem sempre do caller (`request.state.tenant_id`), nunca do payload.
- Carga por id filtra `tenant_id` (404 cross-tenant).
- `placa` única por tenant entre veículos não excluídos (409).
- `id_unidade_responsavel` validado **same-tenant** — a FK do Postgres garante
  integridade mas NÃO filtra por tenant.
- Exclusão = soft-delete (`excluido=true`); a placa volta a ficar disponível.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Motorista,
    SolicitacaoVeiculo,
    UnidadeTrabalho,
    Usuario,
    Veiculo,
)
from ..schemas.frota import (
    MotoristaCreate,
    MotoristaUpdate,
    SolicitacaoVeiculoCreate,
    SolicitacaoVeiculoUpdate,
    VeiculoCreate,
    VeiculoUpdate,
)


async def _validar_placa_unica(
    db: AsyncSession, *, tenant_id: int, placa: str, excluir_id: int | None = None
) -> None:
    stmt = select(Veiculo.id).where(
        Veiculo.tenant_id == tenant_id,
        Veiculo.placa == placa,
        Veiculo.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(Veiculo.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um veículo com a placa '{placa}' neste tenant.",
        )


async def _validar_unidade(
    db: AsyncSession, *, tenant_id: int, id_unidade: int | None
) -> None:
    if id_unidade is None:
        return
    row = (
        await db.execute(
            select(UnidadeTrabalho.id).where(
                UnidadeTrabalho.id == id_unidade,
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unidade responsável inválida: não existe, não é deste tenant ou está inativa.",
        )


async def obter_veiculo(db: AsyncSession, *, tenant_id: int, veiculo_id: int) -> Veiculo:
    veiculo = (
        await db.execute(
            select(Veiculo).where(
                Veiculo.id == veiculo_id,
                Veiculo.tenant_id == tenant_id,
                Veiculo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if veiculo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Veículo não encontrado"
        )
    return veiculo


async def listar_veiculos(db: AsyncSession, *, tenant_id: int) -> list[Veiculo]:
    stmt = (
        select(Veiculo)
        .where(Veiculo.tenant_id == tenant_id, Veiculo.excluido.is_(False))
        .order_by(Veiculo.placa)
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_veiculo(
    db: AsyncSession, *, tenant_id: int, payload: VeiculoCreate
) -> Veiculo:
    dados = payload.model_dump()
    await _validar_placa_unica(db, tenant_id=tenant_id, placa=dados["placa"])
    await _validar_unidade(
        db, tenant_id=tenant_id, id_unidade=dados.get("id_unidade_responsavel")
    )
    veiculo = Veiculo(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(veiculo)
    await db.commit()
    await db.refresh(veiculo)
    return veiculo


async def atualizar_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, payload: VeiculoUpdate
) -> Veiculo:
    veiculo = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    dados = payload.model_dump(exclude_unset=True)

    if "placa" in dados:
        await _validar_placa_unica(
            db, tenant_id=tenant_id, placa=dados["placa"], excluir_id=veiculo_id
        )
    if "id_unidade_responsavel" in dados:
        await _validar_unidade(
            db, tenant_id=tenant_id, id_unidade=dados["id_unidade_responsavel"]
        )

    for campo, valor in dados.items():
        setattr(veiculo, campo, valor)
    veiculo.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(veiculo)
    return veiculo


async def excluir_veiculo(db: AsyncSession, *, tenant_id: int, veiculo_id: int) -> None:
    veiculo = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    veiculo.excluido = True
    veiculo.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Motorista / Condutor ===========================
async def _validar_cpf_unico(
    db: AsyncSession, *, tenant_id: int, cpf: str, excluir_id: int | None = None
) -> None:
    stmt = select(Motorista.id).where(
        Motorista.tenant_id == tenant_id,
        Motorista.cpf == cpf,
        Motorista.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(Motorista.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um motorista com o CPF '{cpf}' neste tenant.",
        )


async def _validar_usuario(
    db: AsyncSession, *, tenant_id: int, id_usuario: int | None
) -> None:
    if id_usuario is None:
        return
    row = (
        await db.execute(
            select(Usuario.id).where(
                Usuario.id == id_usuario,
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário vinculado inválido: não existe, não é deste tenant ou está inativo.",
        )


async def obter_motorista(
    db: AsyncSession, *, tenant_id: int, motorista_id: int
) -> Motorista:
    motorista = (
        await db.execute(
            select(Motorista).where(
                Motorista.id == motorista_id,
                Motorista.tenant_id == tenant_id,
                Motorista.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if motorista is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Motorista não encontrado"
        )
    return motorista


async def listar_motoristas(db: AsyncSession, *, tenant_id: int) -> list[Motorista]:
    stmt = (
        select(Motorista)
        .where(Motorista.tenant_id == tenant_id, Motorista.excluido.is_(False))
        .order_by(Motorista.nome)
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_motorista(
    db: AsyncSession, *, tenant_id: int, payload: MotoristaCreate
) -> Motorista:
    dados = payload.model_dump()
    await _validar_cpf_unico(db, tenant_id=tenant_id, cpf=dados["cpf"])
    await _validar_unidade(db, tenant_id=tenant_id, id_unidade=dados.get("id_unidade"))
    await _validar_usuario(db, tenant_id=tenant_id, id_usuario=dados.get("id_usuario"))
    motorista = Motorista(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(motorista)
    await db.commit()
    await db.refresh(motorista)
    return motorista


async def atualizar_motorista(
    db: AsyncSession, *, tenant_id: int, motorista_id: int, payload: MotoristaUpdate
) -> Motorista:
    motorista = await obter_motorista(db, tenant_id=tenant_id, motorista_id=motorista_id)
    dados = payload.model_dump(exclude_unset=True)

    if "cpf" in dados:
        await _validar_cpf_unico(
            db, tenant_id=tenant_id, cpf=dados["cpf"], excluir_id=motorista_id
        )
    if "id_unidade" in dados:
        await _validar_unidade(db, tenant_id=tenant_id, id_unidade=dados["id_unidade"])
    if "id_usuario" in dados:
        await _validar_usuario(db, tenant_id=tenant_id, id_usuario=dados["id_usuario"])

    for campo, valor in dados.items():
        setattr(motorista, campo, valor)
    motorista.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(motorista)
    return motorista


async def set_situacao_motorista(
    db: AsyncSession, *, tenant_id: int, motorista_id: int, situacao: str
) -> Motorista:
    motorista = await obter_motorista(db, tenant_id=tenant_id, motorista_id=motorista_id)
    motorista.situacao = situacao
    motorista.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(motorista)
    return motorista


async def excluir_motorista(
    db: AsyncSession, *, tenant_id: int, motorista_id: int
) -> None:
    motorista = await obter_motorista(db, tenant_id=tenant_id, motorista_id=motorista_id)
    motorista.excluido = True
    motorista.atualizado_em = datetime.utcnow()
    await db.commit()


# ========================= Solicitação de Veículo ============================
async def obter_solicitacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int
) -> SolicitacaoVeiculo:
    sol = (
        await db.execute(
            select(SolicitacaoVeiculo).where(
                SolicitacaoVeiculo.id == solicitacao_id,
                SolicitacaoVeiculo.tenant_id == tenant_id,
                SolicitacaoVeiculo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if sol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada"
        )
    return sol


async def listar_solicitacoes(
    db: AsyncSession, *, tenant_id: int
) -> list[SolicitacaoVeiculo]:
    stmt = (
        select(SolicitacaoVeiculo)
        .where(
            SolicitacaoVeiculo.tenant_id == tenant_id,
            SolicitacaoVeiculo.excluido.is_(False),
        )
        .order_by(SolicitacaoVeiculo.data_saida_prevista.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_solicitacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_usuario_solicitante: int,
    payload: SolicitacaoVeiculoCreate,
) -> SolicitacaoVeiculo:
    dados = payload.model_dump()
    await _validar_unidade(
        db, tenant_id=tenant_id, id_unidade=dados.get("id_unidade_solicitante")
    )
    sol = SolicitacaoVeiculo(
        tenant_id=tenant_id,
        id_usuario_solicitante=id_usuario_solicitante,
        status="solicitada",
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(sol)
    await db.commit()
    await db.refresh(sol)
    return sol


async def atualizar_solicitacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    solicitacao_id: int,
    payload: SolicitacaoVeiculoUpdate,
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status != "solicitada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível editar solicitações com status 'solicitada'.",
        )
    dados = payload.model_dump(exclude_unset=True)

    if "id_unidade_solicitante" in dados:
        await _validar_unidade(
            db, tenant_id=tenant_id, id_unidade=dados["id_unidade_solicitante"]
        )

    # Coerência de datas sobre os valores efetivos (merge do parcial).
    saida = dados.get("data_saida_prevista", sol.data_saida_prevista)
    retorno = dados.get("data_retorno_prevista", sol.data_retorno_prevista)
    if retorno < saida:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_retorno_prevista deve ser posterior ou igual à data_saida_prevista.",
        )

    for campo, valor in dados.items():
        setattr(sol, campo, valor)
    sol.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(sol)
    return sol


async def _set_status_solicitacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    solicitacao_id: int,
    novo_status: str,
    permitido_de: set[str],
    justificativa: str | None = None,
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status not in permitido_de:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transição inválida: não é possível mudar de '{sol.status}' "
                f"para '{novo_status}'."
            ),
        )
    sol.status = novo_status
    if justificativa is not None:
        sol.justificativa_rejeicao = justificativa
    sol.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(sol)
    return sol


async def aprovar_solicitacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int
) -> SolicitacaoVeiculo:
    return await _set_status_solicitacao(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        novo_status="aprovada",
        permitido_de={"solicitada"},
    )


async def rejeitar_solicitacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int, justificativa: str
) -> SolicitacaoVeiculo:
    return await _set_status_solicitacao(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        novo_status="rejeitada",
        permitido_de={"solicitada"},
        justificativa=justificativa,
    )


async def cancelar_solicitacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int
) -> SolicitacaoVeiculo:
    return await _set_status_solicitacao(
        db,
        tenant_id=tenant_id,
        solicitacao_id=solicitacao_id,
        novo_status="cancelada",
        permitido_de={"solicitada", "aprovada"},
    )


async def excluir_solicitacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int
) -> None:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    sol.excluido = True
    sol.atualizado_em = datetime.utcnow()
    await db.commit()
