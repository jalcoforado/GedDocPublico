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
from sqlalchemy import select, func, case, or_
from sqlalchemy.sql import literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Empresa,
    Linha,
    LinhaHorario,
    LinhaParada,
    Permissionario,
    Ponto,
    PontoOcupacao,
    VeiculoRegulado,
    Usuario,
)
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
    PontoCreate,
    PontoUpdate,
    PontoOcuparInput,
    PontoLiberarInput,
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
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Permissionario], int]:
    """Lista permissionários, com busca por nome ou CPF.

    `q` entrou pela P6: o seletor de ocupante de vaga precisa achar quem está
    além dos 50 primeiros, e sem busca no servidor a tela seria inutilizável em
    município com cadastro grande.

    As condições passaram a ser montadas UMA vez. Antes eram escritas duas — na
    consulta e na contagem — e é assim que `total` diverge de `items` quando
    alguém acrescenta filtro a só uma das cópias. Aconteceu na busca de
    alvarás; acrescentar `q` sobre a duplicação teria repetido o defeito.
    """
    condicoes = [
        Permissionario.tenant_id == tenant_id,
        Permissionario.excluido.is_(False),
    ]
    if situacao is not None:
        condicoes.append(Permissionario.situacao == situacao)
    if tipo_servico is not None:
        condicoes.append(Permissionario.tipo_servico == tipo_servico)
    termo = (q or "").strip()
    if termo:
        # Nome OU CPF: no balcão se digita um ou outro, e o CPF é o que o
        # atendente tem no documento em mãos.
        condicoes.append(
            _or(
                func.lower(Permissionario.nome).like(f"%{termo.lower()}%"),
                Permissionario.cpf.like(f"%{termo}%"),
            )
        )

    total = (
        await db.execute(select(func.count(Permissionario.id)).where(*condicoes))
    ).scalar_one() or 0
    resultado = list(
        (
            await db.execute(
                select(Permissionario)
                .where(*condicoes)
                .order_by(Permissionario.nome)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
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


async def nome_do_regulado(
    db: AsyncSession, *, tenant_id: int, conv: RecadastramentoConvocacao
) -> str:
    """Nome do regulado de uma convocação — `permissionario.nome` ou
    `empresa.razao_social`, conforme o vínculo.

    Existe para que o ajuste de prazo devolva a mesma forma que a listagem.
    Devolver `""` num campo tipado como `str` seria mentira barata: a tela
    passaria a depender de recarregar a lista para exibir o nome.
    """
    if conv.id_permissionario:
        nome = (
            await db.execute(
                select(Permissionario.nome).where(
                    Permissionario.tenant_id == tenant_id,
                    Permissionario.id == conv.id_permissionario,
                )
            )
        ).scalar_one_or_none()
    else:
        nome = (
            await db.execute(
                select(Empresa.razao_social).where(
                    Empresa.tenant_id == tenant_id,
                    Empresa.id == conv.id_empresa,
                )
            )
        ).scalar_one_or_none()
    return nome or ""


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


# ============ Recadastramento — atendimento e fechamento (P5.2) ============
#
# A P5.1 entregou "quem tem de vir e quando". Esta parte entrega "atender e
# fechar": conferir documentos item a item, confrontar as vistorias dos
# veículos, e deferir ou indeferir com parecer.
#
# Spec: docs/superpowers/specs/2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md

from sqlalchemy import and_ as _and

from ..models import (
    RecadastramentoDecisao,
    RecadastramentoItem,
    RecadastramentoMarca,
    RecadastramentoNotificacao,
)
from . import notificacoes as notificacoes_svc
from ..schemas.transporte_regulado import (
    RecadastramentoDecisaoInput,
    RecadastramentoItemCreate,
    RecadastramentoItemUpdate,
    RecadastramentoMarcarInput,
)

APLICA_A_VALIDOS = ("permissionario", "empresa", "ambos")
# Vocabulário de `recadastramento_decisao.tipo`, espelhando o CHECK da 0083.
# `suspensao` e `reativacao` entraram na P5.3 em vez de uma entidade própria de
# recurso: a trilha é uma só e cronológica.
TIPOS_DECISAO = (
    "deferimento",
    "indeferimento",
    "reabertura",
    "suspensao",
    "reativacao",
)
# Colunas NOT NULL do item. Mesma razão de `NAO_ANULAVEIS_DO_CICLO`: todo campo
# do `Update` é opcional, então `{"descricao": null}` chega, e gravá-lo seria
# IntegrityError — HTTP 500 num erro de ENTRADA.
NAO_ANULAVEIS_DO_ITEM = ("descricao", "aplica_a", "obrigatorio", "ordem", "ativo")
# Situações da convocação em que ainda cabe mexer no checklist.
SITUACOES_ABERTAS = ("convocado", "em_analise")
# P5.3. Fica aqui, junto de SITUACOES_ABERTAS, porque é a ausência dela nessa
# tupla que faz a suspensão bloquear checklist e decisão — as duas constantes
# só fazem sentido lado a lado.
SITUACAO_SUSPENSO = "suspenso"
# `condicional` NÃO entra. É o valor que parece aprovado e não é; aceitá-lo
# seria decisão de produto, não detalhe de implementação.
RESULTADO_VISTORIA_ACEITO = "aprovado"


# ------------------------------------------------------------------ catálogo


async def obter_item_recadastramento(
    db: AsyncSession, *, tenant_id: int, item_id: int
) -> RecadastramentoItem:
    stmt = select(RecadastramentoItem).where(
        RecadastramentoItem.tenant_id == tenant_id,
        RecadastramentoItem.id == item_id,
        RecadastramentoItem.excluido.is_(False),
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item de recadastramento não encontrado")
    return item


async def listar_itens_recadastramento(
    db: AsyncSession,
    *,
    tenant_id: int,
    apenas_ativos: bool = False,
    aplica_a: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RecadastramentoItem], int]:
    """Catálogo do tenant, na ordem em que a tela deve exibir.

    Condições montadas UMA vez para consulta e contagem — duplicar é como
    `total` passa a divergir de `items`.
    """
    condicoes = [
        RecadastramentoItem.tenant_id == tenant_id,
        RecadastramentoItem.excluido.is_(False),
    ]
    if apenas_ativos:
        condicoes.append(RecadastramentoItem.ativo.is_(True))
    if aplica_a:
        condicoes.append(RecadastramentoItem.aplica_a == aplica_a)
    termo = (q or "").strip()
    if termo:
        condicoes.append(
            func.lower(RecadastramentoItem.descricao).like(f"%{termo.lower()}%")
        )

    stmt = (
        select(RecadastramentoItem)
        .where(*condicoes)
        .order_by(RecadastramentoItem.ordem.asc(), RecadastramentoItem.id.asc())
    )
    count_stmt = select(func.count(RecadastramentoItem.id)).where(*condicoes)

    total = (await db.execute(count_stmt)).scalar_one() or 0
    itens = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return itens, total


async def _validar_descricao_item_unica(
    db: AsyncSession, *, tenant_id: int, descricao: str, ignorar_id: int | None = None
) -> None:
    """O índice único parcial também barra; isto existe para a mensagem ser
    legível em vez de um erro de integridade."""
    stmt = select(RecadastramentoItem.id).where(
        RecadastramentoItem.tenant_id == tenant_id,
        RecadastramentoItem.descricao == descricao,
        RecadastramentoItem.excluido.is_(False),
    )
    if ignorar_id is not None:
        stmt = stmt.where(RecadastramentoItem.id != ignorar_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Já existe um item com essa descrição neste tenant"
        )


async def criar_item_recadastramento(
    db: AsyncSession, *, tenant_id: int, payload: RecadastramentoItemCreate
) -> RecadastramentoItem:
    await _validar_descricao_item_unica(
        db, tenant_id=tenant_id, descricao=payload.descricao
    )
    item = RecadastramentoItem(
        tenant_id=tenant_id, criado_em=datetime.utcnow(), **payload.model_dump()
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def atualizar_item_recadastramento(
    db: AsyncSession, *, tenant_id: int, item_id: int, payload: RecadastramentoItemUpdate
) -> RecadastramentoItem:
    """Atualiza item do catálogo.

    Editar a `descricao` muda o texto exibido também em fechamentos antigos —
    limite conhecido, registrado na §8 da spec.
    """
    item = await obter_item_recadastramento(db, tenant_id=tenant_id, item_id=item_id)
    dados = payload.model_dump(exclude_unset=True)

    for coluna in NAO_ANULAVEIS_DO_ITEM:
        if coluna in dados and dados[coluna] is None:
            del dados[coluna]

    if dados.get("descricao") and dados["descricao"] != item.descricao:
        await _validar_descricao_item_unica(
            db, tenant_id=tenant_id, descricao=dados["descricao"], ignorar_id=item_id
        )

    for chave, valor in dados.items():
        setattr(item, chave, valor)
    item.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return item


async def excluir_item_recadastramento(
    db: AsyncSession, *, tenant_id: int, item_id: int
) -> None:
    """Soft-delete. As marcas continuam no banco: apagá-las reescreveria
    fechamentos passados."""
    item = await obter_item_recadastramento(db, tenant_id=tenant_id, item_id=item_id)
    item.excluido = True
    item.atualizado_em = datetime.utcnow()
    await db.commit()


def tipo_do_regulado(conv: RecadastramentoConvocacao) -> str:
    """`permissionario` ou `empresa`, pelo vínculo. Função pura."""
    return "permissionario" if conv.id_permissionario else "empresa"


async def itens_aplicaveis(
    db: AsyncSession, *, tenant_id: int, tipo_regulado: str
) -> list[RecadastramentoItem]:
    """Itens ativos que valem para aquele tipo de regulado.

    `aplica_a IN (tipo, 'ambos')` — e não `== tipo`. Trocar por igualdade faz
    todo item `ambos` sumir da ficha, o que é uma tela vazia sem erro nenhum.
    """
    stmt = (
        select(RecadastramentoItem)
        .where(
            RecadastramentoItem.tenant_id == tenant_id,
            RecadastramentoItem.excluido.is_(False),
            RecadastramentoItem.ativo.is_(True),
            RecadastramentoItem.aplica_a.in_([tipo_regulado, "ambos"]),
        )
        .order_by(RecadastramentoItem.ordem.asc(), RecadastramentoItem.id.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


# ------------------------------------------------------------------- marcas


async def marcar_item_recadastramento(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    item_id: int,
    payload: RecadastramentoMarcarInput,
    usuario_id: int | None = None,
) -> RecadastramentoMarca:
    """Registra uma marcação. **Sempre INSERE**, nunca atualiza.

    A tabela é um log: marcar, desmarcar e marcar de novo são três linhas, e o
    estado corrente é a mais recente. Sobrescrever apagaria o rastro de quem
    voltou atrás — que é exatamente o que se quer auditar num balcão.

    Recusa (409) ciclo encerrado e convocação já decidida: mexer no checklist
    depois do parecer mudaria a base da decisão sem mudar a decisão.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita marcação de checklist"
        )
    if conv.situacao not in SITUACOES_ABERTAS:
        raise HTTPException(
            status_code=409,
            detail=(
                # A suspensão da P5.3 entrou fora de SITUACOES_ABERTAS, então
                # cai aqui de graça — mas a mensagem antiga mandaria reabrir, e
                # para suspensa o caminho é REATIVAR. Mensagem que aponta a
                # porta errada custa um chamado de suporte por ocorrência.
                "Convocação suspensa; reative antes de alterar o checklist"
                if conv.situacao == SITUACAO_SUSPENSO
                else "Convocação já decidida; reabra antes de alterar o checklist"
            ),
        )

    item = await obter_item_recadastramento(db, tenant_id=tenant_id, item_id=item_id)
    aplicaveis = {i.id for i in await itens_aplicaveis(
        db, tenant_id=tenant_id, tipo_regulado=tipo_do_regulado(conv)
    )}
    if item.id not in aplicaveis:
        raise HTTPException(
            status_code=400,
            detail="Item não se aplica a este regulado, ou está inativo",
        )

    marca = RecadastramentoMarca(
        tenant_id=tenant_id,
        id_convocacao=convocacao_id,
        id_item=item_id,
        marcado=payload.marcado,
        observacao=payload.observacao,
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(marca)

    # A primeira marcação tira a convocação de `convocado`. Gravado, e não
    # derivado: derivar exigiria subconsulta por linha na listagem, e a P5.3
    # vai filtrar por este campo no relatório.
    if conv.situacao == "convocado":
        conv.situacao = "em_analise"
        conv.atualizado_em = datetime.utcnow()

    await db.commit()
    await db.refresh(marca)
    return marca


async def estado_do_checklist(
    db: AsyncSession, *, tenant_id: int, convocacao_id: int
) -> list[dict]:
    """Itens aplicáveis com o estado corrente resolvido.

    O estado é a marca **mais recente** do par, e o desempate é por `id` além
    de `criado_em`: duas marcações no mesmo segundo são perfeitamente possíveis
    num balcão, e ordenar só por tempo devolveria qualquer uma das duas.

    `marcado is None` significa item nunca tocado — diferente de `False`, que é
    a decisão registrada de que o documento não está em ordem.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    itens = await itens_aplicaveis(
        db, tenant_id=tenant_id, tipo_regulado=tipo_do_regulado(conv)
    )
    if not itens:
        return []

    marcas = (
        await db.execute(
            select(RecadastramentoMarca)
            .where(
                RecadastramentoMarca.tenant_id == tenant_id,
                RecadastramentoMarca.id_convocacao == convocacao_id,
            )
            .order_by(
                RecadastramentoMarca.criado_em.asc(), RecadastramentoMarca.id.asc()
            )
        )
    ).scalars().all()
    # Percorrer em ordem CRESCENTE e sobrescrever deixa a última — a mais
    # recente — no dicionário. Menos sutil que confiar num `DISTINCT ON`.
    ultima_por_item: dict[int, RecadastramentoMarca] = {}
    for m in marcas:
        ultima_por_item[m.id_item] = m

    resultado: list[dict] = []
    for item in itens:
        m = ultima_por_item.get(item.id)
        resultado.append(
            {
                "id_item": item.id,
                "descricao": item.descricao,
                "aplica_a": item.aplica_a,
                "obrigatorio": item.obrigatorio,
                "ordem": item.ordem,
                "marcado": None if m is None else m.marcado,
                "observacao": None if m is None else m.observacao,
                "marcado_por": None if m is None else m.id_usuario,
                "marcado_em": None if m is None else m.criado_em,
            }
        )
    return resultado


# ------------------------------------------------------- amarra da vistoria


async def situacao_vistorias(
    db: AsyncSession, *, tenant_id: int, conv: RecadastramentoConvocacao
) -> dict:
    """Situação das vistorias dos veículos do regulado.

    Devolve TRÊS coisas, e não um booleano, porque a tela precisa distinguir
    "todos em dia" de "nenhum veículo cadastrado" (assunção A1 da spec): as
    duas satisfazem a regra e não significam a mesma coisa. Colapsá-las num
    selo verde esconderia cadastro incompleto.

    Vistoria conta se `resultado == "aprovado"`, não excluída, e `data_validade`
    nula OU no futuro (assunção A2: cadastro herdado costuma não ter validade,
    e bloquear por ausência de dado puniria o regulado por falha do município).

    A referência é HOJE, não o prazo da convocação — quem decide é o servidor,
    no dia em que decide.
    """
    condicoes_veiculo = [
        VeiculoRegulado.tenant_id == tenant_id,
        VeiculoRegulado.excluido.is_(False),
        # Masculino: `VeiculoReguladoSituacao` usa `ativo`, como permissionário.
        VeiculoRegulado.situacao == SITUACAO_PERMISSIONARIO_ATIVO,
    ]
    if conv.id_permissionario:
        condicoes_veiculo.append(
            VeiculoRegulado.id_permissionario == conv.id_permissionario
        )
    else:
        condicoes_veiculo.append(VeiculoRegulado.id_empresa == conv.id_empresa)

    veiculos = (
        await db.execute(
            select(VeiculoRegulado.id, VeiculoRegulado.placa).where(*condicoes_veiculo)
        )
    ).all()

    hoje = date_class.today()
    pendentes: list[dict] = []
    for veiculo_id, placa in veiculos:
        vistoria_ok = (
            await db.execute(
                select(VeiculoVistoria.id).where(
                    VeiculoVistoria.tenant_id == tenant_id,
                    VeiculoVistoria.id_veiculo == veiculo_id,
                    VeiculoVistoria.excluido.is_(False),
                    VeiculoVistoria.resultado == RESULTADO_VISTORIA_ACEITO,
                    _or(
                        VeiculoVistoria.data_validade.is_(None),
                        VeiculoVistoria.data_validade >= hoje,
                    ),
                )
            )
        ).scalar_one_or_none()
        if vistoria_ok is None:
            pendentes.append(
                {
                    "id_veiculo": veiculo_id,
                    "placa": placa,
                    "motivo": "sem vistoria aprovada válida",
                }
            )

    return {
        # Zero veículos ativos satisfaz por vacuidade (A1) — e o chamador
        # enxerga isso por `total_veiculos_ativos == 0`.
        "satisfeita": not pendentes,
        "total_veiculos_ativos": len(veiculos),
        "pendentes": pendentes,
    }


# ------------------------------------------------------------------ decisão


async def situacao_atendimento(
    db: AsyncSession, *, tenant_id: int, convocacao_id: int
) -> dict:
    """Tudo que a tela precisa para desenhar a ficha e explicar o botão.

    `pode_deferir` vem acompanhado do PORQUÊ (`itens_obrigatorios_pendentes` e
    `vistorias`): um booleano sozinho vira botão desabilitado sem explicação, e
    o servidor não descobre o que falta.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    itens = await estado_do_checklist(
        db, tenant_id=tenant_id, convocacao_id=convocacao_id
    )
    vistorias = await situacao_vistorias(db, tenant_id=tenant_id, conv=conv)
    pendentes = [
        i["descricao"] for i in itens if i["obrigatorio"] and i["marcado"] is not True
    ]
    return {
        "id_convocacao": conv.id,
        "situacao": conv.situacao,
        # P5.3: a ficha não mostrava o prazo, numa tela que existe por causa
        # dele. Além de informação que faltava ao atendente, é o que permite à
        # tela só oferecer "Suspender" depois do vencimento, em vez de oferecer
        # sempre e deixar o operador colher 409.
        "prazo": conv.prazo,
        "em_atraso": esta_em_atraso(conv, date_class.today()),
        "tipo_regulado": tipo_do_regulado(conv),
        "nome_regulado": await nome_do_regulado(db, tenant_id=tenant_id, conv=conv),
        "itens": itens,
        "itens_obrigatorios_pendentes": pendentes,
        "vistorias": vistorias,
        "pode_deferir": not pendentes and vistorias["satisfeita"],
    }


async def decidir_recadastramento(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    tipo: str,
    payload: RecadastramentoDecisaoInput,
    usuario_id: int,
) -> RecadastramentoDecisao:
    """Defere ou indefere uma convocação, com parecer.

    **A assimetria central desta fatia: deferir exige completude; indeferir
    não.** Indeferir por falta de documento é o caso real do balcão; um sistema
    que exigisse completude para indeferir só saberia dizer sim.
    """
    if tipo not in ("deferimento", "indeferimento"):
        raise HTTPException(status_code=400, detail="Tipo de decisão inválido")

    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita decisão"
        )
    if conv.situacao not in SITUACOES_ABERTAS:
        raise HTTPException(
            status_code=409,
            detail=(
                "Convocação suspensa; reative antes de decidir"
                if conv.situacao == SITUACAO_SUSPENSO
                else "Convocação já decidida; reabra antes de decidir"
            ),
        )

    parecer = (payload.parecer or "").strip()
    if not parecer:
        raise HTTPException(status_code=400, detail="Parecer é obrigatório")

    if tipo == "deferimento":
        situacao = await situacao_atendimento(
            db, tenant_id=tenant_id, convocacao_id=convocacao_id
        )
        if not situacao["pode_deferir"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Deferimento exige checklist obrigatório completo e vistorias "
                    "em dia"
                ),
            )

    decisao = RecadastramentoDecisao(
        tenant_id=tenant_id,
        id_convocacao=convocacao_id,
        tipo=tipo,
        parecer=parecer,
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(decisao)
    conv.situacao = "deferido" if tipo == "deferimento" else "indeferido"
    conv.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(decisao)
    return decisao


async def reabrir_recadastramento(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario_id: int,
) -> RecadastramentoDecisao:
    """Volta a convocação para `em_analise`, preservando as decisões anteriores.

    Existe para que um deferimento errado não vire dívida de SQL: fechamento
    sem desfazer, em sistema municipal, acaba em `UPDATE` manual no banco de
    produção.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita reabertura"
        )
    if conv.situacao not in ("deferido", "indeferido"):
        raise HTTPException(
            status_code=409,
            detail=(
                # Reabertura e reativação não são portas alternativas para o
                # mesmo estado: uma suspensão desfeita por "reabertura" ficaria
                # indistinguível de um indeferimento desfeito na trilha.
                "Convocação suspensa: use reativar, não reabrir"
                if conv.situacao == SITUACAO_SUSPENSO
                else "Só convocação decidida pode ser reaberta"
            ),
        )

    parecer = (payload.parecer or "").strip()
    if not parecer:
        raise HTTPException(status_code=400, detail="Parecer é obrigatório")

    decisao = RecadastramentoDecisao(
        tenant_id=tenant_id,
        id_convocacao=convocacao_id,
        tipo="reabertura",
        parecer=parecer,
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(decisao)
    conv.situacao = "em_analise"
    conv.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(decisao)
    return decisao


async def listar_decisoes(
    db: AsyncSession, *, tenant_id: int, convocacao_id: int
) -> list[RecadastramentoDecisao]:
    """Histórico completo, mais antigo primeiro. É o que torna a reabertura
    auditável: sem ele, reabrir pareceria não ter acontecido."""
    await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    stmt = (
        select(RecadastramentoDecisao)
        .where(
            RecadastramentoDecisao.tenant_id == tenant_id,
            RecadastramentoDecisao.id_convocacao == convocacao_id,
        )
        .order_by(RecadastramentoDecisao.criado_em.asc(), RecadastramentoDecisao.id.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


# ==========================================================================
# P5.3 — atraso, faltosos, suspensão, reativação e notificação em lote
# ==========================================================================

# Resultados possíveis de um item do lote de notificação. `sem_contato` NÃO é
# erro: `telefone` e `email` são anuláveis em Permissionario e Empresa, então
# cadastro incompleto é caso comum, não borda.
RESULTADOS_NOTIFICACAO = ("enviada", "sem_contato")


def esta_em_atraso(conv: RecadastramentoConvocacao, hoje: date_class) -> bool:
    """Atraso é DERIVADO, não coluna — esta função é a definição única.

    Persistir exigiria job diário e criaria janela em que o banco discorda do
    calendário; pior, o `ajustar_prazo` da P5.1 teria de lembrar de recalcular,
    e esquecer seria silencioso. Derivado, ajustar o prazo desfaz o atraso na
    mesma consulta.

    O que torna isso seguro é o atraso **não gatear nada**: quem perdeu o prazo
    segue podendo marcar checklist e ser deferido; só a suspensão fecha. Se um
    dia o atraso passar a bloquear, esta decisão tem de ser reexaminada.
    """
    return conv.prazo < hoje and conv.situacao in SITUACOES_ABERTAS


def _condicao_em_atraso(hoje: date_class):
    """A mesma regra de `esta_em_atraso`, em SQL.

    Duas expressões da mesma regra é exatamente o que produz teste verde e tela
    errada. Ficam lado a lado de propósito, e há teste que compara as duas sobre
    o mesmo conjunto.
    """
    return _and(
        RecadastramentoConvocacao.prazo < hoje,
        RecadastramentoConvocacao.situacao.in_(SITUACOES_ABERTAS),
    )


async def listar_faltosos(
    db: AsyncSession,
    *,
    tenant_id: int,
    ciclo_id: int,
    hoje: date_class | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Relatório de faltosos do ciclo: KPIs mais a lista dos atrasados.

    `hoje` é injetável para que o teste não dependa da data da máquina — sem
    isso, um teste de atraso passa hoje e falha amanhã, ou pior, passa sempre
    porque a data escolhida ficou longe demais.
    """
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)
    hoje = hoje or date_class.today()

    do_ciclo = [
        RecadastramentoConvocacao.tenant_id == tenant_id,
        RecadastramentoConvocacao.id_ciclo == ciclo_id,
        RecadastramentoConvocacao.excluido.is_(False),
    ]

    async def _conta(*extra) -> int:
        stmt = select(func.count(RecadastramentoConvocacao.id)).where(
            *do_ciclo, *extra
        )
        return (await db.execute(stmt)).scalar_one() or 0

    kpis = {
        "convocados": await _conta(),
        "atendidos": await _conta(
            RecadastramentoConvocacao.situacao.in_(("deferido", "indeferido"))
        ),
        "em_atraso": await _conta(_condicao_em_atraso(hoje)),
        "suspensos": await _conta(
            RecadastramentoConvocacao.situacao == SITUACAO_SUSPENSO
        ),
    }

    base = (
        select(
            RecadastramentoConvocacao,
            Permissionario.nome,
            Permissionario.cpf,
            Empresa.razao_social,
            Empresa.cnpj,
        )
        .outerjoin(
            Permissionario,
            Permissionario.id == RecadastramentoConvocacao.id_permissionario,
        )
        .outerjoin(Empresa, Empresa.id == RecadastramentoConvocacao.id_empresa)
        .where(*do_ciclo, _condicao_em_atraso(hoje))
        .order_by(
            RecadastramentoConvocacao.prazo.asc(),
            RecadastramentoConvocacao.id.asc(),
        )
    )
    linhas = (await db.execute(base.limit(limit).offset(offset))).all()

    # Última notificação só dos ids desta página. Uma subconsulta correlacionada
    # por linha custaria caro para um dado que a tela usa como coluna auxiliar.
    ids_pagina = [linha[0].id for linha in linhas]
    ultima_por_conv: dict[int, datetime] = {}
    if ids_pagina:
        notif = (
            await db.execute(
                select(
                    RecadastramentoNotificacao.id_convocacao,
                    func.max(RecadastramentoNotificacao.criado_em),
                )
                .where(
                    RecadastramentoNotificacao.tenant_id == tenant_id,
                    RecadastramentoNotificacao.id_convocacao.in_(ids_pagina),
                )
                .group_by(RecadastramentoNotificacao.id_convocacao)
            )
        ).all()
        ultima_por_conv = {cid: quando for cid, quando in notif}

    itens = []
    for conv, nome_perm, cpf, razao_social, cnpj in linhas:
        itens.append(
            {
                "id": conv.id,
                "tipo_regulado": (
                    "permissionario" if conv.id_permissionario else "empresa"
                ),
                "nome_regulado": nome_perm or razao_social or "",
                "documento": cpf or cnpj or "",
                "prazo": conv.prazo,
                "dias_atraso": (hoje - conv.prazo).days,
                "situacao": conv.situacao,
                "ultima_notificacao": ultima_por_conv.get(conv.id),
            }
        )

    return {
        "ciclo": {"id": ciclo.id, "nome": ciclo.nome, "situacao": ciclo.situacao},
        "kpis": kpis,
        "itens": itens,
        "total": kpis["em_atraso"],
    }


async def suspender_convocacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario_id: int,
    hoje: date_class | None = None,
) -> RecadastramentoDecisao:
    """Suspende a convocação de quem não recadastrou. Ato humano, com parecer.

    **Suspende só a convocação.** Não toca em `Permissionario.situacao`, em
    `Empresa.situacao` nem em alvará — decisão do Jorge em 2026-08-05. É
    reversível e não tem efeito colateral em outro módulo; o que fazer com o
    alvará de um suspenso é decisão separada.

    Exige prazo vencido. Suspender quem está dentro do prazo é erro de operação,
    não escolha do município, então vira 409 com a data na mensagem em vez de
    passar silenciosamente.
    """
    hoje = hoje or date_class.today()
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita suspensão"
        )
    if conv.situacao == SITUACAO_SUSPENSO:
        raise HTTPException(status_code=409, detail="Convocação já está suspensa")
    if conv.situacao not in SITUACOES_ABERTAS:
        raise HTTPException(
            status_code=409,
            detail="Convocação já decidida; reabra antes de suspender",
        )
    if conv.prazo >= hoje:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Prazo ainda não venceu (termina em {conv.prazo.isoformat()}); "
                "não há falta a suspender"
            ),
        )

    parecer = (payload.parecer or "").strip()
    if not parecer:
        raise HTTPException(status_code=400, detail="Parecer é obrigatório")

    decisao = RecadastramentoDecisao(
        tenant_id=tenant_id,
        id_convocacao=convocacao_id,
        tipo="suspensao",
        parecer=parecer,
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(decisao)
    conv.situacao = SITUACAO_SUSPENSO
    conv.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(decisao)
    return decisao


async def reativar_convocacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    convocacao_id: int,
    payload: RecadastramentoDecisaoInput,
    usuario_id: int,
) -> RecadastramentoDecisao:
    """Desfaz a suspensão. É o deferimento do recurso, e o parecer é o julgamento.

    Volta para `convocado`, e não para `em_analise` mesmo que estivesse em
    análise antes: reativar é recomeçar o atendimento, e inferir o estado
    anterior exigiria guardá-lo. As marcas de checklist **não** são apagadas —
    são log append-only e continuam valendo.
    """
    conv = await obter_convocacao(db, tenant_id=tenant_id, convocacao_id=convocacao_id)
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=conv.id_ciclo)
    if ciclo.situacao == "encerrado":
        raise HTTPException(
            status_code=409, detail="Ciclo encerrado não aceita reativação"
        )
    if conv.situacao != SITUACAO_SUSPENSO:
        raise HTTPException(
            status_code=409, detail="Só convocação suspensa pode ser reativada"
        )

    parecer = (payload.parecer or "").strip()
    if not parecer:
        raise HTTPException(status_code=400, detail="Parecer é obrigatório")

    decisao = RecadastramentoDecisao(
        tenant_id=tenant_id,
        id_convocacao=convocacao_id,
        tipo="reativacao",
        parecer=parecer,
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(decisao)
    conv.situacao = "convocado"
    conv.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(decisao)
    return decisao


async def _contato_do_regulado(
    db: AsyncSession, *, tenant_id: int, conv: RecadastramentoConvocacao
) -> tuple[str, str | None, str | None]:
    """(nome, email, telefone) do regulado. Os dois contatos são anuláveis."""
    if conv.id_permissionario:
        linha = (
            await db.execute(
                select(
                    Permissionario.nome, Permissionario.email, Permissionario.telefone
                ).where(
                    Permissionario.tenant_id == tenant_id,
                    Permissionario.id == conv.id_permissionario,
                )
            )
        ).first()
    else:
        linha = (
            await db.execute(
                select(
                    Empresa.razao_social, Empresa.email, Empresa.telefone
                ).where(
                    Empresa.tenant_id == tenant_id,
                    Empresa.id == conv.id_empresa,
                )
            )
        ).first()
    if not linha:
        return "", None, None
    nome, email, telefone = linha
    return (nome or ""), (email or None), (telefone or None)


async def notificar_faltosos(
    db: AsyncSession,
    *,
    tenant_id: int,
    ciclo_id: int,
    convocacao_ids: list[int],
    usuario_id: int,
) -> list[dict]:
    """Dispara aviso em lote e registra cada envio. Manual nesta fatia.

    **Um cadastro incompleto não derruba o lote.** `email` e `telefone` são
    anuláveis nos dois modelos de regulado, então faltoso sem contato é caso
    comum. Cada item volta com resultado próprio (`enviada` ou `sem_contato`) e
    a tela mostra a contagem dos dois. Falhar tudo por um cadastro sem telefone
    tornaria o recurso inutilizável no município que mais precisa dele.

    Notificar duas vezes é legítimo: o log não deduplica, e é a contagem de
    avisos que depois justifica uma suspensão.

    O motor de notificações só aplica preferência de canal quando o destinatário
    é usuário do sistema (`id_usuario`); aqui o destinatário é o regulado, então
    o envio não é filtrado por opt-out de servidor — verificado em
    `services/notificacoes.enviar`, não suposto.
    """
    ciclo = await obter_ciclo(db, tenant_id=tenant_id, ciclo_id=ciclo_id)

    resultados: list[dict] = []
    for convocacao_id in convocacao_ids:
        conv = await obter_convocacao(
            db, tenant_id=tenant_id, convocacao_id=convocacao_id
        )
        if conv.id_ciclo != ciclo_id:
            raise HTTPException(
                status_code=400,
                detail=f"Convocação {convocacao_id} não pertence a este ciclo",
            )

        nome, email, telefone = await _contato_do_regulado(
            db, tenant_id=tenant_id, conv=conv
        )
        canais = [c for c, tem in (("email", email), ("whatsapp", telefone)) if tem]
        if not canais:
            resultados.append(
                {
                    "id_convocacao": convocacao_id,
                    "nome_regulado": nome,
                    "resultado": "sem_contato",
                    "canais": [],
                }
            )
            continue

        criadas = await notificacoes_svc.enviar(
            db,
            tenant_id=tenant_id,
            destinatarios=[
                notificacoes_svc.Destinatario(email=email, telefone=telefone)
            ],
            canais=canais,
            tipo="recadastramento.faltoso",
            titulo=f"Recadastramento pendente — {ciclo.nome}",
            mensagem=(
                f"{nome}, o prazo do seu recadastramento venceu em "
                f"{conv.prazo.isoformat()}. Procure a prefeitura para regularizar."
            ),
            payload={"id_ciclo": ciclo_id, "id_convocacao": convocacao_id},
        )
        for n in criadas:
            db.add(
                RecadastramentoNotificacao(
                    tenant_id=tenant_id,
                    id_convocacao=convocacao_id,
                    id_notificacao=n.id,
                    id_usuario=usuario_id,
                    criado_em=datetime.utcnow(),
                )
            )
        resultados.append(
            {
                "id_convocacao": convocacao_id,
                "nome_regulado": nome,
                "resultado": "enviada",
                "canais": canais,
            }
        )

    # Um commit para todas as linhas de log. `enviar` já commitou as
    # notificações em si, então uma queda entre as duas coisas deixa envio sem
    # registro — buraco de log, nunca mensagem perdida nem duplicada. O
    # inverso (registrar e não enviar) seria pior.
    await db.commit()
    return resultados


# =========================================================== P6: pontos e vagas
#
# O objeto regulatório de táxi e mototáxi é o PONTO, com vagas numeradas. A
# exclusividade — uma vaga um ocupante, um permissionário uma vaga — está
# garantida por dois índices únicos parciais criados na 0084. As checagens
# abaixo existem para devolver 409 com mensagem útil, NÃO para garantir a
# regra: entre o SELECT e o INSERT de uma checagem não há nada segurando duas
# requisições concorrentes. Ver `test_o_banco_barra_sem_passar_pelo_servico`.

MOTIVOS_LIBERACAO = ("transferencia", "desistencia", "cassacao", "obito", "outro")


async def _carregar_ponto(db: AsyncSession, *, tenant_id: int, ponto_id: int) -> Ponto:
    ponto = (
        await db.execute(
            select(Ponto).where(
                Ponto.id == ponto_id,
                Ponto.tenant_id == tenant_id,
                Ponto.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ponto is None:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    return ponto


async def _validar_nome_ponto_unico(
    db: AsyncSession, *, tenant_id: int, nome: str, excluir_id: int | None = None
) -> None:
    stmt = select(Ponto.id).where(
        Ponto.tenant_id == tenant_id,
        func.lower(Ponto.nome) == nome.strip().lower(),
        Ponto.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(Ponto.id != excluir_id)
    if (await db.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um ponto chamado '{nome.strip()}'",
        )


def _ocupacao_vigente():
    """Vigente = sem `ate` e não excluída. Mesmo predicado dos índices únicos.

    Existe como função por um motivo: escrito à mão em cada consulta, mais cedo
    ou mais tarde uma delas esquece o `excluido` e passa a enxergar ocupação
    apagada. A divergência entre o que a tela mostra e o que o índice impede é
    do tipo que chega como "não consigo ocupar a vaga que está livre".
    """
    return _and(PontoOcupacao.ate.is_(None), PontoOcupacao.excluido.is_(False))


async def _contagem_ocupadas(
    db: AsyncSession, *, tenant_id: int, ponto_ids: list[int]
) -> dict[int, int]:
    if not ponto_ids:
        return {}
    linhas = (
        await db.execute(
            select(PontoOcupacao.id_ponto, func.count(PontoOcupacao.id))
            .where(
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.id_ponto.in_(ponto_ids),
                _ocupacao_vigente(),
            )
            .group_by(PontoOcupacao.id_ponto)
        )
    ).all()
    return {linha[0]: int(linha[1]) for linha in linhas}


async def listar_pontos(
    db: AsyncSession,
    *,
    tenant_id: int,
    q: str | None = None,
    tipo_servico: str | None = None,
    situacao: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Ponto, int]], int]:
    """Pontos com a contagem de vagas ocupadas de cada um.

    Condições montadas UMA vez para consulta e contagem. Duplicá-las é como
    `total` passa a divergir de `items` quando alguém acrescenta filtro a só
    uma das cópias — aconteceu na busca de alvarás.
    """
    condicoes = [Ponto.tenant_id == tenant_id, Ponto.excluido.is_(False)]
    termo = (q or "").strip()
    if termo:
        condicoes.append(func.lower(Ponto.nome).like(f"%{termo.lower()}%"))
    if tipo_servico:
        condicoes.append(Ponto.tipo_servico == tipo_servico)
    if situacao:
        condicoes.append(Ponto.situacao == situacao)

    total = (
        await db.execute(select(func.count(Ponto.id)).where(*condicoes))
    ).scalar_one() or 0
    pontos = list(
        (
            await db.execute(
                select(Ponto)
                .where(*condicoes)
                .order_by(Ponto.nome.asc(), Ponto.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    ocupadas = await _contagem_ocupadas(
        db, tenant_id=tenant_id, ponto_ids=[p.id for p in pontos]
    )
    return [(p, ocupadas.get(p.id, 0)) for p in pontos], total


async def obter_ponto(
    db: AsyncSession, *, tenant_id: int, ponto_id: int
) -> tuple[Ponto, int]:
    ponto = await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    ocupadas = await _contagem_ocupadas(db, tenant_id=tenant_id, ponto_ids=[ponto.id])
    return ponto, ocupadas.get(ponto.id, 0)


async def criar_ponto(
    db: AsyncSession, *, tenant_id: int, payload: PontoCreate
) -> Ponto:
    await _validar_nome_ponto_unico(db, tenant_id=tenant_id, nome=payload.nome)
    ponto = Ponto(
        tenant_id=tenant_id, criado_em=datetime.utcnow(), **payload.model_dump()
    )
    db.add(ponto)
    await db.flush()
    return ponto


async def atualizar_ponto(
    db: AsyncSession, *, tenant_id: int, ponto_id: int, payload: PontoUpdate
) -> Ponto:
    ponto = await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    dados = payload.model_dump(exclude_unset=True)

    if dados.get("nome"):
        await _validar_nome_ponto_unico(
            db, tenant_id=tenant_id, nome=dados["nome"], excluir_id=ponto_id
        )

    if dados.get("vagas_total") is not None:
        # Reduzir abaixo do maior número ocupado deixaria ocupação FORA do mapa
        # da tela: presente no banco, invisível na interface. Pior dos dois
        # mundos, e silencioso.
        maior = (
            await db.execute(
                select(func.max(PontoOcupacao.numero_vaga)).where(
                    PontoOcupacao.tenant_id == tenant_id,
                    PontoOcupacao.id_ponto == ponto_id,
                    _ocupacao_vigente(),
                )
            )
        ).scalar()
        if maior is not None and dados["vagas_total"] < int(maior):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Não é possível reduzir para {dados['vagas_total']} vagas: "
                    f"a vaga {int(maior)} está ocupada. Libere-a antes."
                ),
            )

    for campo, valor in dados.items():
        setattr(ponto, campo, valor)
    ponto.atualizado_em = datetime.utcnow()
    await db.flush()
    return ponto


async def excluir_ponto(db: AsyncSession, *, tenant_id: int, ponto_id: int) -> None:
    ponto = await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    vigentes = (
        await db.execute(
            select(func.count(PontoOcupacao.id)).where(
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.id_ponto == ponto_id,
                _ocupacao_vigente(),
            )
        )
    ).scalar_one() or 0
    if vigentes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O ponto tem {vigentes} vaga(s) ocupada(s). Libere-as antes de "
                "excluir, ou inative o ponto para apenas impedir novas ocupações."
            ),
        )
    ponto.excluido = True
    ponto.atualizado_em = datetime.utcnow()
    await db.flush()


def _ocupacao_dict(oc: PontoOcupacao, nome: str | None, cpf: str | None) -> dict:
    return {
        "id": oc.id,
        "id_ponto": oc.id_ponto,
        "numero_vaga": oc.numero_vaga,
        "id_permissionario": oc.id_permissionario,
        "desde": oc.desde,
        "ate": oc.ate,
        "motivo_liberacao": oc.motivo_liberacao,
        "observacoes": oc.observacoes,
        "nome_permissionario": nome,
        "cpf_permissionario": cpf,
    }


async def mapa_de_vagas(db: AsyncSession, *, tenant_id: int, ponto_id: int) -> dict:
    """As `vagas_total` vagas, livres inclusive.

    Devolver só as ocupadas obrigaria a tela a deduzir os buracos, e "a vaga 7
    sumiu" é um defeito que ninguém vê até alguém reclamar.
    """
    ponto = await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    linhas = (
        await db.execute(
            select(PontoOcupacao, Permissionario.nome, Permissionario.cpf)
            .join(Permissionario, Permissionario.id == PontoOcupacao.id_permissionario)
            .where(
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.id_ponto == ponto_id,
                _ocupacao_vigente(),
            )
        )
    ).all()
    por_vaga = {linha[0].numero_vaga: linha for linha in linhas}

    vagas = []
    for numero in range(1, ponto.vagas_total + 1):
        achado = por_vaga.get(numero)
        vagas.append(
            {
                "numero_vaga": numero,
                "ocupacao": None
                if achado is None
                else _ocupacao_dict(achado[0], achado[1], achado[2]),
            }
        )
    return {
        "id_ponto": ponto.id,
        "nome": ponto.nome,
        "situacao": ponto.situacao,
        "vagas_total": ponto.vagas_total,
        "vagas_ocupadas": len(por_vaga),
        "vagas": vagas,
    }


async def listar_ocupacoes(
    db: AsyncSession,
    *,
    tenant_id: int,
    ponto_id: int,
    apenas_vigentes: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    condicoes = [
        PontoOcupacao.tenant_id == tenant_id,
        PontoOcupacao.id_ponto == ponto_id,
        PontoOcupacao.excluido.is_(False),
    ]
    if apenas_vigentes:
        condicoes.append(PontoOcupacao.ate.is_(None))

    total = (
        await db.execute(select(func.count(PontoOcupacao.id)).where(*condicoes))
    ).scalar_one() or 0
    linhas = (
        await db.execute(
            select(PontoOcupacao, Permissionario.nome, Permissionario.cpf)
            .join(Permissionario, Permissionario.id == PontoOcupacao.id_permissionario)
            .where(*condicoes)
            .order_by(PontoOcupacao.desde.desc(), PontoOcupacao.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [_ocupacao_dict(l[0], l[1], l[2]) for l in linhas], total


async def ocupar_vaga(
    db: AsyncSession, *, tenant_id: int, ponto_id: int, payload: PontoOcuparInput
) -> PontoOcupacao:
    ponto = await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)

    if ponto.situacao != "ativo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ponto inativo não recebe novas ocupações",
        )
    if not 1 <= payload.numero_vaga <= ponto.vagas_total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Vaga {payload.numero_vaga} não existe: o ponto tem "
                f"{ponto.vagas_total} vaga(s)."
            ),
        )

    # Same-tenant explícito: a FK do Postgres não filtra por tenant, e 404
    # cross-tenant (não 403) é a regra do repositório.
    regulado = (
        await db.execute(
            select(Permissionario).where(
                Permissionario.id == payload.id_permissionario,
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if regulado is None:
        raise HTTPException(status_code=404, detail="Permissionário não encontrado")

    ocupada = (
        await db.execute(
            select(PontoOcupacao.id).where(
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.id_ponto == ponto_id,
                PontoOcupacao.numero_vaga == payload.numero_vaga,
                _ocupacao_vigente(),
            )
        )
    ).first()
    if ocupada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A vaga {payload.numero_vaga} já está ocupada",
        )

    # A mensagem diz ONDE o permissionário está. Sem isso o atendente recebe
    # "já tem vaga" e não sabe o que fazer: precisa achar o outro ponto para
    # liberar, e procurar à mão num cadastro de dezenas de pontos é o atrito
    # que faz o operador desistir do sistema.
    atual = (
        await db.execute(
            select(Ponto.nome, PontoOcupacao.numero_vaga)
            .join(Ponto, Ponto.id == PontoOcupacao.id_ponto)
            .where(
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.id_permissionario == payload.id_permissionario,
                _ocupacao_vigente(),
            )
        )
    ).first()
    if atual is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{regulado.nome} já ocupa a vaga {atual[1]} do ponto "
                f"'{atual[0]}'. Libere-a antes."
            ),
        )

    ocupacao = PontoOcupacao(
        tenant_id=tenant_id,
        id_ponto=ponto_id,
        numero_vaga=payload.numero_vaga,
        id_permissionario=payload.id_permissionario,
        desde=payload.desde or date_class.today(),
        observacoes=payload.observacoes,
        criado_em=datetime.utcnow(),
    )
    db.add(ocupacao)
    await db.flush()
    return ocupacao


async def liberar_vaga(
    db: AsyncSession,
    *,
    tenant_id: int,
    ponto_id: int,
    ocupacao_id: int,
    payload: PontoLiberarInput,
) -> PontoOcupacao:
    """Encerra a vigência. NÃO apaga a linha — o histórico é o produto.

    Em disputa de ponto, "quem estava na vaga 3 em março" é exatamente a
    pergunta que se faz, e um DELETE aqui deixaria o município sem resposta.
    """
    await _carregar_ponto(db, tenant_id=tenant_id, ponto_id=ponto_id)
    ocupacao = (
        await db.execute(
            select(PontoOcupacao).where(
                PontoOcupacao.id == ocupacao_id,
                PontoOcupacao.id_ponto == ponto_id,
                PontoOcupacao.tenant_id == tenant_id,
                PontoOcupacao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ocupacao is None:
        raise HTTPException(status_code=404, detail="Ocupação não encontrada")
    if ocupacao.ate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Esta ocupação já foi encerrada em {ocupacao.ate.isoformat()}",
        )

    ate = payload.ate or date_class.today()
    if ate < ocupacao.desde:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A data de liberação ({ate.isoformat()}) é anterior ao início "
                f"da ocupação ({ocupacao.desde.isoformat()})."
            ),
        )
    motivo = payload.motivo_liberacao
    if motivo is not None and motivo not in MOTIVOS_LIBERACAO:
        raise HTTPException(
            status_code=400,
            detail=f"Motivo inválido. Use um de: {', '.join(MOTIVOS_LIBERACAO)}",
        )

    ocupacao.ate = ate
    ocupacao.motivo_liberacao = motivo
    ocupacao.atualizado_em = datetime.utcnow()
    await db.flush()
    return ocupacao


# ------------------------------------------------------------- P6b: linhas

async def _validar_operadores_linha(
    db: AsyncSession, *, tenant_id: int,
    id_empresa: int | None, id_permissionario: int | None,
) -> None:
    """FK soft: same-tenant e não excluído, senão 404 (não 403 — cross-tenant
    não confirma existência)."""
    if id_empresa is not None:
        emp = await db.scalar(
            select(Empresa.id).where(
                Empresa.id == id_empresa,
                Empresa.tenant_id == tenant_id,
                Empresa.excluido.is_(False),
            )
        )
        if emp is None:
            raise HTTPException(404, "Empresa não encontrada")
    if id_permissionario is not None:
        perm = await db.scalar(
            select(Permissionario.id).where(
                Permissionario.id == id_permissionario,
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
            )
        )
        if perm is None:
            raise HTTPException(404, "Permissionário não encontrado")


async def _validar_nome_linha_unico(
    db: AsyncSession, *, tenant_id: int, nome: str, alem_de: int | None = None,
) -> None:
    stmt = select(Linha.id).where(
        Linha.tenant_id == tenant_id,
        func.lower(Linha.nome) == nome.lower(),
        Linha.excluido.is_(False),
    )
    if alem_de is not None:
        stmt = stmt.where(Linha.id != alem_de)
    if await db.scalar(stmt) is not None:
        raise HTTPException(409, f"Já existe uma linha chamada '{nome}'")


async def obter_linha(db: AsyncSession, *, tenant_id: int, linha_id: int) -> Linha:
    linha = await db.scalar(
        select(Linha).where(
            Linha.id == linha_id,
            Linha.tenant_id == tenant_id,
            Linha.excluido.is_(False),
        )
    )
    if linha is None:
        raise HTTPException(404, "Linha não encontrada")
    return linha


async def listar_linhas(
    db: AsyncSession, *, tenant_id: int,
    q: str | None = None, tipo_servico: str | None = None,
    situacao: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[Linha], int]:
    # Condições construídas UMA vez e usadas na consulta E na contagem — a
    # divergência entre as duas já mordeu duas vezes neste módulo.
    cond = [Linha.tenant_id == tenant_id, Linha.excluido.is_(False)]
    if q:
        padrao = f"%{q.strip()}%"
        cond.append(or_(Linha.nome.ilike(padrao), Linha.codigo.ilike(padrao)))
    if tipo_servico:
        cond.append(Linha.tipo_servico == tipo_servico)
    if situacao:
        cond.append(Linha.situacao == situacao)
    total = await db.scalar(select(func.count(Linha.id)).where(*cond)) or 0
    rows = await db.scalars(
        select(Linha).where(*cond).order_by(Linha.nome).limit(limit).offset(offset)
    )
    return list(rows), total


async def criar_linha(db: AsyncSession, *, tenant_id: int, payload) -> Linha:
    await _validar_nome_linha_unico(db, tenant_id=tenant_id, nome=payload.nome)
    await _validar_operadores_linha(
        db, tenant_id=tenant_id,
        id_empresa=payload.id_empresa, id_permissionario=payload.id_permissionario,
    )
    linha = Linha(
        tenant_id=tenant_id, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(linha)
    await db.flush()
    return linha


async def atualizar_linha(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> Linha:
    linha = await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    dados = payload.model_dump(exclude_unset=True)
    if "nome" in dados:
        await _validar_nome_linha_unico(
            db, tenant_id=tenant_id, nome=dados["nome"], alem_de=linha.id
        )
    # O estado FINAL precisa manter ao menos um operador (o CHECK é a rede).
    id_emp = dados.get("id_empresa", linha.id_empresa)
    id_perm = dados.get("id_permissionario", linha.id_permissionario)
    if id_emp is None and id_perm is None:
        raise HTTPException(
            422, "A linha precisa de uma empresa ou um permissionário responsável"
        )
    await _validar_operadores_linha(
        db, tenant_id=tenant_id,
        id_empresa=dados.get("id_empresa"),
        id_permissionario=dados.get("id_permissionario"),
    )
    for campo, valor in dados.items():
        setattr(linha, campo, valor)
    linha.atualizado_em = datetime.utcnow()
    await db.flush()
    return linha


async def excluir_linha(db: AsyncSession, *, tenant_id: int, linha_id: int) -> None:
    """Soft-delete SÓ da linha — paradas e horários ficam intactos e
    invisíveis (toda leitura entra pela linha). Restaurar a linha um dia
    restaura o itinerário de graça."""
    linha = await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    linha.excluido = True
    linha.atualizado_em = datetime.utcnow()
    await db.flush()


# ---------------------------------------------------- P6b: paradas e horários

async def listar_paradas(
    db: AsyncSession, *, tenant_id: int, linha_id: int,
) -> list[LinhaParada]:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    rows = await db.scalars(
        select(LinhaParada)
        .where(
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
        # (ordem, id): estável mesmo com ordem duplicada — ver docstring do modelo.
        .order_by(LinhaParada.ordem, LinhaParada.id)
    )
    return list(rows)


async def criar_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> LinhaParada:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    ultima = await db.scalar(
        select(func.max(LinhaParada.ordem)).where(
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
    )
    parada = LinhaParada(
        tenant_id=tenant_id, id_linha=linha_id,
        ordem=(ultima or 0) + 1, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(parada)
    await db.flush()
    return parada


async def _obter_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int,
) -> LinhaParada:
    parada = await db.scalar(
        select(LinhaParada).where(
            LinhaParada.id == parada_id,
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
    )
    if parada is None:
        raise HTTPException(404, "Parada não encontrada")
    return parada


async def atualizar_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int, payload,
) -> LinhaParada:
    parada = await _obter_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(parada, campo, valor)
    parada.atualizado_em = datetime.utcnow()
    await db.flush()
    return parada


async def excluir_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int,
) -> None:
    parada = await _obter_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    parada.excluido = True
    parada.atualizado_em = datetime.utcnow()
    await db.flush()


async def reordenar_paradas(
    db: AsyncSession, *, tenant_id: int, linha_id: int, ids: list[int],
) -> list[LinhaParada]:
    """Recebe a lista COMPLETA de ids na nova ordem e renumera 1..N na mesma
    transação. Id faltando ou sobrando é 422: o payload não bate com o estado,
    o cliente está desatualizado — renumerar por cima esconderia isso."""
    atuais = await listar_paradas(db, tenant_id=tenant_id, linha_id=linha_id)
    por_id = {p.id: p for p in atuais}
    if sorted(ids) != sorted(por_id):
        raise HTTPException(
            422, "A lista de paradas não corresponde ao estado atual — recarregue a página"
        )
    agora = datetime.utcnow()
    for nova_ordem, parada_id in enumerate(ids, start=1):
        parada = por_id[parada_id]
        if parada.ordem != nova_ordem:
            parada.ordem = nova_ordem
            parada.atualizado_em = agora
    await db.flush()
    return await listar_paradas(db, tenant_id=tenant_id, linha_id=linha_id)


async def listar_horarios(
    db: AsyncSession, *, tenant_id: int, linha_id: int,
) -> list[LinhaHorario]:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    rows = await db.scalars(
        select(LinhaHorario)
        .where(
            LinhaHorario.tenant_id == tenant_id,
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.excluido.is_(False),
        )
        .order_by(LinhaHorario.dia_semana, LinhaHorario.partida)
    )
    return list(rows)


async def criar_horario(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> LinhaHorario:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    # Checagem para devolver 409 legível; quem garante é ux_linha_horario.
    existe = await db.scalar(
        select(LinhaHorario.id).where(
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.dia_semana == payload.dia_semana,
            LinhaHorario.partida == payload.partida,
            LinhaHorario.excluido.is_(False),
        )
    )
    if existe is not None:
        raise HTTPException(409, "Esse horário já está na grade para esse dia")
    horario = LinhaHorario(
        tenant_id=tenant_id, id_linha=linha_id, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(horario)
    await db.flush()
    return horario


async def excluir_horario(
    db: AsyncSession, *, tenant_id: int, linha_id: int, horario_id: int,
) -> None:
    horario = await db.scalar(
        select(LinhaHorario).where(
            LinhaHorario.id == horario_id,
            LinhaHorario.tenant_id == tenant_id,
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.excluido.is_(False),
        )
    )
    if horario is None:
        raise HTTPException(404, "Horário não encontrado")
    horario.excluido = True
    await db.flush()
