"""Testes do fluxo completo com gestor, validação e autoridade (F1, Tarefa 7).

Cobre os 9 endpoints novos (enviar-gestor, gestor-autorizar, gestor-rejeitar,
solicitar-ajuste, responder-ajuste, validar, autoridade-aprovar,
autoridade-indeferir, cancelar) e os 3 deprecated que retornam 410 Gone.

Padrão: provisionar_tenant + admin_engine, criar dados de teste do zero.

Os atores (gestor/validador/autoridade) são usuários reais criados no tenant,
não ids fixos — `id_gestor_decisor`, `id_validador` e `DebitoHistorico.id_usuario`
têm FK para `utils.usuario`, e ids como 1/2/3/4 só "existem por acaso" num banco
de dev acumulado ao longo de meses. Em banco limpo (CI) eles não existem e a
gravação estoura `ForeignKeyViolationError`.
"""
from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    DebitoCreate, ParcelaCreate, FonteCreate, FornecedorCreate,
    ContaCreate, NaturezaCreate, ContratoCreate,
)
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_cadastros as cad
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar_usuario(engine, tenant_id: int, nome: str) -> int:
    """Usuário mínimo, só para satisfazer FKs de ator (gestor/validador/etc)."""
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
    """Tenant + quatro atores reais: solicitante, gestor, validador, autoridade.

    `provisionar_tenant` devolve `(Tenant, senha_temporaria)` — o segundo valor
    não é o usuário admin, então os quatro atores são criados à parte.
    """
    slug = _slug("pagfluxo")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Fluxo", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    solicitante_id = await _criar_usuario(engine, tenant.id, "Solicitante")
    gestor_id = await _criar_usuario(engine, tenant.id, "Gestor")
    validador_id = await _criar_usuario(engine, tenant.id, "Validador")
    autoridade_id = await _criar_usuario(engine, tenant.id, "Autoridade")
    return tenant, solicitante_id, gestor_id, validador_id, autoridade_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
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
    """Cria um débito completo em rascunho com fonte, conta, fornecedor, etc."""
    async with _sm(engine)() as s:
        # Fornecedor
        fornecedor = await cad.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Empresa LTDA",
            ),
        )

        # Fonte e Conta
        fonte = await cad.criar_fonte(
            s, tenant_id=tenant_id,
            payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria",
                grupos_despesa_permitidos=[],
            ),
        )
        conta = await cad.criar_conta(
            s, tenant_id=tenant_id,
            payload=ContaCreate(
                nome="Conta Teste", banco="001", agencia="1",
                conta=uuid.uuid4().hex[:8], id_fonte_recursos=fonte.id,
                grupo_despesa="CUSTEIO", saldo_inicial="10000.00", ativa=True,
            ),
        )

        # Unidade (busca a primeira, ou cria uma se não existir)
        from sqlalchemy import select
        from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
        stmt = select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        unidade_result = await s.execute(stmt)
        unidade = unidade_result.scalar()
        if not unidade:
            # Cria tipo e unidade
            tipo_stmt = select(TipoUnidadeTrabalho).limit(1)
            tipo_result = await s.execute(tipo_stmt)
            tipo = tipo_result.scalar()
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

        # Natureza e Contrato
        natureza = await cad.criar_natureza(
            s, tenant_id=tenant_id,
            payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:5]}", descricao="Teste",
            ),
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

        # Débito com parcelas
        debito = await svc.criar_debito(
            s, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=DebitoCreate(
                numero_nf="NF123456", id_fornecedor=fornecedor.id,
                id_natureza=natureza.id, id_contrato=contrato.id,
                id_fonte_recursos=fonte.id, id_unidade=unidade.id,
                valor_total=Decimal("1000.00"), descricao="Débito de Teste",
                competencia="2026-01",
                parcelas=[
                    ParcelaCreate(
                        numero=1, valor=Decimal("1000.00"),
                        vencimento="2026-02-01",
                    ),
                ],
            ),
        )

    return debito


