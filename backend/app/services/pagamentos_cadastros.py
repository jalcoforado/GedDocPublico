"""Cadastros de Pagamentos — serviço de domínio (PAG-1). tenant-scoped, soft-delete,
unicidade por tenant. Dados bancários do credor cifrados via app.core.crypto."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import crypto
from ..models import ContaBancaria, Credor, FonteRecursos, NaturezaDespesa
from ..schemas.pagamentos import (
    ContaCreate, ContaUpdate,
    CredorCreate, CredorUpdate, DadosBancarios,
    FonteCreate, FonteUpdate, NaturezaCreate, NaturezaUpdate,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoCadastroError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def credor_out(c: Credor) -> dict:
    return {
        "id": c.id, "tipo_pessoa": c.tipo_pessoa, "cnpj_cpf": c.cnpj_cpf, "nome": c.nome,
        "situacao_cadastral": c.situacao_cadastral, "motivo_pendencia": c.motivo_pendencia,
        "tem_dados_bancarios": any([c.banco_cif, c.agencia_cif, c.conta_cif, c.chave_pix_cif]),
        "criado_em": c.criado_em, "atualizado_em": c.atualizado_em,
    }


async def _validar_doc_unico(db, *, tenant_id: int, cnpj_cpf: str, excluir_id: int | None = None) -> None:
    stmt = select(Credor.id).where(Credor.tenant_id == tenant_id, Credor.cnpj_cpf == cnpj_cpf,
                                   Credor.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(Credor.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe credor com o documento '{cnpj_cpf}'.", status.HTTP_409_CONFLICT)


def _aplicar_dados_bancarios(c: Credor, db_dados: DadosBancarios | None) -> None:
    if db_dados is None:
        return
    c.banco_cif = crypto.encrypt(db_dados.banco)
    c.agencia_cif = crypto.encrypt(db_dados.agencia)
    c.conta_cif = crypto.encrypt(db_dados.conta)
    c.chave_pix_cif = crypto.encrypt(db_dados.chave_pix)


async def obter_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> Credor:
    c = (await db.execute(select(Credor).where(Credor.id == credor_id, Credor.tenant_id == tenant_id,
                                               Credor.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoCadastroError("Credor não encontrado", status.HTTP_404_NOT_FOUND)
    return c


async def listar_credores(db: AsyncSession, *, tenant_id: int, q: str | None = None) -> list[Credor]:
    stmt = select(Credor).where(Credor.tenant_id == tenant_id, Credor.excluido.is_(False))
    if q:
        stmt = stmt.where(Credor.nome.ilike(f"%{q}%"))
    return list((await db.execute(stmt.order_by(Credor.nome))).scalars().all())


async def criar_credor(db: AsyncSession, *, tenant_id: int, payload: CredorCreate) -> Credor:
    await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=payload.cnpj_cpf)
    c = Credor(tenant_id=tenant_id, tipo_pessoa=payload.tipo_pessoa, cnpj_cpf=payload.cnpj_cpf,
               nome=payload.nome, situacao_cadastral=payload.situacao_cadastral,
               motivo_pendencia=payload.motivo_pendencia, criado_em=_utcnow())
    _aplicar_dados_bancarios(c, payload.dados_bancarios)
    db.add(c); await db.commit(); await db.refresh(c)
    return c


async def atualizar_credor(db: AsyncSession, *, tenant_id: int, credor_id: int, payload: CredorUpdate) -> Credor:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    dados = payload.model_dump(exclude_unset=True)
    if "cnpj_cpf" in dados:
        await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=dados["cnpj_cpf"], excluir_id=credor_id)
    for campo in ("tipo_pessoa", "cnpj_cpf", "nome", "situacao_cadastral", "motivo_pendencia"):
        if campo in dados:
            setattr(c, campo, dados[campo])
    if "dados_bancarios" in dados and payload.dados_bancarios is not None:
        _aplicar_dados_bancarios(c, payload.dados_bancarios)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c)
    return c


async def excluir_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> None:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()


async def dados_bancarios_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> DadosBancarios:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    return DadosBancarios(banco=crypto.decrypt(c.banco_cif), agencia=crypto.decrypt(c.agencia_cif),
                          conta=crypto.decrypt(c.conta_cif), chave_pix=crypto.decrypt(c.chave_pix_cif))


# ============================ natureza_despesa / fonte_recursos ==============

async def _codigo_unico(db: AsyncSession, model, *, tenant_id: int, codigo: str,
                         excluir_id: int | None = None) -> None:
    stmt = select(model.id).where(model.tenant_id == tenant_id, model.codigo == codigo,
                                   model.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(model.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe cadastro com o código '{codigo}'.", status.HTTP_409_CONFLICT)


async def obter_natureza(db: AsyncSession, *, tenant_id: int, natureza_id: int) -> NaturezaDespesa:
    n = (await db.execute(select(NaturezaDespesa).where(
        NaturezaDespesa.id == natureza_id, NaturezaDespesa.tenant_id == tenant_id,
        NaturezaDespesa.excluido.is_(False)))).scalar_one_or_none()
    if n is None:
        raise PagamentoCadastroError("Natureza não encontrada", status.HTTP_404_NOT_FOUND)
    return n


async def listar_naturezas(db: AsyncSession, *, tenant_id: int) -> list[NaturezaDespesa]:
    stmt = select(NaturezaDespesa).where(NaturezaDespesa.tenant_id == tenant_id,
                                          NaturezaDespesa.excluido.is_(False))
    return list((await db.execute(stmt.order_by(NaturezaDespesa.codigo))).scalars().all())


async def criar_natureza(db: AsyncSession, *, tenant_id: int, payload: NaturezaCreate) -> NaturezaDespesa:
    await _codigo_unico(db, NaturezaDespesa, tenant_id=tenant_id, codigo=payload.codigo)
    n = NaturezaDespesa(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(n); await db.commit(); await db.refresh(n)
    return n


async def atualizar_natureza(db: AsyncSession, *, tenant_id: int, natureza_id: int,
                              payload: NaturezaUpdate) -> NaturezaDespesa:
    n = await obter_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)
    dados = payload.model_dump(exclude_unset=True)
    if "codigo" in dados:
        await _codigo_unico(db, NaturezaDespesa, tenant_id=tenant_id, codigo=dados["codigo"],
                             excluir_id=natureza_id)
    for k, v in dados.items():
        setattr(n, k, v)
    n.atualizado_em = _utcnow(); await db.commit(); await db.refresh(n)
    return n


async def excluir_natureza(db: AsyncSession, *, tenant_id: int, natureza_id: int) -> None:
    n = await obter_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)
    n.excluido = True; n.atualizado_em = _utcnow(); await db.commit()


async def obter_fonte(db: AsyncSession, *, tenant_id: int, fonte_id: int) -> FonteRecursos:
    f = (await db.execute(select(FonteRecursos).where(
        FonteRecursos.id == fonte_id, FonteRecursos.tenant_id == tenant_id,
        FonteRecursos.excluido.is_(False)))).scalar_one_or_none()
    if f is None:
        raise PagamentoCadastroError("Fonte não encontrada", status.HTTP_404_NOT_FOUND)
    return f


async def listar_fontes(db: AsyncSession, *, tenant_id: int) -> list[FonteRecursos]:
    stmt = select(FonteRecursos).where(FonteRecursos.tenant_id == tenant_id,
                                        FonteRecursos.excluido.is_(False))
    return list((await db.execute(stmt.order_by(FonteRecursos.codigo))).scalars().all())


async def criar_fonte(db: AsyncSession, *, tenant_id: int, payload: FonteCreate) -> FonteRecursos:
    await _codigo_unico(db, FonteRecursos, tenant_id=tenant_id, codigo=payload.codigo)
    f = FonteRecursos(tenant_id=tenant_id, criado_em=_utcnow(),
                       codigo=payload.codigo, descricao=payload.descricao,
                       grupos_despesa_permitidos=[g for g in payload.grupos_despesa_permitidos])
    db.add(f); await db.commit(); await db.refresh(f)
    return f


async def atualizar_fonte(db: AsyncSession, *, tenant_id: int, fonte_id: int,
                           payload: FonteUpdate) -> FonteRecursos:
    f = await obter_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id)
    dados = payload.model_dump(exclude_unset=True)
    if "codigo" in dados:
        await _codigo_unico(db, FonteRecursos, tenant_id=tenant_id, codigo=dados["codigo"],
                             excluir_id=fonte_id)
    for k, v in dados.items():
        setattr(f, k, v)
    f.atualizado_em = _utcnow(); await db.commit(); await db.refresh(f)
    return f


async def excluir_fonte(db: AsyncSession, *, tenant_id: int, fonte_id: int) -> None:
    f = await obter_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id)
    f.excluido = True; f.atualizado_em = _utcnow(); await db.commit()


# ============================ conta_bancaria (fonte x grupo) ==================

async def _validar_fonte_grupo(db: AsyncSession, *, tenant_id: int, id_fonte_recursos: int,
                                grupo_despesa: str) -> None:
    fonte = await obter_fonte(db, tenant_id=tenant_id, fonte_id=id_fonte_recursos)
    permitidos = fonte.grupos_despesa_permitidos or []
    if permitidos and grupo_despesa not in permitidos:
        raise PagamentoCadastroError(
            f"Grupo '{grupo_despesa}' incompatível com a fonte '{fonte.codigo}'.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


async def obter_conta(db: AsyncSession, *, tenant_id: int, conta_id: int) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoCadastroError("Conta não encontrada", status.HTTP_404_NOT_FOUND)
    return c


async def listar_contas(db: AsyncSession, *, tenant_id: int) -> list[ContaBancaria]:
    stmt = select(ContaBancaria).where(ContaBancaria.tenant_id == tenant_id,
                                        ContaBancaria.excluido.is_(False))
    return list((await db.execute(stmt.order_by(ContaBancaria.nome))).scalars().all())


async def criar_conta(db: AsyncSession, *, tenant_id: int, payload: ContaCreate) -> ContaBancaria:
    await _validar_fonte_grupo(db, tenant_id=tenant_id, id_fonte_recursos=payload.id_fonte_recursos,
                                grupo_despesa=payload.grupo_despesa)
    c = ContaBancaria(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(c); await db.commit(); await db.refresh(c)
    return c


async def atualizar_conta(db: AsyncSession, *, tenant_id: int, conta_id: int,
                           payload: ContaUpdate) -> ContaBancaria:
    c = await obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    dados = payload.model_dump(exclude_unset=True)
    if "id_fonte_recursos" in dados or "grupo_despesa" in dados:
        fonte_id = dados.get("id_fonte_recursos", c.id_fonte_recursos)
        grupo = dados.get("grupo_despesa", c.grupo_despesa)
        await _validar_fonte_grupo(db, tenant_id=tenant_id, id_fonte_recursos=fonte_id, grupo_despesa=grupo)
    for k, v in dados.items():
        setattr(c, k, v)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c)
    return c


async def excluir_conta(db: AsyncSession, *, tenant_id: int, conta_id: int) -> None:
    c = await obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()
