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

from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Motorista,
    SolicitacaoVeiculo,
    UnidadeTrabalho,
    Usuario,
    Veiculo,
    VeiculoAbastecimento,
    VeiculoDocumento,
    VeiculoManutencao,
    VeiculoOcorrencia,
    VeiculoVistoria,
)
from ..schemas.frota import (
    MotoristaCreate,
    MotoristaUpdate,
    SolicitacaoVeiculoCreate,
    SolicitacaoVeiculoDesignar,
    SolicitacaoVeiculoRegistrarRetorno,
    SolicitacaoVeiculoRegistrarSaida,
    SolicitacaoVeiculoUpdate,
    VeiculoAbastecimentoCreate,
    VeiculoAbastecimentoUpdate,
    VeiculoCreate,
    VeiculoDocumentoCreate,
    VeiculoDocumentoUpdate,
    VeiculoManutencaoConcluir,
    VeiculoManutencaoCreate,
    VeiculoManutencaoUpdate,
    VeiculoOcorrenciaCreate,
    VeiculoOcorrenciaResolver,
    VeiculoOcorrenciaUpdate,
    VeiculoUpdate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaUpdate,
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


# --------------------------- Designação (PR Frota-4) -------------------------
async def _validar_veiculo_designavel(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int
) -> None:
    veiculo = (
        await db.execute(
            select(Veiculo).where(
                Veiculo.id == id_veiculo,
                Veiculo.tenant_id == tenant_id,
                Veiculo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if veiculo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veículo não encontrado",
        )
    if veiculo.situacao != "disponivel":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Veículo não disponível para designação (situação atual: "
                f"'{veiculo.situacao}'). Só veículos com situação 'disponivel' podem ser designados."
            ),
        )


async def _validar_motorista_designavel(
    db: AsyncSession, *, tenant_id: int, id_motorista: int
) -> None:
    motorista = (
        await db.execute(
            select(Motorista).where(
                Motorista.id == id_motorista,
                Motorista.tenant_id == tenant_id,
                Motorista.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if motorista is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motorista não encontrado",
        )
    if motorista.situacao != "ativo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Motorista não disponível para designação (situação atual: "
                f"'{motorista.situacao}'). Só motoristas com situação 'ativo' podem ser designados."
            ),
        )


async def designar_solicitacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    solicitacao_id: int,
    id_usuario_designador: int,
    payload: SolicitacaoVeiculoDesignar,
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status != "aprovada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível designar veículo/motorista para solicitações 'aprovada'.",
        )

    if sol.necessita_motorista and payload.id_motorista is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta solicitação exige motorista: id_motorista é obrigatório.",
        )

    await _validar_veiculo_designavel(db, tenant_id=tenant_id, id_veiculo=payload.id_veiculo)
    if payload.id_motorista is not None:
        await _validar_motorista_designavel(
            db, tenant_id=tenant_id, id_motorista=payload.id_motorista
        )

    # Redesignação enquanto 'aprovada' = sobrescreve (sem histórico, por escopo).
    sol.id_veiculo_designado = payload.id_veiculo
    sol.id_motorista_designado = payload.id_motorista
    sol.id_usuario_designador = id_usuario_designador
    sol.data_designacao = datetime.utcnow()
    sol.observacoes_designacao = payload.observacoes_designacao
    sol.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(sol)
    return sol


async def limpar_designacao(
    db: AsyncSession, *, tenant_id: int, solicitacao_id: int
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status != "aprovada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível limpar a designação de solicitações 'aprovada'.",
        )
    sol.id_veiculo_designado = None
    sol.id_motorista_designado = None
    sol.id_usuario_designador = None
    sol.data_designacao = None
    sol.observacoes_designacao = None
    sol.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(sol)
    return sol


