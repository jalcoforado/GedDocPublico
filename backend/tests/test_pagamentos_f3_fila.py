"""Testes da fila cronológica (F3, Task 1) — migration 0107.

Padrão de dados: `_provisionar`/`_criar_usuario`/`_setup_debito` copiados de
`test_pagamentos_f2_ajustes.py` (atores reais — FK para `utils.usuario` não
aceita id fixo).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PosicaoCronologica
from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar_usuario(engine, tenant_id: int, nome: str) -> int:
    async with _sm(engine)() as s:
        uid = (await s.execute(text(
            "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, "
            "cpf, ativo, excluido, app, nivel_acesso_sigilo, must_change_password) "
            "VALUES (:t, :n, :e, '', '', :c, true, false, 'sistemas', 'interno', false) "
            "RETURNING id"
        ), {"t": tenant_id, "n": nome, "e": f"{uuid.uuid4().hex[:10]}@t.local",
            "c": str(uuid.uuid4().int)[:11]})).scalar_one()
        await s.commit()
    return uid


async def _provisionar(engine):
    slug = _slug("pagf3fila")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F3 Fila", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    solicitante_id = await _criar_usuario(engine, tenant.id, "Solicitante")
    return tenant, solicitante_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.posicao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.excecao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.anexo_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_versao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.pedido_ajuste WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


async def _setup_debito(engine, tenant_id: int, usuario_id: int):
    """Cria um débito completo em rascunho com fonte, conta, fornecedor etc.

    Cópia do helper homônimo em `test_pagamentos_f2_ajustes.py`."""
    async with _sm(engine)() as s:
        fornecedor = await cad.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Empresa LTDA"),
        )
        fonte = await cad.criar_fonte(
            s, tenant_id=tenant_id,
            payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria",
                grupos_despesa_permitidos=[],
            ),
        )
        await cad.criar_conta(
            s, tenant_id=tenant_id,
            payload=ContaCreate(
                nome="Conta Teste", banco="001", agencia="1",
                conta=uuid.uuid4().hex[:8], id_fonte_recursos=fonte.id,
                grupo_despesa="CUSTEIO", saldo_inicial="10000.00", ativa=True,
            ),
        )

        from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
        stmt = select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        unidade = (await s.execute(stmt)).scalar()
        if not unidade:
            tipo = (await s.execute(select(TipoUnidadeTrabalho).limit(1))).scalar()
            if not tipo:
                tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
                s.add(tipo)
                await s.flush()
            unidade = UnidadeTrabalho(
                tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
                unidade_trabalho="Unidade Teste",
            )
            s.add(unidade)
            await s.flush()

        natureza = await cad.criar_natureza(
            s, tenant_id=tenant_id,
            payload=NaturezaCreate(codigo=f"N{uuid.uuid4().hex[:5]}", descricao="Teste"),
        )
        contrato = await cad.criar_contrato(
            s, tenant_id=tenant_id,
            payload=ContratoCreate(
                numero=f"CT-{uuid.uuid4().hex[:8]}", id_fornecedor=fornecedor.id,
                id_unidade=unidade.id, objeto="Serviços de Teste",
                vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                valor_total=Decimal("5000.00"),
            ),
        )

        debito = await svc.criar_debito(
            s, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=DebitoCreate(
                numero_nf="NF123456", id_fornecedor=fornecedor.id,
                id_natureza=natureza.id, id_contrato=contrato.id,
                id_fonte_recursos=fonte.id, id_unidade=unidade.id,
                valor_total=Decimal("1000.00"), descricao="Débito de Teste",
                competencia="2026-01",
                parcelas=[ParcelaCreate(numero=1, valor=Decimal("1000.00"), vencimento="2026-02-01")],
            ),
        )
    return debito, fonte.id, unidade.id


@pytest.mark.asyncio
async def test_nenhum_contrato_sem_categoria(admin_engine):
    """Pós-0107: nenhum `pagamentos.contrato` fica com `categoria IS NULL` —
    prova o backfill que a migration aplica sobre os 19 contratos do dev que
    escaparam do backfill original da 0085."""
    async with _sm(admin_engine)() as s:
        total = (await s.execute(
            text("SELECT count(*) FROM pagamentos.contrato WHERE categoria IS NULL")
        )).scalar_one()
    assert total == 0


@pytest.mark.asyncio
async def test_posicao_e_unica_por_debito(admin_engine):
    """Prova o UNIQUE `(tenant_id, id_debito)` de `posicao_cronologica`:
    inserir uma segunda posição para o mesmo débito estoura IntegrityError."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, fonte_id, unidade_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)

        async with _sm(admin_engine)() as s:
            s.add(PosicaoCronologica(
                tenant_id=tenant.id, id_debito=debito.id, id_unidade=unidade_id,
                id_fonte_recursos=fonte_id, categoria="SERVICOS", exercicio=2026,
                marco_em=datetime(2026, 1, 1), situacao="NAO_REGISTRADA",
                registrado_em=datetime.utcnow(),
            ))
            await s.commit()

        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as s:
                s.add(PosicaoCronologica(
                    tenant_id=tenant.id, id_debito=debito.id, id_unidade=unidade_id,
                    id_fonte_recursos=fonte_id, categoria="SERVICOS", exercicio=2026,
                    marco_em=datetime(2026, 1, 2), situacao="NAO_REGISTRADA",
                    registrado_em=datetime.utcnow(),
                ))
                await s.commit()
    finally:
        await _cleanup(admin_engine, tenant.id)
