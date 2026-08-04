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
from sqlalchemy import select, func, case
from sqlalchemy.sql import literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Empresa, Permissionario, VeiculoRegulado, Usuario
from ..models.transporte_regulado import (
    VeiculoDocumento,
    VeiculoAvaliacao,
    VeiculoVistoria,
    Alvara,
    AlvaraDocumento,
    AlvaraResponsavel,
    AlvaraVeiculo,
    AlvaraAuditoria,
)
from ..schemas.transporte_regulado import (
    EmpresaCreate,
    EmpresaUpdate,
    PermissionarioCreate,
    PermissionarioUpdate,
    VeiculoReguladoCreate,
    VeiculoReguladoUpdate,
    VeiculoDocumentoCreate,
    VeiculoDocumentoUpdate,
    VeiculoAvaliacaoCreate,
    VeiculoAvaliacaoUpdate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaUpdate,
    VeiculoVistoriaRenovarInput,
    AlvaraCreate,
    AlvaraUpdate,
    AlvaraOut,
    AlvaraRenovarInput,
    AlvaraDocumentoCreate,
    AlvaraDocumentoUpdate,
    AlvaraDocumentoOut,
    AlvaraResponsavelCreate,
    AlvaraResponsavelOut,
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
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Permissionario], int]:
    stmt = select(Permissionario).where(
        Permissionario.tenant_id == tenant_id,
        Permissionario.excluido.is_(False),
    )
    if situacao is not None:
        stmt = stmt.where(Permissionario.situacao == situacao)
    if tipo_servico is not None:
        stmt = stmt.where(Permissionario.tipo_servico == tipo_servico)
    stmt = stmt.order_by(Permissionario.nome)

    # Contar total antes de limitar
    count_stmt = select(func.count(Permissionario.id)).where(
        Permissionario.tenant_id == tenant_id,
        Permissionario.excluido.is_(False),
    )
    if situacao is not None:
        count_stmt = count_stmt.where(Permissionario.situacao == situacao)
    if tipo_servico is not None:
        count_stmt = count_stmt.where(Permissionario.tipo_servico == tipo_servico)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


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
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Empresa], int]:
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

    # Contar total antes de limitar
    count_stmt = select(func.count(Empresa.id)).where(
        Empresa.tenant_id == tenant_id,
        Empresa.excluido.is_(False),
    )
    if situacao is not None:
        count_stmt = count_stmt.where(Empresa.situacao == situacao)
    if tipo_servico is not None:
        count_stmt = count_stmt.where(Empresa.tipo_servico == tipo_servico)
    if q:
        termo = f"%{q.strip()}%"
        count_stmt = count_stmt.where(
            Empresa.razao_social.ilike(termo)
            | Empresa.nome_fantasia.ilike(termo)
            | Empresa.cnpj.ilike(termo)
        )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


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


# ============================ Veículo regulado ==============================
async def _validar_campo_unico_veiculo(
    db: AsyncSession, *, tenant_id: int, campo, valor: str, excluir_id: int | None = None
) -> bool:
    """Retorna True se já existe outro veículo não-excluído do tenant com `campo == valor`."""
    stmt = select(VeiculoRegulado.id).where(
        VeiculoRegulado.tenant_id == tenant_id,
        campo == valor,
        VeiculoRegulado.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(VeiculoRegulado.id != excluir_id)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def _validar_unicidade_veiculo(
    db: AsyncSession, *, tenant_id: int, dados: dict, excluir_id: int | None = None
) -> None:
    if "placa" in dados and dados["placa"] is not None:
        if await _validar_campo_unico_veiculo(
            db, tenant_id=tenant_id, campo=VeiculoRegulado.placa,
            valor=dados["placa"], excluir_id=excluir_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um veículo com a placa '{dados['placa']}' neste tenant.",
            )
    if dados.get("renavam") is not None:
        if await _validar_campo_unico_veiculo(
            db, tenant_id=tenant_id, campo=VeiculoRegulado.renavam,
            valor=dados["renavam"], excluir_id=excluir_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um veículo com o RENAVAM '{dados['renavam']}' neste tenant.",
            )
    if dados.get("chassi") is not None:
        if await _validar_campo_unico_veiculo(
            db, tenant_id=tenant_id, campo=VeiculoRegulado.chassi,
            valor=dados["chassi"], excluir_id=excluir_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um veículo com o chassi '{dados['chassi']}' neste tenant.",
            )


async def _validar_vinculos_veiculo(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_permissionario: int | None,
    id_empresa: int | None,
) -> None:
    """Se informados, permissionário/empresa devem ser do MESMO tenant e não-excluídos."""
    if id_permissionario is not None:
        existe = (
            await db.execute(
                select(Permissionario.id).where(
                    Permissionario.id == id_permissionario,
                    Permissionario.tenant_id == tenant_id,
                    Permissionario.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permissionário do vínculo não encontrado neste tenant.",
            )
    if id_empresa is not None:
        existe = (
            await db.execute(
                select(Empresa.id).where(
                    Empresa.id == id_empresa,
                    Empresa.tenant_id == tenant_id,
                    Empresa.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa do vínculo não encontrada neste tenant.",
            )


async def obter_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int
) -> VeiculoRegulado:
    v = (
        await db.execute(
            select(VeiculoRegulado).where(
                VeiculoRegulado.id == veiculo_id,
                VeiculoRegulado.tenant_id == tenant_id,
                VeiculoRegulado.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Veículo não encontrado"
        )
    return v


async def listar_veiculos(
    db: AsyncSession,
    *,
    tenant_id: int,
    situacao: str | None = None,
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    id_empresa: int | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[VeiculoRegulado], int]:
    stmt = select(VeiculoRegulado).where(
        VeiculoRegulado.tenant_id == tenant_id,
        VeiculoRegulado.excluido.is_(False),
    )
    if situacao is not None:
        stmt = stmt.where(VeiculoRegulado.situacao == situacao)
    if tipo_servico is not None:
        stmt = stmt.where(VeiculoRegulado.tipo_servico == tipo_servico)
    if id_permissionario is not None:
        stmt = stmt.where(VeiculoRegulado.id_permissionario == id_permissionario)
    if id_empresa is not None:
        stmt = stmt.where(VeiculoRegulado.id_empresa == id_empresa)
    if q:
        termo = f"%{q.strip()}%"
        stmt = stmt.where(
            VeiculoRegulado.placa.ilike(termo)
            | VeiculoRegulado.marca.ilike(termo)
            | VeiculoRegulado.modelo.ilike(termo)
            | VeiculoRegulado.renavam.ilike(termo)
            | VeiculoRegulado.chassi.ilike(termo)
        )
    stmt = stmt.order_by(VeiculoRegulado.placa)

    # Contar total antes de limitar
    count_stmt = select(func.count(VeiculoRegulado.id)).where(
        VeiculoRegulado.tenant_id == tenant_id,
        VeiculoRegulado.excluido.is_(False),
    )
    if situacao is not None:
        count_stmt = count_stmt.where(VeiculoRegulado.situacao == situacao)
    if tipo_servico is not None:
        count_stmt = count_stmt.where(VeiculoRegulado.tipo_servico == tipo_servico)
    if id_permissionario is not None:
        count_stmt = count_stmt.where(VeiculoRegulado.id_permissionario == id_permissionario)
    if id_empresa is not None:
        count_stmt = count_stmt.where(VeiculoRegulado.id_empresa == id_empresa)
    if q:
        termo = f"%{q.strip()}%"
        count_stmt = count_stmt.where(
            VeiculoRegulado.placa.ilike(termo)
            | VeiculoRegulado.marca.ilike(termo)
            | VeiculoRegulado.modelo.ilike(termo)
            | VeiculoRegulado.renavam.ilike(termo)
            | VeiculoRegulado.chassi.ilike(termo)
        )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


async def criar_veiculo(
    db: AsyncSession, *, tenant_id: int, payload: VeiculoReguladoCreate
) -> VeiculoRegulado:
    dados = payload.model_dump()
    await _validar_unicidade_veiculo(db, tenant_id=tenant_id, dados=dados)
    await _validar_vinculos_veiculo(
        db, tenant_id=tenant_id,
        id_permissionario=dados.get("id_permissionario"),
        id_empresa=dados.get("id_empresa"),
    )
    v = VeiculoRegulado(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


async def atualizar_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, payload: VeiculoReguladoUpdate
) -> VeiculoRegulado:
    v = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    dados = payload.model_dump(exclude_unset=True)

    await _validar_unicidade_veiculo(
        db, tenant_id=tenant_id, dados=dados, excluir_id=veiculo_id
    )
    if "id_permissionario" in dados or "id_empresa" in dados:
        await _validar_vinculos_veiculo(
            db, tenant_id=tenant_id,
            id_permissionario=dados.get("id_permissionario"),
            id_empresa=dados.get("id_empresa"),
        )

    # Vínculo efetivo (merge do parcial): ao menos um deve permanecer.
    novo_perm = dados.get("id_permissionario", v.id_permissionario)
    nova_emp = dados.get("id_empresa", v.id_empresa)
    if novo_perm is None and nova_emp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe ao menos um vínculo: id_permissionario ou id_empresa.",
        )

    # Coerência de anos e datas sobre os valores efetivos.
    ano_fab = dados.get("ano_fabricacao", v.ano_fabricacao)
    ano_mod = dados.get("ano_modelo", v.ano_modelo)
    if ano_fab is not None and ano_mod is not None and ano_mod < ano_fab:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ano_modelo deve ser maior ou igual a ano_fabricacao.",
        )
    inicio = dados.get("data_inicio_autorizacao", v.data_inicio_autorizacao)
    validade = dados.get("data_validade_autorizacao", v.data_validade_autorizacao)
    if inicio is not None and validade is not None and validade < inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_validade_autorizacao deve ser posterior ou igual à data_inicio_autorizacao.",
        )

    for campo, valor in dados.items():
        setattr(v, campo, valor)
    v.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(v)
    return v


async def set_situacao_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, situacao: str
) -> VeiculoRegulado:
    v = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    v.situacao = situacao
    v.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(v)
    return v


async def excluir_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int
) -> None:
    v = await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)
    v.excluido = True
    v.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Documento Veículo ==============================