# ----------------------- Saída / Retorno real (PR Frota-5) -------------------
async def _carregar_veiculo_tenant(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int
) -> Veiculo:
    """Carrega o veículo same-tenant para mutação (situação/quilometragem).

    A FK do Postgres garante integridade mas NÃO filtra por tenant — daí o
    filtro explícito. Retorna 404 se não existe, não é deste tenant ou foi
    excluído (mesmo critério de `obter_veiculo`)."""
    veiculo = (
        await db.execute(
            select(Veiculo).where(
                Veiculo.id == id_veiculo,
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


async def registrar_saida(
    db: AsyncSession,
    *,
    tenant_id: int,
    solicitacao_id: int,
    id_usuario_registro: int,
    payload: SolicitacaoVeiculoRegistrarSaida,
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status != "aprovada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível registrar saída de solicitações 'aprovada'.",
        )
    if sol.id_veiculo_designado is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não há veículo designado: designe um veículo antes de registrar a saída.",
        )
    if sol.necessita_motorista and sol.id_motorista_designado is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta solicitação exige motorista: designe um motorista antes da saída.",
        )

    veiculo = await _carregar_veiculo_tenant(
        db, tenant_id=tenant_id, id_veiculo=sol.id_veiculo_designado
    )
    if veiculo.situacao != "disponivel":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Veículo não disponível para saída (situação atual: "
                f"'{veiculo.situacao}'). Só veículos 'disponivel' podem sair."
            ),
        )
    if payload.km_saida < veiculo.quilometragem_atual:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"km_saida ({payload.km_saida}) não pode ser menor que a "
                f"quilometragem atual do veículo ({veiculo.quilometragem_atual})."
            ),
        )

    agora = datetime.utcnow()
    sol.status = "em_uso"
    sol.km_saida = payload.km_saida
    sol.observacoes_saida = payload.observacoes_saida
    sol.data_saida_real = agora
    sol.id_usuario_registro_saida = id_usuario_registro
    sol.atualizado_em = agora
    veiculo.situacao = "em_uso"
    veiculo.atualizado_em = agora
    await db.commit()
    await db.refresh(sol)
    return sol


async def registrar_retorno(
    db: AsyncSession,
    *,
    tenant_id: int,
    solicitacao_id: int,
    id_usuario_registro: int,
    payload: SolicitacaoVeiculoRegistrarRetorno,
) -> SolicitacaoVeiculo:
    sol = await obter_solicitacao(db, tenant_id=tenant_id, solicitacao_id=solicitacao_id)
    if sol.status != "em_uso":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível registrar retorno de solicitações 'em_uso'.",
        )
    if sol.km_saida is not None and payload.km_retorno < sol.km_saida:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"km_retorno ({payload.km_retorno}) não pode ser menor que a "
                f"quilometragem de saída ({sol.km_saida})."
            ),
        )

    veiculo = await _carregar_veiculo_tenant(
        db, tenant_id=tenant_id, id_veiculo=sol.id_veiculo_designado
    )

    agora = datetime.utcnow()
    sol.status = "concluida"
    sol.km_retorno = payload.km_retorno
    sol.observacoes_retorno = payload.observacoes_retorno
    sol.data_retorno_real = agora
    sol.id_usuario_registro_retorno = id_usuario_registro
    sol.atualizado_em = agora
    veiculo.situacao = "disponivel"
    veiculo.quilometragem_atual = payload.km_retorno
    veiculo.atualizado_em = agora
    await db.commit()
    await db.refresh(sol)
    return sol


# --------------------- Documentos do Veículo (PR Frota-6) --------------------
# Documentos retirados (substituido/cancelado) não disparam alerta de vencimento.
_DOC_STATUS_ALERTAVEL = ("ativo", "vencido")


