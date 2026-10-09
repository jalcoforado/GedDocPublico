"""Apoio dos testes do módulo Contratos (G1). Não é arquivo de teste.

Os helpers de tenant/usuário seguem o padrão já usado na suíte
(`test_pagamentos_f3_fila.py`, `test_transporte_p4_relatorio.py`); ficam aqui,
e não copiados em cada arquivo, porque a bateria da G1 tem quatro arquivos que
precisam dos mesmos cinco.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import TipoUnidadeTrabalho, UnidadeTrabalho, Usuario
from app.schemas.contratos import AditivoCreate, ContratoCreate
from app.schemas.pagamentos import FornecedorCreate
from app.services import contratos as svc
from app.services import pagamentos_cadastros as cad
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def numero() -> str:
    """Número de contrato/aditivo dentro dos 15 caracteres do SIM."""
    return f"CT{uuid.uuid4().hex[:10]}"


async def provisionar(engine, prefixo: str = "ctg1"):
    """Tenant novo. `provisionar_tenant` contrata TODOS os módulos contratáveis
    e ativos — inclusive `contratos`, desde a migration 0132."""
    slug = f"{prefixo}-{uuid.uuid4().hex[:8]}"
    async with sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Contratos G1", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def criar_usuario_su(engine, tenant_id: int) -> int:
    """Devolve o id do admin que o provisionamento criou (super-usuário)."""
    async with sm(engine)() as s:
        return (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id = :t AND excluido = false "
            "ORDER BY id LIMIT 1"
        ), {"t": tenant_id})).scalar_one()


async def criar_usuario_comum(engine, tenant_id: int, *, transacao: str | None,
                              credencial: str = "interno") -> int:
    """Usuário NÃO super-usuário (nível != 0). Com `transacao`, o grupo dele
    recebe a transação com inserir/atualizar/excluir; com `None`, o usuário
    existe e não tem permissão nenhuma.

    Mesmo padrão de `test_permissoes_modulo.py::_cria_usuario_comum`. Existe
    porque o bypass de SU em `auth/perms.py` retorna ANTES do gate: a suíte
    inteira de SU passaria verde com o gate quebrado para o usuário comum.
    """
    async with sm(engine)() as session:
        async with session.begin():
            sistema_id = (await session.execute(text(
                "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
            ), {"app": APP})).scalar_one()
            nivel_id = (await session.execute(text(
                "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
            ))).scalar_one_or_none()
            if nivel_id is None:
                nivel_id = (await session.execute(text(
                    "INSERT INTO utils.nivel (nivel, valor, excluido) "
                    "VALUES ('Operacional', 1, false) RETURNING id"
                ))).scalar_one()
            uid = (await session.execute(text("""
                INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                           excluido, app, nivel_acesso_sigilo)
                VALUES (:t, 'Usuario Comum Contratos', :email, '', :cpf, true, false,
                        :app, :cred)
                RETURNING id
            """), {
                "t": tenant_id, "email": f"comum-ct-{uuid.uuid4().hex[:8]}@t.local",
                "cpf": uuid.uuid4().hex[:11], "app": APP, "cred": credencial,
            })).scalar_one()
            gid = (await session.execute(text("""
                INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
                VALUES (:t, :n, :s, 'Grupo Comum Contratos', false) RETURNING id
            """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
            await session.execute(text("""
                INSERT INTO utils.usuario_grupo
                    (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
                VALUES (:t, :u, :g, true, false, :app)
            """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
            if transacao is not None:
                transacao_id = (await session.execute(text(
                    "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false "
                    "LIMIT 1"
                ), {"c": transacao})).scalar_one()
                await session.execute(text("""
                    INSERT INTO utils.grupo_transacao
                        (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                    VALUES (:t, :g, :tr, true, true, true, false)
                """), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return uid


def como_usuario(engine, usuario_id: int, tenant_id: int, tenant_slug: str) -> None:
    """Instala o usuário e o tenant nas dependências da app. Quem chama limpa
    com `app.dependency_overrides.clear()` no `finally`."""

    async def _get_user():
        async with sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)


async def carregar_usuario(engine, usuario_id: int) -> Usuario:
    async with sm(engine)() as s:
        return (await s.execute(select(Usuario).where(Usuario.id == usuario_id))).scalar_one()


async def criar_fornecedor_e_unidade(engine, tenant_id: int) -> tuple[int, int]:
    async with sm(engine)() as s:
        fornecedor = await cad.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=str(uuid.uuid4().int)[:14],
                nome="Fornecedora Teste LTDA"),
        )
        unidade = (await s.execute(
            select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        )).scalar()
        if unidade is None:
            tipo = (await s.execute(select(TipoUnidadeTrabalho).limit(1))).scalar()
            if tipo is None:
                tipo = TipoUnidadeTrabalho(
                    tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
                s.add(tipo)
                await s.flush()
            unidade = UnidadeTrabalho(
                tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
                unidade_trabalho="Unidade Teste")
            s.add(unidade)
            await s.commit()
        return fornecedor.id, unidade.id


def payload_contrato(id_fornecedor: int, id_unidade: int, **extra) -> ContratoCreate:
    dados = {
        "numero": numero(), "id_fornecedor": id_fornecedor, "id_unidade": id_unidade,
        "objeto": "Serviços de teste", "vigencia_inicio": date(2026, 1, 1),
        "vigencia_fim": date(2026, 12, 31), "valor_total": Decimal("100000.00"),
        "categoria": "SERVICOS", "data_celebracao": date(2026, 1, 1),
        "tipo_objeto": "O", "natureza_duracao": "CONTINUO",
    }
    dados.update(extra)
    return ContratoCreate(**dados)


async def contrato_vigente(engine, tenant_id: int, usuario, **extra):
    """Cria e assina um contrato de R$ 100.000,00, de 01/01 a 31/12/2026."""
    id_fornecedor, id_unidade = await criar_fornecedor_e_unidade(engine, tenant_id)
    async with sm(engine)() as s:
        c = await svc.criar(
            s, tenant_id=tenant_id, usuario=usuario,
            payload=payload_contrato(id_fornecedor, id_unidade, **extra))
        return await svc.assinar(s, tenant_id=tenant_id, contrato_id=c.id)


async def aditivo_vigente(engine, tenant_id: int, contrato_id: int, usuario_id: int, *,
                          tipo: str, valor: str = "0", nova_vigencia_fim: date | None = None,
                          justificativa: str | None = None, hoje: date | None = None):
    async with sm(engine)() as s:
        a = await svc.criar_aditivo(
            s, tenant_id=tenant_id, contrato_id=contrato_id, usuario_id=usuario_id,
            payload=AditivoCreate(
                numero=numero(), tipo=tipo, data_assinatura=date(2026, 6, 1),
                valor=Decimal(valor), nova_vigencia_fim=nova_vigencia_fim,
                justificativa=justificativa))
        return await svc.assinar_aditivo(
            s, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=a.id,
            hoje=hoje or date(2026, 6, 1))
