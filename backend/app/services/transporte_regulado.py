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

from ..models import Empresa, Permissionario, VeiculoRegulado, Usuario
from ..models.transporte_regulado import VeiculoDocumento, VeiculoAvaliacao, VeiculoVistoria
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
) -> list[VeiculoRegulado]:
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
    return list((await db.execute(stmt)).scalars().all())


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
) -> list[VeiculoDocumento]:
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
    return list((await db.execute(stmt)).scalars().all())


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
    db: AsyncSession, *, tenant_id: int, veiculo_id: int
) -> list[VeiculoAvaliacao]:
    """Lista avaliações de um veículo."""
    stmt = select(VeiculoAvaliacao).where(
        VeiculoAvaliacao.tenant_id == tenant_id,
        VeiculoAvaliacao.id_veiculo == veiculo_id,
        VeiculoAvaliacao.excluido.is_(False),
    )
    stmt = stmt.order_by(VeiculoAvaliacao.data_avaliacao.desc())
    return list((await db.execute(stmt)).scalars().all())


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
    db: AsyncSession, *, tenant_id: int, veiculo_id: int
) -> list[VeiculoVistoria]:
    """Lista vistorias de um veículo."""
    stmt = select(VeiculoVistoria).where(
        VeiculoVistoria.tenant_id == tenant_id,
        VeiculoVistoria.id_veiculo == veiculo_id,
        VeiculoVistoria.excluido.is_(False),
    )
    stmt = stmt.order_by(VeiculoVistoria.data_vistoria.desc())
    return list((await db.execute(stmt)).scalars().all())


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
