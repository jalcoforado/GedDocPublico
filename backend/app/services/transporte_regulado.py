"""Transporte Regulado — serviço de domínio do cadastro de Permissionários.

Tenant-scoped, mesmo padrão de `services/frota.py`:
- `tenant_id` sempre do caller (`request.state.tenant_id`), nunca do payload.
- Carga por id filtra `tenant_id` (404 cross-tenant).
- `cpf` único por tenant entre permissionários não excluídos (409).
- Exclusão = soft-delete (`excluido=true`); o CPF volta a ficar disponível.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Empresa, Permissionario
from ..schemas.transporte_regulado import (
    EmpresaCreate,
    EmpresaUpdate,
    PermissionarioCreate,
    PermissionarioUpdate,
)


async def _validar_cpf_unico(
    db: AsyncSession, *, tenant_id: int, cpf: str, excluir_id: int | None = None
) -> None:
    stmt = select(Permissionario.id).where(
        Permissionario.tenant_id == tenant_id,
        Permissionario.cpf == cpf,
        Permissionario.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(Permissionario.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um permissionário com o CPF '{cpf}' neste tenant.",
        )


async def obter_permissionario(
    db: AsyncSession, *, tenant_id: int, permissionario_id: int
) -> Permissionario:
    p = (
        await db.execute(
            select(Permissionario).where(
                Permissionario.id == permissionario_id,
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permissionário não encontrado"
        )
    return p


async def listar_permissionarios(
    db: AsyncSession,
    *,
    tenant_id: int,
    situacao: str | None = None,
    tipo_servico: str | None = None,
) -> list[Permissionario]:
    stmt = select(Permissionario).where(
        Permissionario.tenant_id == tenant_id,
        Permissionario.excluido.is_(False),
    )
    if situacao is not None:
        stmt = stmt.where(Permissionario.situacao == situacao)
    if tipo_servico is not None:
        stmt = stmt.where(Permissionario.tipo_servico == tipo_servico)
    stmt = stmt.order_by(Permissionario.nome)
    return list((await db.execute(stmt)).scalars().all())


async def criar_permissionario(
    db: AsyncSession, *, tenant_id: int, payload: PermissionarioCreate
) -> Permissionario:
    dados = payload.model_dump()
    await _validar_cpf_unico(db, tenant_id=tenant_id, cpf=dados["cpf"])
    p = Permissionario(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def atualizar_permissionario(
    db: AsyncSession,
    *,
    tenant_id: int,
    permissionario_id: int,
    payload: PermissionarioUpdate,
) -> Permissionario:
    p = await obter_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
    dados = payload.model_dump(exclude_unset=True)

    if "cpf" in dados:
        await _validar_cpf_unico(
            db, tenant_id=tenant_id, cpf=dados["cpf"], excluir_id=permissionario_id
        )

    # Coerências sobre os valores efetivos (merge do parcial).
    cnh_numero = dados.get("cnh_numero", p.cnh_numero)
    cnh_validade = dados.get("cnh_validade", p.cnh_validade)
    if cnh_numero and cnh_validade is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cnh_validade é obrigatória quando a CNH é informada.",
        )
    inicio = dados.get("data_inicio_permissao", p.data_inicio_permissao)
    validade = dados.get("data_validade_permissao", p.data_validade_permissao)
    if inicio is not None and validade is not None and validade < inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_validade_permissao deve ser posterior ou igual à data_inicio_permissao.",
        )

    for campo, valor in dados.items():
        setattr(p, campo, valor)
    p.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return p


async def set_situacao_permissionario(
    db: AsyncSession, *, tenant_id: int, permissionario_id: int, situacao: str
) -> Permissionario:
    p = await obter_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
    p.situacao = situacao
    p.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return p


async def excluir_permissionario(
    db: AsyncSession, *, tenant_id: int, permissionario_id: int
) -> None:
    p = await obter_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
    p.excluido = True
    p.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Empresa =======================================
async def _validar_cnpj_unico(
    db: AsyncSession, *, tenant_id: int, cnpj: str, excluir_id: int | None = None
) -> None:
    stmt = select(Empresa.id).where(
        Empresa.tenant_id == tenant_id,
        Empresa.cnpj == cnpj,
        Empresa.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(Empresa.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma empresa com o CNPJ '{cnpj}' neste tenant.",
        )


async def _validar_representante(
    db: AsyncSession, *, tenant_id: int, representante_id: int | None
) -> None:
    """Se informado, o representante deve ser um permissionário do mesmo tenant,
    não excluído (404 caso contrário)."""
    if representante_id is None:
        return
    existe = (
        await db.execute(
            select(Permissionario.id).where(
                Permissionario.id == representante_id,
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permissionário representante não encontrado neste tenant.",
        )


async def obter_empresa(
    db: AsyncSession, *, tenant_id: int, empresa_id: int
) -> Empresa:
    e = (
        await db.execute(
            select(Empresa).where(
                Empresa.id == empresa_id,
                Empresa.tenant_id == tenant_id,
                Empresa.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada"
        )
    return e


async def listar_empresas(
    db: AsyncSession,
    *,
    tenant_id: int,
    situacao: str | None = None,
    tipo_servico: str | None = None,
    q: str | None = None,
) -> list[Empresa]:
    stmt = select(Empresa).where(
        Empresa.tenant_id == tenant_id,
        Empresa.excluido.is_(False),
    )
    if situacao is not None:
        stmt = stmt.where(Empresa.situacao == situacao)
    if tipo_servico is not None:
        stmt = stmt.where(Empresa.tipo_servico == tipo_servico)
    if q:
        termo = f"%{q.strip()}%"
        stmt = stmt.where(
            Empresa.razao_social.ilike(termo)
            | Empresa.nome_fantasia.ilike(termo)
            | Empresa.cnpj.ilike(termo)
        )
    stmt = stmt.order_by(Empresa.razao_social)
    return list((await db.execute(stmt)).scalars().all())


async def criar_empresa(
    db: AsyncSession, *, tenant_id: int, payload: EmpresaCreate
) -> Empresa:
    dados = payload.model_dump()
    await _validar_cnpj_unico(db, tenant_id=tenant_id, cnpj=dados["cnpj"])
    await _validar_representante(
        db, tenant_id=tenant_id,
        representante_id=dados.get("id_representante_permissionario"),
    )
    e = Empresa(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


async def atualizar_empresa(
    db: AsyncSession, *, tenant_id: int, empresa_id: int, payload: EmpresaUpdate
) -> Empresa:
    e = await obter_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
    dados = payload.model_dump(exclude_unset=True)

    if "cnpj" in dados:
        await _validar_cnpj_unico(
            db, tenant_id=tenant_id, cnpj=dados["cnpj"], excluir_id=empresa_id
        )
    if "id_representante_permissionario" in dados:
        await _validar_representante(
            db, tenant_id=tenant_id,
            representante_id=dados["id_representante_permissionario"],
        )

    # Coerência das datas da autorização sobre os valores efetivos (merge do parcial).
    inicio = dados.get("data_inicio_autorizacao", e.data_inicio_autorizacao)
    validade = dados.get("data_validade_autorizacao", e.data_validade_autorizacao)
    if inicio is not None and validade is not None and validade < inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_validade_autorizacao deve ser posterior ou igual à data_inicio_autorizacao.",
        )

    for campo, valor in dados.items():
        setattr(e, campo, valor)
    e.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(e)
    return e


async def set_situacao_empresa(
    db: AsyncSession, *, tenant_id: int, empresa_id: int, situacao: str
) -> Empresa:
    e = await obter_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
    e.situacao = situacao
    e.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(e)
    return e


async def excluir_empresa(
    db: AsyncSession, *, tenant_id: int, empresa_id: int
) -> None:
    e = await obter_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
    e.excluido = True
    e.atualizado_em = datetime.utcnow()
    await db.commit()
