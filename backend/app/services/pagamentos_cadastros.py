"""Cadastros de Pagamentos — serviço de domínio (PAG-1). tenant-scoped, soft-delete,
unicidade por tenant. Dados bancários do credor cifrados via app.core.crypto."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import crypto
from ..models import Credor
from ..schemas.pagamentos import CredorCreate, CredorUpdate, DadosBancarios


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