async def obter_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> VeiculoDocumento:
    doc = (
        await db.execute(
            select(VeiculoDocumento).where(
                VeiculoDocumento.id == documento_id,
                VeiculoDocumento.tenant_id == tenant_id,
                VeiculoDocumento.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado"
        )
    return doc


async def listar_documentos_veiculo(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int
) -> list[VeiculoDocumento]:
    # Garante que o veículo existe e é deste tenant (404 cross-tenant/excluído).
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    stmt = (
        select(VeiculoDocumento)
        .where(
            VeiculoDocumento.tenant_id == tenant_id,
            VeiculoDocumento.id_veiculo == id_veiculo,
            VeiculoDocumento.excluido.is_(False),
        )
        .order_by(VeiculoDocumento.data_vencimento)
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_documento(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: VeiculoDocumentoCreate,
) -> VeiculoDocumento:
    # Veículo deve existir, ser deste tenant e não estar excluído (404).
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    dados = payload.model_dump()
    doc = VeiculoDocumento(
        tenant_id=tenant_id,
        id_veiculo=id_veiculo,
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def atualizar_documento(
    db: AsyncSession,
    *,
    tenant_id: int,
    documento_id: int,
    payload: VeiculoDocumentoUpdate,
) -> VeiculoDocumento:
    doc = await obter_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    dados = payload.model_dump(exclude_unset=True)

    # Coerência de datas sobre os valores efetivos (merge do parcial).
    emissao = dados.get("data_emissao", doc.data_emissao)
    vencimento = dados.get("data_vencimento", doc.data_vencimento)
    if emissao is not None and emissao > vencimento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_emissao não pode ser posterior à data_vencimento.",
        )

    for campo, valor in dados.items():
        setattr(doc, campo, valor)
    doc.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(doc)
    return doc


async def excluir_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> None:
    doc = await obter_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    doc.excluido = True
    doc.atualizado_em = datetime.utcnow()
    await db.commit()


async def listar_alertas_documentos(
    db: AsyncSession, *, tenant_id: int, dias: int
) -> dict[str, list[VeiculoDocumento]]:
    """Documentos vencidos (data_vencimento < hoje) e a vencer (entre hoje e
    hoje + `dias`). Tenant-scoped; ignora excluídos e os retirados
    (substituido/cancelado)."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)
    base = (
        select(VeiculoDocumento)
        .where(
            VeiculoDocumento.tenant_id == tenant_id,
            VeiculoDocumento.excluido.is_(False),
            VeiculoDocumento.status.in_(_DOC_STATUS_ALERTAVEL),
        )
        .order_by(VeiculoDocumento.data_vencimento)
    )
    vencidos = list(
        (
            await db.execute(base.where(VeiculoDocumento.data_vencimento < hoje))
        ).scalars().all()
    )
    a_vencer = list(
        (
            await db.execute(
                base.where(
                    VeiculoDocumento.data_vencimento >= hoje,
                    VeiculoDocumento.data_vencimento <= limite,
                )
            )
        ).scalars().all()
    )
    return {"vencidos": vencidos, "a_vencer": a_vencer}


# ----------------------- Manutenção do Veículo (operacional) -----------------
# Decisões de efeito na situação do veículo (documentadas):
#  - Abrir manutenção: se o veículo está 'disponivel', passa para 'manutencao'.
#    NÃO mexe se está 'em_uso'/'baixado'/'inativo' (não atrapalha viagem em curso).
#  - Concluir/Cancelar: devolve o veículo a 'disponivel' SOMENTE se ele está em
#    'manutencao' (não sobrescreve 'em_uso' nem outros estados).
_MANUT_ENCERRAVEL = {"aberta", "em_andamento"}


async def obter_manutencao(
    db: AsyncSession, *, tenant_id: int, manutencao_id: int
) -> VeiculoManutencao:
    m = (
        await db.execute(
            select(VeiculoManutencao).where(
                VeiculoManutencao.id == manutencao_id,
                VeiculoManutencao.tenant_id == tenant_id,
                VeiculoManutencao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manutenção não encontrada"
        )
    return m


async def listar_manutencoes(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int | None = None,
    status_filtro: str | None = None,
) -> list[VeiculoManutencao]:
    stmt = select(VeiculoManutencao).where(
        VeiculoManutencao.tenant_id == tenant_id,
        VeiculoManutencao.excluido.is_(False),
    )
    if id_veiculo is not None:
        stmt = stmt.where(VeiculoManutencao.id_veiculo == id_veiculo)
    if status_filtro is not None:
        stmt = stmt.where(VeiculoManutencao.status == status_filtro)
    stmt = stmt.order_by(VeiculoManutencao.data_abertura.desc(), VeiculoManutencao.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def criar_manutencao(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: VeiculoManutencaoCreate,
) -> VeiculoManutencao:
    veiculo = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    dados = payload.model_dump(exclude={"id_veiculo"})
    if dados.get("data_abertura") is None:
        dados["data_abertura"] = date.today()
    m = VeiculoManutencao(
        tenant_id=tenant_id,
        id_veiculo=id_veiculo,
        status="aberta",
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(m)
    # Abrir manutenção tira o veículo de 'disponivel' (não mexe em 'em_uso' etc.).
    if veiculo.situacao == "disponivel":
        veiculo.situacao = "manutencao"
        veiculo.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(m)
    return m


async def atualizar_manutencao(
    db: AsyncSession,
    *,
    tenant_id: int,
    manutencao_id: int,
    payload: VeiculoManutencaoUpdate,
) -> VeiculoManutencao:
    m = await obter_manutencao(db, tenant_id=tenant_id, manutencao_id=manutencao_id)
    if m.status in ("concluida", "cancelada"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível editar manutenção concluída ou cancelada.",
        )
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(m, campo, valor)
    m.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(m)
    return m


async def iniciar_manutencao(
    db: AsyncSession, *, tenant_id: int, manutencao_id: int
) -> VeiculoManutencao:
    m = await obter_manutencao(db, tenant_id=tenant_id, manutencao_id=manutencao_id)
    if m.status != "aberta":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível iniciar manutenções 'aberta'.",
        )
    m.status = "em_andamento"
    m.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(m)
    return m


async def _liberar_veiculo_se_em_manutencao(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int
) -> None:
    veiculo = (
        await db.execute(
            select(Veiculo).where(
                Veiculo.id == id_veiculo,
                Veiculo.tenant_id == tenant_id,
                Veiculo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if veiculo is not None and veiculo.situacao == "manutencao":
        veiculo.situacao = "disponivel"
        veiculo.atualizado_em = datetime.utcnow()


async def concluir_manutencao(
    db: AsyncSession,
    *,
    tenant_id: int,
    manutencao_id: int,
    payload: VeiculoManutencaoConcluir,
) -> VeiculoManutencao:
    m = await obter_manutencao(db, tenant_id=tenant_id, manutencao_id=manutencao_id)
    if m.status not in _MANUT_ENCERRAVEL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível concluir manutenções 'aberta' ou 'em_andamento'.",
        )
    dados = payload.model_dump(exclude_unset=True)
    m.status = "concluida"
    m.data_conclusao = dados.get("data_conclusao") or m.data_conclusao or date.today()
    if "custo_final" in dados:
        m.custo_final = dados["custo_final"]
    if "km_atual" in dados and dados["km_atual"] is not None:
        m.km_atual = dados["km_atual"]
    if "observacoes" in dados:
        m.observacoes = dados["observacoes"]
    m.atualizado_em = datetime.utcnow()
    await _liberar_veiculo_se_em_manutencao(db, tenant_id=tenant_id, id_veiculo=m.id_veiculo)
    await db.commit()
    await db.refresh(m)
    return m


async def cancelar_manutencao(
    db: AsyncSession, *, tenant_id: int, manutencao_id: int
) -> VeiculoManutencao:
    m = await obter_manutencao(db, tenant_id=tenant_id, manutencao_id=manutencao_id)
    if m.status not in _MANUT_ENCERRAVEL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível cancelar manutenções 'aberta' ou 'em_andamento'.",
        )
    m.status = "cancelada"
    m.atualizado_em = datetime.utcnow()
    await _liberar_veiculo_se_em_manutencao(db, tenant_id=tenant_id, id_veiculo=m.id_veiculo)
    await db.commit()
    await db.refresh(m)
    return m


async def excluir_manutencao(
    db: AsyncSession, *, tenant_id: int, manutencao_id: int
) -> None:
    m = await obter_manutencao(db, tenant_id=tenant_id, manutencao_id=manutencao_id)
    m.excluido = True
    m.atualizado_em = datetime.utcnow()
    await db.commit()


# ----------------------- Abastecimento do Veículo (operacional) -------------
async def obter_abastecimento(
    db: AsyncSession, *, tenant_id: int, abastecimento_id: int
) -> VeiculoAbastecimento:
    a = (
        await db.execute(
            select(VeiculoAbastecimento).where(
                VeiculoAbastecimento.id == abastecimento_id,
                VeiculoAbastecimento.tenant_id == tenant_id,
                VeiculoAbastecimento.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Abastecimento não encontrado"
        )
    return a


async def listar_abastecimentos(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int | None = None
) -> list[VeiculoAbastecimento]:
    stmt = select(VeiculoAbastecimento).where(
        VeiculoAbastecimento.tenant_id == tenant_id,
        VeiculoAbastecimento.excluido.is_(False),
    )
    if id_veiculo is not None:
        stmt = stmt.where(VeiculoAbastecimento.id_veiculo == id_veiculo)
    stmt = stmt.order_by(
        VeiculoAbastecimento.data_abastecimento.desc(), VeiculoAbastecimento.id.desc()
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_abastecimento(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: VeiculoAbastecimentoCreate,
) -> VeiculoAbastecimento:
    veiculo = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    if payload.id_motorista is not None:
        # 404 same-tenant (não exige situação específica para abastecer).
        await obter_motorista(db, tenant_id=tenant_id, motorista_id=payload.id_motorista)
    dados = payload.model_dump(exclude={"id_veiculo"})
    if dados.get("data_abastecimento") is None:
        dados["data_abastecimento"] = date.today()
    a = VeiculoAbastecimento(
        tenant_id=tenant_id,
        id_veiculo=id_veiculo,
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(a)
    # Atualiza a quilometragem do veículo se o hodômetro avançou (não mexe na
    # situação). km menor é aceito (pode ser correção/registro retroativo).
    if payload.km_atual > veiculo.quilometragem_atual:
        veiculo.quilometragem_atual = payload.km_atual
        veiculo.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(a)
    return a


async def atualizar_abastecimento(
    db: AsyncSession,
    *,
    tenant_id: int,
    abastecimento_id: int,
    payload: VeiculoAbastecimentoUpdate,
) -> VeiculoAbastecimento:
    a = await obter_abastecimento(db, tenant_id=tenant_id, abastecimento_id=abastecimento_id)
    dados = payload.model_dump(exclude_unset=True)
    if "id_motorista" in dados and dados["id_motorista"] is not None:
        await obter_motorista(db, tenant_id=tenant_id, motorista_id=dados["id_motorista"])
    for campo, valor in dados.items():
        setattr(a, campo, valor)
    a.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(a)
    return a


async def excluir_abastecimento(
    db: AsyncSession, *, tenant_id: int, abastecimento_id: int
) -> None:
    a = await obter_abastecimento(db, tenant_id=tenant_id, abastecimento_id=abastecimento_id)
    a.excluido = True
    a.atualizado_em = datetime.utcnow()
    await db.commit()


async def resumo_abastecimentos(
    db: AsyncSession, *, tenant_id: int, id_veiculo: int | None = None
) -> dict:
    """Agregados simples: nº, litros, valor, média R$/litro e último (tenant-scoped)."""
    registros = await listar_abastecimentos(db, tenant_id=tenant_id, id_veiculo=id_veiculo)
    total = len(registros)
    total_litros = sum(float(r.litros) for r in registros)
    total_valor = sum(float(r.valor_total) for r in registros)
    media = round(total_valor / total_litros, 4) if total_litros > 0 else None
    ultimo = max((r.data_abastecimento for r in registros), default=None)
    return {
        "total_abastecimentos": total,
        "total_litros": round(total_litros, 3),
        "total_valor": round(total_valor, 2),
        "media_valor_litro": media,
        "ultimo_abastecimento": ultimo,
    }


# ----------------------- Vistoria / Checklist (operacional) -----------------
# NÃO altera a situação do veículo, mesmo em resultado 'reprovada' (decisão
# deste módulo — registrar a vistoria não muda o estado operacional).
async def obter_vistoria(
    db: AsyncSession, *, tenant_id: int, vistoria_id: int
) -> VeiculoVistoria:
    v = (
        await db.execute(
            select(VeiculoVistoria).where(
                VeiculoVistoria.id == vistoria_id,
                VeiculoVistoria.tenant_id == tenant_id,
                VeiculoVistoria.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vistoria não encontrada"
        )
    return v


async def listar_vistorias(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int | None = None,
    resultado: str | None = None,
) -> list[VeiculoVistoria]:
    stmt = select(VeiculoVistoria).where(
        VeiculoVistoria.tenant_id == tenant_id,
        VeiculoVistoria.excluido.is_(False),
    )
    if id_veiculo is not None:
        stmt = stmt.where(VeiculoVistoria.id_veiculo == id_veiculo)
    if resultado is not None:
        stmt = stmt.where(VeiculoVistoria.resultado == resultado)
    stmt = stmt.order_by(
        VeiculoVistoria.data_vistoria.desc(), VeiculoVistoria.id.desc()
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_vistoria(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: VeiculoVistoriaCreate,
) -> VeiculoVistoria:
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    dados = payload.model_dump(exclude={"id_veiculo"})
    if dados.get("data_vistoria") is None:
        dados["data_vistoria"] = date.today()
    v = VeiculoVistoria(
        tenant_id=tenant_id,
        id_veiculo=id_veiculo,
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


async def atualizar_vistoria(
    db: AsyncSession,
    *,
    tenant_id: int,
    vistoria_id: int,
    payload: VeiculoVistoriaUpdate,
) -> VeiculoVistoria:
    v = await obter_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(v, campo, valor)
    v.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(v)
    return v


async def excluir_vistoria(
    db: AsyncSession, *, tenant_id: int, vistoria_id: int
) -> None:
    v = await obter_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
    v.excluido = True
    v.atualizado_em = datetime.utcnow()
    await db.commit()


# ----------------------- Ocorrências internas (operacional) -----------------
# NÃO altera a situação do veículo. data_resolucao é gravada server-side.
_OCORRENCIA_TRATAVEL = {"aberta", "em_tratamento"}


async def obter_ocorrencia(
    db: AsyncSession, *, tenant_id: int, ocorrencia_id: int
) -> VeiculoOcorrencia:
    o = (
        await db.execute(
            select(VeiculoOcorrencia).where(
                VeiculoOcorrencia.id == ocorrencia_id,
                VeiculoOcorrencia.tenant_id == tenant_id,
                VeiculoOcorrencia.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if o is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada"
        )
    return o


async def listar_ocorrencias(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int | None = None,
    status_filtro: str | None = None,
) -> list[VeiculoOcorrencia]:
    stmt = select(VeiculoOcorrencia).where(
        VeiculoOcorrencia.tenant_id == tenant_id,
        VeiculoOcorrencia.excluido.is_(False),
    )
    if id_veiculo is not None:
        stmt = stmt.where(VeiculoOcorrencia.id_veiculo == id_veiculo)
    if status_filtro is not None:
        stmt = stmt.where(VeiculoOcorrencia.status == status_filtro)
    stmt = stmt.order_by(
        VeiculoOcorrencia.data_ocorrencia.desc(), VeiculoOcorrencia.id.desc()
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_ocorrencia(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: VeiculoOcorrenciaCreate,
) -> VeiculoOcorrencia:
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)
    if payload.id_motorista is not None:
        await obter_motorista(db, tenant_id=tenant_id, motorista_id=payload.id_motorista)
    dados = payload.model_dump(exclude={"id_veiculo"})
    if dados.get("data_ocorrencia") is None:
        dados["data_ocorrencia"] = date.today()
    o = VeiculoOcorrencia(
        tenant_id=tenant_id,
        id_veiculo=id_veiculo,
        status="aberta",
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return o


async def atualizar_ocorrencia(
    db: AsyncSession,
    *,
    tenant_id: int,
    ocorrencia_id: int,
    payload: VeiculoOcorrenciaUpdate,
) -> VeiculoOcorrencia:
    o = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    if o.status in ("resolvida", "cancelada"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível editar ocorrência resolvida ou cancelada.",
        )
    dados = payload.model_dump(exclude_unset=True)
    if "id_motorista" in dados and dados["id_motorista"] is not None:
        await obter_motorista(db, tenant_id=tenant_id, motorista_id=dados["id_motorista"])
    for campo, valor in dados.items():
        setattr(o, campo, valor)
    o.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(o)
    return o


async def iniciar_tratamento_ocorrencia(
    db: AsyncSession, *, tenant_id: int, ocorrencia_id: int
) -> VeiculoOcorrencia:
    o = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    if o.status != "aberta":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível iniciar tratamento de ocorrências 'aberta'.",
        )
    o.status = "em_tratamento"
    o.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(o)
    return o


async def resolver_ocorrencia(
    db: AsyncSession,
    *,
    tenant_id: int,
    ocorrencia_id: int,
    payload: VeiculoOcorrenciaResolver,
) -> VeiculoOcorrencia:
    o = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    if o.status not in _OCORRENCIA_TRATAVEL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível resolver ocorrências 'aberta' ou 'em_tratamento'.",
        )
    dados = payload.model_dump(exclude_unset=True)
    o.status = "resolvida"
    o.data_resolucao = dados.get("data_resolucao") or date.today()
    if "providencias" in dados:
        o.providencias = dados["providencias"]
    o.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(o)
    return o


async def cancelar_ocorrencia(
    db: AsyncSession, *, tenant_id: int, ocorrencia_id: int
) -> VeiculoOcorrencia:
    o = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    if o.status not in _OCORRENCIA_TRATAVEL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível cancelar ocorrências 'aberta' ou 'em_tratamento'.",
        )
    o.status = "cancelada"
    o.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(o)
    return o


async def excluir_ocorrencia(
    db: AsyncSession, *, tenant_id: int, ocorrencia_id: int
) -> None:
    o = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    o.excluido = True
    o.atualizado_em = datetime.utcnow()
    await db.commit()