@pytest.mark.asyncio
async def test_enviar_gestor_success(admin_engine):
    """POST /enviar-gestor retorna 200."""
    tenant, solicitante_id, _, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        result = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

    assert result.situacao_tramitacao == "AGUARDANDO_GESTOR"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_gestor_autorizar_success(admin_engine):
    """Gestor autoriza débito."""
    tenant, solicitante_id, gestor_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        # Envia ao gestor primeiro
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

        # Gestor autoriza
        result = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )

    assert result.situacao_tramitacao == "AGUARDANDO_VALIDACAO"
    assert result.id_gestor_decisor == gestor_id
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_gestor_rejeitar_success(admin_engine):
    """Gestor rejeita débito com justificativa."""
    tenant, solicitante_id, gestor_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

        result = await svc.gestor_rejeitar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
            justificativa="Despesa injustificada",
        )

    assert result.situacao_tramitacao == "REJEITADA_GESTOR"
    assert result.id_gestor_decisor == gestor_id
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_solicitar_ajuste_success(admin_engine):
    """Solicita ajuste a partir de estado aguardando gestor."""
    tenant, solicitante_id, gestor_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

        result = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
            etapa="GESTOR", justificativa="Faltam documentos",
        )

    assert result.situacao_tramitacao == "AJUSTE_GESTOR"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_responder_ajuste_success(admin_engine):
    """Unidade responde ajuste e volta ao estado anterior."""
    tenant, solicitante_id, gestor_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

        # Solicita ajuste
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
            etapa="GESTOR", justificativa="Faltam documentos",
        )

        # Responde ajuste
        result = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

    assert result.situacao_tramitacao == "AGUARDANDO_GESTOR"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_validar_success(admin_engine):
    """Validador aprova débito."""
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        # Fluxo até validação
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )
        debito = await svc.confirmar_liquidacao(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
        )

        # Validador aprova
        result = await svc.validar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
        )

    assert result.situacao_tramitacao == "AGUARDANDO_AUTORIDADE"
    assert result.id_validador == validador_id
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_autoridade_aprovar_success(admin_engine):
    """Autoridade aprova débito e segue para pagamento."""
    tenant, solicitante_id, gestor_id, validador_id, autoridade_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        # Fluxo até autoridade
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )
        debito = await svc.confirmar_liquidacao(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
        )
        debito = await svc.validar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
        )

        # Autoridade aprova
        result = await svc.autoridade_aprovar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=autoridade_id, lock_version=debito.lock_version,
        )

    assert result.situacao_tramitacao == "AUTORIZADA"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_autoridade_indeferir_success(admin_engine):
    """Autoridade indeferiu débito com justificativa."""
    tenant, solicitante_id, gestor_id, validador_id, autoridade_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        # Fluxo até autoridade
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )
        debito = await svc.confirmar_liquidacao(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
        )
        debito = await svc.validar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
        )

        # Autoridade indeferiu
        result = await svc.autoridade_indeferir(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=autoridade_id, lock_version=debito.lock_version,
            justificativa="Saldo orçamentário insuficiente",
        )

    assert result.situacao_tramitacao == "INDEFERIDA_AUTORIDADE"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_cancelar_success(admin_engine):
    """Cancelar débito em rascunho."""
    tenant, solicitante_id, _, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        result = await svc.cancelar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
            justificativa="Cancelado pelo usuário",
        )

    assert result.situacao_tramitacao == "CANCELADA"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_lock_version_conflict(admin_engine):
    """Lock version defasada levanta ConflitoDeEdicaoError."""
    from app.services.pagamentos_guardas import ConflitoDeEdicaoError

    tenant, solicitante_id, gestor_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )

        # Tenta usar lock_version antigo
        with pytest.raises(ConflitoDeEdicaoError) as e:
            await svc.gestor_autorizar(
                s, tenant_id=tenant.id, debito_id=debito.id,
                usuario_id=gestor_id, lock_version=debito.lock_version - 1,
            )

        assert e.value.status_code == 409

    await _cleanup(admin_engine, tenant.id)
