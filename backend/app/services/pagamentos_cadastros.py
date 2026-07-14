"""Cadastros de Pagamentos — serviço de domínio (PAG-1). tenant-scoped, soft-delete,
unicidade por tenant. Dados bancários do fornecedor cifrados via app.core.crypto."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import crypto
from ..models import Alcada, ContaBancaria, Contrato, Fornecedor, FonteRecursos, NaturezaDespesa, UnidadeTrabalho
from ..schemas.pagamentos import (
    AlcadaCreate, AlcadaUpdate,
    ContaCreate, ContaUpdate,
    ContratoCreate, ContratoUpdate,
    FornecedorCreate, FornecedorUpdate, DadosBancarios,
    FonteCreate, FonteUpdate, NaturezaCreate, NaturezaUpdate,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoCadastroError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def fornecedor_out(c: Fornecedor) -> dict:
    return {
        "id": c.id, "tipo_pessoa": c.tipo_pessoa, "cnpj_cpf": c.cnpj_cpf, "nome": c.nome,
        "situacao_cadastral": c.situacao_cadastral, "motivo_pendencia": c.motivo_pendencia,
        "tem_dados_bancarios": any([c.banco_cif, c.agencia_cif, c.conta_cif, c.chave_pix_cif]),
        "criado_em": c.criado_em, "atualizado_em": c.atualizado_em,
    }


async def _validar_doc_unico(db, *, tenant_id: int, cnpj_cpf: str, excluir_id: int | None = None) -> None:
    stmt = select(Fornecedor.id).where(Fornecedor.tenant_id == tenant_id, Fornecedor.cnpj_cpf == cnpj_cpf,
                                        Fornecedor.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(Fornecedor.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe fornecedor com o documento '{cnpj_cpf}'.", status.HTTP_409_CONFLICT)


def _aplicar_dados_bancarios(c: Fornecedor, db_dados: DadosBancarios | None) -> None:
    if db_dados is None:
        return
    c.banco_cif = crypto.encrypt(db_dados.banco)
    c.agencia_cif = crypto.encrypt(db_dados.agencia)
    c.conta_cif = crypto.encrypt(db_dados.conta)
    c.chave_pix_cif = crypto.encrypt(db_dados.chave_pix)


async def obter_fornecedor(db: AsyncSession, *, tenant_id: int, fornecedor_id: int) -> Fornecedor:
    c = (await db.execute(select(Fornecedor).where(Fornecedor.id == fornecedor_id, Fornecedor.tenant_id == tenant_id,
                                                     Fornecedor.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoCadastroError("Fornecedor não encontrado", status.HTTP_404_NOT_FOUND)
    return c


async def listar_fornecedores(db: AsyncSession, *, tenant_id: int, q: str | None = None) -> list[Fornecedor]:
    stmt = select(Fornecedor).where(Fornecedor.tenant_id == tenant_id, Fornecedor.excluido.is_(False))
    if q:
        stmt = stmt.where(Fornecedor.nome.ilike(f"%{q}%"))
    return list((await db.execute(stmt.order_by(Fornecedor.nome))).scalars().all())


async def criar_fornecedor(db: AsyncSession, *, tenant_id: int, payload: FornecedorCreate) -> Fornecedor:
    await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=payload.cnpj_cpf)
    c = Fornecedor(tenant_id=tenant_id, tipo_pessoa=payload.tipo_pessoa, cnpj_cpf=payload.cnpj_cpf,
                    nome=payload.nome, situacao_cadastral=payload.situacao_cadastral,
                    motivo_pendencia=payload.motivo_pendencia, criado_em=_utcnow())
    _aplicar_dados_bancarios(c, payload.dados_bancarios)
    db.add(c); await db.commit(); await db.refresh(c)
    return c


async def atualizar_fornecedor(db: AsyncSession, *, tenant_id: int, fornecedor_id: int,
                                payload: FornecedorUpdate) -> Fornecedor:
    c = await obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=fornecedor_id)
    dados = payload.model_dump(exclude_unset=True)
    if "cnpj_cpf" in dados:
        await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=dados["cnpj_cpf"], excluir_id=fornecedor_id)
    for campo in ("tipo_pessoa", "cnpj_cpf", "nome", "situacao_cadastral", "motivo_pendencia"):
        if campo in dados:
            setattr(c, campo, dados[campo])
    if "dados_bancarios" in dados and payload.dados_bancarios is not None:
        _aplicar_dados_bancarios(c, payload.dados_bancarios)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c)
    return c


async def excluir_fornecedor(db: AsyncSession, *, tenant_id: int, fornecedor_id: int) -> None:
    c = await obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=fornecedor_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()


async def dados_bancarios_fornecedor(db: AsyncSession, *, tenant_id: int, fornecedor_id: int) -> DadosBancarios:
    c = await obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=fornecedor_id)
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


# ============================ contrato =========================================

async def _numero_unico(db: AsyncSession, *, tenant_id: int, numero: str,
                         excluir_id: int | None = None) -> None:
    stmt = select(Contrato.id).where(Contrato.tenant_id == tenant_id, Contrato.numero == numero,
                                      Contrato.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(Contrato.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe contrato número '{numero}'.", status.HTTP_409_CONFLICT)


async def _validar_unidade(db: AsyncSession, *, tenant_id: int, id_unidade: int) -> None:
    u = (await db.execute(select(UnidadeTrabalho.id).where(
        UnidadeTrabalho.id == id_unidade, UnidadeTrabalho.tenant_id == tenant_id,
        UnidadeTrabalho.excluido.is_(False)))).scalar_one_or_none()
    if u is None:
        raise PagamentoCadastroError("Unidade (órgão) inválida.", status.HTTP_422_UNPROCESSABLE_ENTITY)


async def obter_contrato(db: AsyncSession, *, tenant_id: int, contrato_id: int) -> Contrato:
    c = (await db.execute(select(Contrato).where(
        Contrato.id == contrato_id, Contrato.tenant_id == tenant_id,
        Contrato.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoCadastroError("Contrato não encontrado", status.HTTP_404_NOT_FOUND)
    return c


async def listar_contratos(db: AsyncSession, *, tenant_id: int) -> list[Contrato]:
    stmt = select(Contrato).where(Contrato.tenant_id == tenant_id, Contrato.excluido.is_(False))
    return list((await db.execute(stmt.order_by(Contrato.numero))).scalars().all())


async def criar_contrato(db: AsyncSession, *, tenant_id: int, payload: ContratoCreate) -> Contrato:
    await _numero_unico(db, tenant_id=tenant_id, numero=payload.numero)
    await obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=payload.id_fornecedor)
    await _validar_unidade(db, tenant_id=tenant_id, id_unidade=payload.id_unidade)
    c = Contrato(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(c); await db.commit(); await db.refresh(c)
    return c


async def atualizar_contrato(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                              payload: ContratoUpdate) -> Contrato:
    c = await obter_contrato(db, tenant_id=tenant_id, contrato_id=contrato_id)
    dados = payload.model_dump(exclude_unset=True)
    if "numero" in dados:
        await _numero_unico(db, tenant_id=tenant_id, numero=dados["numero"], excluir_id=contrato_id)
    if "id_fornecedor" in dados:
        await obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=dados["id_fornecedor"])
    if "id_unidade" in dados:
        await _validar_unidade(db, tenant_id=tenant_id, id_unidade=dados["id_unidade"])
    for k, v in dados.items():
        setattr(c, k, v)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c)
    return c


async def excluir_contrato(db: AsyncSession, *, tenant_id: int, contrato_id: int) -> None:
    c = await obter_contrato(db, tenant_id=tenant_id, contrato_id=contrato_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()


# ============================ alcada ============================================

async def _alcada_unica(db: AsyncSession, *, tenant_id: int, id_usuario: int, id_natureza: int | None,
                         excluir_id: int | None = None) -> None:
    stmt = select(Alcada.id).where(Alcada.tenant_id == tenant_id, Alcada.id_usuario == id_usuario,
                                    Alcada.excluido.is_(False))
    if id_natureza is None:
        stmt = stmt.where(Alcada.id_natureza.is_(None))
    else:
        stmt = stmt.where(Alcada.id_natureza == id_natureza)
    if excluir_id is not None:
        stmt = stmt.where(Alcada.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError("Já existe alçada para este usuário/natureza.", status.HTTP_409_CONFLICT)


async def obter_alcada(db: AsyncSession, *, tenant_id: int, alcada_id: int) -> Alcada:
    a = (await db.execute(select(Alcada).where(
        Alcada.id == alcada_id, Alcada.tenant_id == tenant_id,
        Alcada.excluido.is_(False)))).scalar_one_or_none()
    if a is None:
        raise PagamentoCadastroError("Alçada não encontrada", status.HTTP_404_NOT_FOUND)
    return a


async def listar_alcadas(db: AsyncSession, *, tenant_id: int) -> list[Alcada]:
    stmt = select(Alcada).where(Alcada.tenant_id == tenant_id, Alcada.excluido.is_(False))
    return list((await db.execute(stmt.order_by(Alcada.id))).scalars().all())


async def criar_alcada(db: AsyncSession, *, tenant_id: int, payload: AlcadaCreate) -> Alcada:
    await _alcada_unica(db, tenant_id=tenant_id, id_usuario=payload.id_usuario,
                         id_natureza=payload.id_natureza)
    a = Alcada(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(a); await db.commit(); await db.refresh(a)
    return a


async def atualizar_alcada(db: AsyncSession, *, tenant_id: int, alcada_id: int,
                            payload: AlcadaUpdate) -> Alcada:
    a = await obter_alcada(db, tenant_id=tenant_id, alcada_id=alcada_id)
    dados = payload.model_dump(exclude_unset=True)
    if "id_usuario" in dados or "id_natureza" in dados:
        id_usuario = dados.get("id_usuario", a.id_usuario)
        id_natureza = dados.get("id_natureza", a.id_natureza)
        await _alcada_unica(db, tenant_id=tenant_id, id_usuario=id_usuario, id_natureza=id_natureza,
                             excluir_id=alcada_id)
    for k, v in dados.items():
        setattr(a, k, v)
    a.atualizado_em = _utcnow(); await db.commit(); await db.refresh(a)
    return a


async def excluir_alcada(db: AsyncSession, *, tenant_id: int, alcada_id: int) -> None:
    a = await obter_alcada(db, tenant_id=tenant_id, alcada_id=alcada_id)
    a.excluido = True; a.atualizado_em = _utcnow(); await db.commit()