async def _validar_documento_existe(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, tipo_documento: str
) -> bool:
    """Retorna True se já existe documento não-excluído do mesmo tipo para o veículo."""
    stmt = select(VeiculoDocumento.id).where(
        VeiculoDocumento.tenant_id == tenant_id,
        VeiculoDocumento.id_veiculo == veiculo_id,
        VeiculoDocumento.tipo_documento == tipo_documento,
        VeiculoDocumento.excluido.is_(False),
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def _validar_usuario_existe(
    db: AsyncSession, *, tenant_id: int, usuario_id: int
) -> bool:
    """Valida se usuário existe no mesmo tenant (retorna True se existe)."""
    stmt = select(Usuario.id).where(
        Usuario.id == usuario_id,
        Usuario.tenant_id == tenant_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def obter_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> VeiculoDocumento:
    """Obtém documento por ID, validando tenant e soft-delete."""
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


async def listar_documentos(
    db: AsyncSession,
    *,
    tenant_id: int,
    veiculo_id: int,
    tipo_documento: str | None = None,
    situacao: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[VeiculoDocumento], int]:
    """Lista documentos de um veículo com filtros opcionais."""
    stmt = select(VeiculoDocumento).where(
        VeiculoDocumento.tenant_id == tenant_id,
        VeiculoDocumento.id_veiculo == veiculo_id,
        VeiculoDocumento.excluido.is_(False),
    )
    if tipo_documento is not None:
        stmt = stmt.where(VeiculoDocumento.tipo_documento == tipo_documento)
    if situacao is not None:
        stmt = stmt.where(VeiculoDocumento.situacao == situacao)
    stmt = stmt.order_by(VeiculoDocumento.criado_em)

    # Contar total antes de limitar
    count_stmt = select(func.count(VeiculoDocumento.id)).where(
        VeiculoDocumento.tenant_id == tenant_id,
        VeiculoDocumento.id_veiculo == veiculo_id,
        VeiculoDocumento.excluido.is_(False),
    )
    if tipo_documento is not None:
        count_stmt = count_stmt.where(VeiculoDocumento.tipo_documento == tipo_documento)
    if situacao is not None:
        count_stmt = count_stmt.where(VeiculoDocumento.situacao == situacao)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


async def criar_documento(
    db: AsyncSession,
    *,
    tenant_id: int,
    veiculo_id: int,
    payload: VeiculoDocumentoCreate,
) -> VeiculoDocumento:
    """Cria novo documento para veículo regulado.

    1. Valida que veículo existe no tenant
    2. Valida unicidade do tipo de documento por veículo
    3. Insere registro com criado_em = now()
    """
    # 1. Valida veículo
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)

    # 2. Valida unicidade
    if await _validar_documento_existe(
        db,
        tenant_id=tenant_id,
        veiculo_id=veiculo_id,
        tipo_documento=payload.tipo_documento,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Documento do tipo '{payload.tipo_documento}' já existe para este veículo.",
        )

    # 3. Insere
    dados = payload.model_dump()
    doc = VeiculoDocumento(
        tenant_id=tenant_id,
        id_veiculo=veiculo_id,
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
    """Atualiza documento existente.

    1. Valida que documento existe no tenant
    2. Se tipo_documento muda, valida unicidade do novo tipo
    3. Atualiza com atualizado_em = now()
    """
    # 1. Valida documento
    doc = await obter_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    dados = payload.model_dump(exclude_unset=True)

    # 2. Valida novo tipo se foi mudado
    if "tipo_documento" in dados and dados["tipo_documento"] != doc.tipo_documento:
        if await _validar_documento_existe(
            db,
            tenant_id=tenant_id,
            veiculo_id=doc.id_veiculo,
            tipo_documento=dados["tipo_documento"],
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Documento do tipo '{dados['tipo_documento']}' já existe para este veículo.",
            )

    # 3. Atualiza
    for campo, valor in dados.items():
        setattr(doc, campo, valor)
    doc.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(doc)
    return doc


async def excluir_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> None:
    """Soft-delete de documento (excluido=True)."""
    doc = await obter_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    doc.excluido = True
    doc.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Avaliação Veículo ==============================
async def obter_avaliacao(
    db: AsyncSession, *, tenant_id: int, avaliacao_id: int
) -> VeiculoAvaliacao:
    """Obtém avaliação por ID, validando tenant e soft-delete."""
    av = (
        await db.execute(
            select(VeiculoAvaliacao).where(
                VeiculoAvaliacao.id == avaliacao_id,
                VeiculoAvaliacao.tenant_id == tenant_id,
                VeiculoAvaliacao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if av is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada"
        )
    return av


async def listar_avaliacoes(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[VeiculoAvaliacao], int]:
    """Lista avaliações de um veículo."""
    stmt = select(VeiculoAvaliacao).where(
        VeiculoAvaliacao.tenant_id == tenant_id,
        VeiculoAvaliacao.id_veiculo == veiculo_id,
        VeiculoAvaliacao.excluido.is_(False),
    )
    stmt = stmt.order_by(VeiculoAvaliacao.data_avaliacao.desc())

    count_stmt = select(func.count(VeiculoAvaliacao.id)).where(
        VeiculoAvaliacao.tenant_id == tenant_id,
        VeiculoAvaliacao.id_veiculo == veiculo_id,
        VeiculoAvaliacao.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


async def criar_avaliacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    veiculo_id: int,
    usuario_id: int,
    payload: VeiculoAvaliacaoCreate,
) -> VeiculoAvaliacao:
    """Cria nova avaliação para veículo regulado.

    1. Valida que veículo existe no tenant
    2. Valida que usuário existe no tenant
    3. Insere registro com id_usuario_avaliador = usuario_id
    """
    # 1. Valida veículo
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)

    # 2. Valida usuário
    if not await _validar_usuario_existe(db, tenant_id=tenant_id, usuario_id=usuario_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário avaliador não encontrado neste tenant.",
        )

    # 3. Insere
    dados = payload.model_dump()
    av = VeiculoAvaliacao(
        tenant_id=tenant_id,
        id_veiculo=veiculo_id,
        id_usuario_avaliador=usuario_id,
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(av)
    await db.commit()
    await db.refresh(av)
    return av


async def atualizar_avaliacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    avaliacao_id: int,
    payload: VeiculoAvaliacaoUpdate,
) -> VeiculoAvaliacao:
    """Atualiza avaliação existente com atualizado_em = now()."""
    av = await obter_avaliacao(db, tenant_id=tenant_id, avaliacao_id=avaliacao_id)
    dados = payload.model_dump(exclude_unset=True)

    for campo, valor in dados.items():
        setattr(av, campo, valor)
    av.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(av)
    return av


async def excluir_avaliacao(
    db: AsyncSession, *, tenant_id: int, avaliacao_id: int
) -> None:
    """Soft-delete de avaliação (excluido=True)."""
    av = await obter_avaliacao(db, tenant_id=tenant_id, avaliacao_id=avaliacao_id)
    av.excluido = True
    av.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Vistoria Veículo ================================
async def obter_vistoria(
    db: AsyncSession, *, tenant_id: int, vistoria_id: int
) -> VeiculoVistoria:
    """Obtém vistoria por ID, validando tenant e soft-delete."""
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
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[VeiculoVistoria], int]:
    """Lista vistorias de um veículo."""
    stmt = select(VeiculoVistoria).where(
        VeiculoVistoria.tenant_id == tenant_id,
        VeiculoVistoria.id_veiculo == veiculo_id,
        VeiculoVistoria.excluido.is_(False),
    )
    stmt = stmt.order_by(VeiculoVistoria.data_vistoria.desc())

    count_stmt = select(func.count(VeiculoVistoria.id)).where(
        VeiculoVistoria.tenant_id == tenant_id,
        VeiculoVistoria.id_veiculo == veiculo_id,
        VeiculoVistoria.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return resultado, total


async def criar_vistoria(
    db: AsyncSession,
    *,
    tenant_id: int,
    veiculo_id: int,
    auditor_id: int,
    payload: VeiculoVistoriaCreate,
) -> VeiculoVistoria:
    """Cria nova vistoria para veículo regulado.

    1. Valida que veículo existe no tenant
    2. Valida que usuário (auditor) existe no tenant
    3. Insere registro com id_auditor = auditor_id
    """
    # 1. Valida veículo
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)

    # 2. Valida usuário auditor
    if not await _validar_usuario_existe(db, tenant_id=tenant_id, usuario_id=auditor_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário auditor não encontrado neste tenant.",
        )

    # 3. Insere
    dados = payload.model_dump()
    v = VeiculoVistoria(
        tenant_id=tenant_id,
        id_veiculo=veiculo_id,
        id_auditor=auditor_id,
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
    """Atualiza vistoria existente com atualizado_em = now()."""
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
    """Soft-delete de vistoria (excluido=True)."""
    v = await obter_vistoria(db, tenant_id=tenant_id, vistoria_id=vistoria_id)
    v.excluido = True
    v.atualizado_em = datetime.utcnow()
    await db.commit()


async def listar_vistorias_vencidas(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[VeiculoVistoria], int]:
    """Lista vistorias de um veículo cuja data_validade já passou (vencidas)."""
    from datetime import date as date_type

    stmt = (
        select(VeiculoVistoria)
        .where(
            VeiculoVistoria.tenant_id == tenant_id,
            VeiculoVistoria.id_veiculo == veiculo_id,
            VeiculoVistoria.data_validade <= date_type.today(),
            VeiculoVistoria.excluido.is_(False),
        )
        .order_by(VeiculoVistoria.data_vistoria.desc())
    )

    count_stmt = select(func.count(VeiculoVistoria.id)).where(
        VeiculoVistoria.tenant_id == tenant_id,
        VeiculoVistoria.id_veiculo == veiculo_id,
        VeiculoVistoria.data_validade <= date_type.today(),
        VeiculoVistoria.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def renovar_vistoria(
    db: AsyncSession,
    *,
    tenant_id: int,
    veiculo_id: int,
    vistoria_id: int,
    auditor_id: int,
    payload: VeiculoVistoriaRenovarInput,
) -> VeiculoVistoria:
    """Cria nova vistoria como renovação da anterior (via renovada_de).
    Valida que vistoria anterior existe e está vencida."""
    vistoria_anterior = await obter_vistoria(
        db, tenant_id=tenant_id, vistoria_id=vistoria_id
    )
    if vistoria_anterior.id_veiculo != veiculo_id:
        raise HTTPException(status_code=409, detail="Vistoria não pertence a este veículo")

    from datetime import date as date_type

    if vistoria_anterior.data_validade and vistoria_anterior.data_validade > date_type.today():
        raise HTTPException(
            status_code=400, detail="Vistoria anterior não está vencida"
        )

    # Valida auditor
    if not await _validar_usuario_existe(db, tenant_id=tenant_id, usuario_id=auditor_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário auditor não encontrado neste tenant.",
        )

    v = VeiculoVistoria(
        tenant_id=tenant_id,
        id_veiculo=veiculo_id,
        id_auditor=auditor_id,
        resultado=payload.resultado,
        parecer=payload.parecer,
        observacoes=payload.observacoes,
        data_vistoria=datetime.utcnow(),
        data_validade=payload.data_validade,
        renovada_de=vistoria_id,
        criado_em=datetime.utcnow(),
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


# ================================= Alvara (P2) =====================================


async def obter_alvara(
    db: AsyncSession, *, tenant_id: int, alvara_id: int
) -> Alvara:
    """Obtém alvará pelo ID, filtrando por tenant."""
    stmt = select(Alvara).where(
        Alvara.tenant_id == tenant_id,
        Alvara.id == alvara_id,
        Alvara.excluido.is_(False),
    )
    alvara = (await db.execute(stmt)).scalar_one_or_none()
    if not alvara:
        raise HTTPException(status_code=404, detail="Alvará não encontrado")
    return alvara


async def listar_alvaras(
    db: AsyncSession,
    *,
    tenant_id: int,
    empresa_id: int | None = None,
    permissionario_id: int | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Alvara], int]:
    """Lista alvarás do tenant, filtrando por empresa, permissionário ou número.

    `q` é busca por substring em `numero_alvara`, e existe porque a tela
    filtrava no cliente sobre a página já truncada em 50: o usuário digitava um
    número que existe no banco e a tela dizia que não achou. Não é "não vejo
    tudo" — é a tela afirmando que o registro não existe.

    As condições são montadas UMA vez e aplicadas às duas consultas. Antes eram
    duplicadas, e um filtro acrescentado só numa das cópias devolveria `total`
    incoerente com `items` — a paginação passaria a mentir de outro jeito.
    """
    condicoes = [Alvara.tenant_id == tenant_id, Alvara.excluido.is_(False)]
    if empresa_id is not None:
        condicoes.append(Alvara.id_empresa == empresa_id)
    if permissionario_id is not None:
        condicoes.append(Alvara.id_permissionario == permissionario_id)
    termo = (q or "").strip()
    if termo:
        # `lower(...) LIKE lower(...)` é o idioma de `routers/_crud.py`. Não usa
        # índice, e não vale criar um: `%termo%` não é sargável de qualquer
        # forma, e a tabela é pequena por tenant.
        condicoes.append(func.lower(Alvara.numero_alvara).like(f"%{termo.lower()}%"))

    stmt = select(Alvara).where(*condicoes).order_by(Alvara.criado_em.desc())
    count_stmt = select(func.count(Alvara.id)).where(*condicoes)

    total = (await db.execute(count_stmt)).scalar_one() or 0
    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def criar_alvara(
    db: AsyncSession, *, tenant_id: int, payload: AlvaraCreate
) -> Alvara:
    """Cria novo alvará — valida número único, ao menos um vínculo."""
    # Valida número único
    stmt_check = select(Alvara.id).where(
        Alvara.tenant_id == tenant_id,
        Alvara.numero_alvara == payload.numero_alvara,
        Alvara.excluido.is_(False),
    )
    if (await db.execute(stmt_check)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Número de alvará já existe neste tenant"
        )

    # Valida empresa (se informada)
    if payload.id_empresa:
        await obter_empresa(db, tenant_id=tenant_id, empresa_id=payload.id_empresa)

    # Valida permissionário (se informado)
    if payload.id_permissionario:
        await obter_permissionario(
            db, tenant_id=tenant_id, permissionario_id=payload.id_permissionario
        )

    dados = payload.model_dump()
    a = Alvara(
        tenant_id=tenant_id,
        criado_em=datetime.utcnow(),
        **dados,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def atualizar_alvara(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, payload: AlvaraUpdate
) -> Alvara:
    """Atualiza alvará — todos campos opcionais."""
    a = await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    # Se atualizando número, valida unicidade
    if payload.numero_alvara and payload.numero_alvara != a.numero_alvara:
        stmt_check = select(Alvara.id).where(
            Alvara.tenant_id == tenant_id,
            Alvara.numero_alvara == payload.numero_alvara,
            Alvara.excluido.is_(False),
            Alvara.id != alvara_id,
        )
        if (await db.execute(stmt_check)).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail="Número de alvará já existe neste tenant"
            )

    # Se atualizando empresa, valida
    if payload.id_empresa:
        await obter_empresa(db, tenant_id=tenant_id, empresa_id=payload.id_empresa)

    # Se atualizando permissionário, valida
    if payload.id_permissionario:
        await obter_permissionario(
            db, tenant_id=tenant_id, permissionario_id=payload.id_permissionario
        )

    dados = payload.model_dump(exclude_unset=True)
    for key, val in dados.items():
        setattr(a, key, val)
    a.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(a)
    return a


async def excluir_alvara(
    db: AsyncSession, *, tenant_id: int, alvara_id: int
) -> None:
    """Exclui alvará (soft-delete)."""
    a = await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)
    a.excluido = True
    a.atualizado_em = datetime.utcnow()
    await db.commit()


async def listar_alvaras_vencidos(
    db: AsyncSession, *, tenant_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[Alvara], int]:
    """Lista alvarás vencidos (data_validade <= hoje) do tenant, ordenados por data_validade ASC."""
    hoje = datetime.utcnow().date()
    stmt = select(Alvara).where(
        Alvara.tenant_id == tenant_id,
        Alvara.data_validade.is_not(None),
        Alvara.data_validade <= hoje,
        Alvara.excluido.is_(False),
    ).order_by(Alvara.data_validade.asc())

    count_stmt = select(func.count(Alvara.id)).where(
        Alvara.tenant_id == tenant_id,
        Alvara.data_validade.is_not(None),
        Alvara.data_validade <= hoje,
        Alvara.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def renovar_alvara(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, payload: AlvaraRenovarInput
) -> Alvara:
    """Renova um alvará vencido — cria novo alvará atrelado ao anterior via renovado_de."""
    # Obter alvará original
    original = await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    # Validar que está vencido
    hoje = datetime.utcnow().date()
    if original.data_validade is None or original.data_validade > hoje:
        raise HTTPException(
            status_code=400,
            detail="Alvará não está vencido; renovação só permitida para alvarás expirados.",
        )

    # Criar novo alvará com mesmos vínculos e número
    novo = Alvara(
        tenant_id=tenant_id,
        id_empresa=original.id_empresa,
        id_permissionario=original.id_permissionario,
        numero_alvara=original.numero_alvara,
        data_inicio=payload.data_inicio if payload.data_inicio is not None else original.data_inicio,
        data_validade=payload.data_validade,
        tipo_servico=original.tipo_servico,
        observacoes=payload.observacoes if payload.observacoes is not None else original.observacoes,
        renovado_de=original.id,
        criado_em=datetime.utcnow(),
    )
    db.add(novo)
    await db.commit()
    await db.refresh(novo)
    return novo


# ============================ AlvaraDocumento ===============================


async def criar_alvara_documento(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, payload: AlvaraDocumentoCreate
) -> AlvaraDocumento:
    """Cria documento anexado a um alvará."""
    # Validar que alvará existe (404 cross-tenant)
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    doc = AlvaraDocumento(
        tenant_id=tenant_id,
        id_alvara=alvara_id,
        tipo_documento=payload.tipo_documento,
        arquivo=payload.arquivo,
        observacoes=payload.observacoes,
        criado_em=datetime.utcnow(),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def obter_alvara_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> AlvaraDocumento:
    """Obtém documento de alvará — 404 se não encontrado ou cross-tenant."""
    stmt = select(AlvaraDocumento).where(
        AlvaraDocumento.tenant_id == tenant_id,
        AlvaraDocumento.id == documento_id,
        AlvaraDocumento.excluido.is_(False),
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento de alvará não encontrado.",
        )
    return doc


async def listar_alvara_documentos(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[AlvaraDocumento], int]:
    """Lista documentos de um alvará."""
    # Validar que alvará existe
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    stmt = select(AlvaraDocumento).where(
        AlvaraDocumento.tenant_id == tenant_id,
        AlvaraDocumento.id_alvara == alvara_id,
        AlvaraDocumento.excluido.is_(False),
    ).order_by(AlvaraDocumento.criado_em.desc())

    count_stmt = select(func.count(AlvaraDocumento.id)).where(
        AlvaraDocumento.tenant_id == tenant_id,
        AlvaraDocumento.id_alvara == alvara_id,
        AlvaraDocumento.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def atualizar_alvara_documento(
    db: AsyncSession,
    *,
    tenant_id: int,
    documento_id: int,
    payload: AlvaraDocumentoUpdate,
) -> AlvaraDocumento:
    """Atualiza documento de alvará — 404 cross-tenant."""
    doc = await obter_alvara_documento(db, tenant_id=tenant_id, documento_id=documento_id)

    if payload.tipo_documento is not None:
        doc.tipo_documento = payload.tipo_documento
    if payload.arquivo is not None:
        doc.arquivo = payload.arquivo
    if payload.observacoes is not None:
        doc.observacoes = payload.observacoes

    doc.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(doc)
    return doc


async def excluir_alvara_documento(
    db: AsyncSession, *, tenant_id: int, documento_id: int
) -> None:
    """Soft-delete documento de alvará."""
    doc = await obter_alvara_documento(db, tenant_id=tenant_id, documento_id=documento_id)
    doc.excluido = True
    doc.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ AlvaraResponsavel =============================


async def adicionar_responsavel(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, payload: AlvaraResponsavelCreate
) -> AlvaraResponsavel:
    """Adiciona usuário como responsável por um alvará."""
    # Validar que alvará existe (404 cross-tenant)
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    # Validar que usuário existe (mesma tenant)
    await _validar_usuario_existe(db, tenant_id=tenant_id, usuario_id=payload.id_usuario)

    resp = AlvaraResponsavel(
        tenant_id=tenant_id,
        id_alvara=alvara_id,
        id_usuario=payload.id_usuario,
        cargo_funcao=payload.cargo_funcao,
        criado_em=datetime.utcnow(),
    )
    db.add(resp)
    await db.commit()
    await db.refresh(resp)
    return resp


async def obter_responsavel(
    db: AsyncSession, *, tenant_id: int, responsavel_id: int
) -> AlvaraResponsavel:
    """Obtém responsável — 404 se não encontrado ou cross-tenant."""
    stmt = select(AlvaraResponsavel).where(
        AlvaraResponsavel.tenant_id == tenant_id,
        AlvaraResponsavel.id == responsavel_id,
        AlvaraResponsavel.excluido.is_(False),
    )
    resp = (await db.execute(stmt)).scalar_one_or_none()
    if resp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Responsável do alvará não encontrado.",
        )
    return resp


async def listar_responsaveis(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[AlvaraResponsavel], int]:
    """Lista responsáveis de um alvará."""
    # Validar que alvará existe
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    stmt = select(AlvaraResponsavel).where(
        AlvaraResponsavel.tenant_id == tenant_id,
        AlvaraResponsavel.id_alvara == alvara_id,
        AlvaraResponsavel.excluido.is_(False),
    ).order_by(AlvaraResponsavel.criado_em.desc())

    count_stmt = select(func.count(AlvaraResponsavel.id)).where(
        AlvaraResponsavel.tenant_id == tenant_id,
        AlvaraResponsavel.id_alvara == alvara_id,
        AlvaraResponsavel.excluido.is_(False),
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def remover_responsavel(
    db: AsyncSession, *, tenant_id: int, responsavel_id: int
) -> None:
    """Soft-delete responsável de um alvará."""
    resp = await obter_responsavel(db, tenant_id=tenant_id, responsavel_id=responsavel_id)
    resp.excluido = True
    resp.atualizado_em = datetime.utcnow()
    await db.commit()


# ============================ Veículos do Alvará (P4) ================================
async def vincular_veiculo_alvara(
    db: AsyncSession,
    *,
    tenant_id: int,
    alvara_id: int,
    veiculo_id: int,
) -> AlvaraVeiculo:
    """Vincula um veículo a um alvará.

    Validações:
    - Alvará existe e pertence ao tenant
    - Veículo existe e pertence ao tenant
    - Vínculo não existe (UNIQUE constraint)

    Raises:
        HTTPException: 404 alvará/veículo não encontrado, 409 já vinculado
    """
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)

    # Verificar duplicata
    stmt = select(AlvaraVeiculo).where(
        AlvaraVeiculo.tenant_id == tenant_id,
        AlvaraVeiculo.id_alvara == alvara_id,
        AlvaraVeiculo.id_veiculo == veiculo_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este veículo já está vinculado a este alvará.",
        )

    agora = datetime.utcnow()
    av = AlvaraVeiculo(
        tenant_id=tenant_id,
        id_alvara=alvara_id,
        id_veiculo=veiculo_id,
        data_vinculo=agora,
        criado_em=agora,
    )
    db.add(av)
    await db.commit()
    await db.refresh(av)
    return av


async def desvincular_veiculo_alvara(
    db: AsyncSession,
    *,
    tenant_id: int,
    alvara_id: int,
    veiculo_id: int,
) -> None:
    """Desvincula um veículo de um alvará (soft-delete)."""
    av = (
        await db.execute(
            select(AlvaraVeiculo).where(
                AlvaraVeiculo.tenant_id == tenant_id,
                AlvaraVeiculo.id_alvara == alvara_id,
                AlvaraVeiculo.id_veiculo == veiculo_id,
            )
        )
    ).scalar_one_or_none()
    if av is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vínculo entre alvará e veículo não encontrado.",
        )
    await db.delete(av)
    await db.commit()


async def listar_veiculos_alvara(
    db: AsyncSession, *, tenant_id: int, alvara_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[AlvaraVeiculo], int]:
    """Lista veículos vinculados a um alvará."""
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    stmt = select(AlvaraVeiculo).where(
        AlvaraVeiculo.tenant_id == tenant_id,
        AlvaraVeiculo.id_alvara == alvara_id,
    ).order_by(AlvaraVeiculo.criado_em.desc())

    count_stmt = select(func.count(AlvaraVeiculo.id)).where(
        AlvaraVeiculo.tenant_id == tenant_id,
        AlvaraVeiculo.id_alvara == alvara_id,
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


async def listar_alvaras_veiculo(
    db: AsyncSession, *, tenant_id: int, veiculo_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[AlvaraVeiculo], int]:
    """Lista alvarás vinculados a um veículo."""
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=veiculo_id)

    stmt = select(AlvaraVeiculo).where(
        AlvaraVeiculo.tenant_id == tenant_id,
        AlvaraVeiculo.id_veiculo == veiculo_id,
    ).order_by(AlvaraVeiculo.criado_em.desc())

    count_stmt = select(func.count(AlvaraVeiculo.id)).where(
        AlvaraVeiculo.tenant_id == tenant_id,
        AlvaraVeiculo.id_veiculo == veiculo_id,
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    resultado = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return resultado, total


# ============================ Auditoria de Alvará (P4) ===========================
async def registrar_auditoria_alvara(
    db: AsyncSession,
    *,
    tenant_id: int,
    alvara_id: int,
    acao: str,
    dados_antigos: dict | None = None,
    dados_novos: dict | None = None,
    usuario_id: int | None = None,
) -> AlvaraAuditoria:
    """Registra evento de auditoria para um alvará (append-only).

    Args:
        db: Sessão async
        tenant_id: Tenant do alvará
        alvara_id: ID do alvará
        acao: Ação realizada (alvara.criada, alvara.renovada, etc.)
        dados_antigos: Snapshot do estado anterior (JSONB)
        dados_novos: Snapshot do estado novo (JSONB)
        usuario_id: ID do usuário que fez a ação (opcional)

    Returns:
        Registro de auditoria criado
    """
    # Validar que alvará existe
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    agora = datetime.utcnow()
    audit = AlvaraAuditoria(
        tenant_id=tenant_id,
        id_alvara=alvara_id,
        acao=acao,
        dados_antigos=dados_antigos,
        dados_novos=dados_novos,
        id_usuario=usuario_id,
        criado_em=agora,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


async def listar_auditoria_alvara(
    db: AsyncSession,
    *,
    tenant_id: int,
    alvara_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[AlvaraAuditoria]:
    """Lista histórico de auditoria de um alvará (DESC por criado_em).

    Args:
        db: Sessão async
        tenant_id: Tenant do alvará
        alvara_id: ID do alvará
        limit: Máximo de registros (default 50)
        offset: Offset para paginação

    Returns:
        Lista de eventos de auditoria (mais recentes primeiro)
    """
    # Validar que alvará existe
    await obter_alvara(db, tenant_id=tenant_id, alvara_id=alvara_id)

    stmt = select(AlvaraAuditoria).where(
        AlvaraAuditoria.tenant_id == tenant_id,
        AlvaraAuditoria.id_alvara == alvara_id,
    ).order_by(AlvaraAuditoria.criado_em.desc()).limit(limit).offset(offset)

    return (await db.execute(stmt)).scalars().all()


# ============================ Relatório (P4.3) ================================
from datetime import date as date_class, timedelta


def _calcular_status_e_dias(data_validade: date_class | None) -> tuple[str, int | None]:
    """Calcula status do alvará e dias para vencimento.

    Retorna (status, dias_para_vencimento):
    - "ativo" / dias positivos
    - "a_renovar_30d" / dias entre 0 e 30
    - "vencido" / dias negativos (None retorna "indefinido")
    - "indefinido" / None se data_validade é None
    """
    if data_validade is None:
        return ("indefinido", None)

    hoje = date_class.today()
    dias = (data_validade - hoje).days

    if dias < 0:
        return ("vencido", dias)
    elif dias <= 30:
        return ("a_renovar_30d", dias)
    else:
        return ("ativo", dias)


async def listar_relatorio_alvaras(
    db: AsyncSession,
    *,
    tenant_id: int,
    tipo_servico: str | None = None,
    id_permissionario: int | None = None,
    status_filtro: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Lista alvarás com KPIs para relatório.

    Filtros opcionais:
    - tipo_servico: filtrar por tipo
    - id_permissionario: filtrar por permissionário
    - status_filtro: filtrar por status (ativo, vencido, a_renovar_30d, indefinido)

    Retorna (alvaras_com_kpis, total_count).
    """
    # Query base: alvarás não excluídos do tenant
    stmt = select(Alvara).where(
        Alvara.tenant_id == tenant_id,
        Alvara.excluido.is_(False),
    )

    # Aplicar filtros
    if tipo_servico:
        stmt = stmt.where(Alvara.tipo_servico == tipo_servico)
    if id_permissionario:
        stmt = stmt.where(Alvara.id_permissionario == id_permissionario)

    # Contar total antes de paginação (usando SQL COUNT, não .all())
    count_stmt = select(func.count(Alvara.id)).where(
        Alvara.tenant_id == tenant_id,
        Alvara.excluido.is_(False),
    )
    if tipo_servico:
        count_stmt = count_stmt.where(Alvara.tipo_servico == tipo_servico)
    if id_permissionario:
        count_stmt = count_stmt.where(Alvara.id_permissionario == id_permissionario)

    total = (await db.execute(count_stmt)).scalar_one() or 0

    # Buscar alvarás (sem limit se houver status_filtro para aplicar filtro correto)
    query_stmt = stmt.order_by(Alvara.criado_em.desc())
    if not status_filtro:
        # Sem filtro de status, pode limitar direto
        query_stmt = query_stmt.limit(limit).offset(offset)

    alvaras = (await db.execute(query_stmt)).scalars().all()

    # Calcular KPIs, aplicar status filter em Python, e montar resposta
    resultado = []
    for alvara in alvaras:
        status, dias = _calcular_status_e_dias(alvara.data_validade)

        # Filtro por status (aplicado antes de limitar resultado)
        if status_filtro and status != status_filtro:
            continue

        resultado.append({
            "id": alvara.id,
            "numero_alvara": alvara.numero_alvara,
            "tipo_servico": alvara.tipo_servico,
            "id_permissionario": alvara.id_permissionario,
            "id_empresa": alvara.id_empresa,
            "data_inicio": alvara.data_inicio,
            "data_validade": alvara.data_validade,
            "criado_em": alvara.criado_em,
            "status": status,
            "dias_para_vencimento": dias,
        })

        # Aplicar limit depois de filtrar
        if len(resultado) >= limit:
            break

    # Se houver status_filtro, ajustar offset aplicando manualmente
    if status_filtro:
        resultado = resultado[offset:offset + limit]

    return resultado, total


async def obter_kpis_agregados(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> dict:
    """Retorna KPIs agregados de alvarás do tenant."""
    stmt = select(Alvara).where(
        Alvara.tenant_id == tenant_id,
        Alvara.excluido.is_(False),
    )
    alvaras = (await db.execute(stmt)).scalars().all()

    kpis = {
        "total_alvaras": len(alvaras),
        "ativos": 0,
        "vencidos": 0,
        "a_renovar_30d": 0,
        "indefinidos": 0,
    }

    # _calcular_status_e_dias devolve o status no SINGULAR ("ativo", "vencido",
    # "indefinido"); as chaves do KPI são plurais. Sem esse mapa, `status in kpis`
    # só casava em "a_renovar_30d" e os outros três contadores ficavam sempre 0.
    plural = {
        "ativo": "ativos",
        "vencido": "vencidos",
        "a_renovar_30d": "a_renovar_30d",
        "indefinido": "indefinidos",
    }
    for alvara in alvaras:
        status, _ = _calcular_status_e_dias(alvara.data_validade)
        chave = plural.get(status)
        if chave in kpis:
            kpis[chave] += 1

    return kpis


def format_csv_row(alvara: dict) -> str:
    """Formata uma linha CSV com escape correto de aspas/vírgulas."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        alvara.get("id", ""),
        alvara.get("numero_alvara", ""),
        alvara.get("tipo_servico", ""),
        alvara.get("id_permissionario", ""),
        alvara.get("id_empresa", ""),
        alvara.get("data_inicio", ""),
        alvara.get("data_validade", ""),
        alvara.get("criado_em", ""),
        alvara.get("status", ""),
        alvara.get("dias_para_vencimento", ""),
    ])
    return output.getvalue()


def gerar_csv_alvaras(alvaras_com_kpis: list[dict]) -> str:
    """Gera CSV simples a partir de lista de alvarás com KPIs (deprecado — usar streaming)."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "numero_alvara",
            "tipo_servico",
            "id_permissionario",
            "id_empresa",
            "data_inicio",
            "data_validade",
            "criado_em",
            "status",
            "dias_para_vencimento",
        ],
    )
    writer.writeheader()
    writer.writerows(alvaras_com_kpis)
    return output.getvalue()


# ==================== Recadastramento (P5.1) ==============================
#
# Recadastramento NÃO é renovação de alvará. Renovação trata do documento de
# operação (`renovar_alvara`, acima); recadastramento trata de o titular
# continuar elegível. Um permissionário pode ter alvará válido e estar em
# falta com o recadastramento.
#
# Spec: docs/superpowers/specs/2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md

from sqlalchemy import or_ as _or
from sqlalchemy.exc import IntegrityError as _IntegrityError

from ..models import RecadastramentoCiclo, RecadastramentoConvocacao
from ..schemas.transporte_regulado import (
    RecadastramentoAjustePrazo,
    RecadastramentoCicloCreate,
    RecadastramentoCicloUpdate,
)

CRITERIOS_ESCALONAMENTO = ("final_documento", "sem_escalonamento")
SITUACOES_CICLO = ("rascunho", "aberto", "encerrado")
# Masculino para permissionário, feminino para empresa. Não é preciosismo de
# idioma: filtrar "ativo" nos dois convoca ZERO empresas, sem erro nenhum.
SITUACAO_PERMISSIONARIO_ATIVO = "ativo"
SITUACAO_EMPRESA_ATIVA = "ativa"
FAIXAS_ESCALONAMENTO = 10
# Colunas NOT NULL do ciclo. `observacoes` NÃO entra: ali `null` é apagar.
NAO_ANULAVEIS_DO_CICLO = (
    "nome",
    "data_inicio",
    "data_fim",
    "criterio_escalonamento",
    "situacao",
)


async def obter_ciclo(
    db: AsyncSession, *, tenant_id: int, ciclo_id: int
) -> RecadastramentoCiclo:
    """Carrega ciclo pelo id, filtrando tenant. 404 cross-tenant, não 403."""
    stmt = select(RecadastramentoCiclo).where(
        RecadastramentoCiclo.tenant_id == tenant_id,
        RecadastramentoCiclo.id == ciclo_id,
        RecadastramentoCiclo.excluido.is_(False),
    )
    ciclo = (await db.execute(stmt)).scalar_one_or_none()
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    return ciclo


async def listar_ciclos(
    db: AsyncSession,
    *,
    tenant_id: int,
    situacao: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RecadastramentoCiclo], int]:
    """Lista ciclos do tenant, janela mais recente primeiro.

    Condições montadas UMA vez e aplicadas à consulta e à contagem — duplicar
    é como `total` passa a divergir de `items`.
    """
    condicoes = [
        RecadastramentoCiclo.tenant_id == tenant_id,
        RecadastramentoCiclo.excluido.is_(False),
    ]
    if situacao:
        condicoes.append(RecadastramentoCiclo.situacao == situacao)
    termo = (q or "").strip()
    if termo:
        condicoes.append(
            func.lower(RecadastramentoCiclo.nome).like(f"%{termo.lower()}%")
        )

    stmt = (
        select(RecadastramentoCiclo)
        .where(*condicoes)
        .order_by(
            RecadastramentoCiclo.data_inicio.desc(), RecadastramentoCiclo.id.desc()
        )
    )
    count_stmt = select(func.count(RecadastramentoCiclo.id)).where(*condicoes)

    total = (await db.execute(count_stmt)).scalar_one() or 0
    itens = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return itens, total


async def _validar_nome_ciclo_unico(
    db: AsyncSession, *, tenant_id: int, nome: str, ignorar_id: int | None = None
) -> None:
    """Dois ciclos "Recadastramento 2026" no mesmo município é erro de
    digitação, não caso de uso. O índice único parcial também barra; isto aqui
    é para a mensagem ser legível em vez de um erro de integridade."""
    stmt = select(RecadastramentoCiclo.id).where(
        RecadastramentoCiclo.tenant_id == tenant_id,
        RecadastramentoCiclo.nome == nome,
        RecadastramentoCiclo.excluido.is_(False),
    )
    if ignorar_id is not None:
        stmt = stmt.where(RecadastramentoCiclo.id != ignorar_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Já existe um ciclo com esse nome neste tenant"
        )


async def criar_ciclo(
    db: AsyncSession, *, tenant_id: int, payload: RecadastramentoCicloCreate
) -> RecadastramentoCiclo:
    """Cria ciclo em `rascunho`. A situação não vem do payload."""
    await _validar_nome_ciclo_unico(db, tenant_id=tenant_id, nome=payload.nome)
    ciclo = RecadastramentoCiclo(
        tenant_id=tenant_id,
        situacao="rascunho",
        criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(ciclo)
    await db.commit()
    await db.refresh(ciclo)
    return ciclo


async def atualizar_ciclo(
    db: AsyncSession,
    *,
    tenant_id: int,
    ciclo_id: int,
    payload: RecadastramentoCicloUpdate,
) -> RecadastramentoCiclo:
    """Atualiza ciclo.

    Mudar a janela NÃO remarca convocações já geradas (§8 da spec): remarcar em
    massa prazo já comunicado é decisão de produto, e a alternativa silenciosa
    — mudar sem avisar — é a pior das duas.
    """
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    dados = payload.model_dump(exclude_unset=True)

    # `null` explícito nas colunas NOT NULL é descartado, não gravado. Todo
    # campo do `Update` é opcional para permitir PATCH parcial, então nada
    # impede o cliente de mandar `{"nome": null}` — e `setattr` fiel ao payload
    # levaria a um IntegrityError, ou seja, HTTP 500 num erro de entrada.
    # `observacoes` fica de fora da lista: ali o `null` é apagar de propósito.
    for coluna in NAO_ANULAVEIS_DO_CICLO:
        if coluna in dados and dados[coluna] is None:
            del dados[coluna]

    if dados.get("nome") and dados["nome"] != ciclo.nome:
        await _validar_nome_ciclo_unico(
            db, tenant_id=tenant_id, nome=dados["nome"], ignorar_id=ciclo_id
        )

    # A janela é confrontada com o VALOR GRAVADO quando só uma das datas vem no
    # payload. O validador do schema enxerga apenas o que foi enviado: mandar
    # só `data_fim`, anterior ao `data_inicio` já persistido, passaria por ele.
    inicio = dados.get("data_inicio") or ciclo.data_inicio
    fim = dados.get("data_fim") or ciclo.data_fim
    if inicio and fim and inicio > fim:
        raise HTTPException(
            status_code=400, detail="data_inicio não pode ser posterior a data_fim"
        )

    for chave, valor in dados.items():
        setattr(ciclo, chave, valor)
    ciclo.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(ciclo)
    return ciclo


async def excluir_ciclo(db: AsyncSession, *, tenant_id: int, ciclo_id: int) -> None:
    """Soft-delete do ciclo. As convocações continuam no banco — apagá-las
    esconderia que aquelas pessoas foram convocadas."""
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    ciclo.excluido = True
    ciclo.atualizado_em = datetime.utcnow()
    await db.commit()


def prazo_do_regulado(documento: str | None, ciclo: RecadastramentoCiclo) -> date_class:
    """Prazo individual do regulado dentro da janela do ciclo. Função pura.

    `final_documento`: o último CARACTERE do CPF/CNPJ escolhe uma de dez faixas
    iguais em `[data_inicio, data_fim]`; o prazo é o FIM da faixa. Caractere não
    numérico — a base vinda do legado costuma ter cadastro sujo — cai na faixa
    final, em vez de derrubar a geração inteira por causa de um registro.

    `sem_escalonamento`: todos recebem `data_fim`.

    Faixa vazia é aceitável: se ninguém termina em 7, ninguém tem aquele prazo.
    Redistribuir tornaria o prazo de cada um dependente da composição da base, e
    o recálculo mudaria prazo já comunicado.
    """
    if ciclo.criterio_escalonamento != "final_documento":
        return ciclo.data_fim

    texto = (documento or "").strip()
    ultimo = texto[-1] if texto else ""
    if not ultimo.isdigit():
        return ciclo.data_fim

    faixa = int(ultimo)
    total_dias = (ciclo.data_fim - ciclo.data_inicio).days
    # Fim da faixa, com a última caindo exatamente em `data_fim`.
    dias = ((faixa + 1) * total_dias) // FAIXAS_ESCALONAMENTO
    return ciclo.data_inicio + timedelta(days=dias)


def _validar_vinculo_exclusivo(
    id_permissionario: int | None, id_empresa: int | None
) -> None:
    """Exatamente um dos dois. Diferente do `Alvara`, que aceita "ao menos um".

    O banco também tem o CHECK `ck_recadconv_vinculo_exclusivo`; esta validação
    existe pela mensagem, não no lugar dele.
    """
    if bool(id_permissionario) == bool(id_empresa):
        raise HTTPException(
            status_code=400,
            detail=(
                "Convocação deve ter exatamente um vínculo: "
                "permissionário OU empresa"
            ),
        )


async def gerar_convocacoes(
    db: AsyncSession, *, tenant_id: int, ciclo_id: int
) -> dict[str, int]:
    """Convoca todo regulado ativo ainda sem convocação neste ciclo.

    **Idempotente por desenho.** Rodar de novo alcança quem foi cadastrado
    depois do primeiro disparo — que é o caso real — sem duplicar nem remarcar
    quem já tem prazo. A garantia final é o índice único parcial no banco, não
    esta consulta: duas execuções concorrentes passariam as duas pela checagem.

    Devolve `criadas` e `ja_existentes`. Um `0/0` diz ao operador que não há
    regulado ativo, o que é diferente de "funcionou".

    Não remove convocação de quem deixou de ser ativo depois de convocado:
    apagar a linha esconderia que a pessoa foi convocada. P5.3 decide o destino
    desses casos.
    """
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não gera convocações"
        )

    convocados = (
        await db.execute(
            select(
                RecadastramentoConvocacao.id_permissionario,
                RecadastramentoConvocacao.id_empresa,
            ).where(
                RecadastramentoConvocacao.tenant_id == tenant_id,
                RecadastramentoConvocacao.id_ciclo == ciclo_id,
                RecadastramentoConvocacao.excluido.is_(False),
            )
        )
    ).all()
    perms_convocados = {linha[0] for linha in convocados if linha[0] is not None}
    empresas_convocadas = {linha[1] for linha in convocados if linha[1] is not None}

    permissionarios = (
        await db.execute(
            select(Permissionario.id, Permissionario.cpf).where(
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
                # Masculino. Ver SITUACAO_PERMISSIONARIO_ATIVO.
                Permissionario.situacao == SITUACAO_PERMISSIONARIO_ATIVO,
            )
        )
    ).all()
    empresas = (
        await db.execute(
            select(Empresa.id, Empresa.cnpj).where(
                Empresa.tenant_id == tenant_id,
                Empresa.excluido.is_(False),
                # Feminino. Ver SITUACAO_EMPRESA_ATIVA.
                Empresa.situacao == SITUACAO_EMPRESA_ATIVA,
            )
        )
    ).all()

    agora = datetime.utcnow()
    criadas = 0
    ja_existentes = 0

    for perm_id, cpf in permissionarios:
        if perm_id in perms_convocados:
            ja_existentes += 1
            continue
        prazo = prazo_do_regulado(cpf, ciclo)
        db.add(
            RecadastramentoConvocacao(
                tenant_id=tenant_id,
                id_ciclo=ciclo_id,
                id_permissionario=perm_id,
                prazo=prazo,
                prazo_original=prazo,
                situacao="convocado",
                criado_em=agora,
            )
        )
        criadas += 1

    for empresa_id, cnpj in empresas:
        if empresa_id in empresas_convocadas:
            ja_existentes += 1
            continue
        prazo = prazo_do_regulado(cnpj, ciclo)
        db.add(
            RecadastramentoConvocacao(
                tenant_id=tenant_id,
                id_ciclo=ciclo_id,
                id_empresa=empresa_id,
                prazo=prazo,
                prazo_original=prazo,
                situacao="convocado",
                criado_em=agora,
            )
        )
        criadas += 1

    try:
        await db.commit()
    except _IntegrityError:
        # O índice único recusou: outra geração do mesmo ciclo correu junto.
        # 409 é honesto — rodar de novo resolve, e a segunda passada verá tudo
        # como `ja_existentes`.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Geração concorrente detectada; "
                "rode novamente para conferir o resultado"
            ),
        )

    return {"criadas": criadas, "ja_existentes": ja_existentes}


async def obter_convocacao(
    db: AsyncSession, *, tenant_id: int, convocacao_id: int
) -> RecadastramentoConvocacao:
    """Carrega convocação pelo id, filtrando tenant. 404 cross-tenant."""
    stmt = select(RecadastramentoConvocacao).where(
        RecadastramentoConvocacao.tenant_id == tenant_id,
        RecadastramentoConvocacao.id == convocacao_id,
        RecadastramentoConvocacao.excluido.is_(False),
    )
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Convocação não encontrada")
    return conv


async def listar_convocacoes(
    db: AsyncSession,
    *,
    tenant_id: int,
    ciclo_id: int,
    tipo: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Convocados de um ciclo, com o nome do regulado já resolvido.

    Devolve dicionários, e não entidades, porque a tela precisa do nome — que
    mora em duas tabelas diferentes conforme o tipo de regulado. Resolver isso
    no router custaria uma consulta por linha.

    `tipo` aceita `permissionario` ou `empresa`. `q` casa nome do permissionário
    OU razão social da empresa. Busca e paginação no SERVIDOR: a fatia anterior
    consertou exatamente o defeito de filtrar no cliente sobre lista truncada,
    em que a tela afirmava que um registro não existia.
    """
    await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)

    condicoes = [
        RecadastramentoConvocacao.tenant_id == tenant_id,
        RecadastramentoConvocacao.id_ciclo == ciclo_id,
        RecadastramentoConvocacao.excluido.is_(False),
    ]
    if tipo == "permissionario":
        condicoes.append(RecadastramentoConvocacao.id_permissionario.isnot(None))
    elif tipo == "empresa":
        condicoes.append(RecadastramentoConvocacao.id_empresa.isnot(None))
    termo = (q or "").strip()
    if termo:
        alvo = f"%{termo.lower()}%"
        condicoes.append(
            _or(
                func.lower(Permissionario.nome).like(alvo),
                func.lower(Empresa.razao_social).like(alvo),
            )
        )

    def _com_joins(stmt):
        """Os dois LEFT JOIN são idênticos na consulta e na contagem. Montados
        aqui uma vez pelo mesmo motivo das condições: divergir faz `total`
        deixar de bater com `items`."""
        return stmt.outerjoin(
            Permissionario,
            Permissionario.id == RecadastramentoConvocacao.id_permissionario,
        ).outerjoin(Empresa, Empresa.id == RecadastramentoConvocacao.id_empresa)

    base = _com_joins(
        select(RecadastramentoConvocacao, Permissionario.nome, Empresa.razao_social)
    ).where(*condicoes)
    count_stmt = _com_joins(
        select(func.count(RecadastramentoConvocacao.id))
    ).where(*condicoes)

    total = (await db.execute(count_stmt)).scalar_one() or 0
    linhas = (
        await db.execute(
            base.order_by(
                RecadastramentoConvocacao.prazo.asc(),
                RecadastramentoConvocacao.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()

    itens: list[dict] = []
    for conv, nome_perm, razao_social in linhas:
        itens.append(
            {
                "id": conv.id,
                "id_ciclo": conv.id_ciclo,
                "id_permissionario": conv.id_permissionario,
                "id_empresa": conv.id_empresa,
                "tipo_regulado": (
                    "permissionario" if conv.id_permissionario else "empresa"
                ),
                "nome_regulado": nome_perm or razao_social or "",
                "prazo": conv.prazo,
                "prazo_original": conv.prazo_original,
                "ajustado": conv.ajustado_em is not None,
                "ajuste_justificativa": conv.ajuste_justificativa,
                "ajustado_por": conv.ajustado_por,
                "ajustado_em": conv.ajustado_em,
                "situacao": conv.situacao,
                "criado_em": conv.criado_em,
            }
        )
    return itens, total


async def ajustar_prazo(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    payload: RecadastramentoAjustePrazo,
    usuario_id: int | None = None,
) -> RecadastramentoConvocacao:
    """Ajuste individual de prazo, com justificativa obrigatória.

    `prazo_original` é preservado: sem ele não dá para saber do que o ajuste se
    afastou. Prazo no PASSADO é permitido — regularizar alguém retroativamente
    é caso real de balcão. Fora da janela do ciclo é 400; ciclo encerrado, 409.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)

    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita ajuste de prazo"
        )

    justificativa = (payload.justificativa or "").strip()
    if not justificativa:
        raise HTTPException(status_code=400, detail="Justificativa é obrigatória")

    if not (ciclo.data_inicio <= payload.prazo <= ciclo.data_fim):
        raise HTTPException(status_code=400, detail="Prazo fora da janela do ciclo")

    conv.prazo = payload.prazo
    conv.ajuste_justificativa = justificativa
    conv.ajustado_por = usuario_id
    conv.ajustado_em = datetime.utcnow()
    conv.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(conv)
    return conv
