"""Testes da fila cronológica (F3, Task 1) — migration 0107.

Padrão de dados: `_provisionar`/`_criar_usuario`/`_setup_debito` copiados de
`test_pagamentos_f2_ajustes.py` (atores reais — FK para `utils.usuario` não
aceita id fixo).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PosicaoCronologica
from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, DebitoUpdate, FonteCreate,
    FornecedorCreate, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
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
    gestor_id = await _criar_usuario(engine, tenant.id, "Gestor")
    validador_id = await _criar_usuario(engine, tenant.id, "Validador")
    return tenant, solicitante_id, gestor_id, validador_id


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


async def _setup_debito(engine, tenant_id: int, usuario_id: int, *,
                        com_contrato: bool = True, categoria: str | None = None):
    """Cria um débito completo em rascunho com fonte, conta, fornecedor etc.

    Cópia do helper homônimo em `test_pagamentos_f2_ajustes.py`, com
    `com_contrato`/`categoria` novos (Task 2) para exercitar o débito SEM
    contrato, que carrega a categoria em si mesmo."""
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
        id_contrato = None
        if com_contrato:
            contrato = await cad.criar_contrato(
                s, tenant_id=tenant_id,
                payload=ContratoCreate(
                    numero=f"CT-{uuid.uuid4().hex[:8]}", id_fornecedor=fornecedor.id,
                    id_unidade=unidade.id, objeto="Serviços de Teste",
                    vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                    valor_total=Decimal("5000.00"), categoria="SERVICOS",
                ),
            )
            id_contrato = contrato.id

        debito = await svc.criar_debito(
            s, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=DebitoCreate(
                numero_nf="NF123456", id_fornecedor=fornecedor.id,
                id_natureza=natureza.id, id_contrato=id_contrato,
                id_fonte_recursos=fonte.id, id_unidade=unidade.id,
                valor_total=Decimal("1000.00"), descricao="Débito de Teste",
                competencia="2026-01", categoria=categoria,
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
    tenant, solicitante_id, _gestor_id, _validador_id = await _provisionar(admin_engine)
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


# ---------------------------------------------------------------------------
# Task 2 — registro do marco na liquidação
# ---------------------------------------------------------------------------


async def _levar_ate_aguardando_validacao(engine, tenant_id, debito, solicitante_id, gestor_id):
    """Fluxo real: enviar ao gestor -> gestor autoriza -> AGUARDANDO_VALIDACAO.

    Cópia do helper homônimo em `test_pagamentos_f2_ajustes.py`."""
    async with _sm(engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )
    return debito


async def _posicao_do_debito(engine, tenant_id: int, debito_id: int) -> PosicaoCronologica | None:
    async with _sm(engine)() as s:
        return (await s.execute(select(PosicaoCronologica).where(
            PosicaoCronologica.tenant_id == tenant_id,
            PosicaoCronologica.id_debito == debito_id,
        ))).scalar_one_or_none()


@pytest.mark.asyncio
async def test_liquidacao_registra_na_fila(admin_engine):
    """Débito COM contrato (categoria SERVICOS): `confirmar_liquidacao` cria a
    posição na fila (situacao REGISTRADA, exercicio=ano, categoria do
    contrato, marco_em.date()==data_liquidacao) e sincroniza `situacao_fila`."""
    tenant, solicitante_id, _gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, fonte_id, unidade_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        data_liq = date(2026, 3, 10)

        async with _sm(admin_engine)() as s:
            debito = await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=data_liq)

        assert debito.situacao_fila == est.REGISTRADA

        posicao = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert posicao is not None
        assert posicao.situacao == est.REGISTRADA
        assert posicao.exercicio == 2026
        assert posicao.categoria == "SERVICOS"
        assert posicao.id_unidade == unidade_id
        assert posicao.id_fonte_recursos == fonte_id
        assert posicao.marco_em.date() == data_liq
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_liquidacao_sem_contrato_usa_categoria_do_debito(admin_engine):
    """Débito SEM contrato: a categoria vem do próprio débito."""
    tenant, solicitante_id, _gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, _fonte_id, _unidade_id = await _setup_debito(
            admin_engine, tenant.id, solicitante_id, com_contrato=False, categoria="BENS")
        data_liq = date(2026, 4, 1)

        async with _sm(admin_engine)() as s:
            await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=data_liq)

        posicao = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert posicao is not None
        assert posicao.categoria == "BENS"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_liquidacao_sem_contrato_e_sem_categoria_e_422(admin_engine):
    """Débito SEM contrato E sem categoria própria: 422 — sem categoria não
    há como entrar na fila cronológica."""
    tenant, solicitante_id, _gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, _fonte_id, _unidade_id = await _setup_debito(
            admin_engine, tenant.id, solicitante_id, com_contrato=False, categoria=None)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.confirmar_liquidacao(
                    s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id)
        assert exc.value.status_code == 422

        posicao = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert posicao is None
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_liquidar_duas_vezes_nao_regrava_marco(admin_engine):
    """Segunda confirmação de liquidação (re-liquidação) mantém o marco_em
    original — `registrar_na_fila` é idempotente."""
    tenant, solicitante_id, _gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, _fonte_id, _unidade_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)

        async with _sm(admin_engine)() as s:
            debito = await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=date(2026, 3, 10))
        primeira = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        marco_original = primeira.marco_em

        async with _sm(admin_engine)() as s:
            await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=date(2026, 5, 20))

        segunda = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert segunda.marco_em == marco_original
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_edicao_material_de_data_liquidacao_regrava_marco(admin_engine):
    """Débito liquidado + em AJUSTE_VALIDACAO: `atualizar_debito` mudando
    `data_liquidacao` regrava o marco e grava histórico MARCO_REGRAVADO."""
    tenant, solicitante_id, gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, _fonte_id, _unidade_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        debito = await _levar_ate_aguardando_validacao(
            admin_engine, tenant.id, debito, solicitante_id, gestor_id)

        async with _sm(admin_engine)() as s:
            debito = await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=date(2026, 3, 10))
        posicao_antes = await _posicao_do_debito(admin_engine, tenant.id, debito.id)

        async with _sm(admin_engine)() as s:
            debito = await svc.solicitar_ajuste(
                s, tenant_id=tenant.id, debito_id=debito.id,
                usuario_id=validador_id, lock_version=debito.lock_version,
                etapa="VALIDACAO", motivo="Data de liquidação errada",
                descricao="A data de liquidação registrada está errada.",
                transacao_responsavel="pagamento_solicitar", tipo="MATERIAL",
            )
        assert debito.situacao_tramitacao == "AJUSTE_VALIDACAO"

        nova_data = date(2026, 6, 15)
        async with _sm(admin_engine)() as s:
            debito = await svc.atualizar_debito(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                payload=DebitoUpdate(data_liquidacao=nova_data),
            )

        posicao_depois = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert posicao_depois.marco_em.date() == nova_data
        assert posicao_depois.marco_em != posicao_antes.marco_em

        async with _sm(admin_engine)() as s:
            historico = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
        assert any(h.acao == "MARCO_REGRAVADO" for h in historico)
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_cancelar_debito_na_fila_vira_retirada(admin_engine):
    """`cancelar` um débito com posição na fila muda `situacao_fila` para
    RETIRADA e espelha em `posicao_cronologica.situacao`."""
    tenant, solicitante_id, gestor_id, validador_id = await _provisionar(admin_engine)
    try:
        debito, _fonte_id, _unidade_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        debito = await _levar_ate_aguardando_validacao(
            admin_engine, tenant.id, debito, solicitante_id, gestor_id)

        async with _sm(admin_engine)() as s:
            debito = await svc.confirmar_liquidacao(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=validador_id,
                data_liquidacao=date(2026, 3, 10))

        # AGUARDANDO_VALIDACAO não alcança CANCELADA no grafo de tramitação —
        # passa por AJUSTE_VALIDACAO, que alcança, para exercitar o
        # cancelamento com posição já registrada na fila.
        async with _sm(admin_engine)() as s:
            debito = await svc.solicitar_ajuste(
                s, tenant_id=tenant.id, debito_id=debito.id,
                usuario_id=validador_id, lock_version=debito.lock_version,
                etapa="VALIDACAO", motivo="Pendência qualquer",
                descricao="Pendência qualquer antes do cancelamento.",
                transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
            )

        async with _sm(admin_engine)() as s:
            debito = await svc.cancelar(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                lock_version=debito.lock_version, justificativa="Erro na solicitação.",
            )

        assert debito.situacao_fila == est.RETIRADA

        posicao = await _posicao_do_debito(admin_engine, tenant.id, debito.id)
        assert posicao.situacao == est.RETIRADA
    finally:
        await _cleanup(admin_engine, tenant.id)
