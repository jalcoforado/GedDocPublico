"""Testes de migration/backfill da F2 — pedido_ajuste, debito_versao,
anexo_debito (Task 1).

Padrão emprestado de `test_pagamentos_fluxo_gestor.py`: `provisionar_tenant`
+ `admin_engine`, tenant/atores reais (as FKs de ator não aceitam id fixo —
ids como 1/2/3 só "existem por acaso" num banco de dev acumulado; em banco
limpo do CI estouram `ForeignKeyViolationError`).

Não usamos a fixture `two_tenants`: o teardown dela só limpa tabelas de
`protocolos`/`aprimora_py`/`utils`, não `pagamentos` — um débito preso ao
tenant faria o `DELETE FROM aprimora_py.tenant` do teardown estourar por FK.
Cada teste aqui provisiona e limpa o próprio tenant, como os outros arquivos
de pagamentos já fazem.

Este arquivo não roda a migration 0105 dentro do teste — o CI já a exercita
em banco limpo via `alembic upgrade head`/stamp+upgrade, o que prova que o
SQL do backfill é válido mesmo inserindo zero linhas (não há débito
`AJUSTE_*` em banco recém-criado). O que se testa aqui é a PROPRIEDADE que o
backfill existe para garantir: nenhum débito em situação `AJUSTE_*` fica sem
`pedido_ajuste` não-cancelado associado — a invariante que a Task 3 (consulta
de pendências por etapa) vai assumir como verdadeira em qualquer tenant.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services.provisioning_tenant import provisionar_tenant

_ORFAOS_SQL = text(
    "SELECT count(*) FROM pagamentos.debito d "
    "WHERE d.tenant_id = :t AND d.situacao_tramitacao LIKE 'AJUSTE%' "
    "AND d.excluido = false "
    "AND NOT EXISTS ("
    "  SELECT 1 FROM pagamentos.pedido_ajuste p "
    "  WHERE p.id_debito = d.id AND p.tenant_id = d.tenant_id "
    "    AND p.situacao <> 'CANCELADO'"
    ")"
)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar_usuario(engine, tenant_id: int, nome: str) -> int:
    """Usuário mínimo, só para satisfazer FKs de ator (solicitante)."""
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
    slug = _slug("pagf2v")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F2 Versionamento",
            admin_email=f"{slug}@t.local", admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    solicitante_id = await _criar_usuario(engine, tenant.id, "Solicitante")
    return tenant, solicitante_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.anexo_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_versao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.pedido_ajuste WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
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

    Cópia enxuta do helper homônimo em `test_pagamentos_fluxo_gestor.py`
    (mesmo padrão, sem os campos que este arquivo não usa)."""
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

        from sqlalchemy import select

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
                valor_total=Decimal("5000.00"), categoria="SERVICOS",
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
    return debito


@pytest.mark.asyncio
async def test_debito_em_ajuste_com_pedido_aberto_nao_e_orfao(admin_engine):
    """Invariante que o backfill sintético da 0105 garante: todo débito em
    situação AJUSTE_* tem >= 1 pedido_ajuste não-CANCELADO. Simula o cenário
    que a migration criou em massa para dados pré-F2 — débito AJUSTE_* mais
    um pedido ABERTO amarrado — e confirma que a consulta de órfãos (a mesma
    que a Task 3 vai usar para achar pendências reais) dá zero.
    """
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE pagamentos.debito SET situacao_tramitacao='AJUSTE_VALIDACAO' WHERE id=:id"),
            {"id": debito.id},
        )
        await s.execute(
            text(
                "INSERT INTO pagamentos.debito_historico "
                "(tenant_id, id_debito, status_novo, acao, justificativa, id_usuario, criado_em) "
                "VALUES (:t, :d, 'AJUSTE_VALIDACAO', 'AJUSTE_SOLICITADO', 'Falta anexo', :u, now())"
            ),
            {"t": tenant.id, "d": debito.id, "u": solicitante_id},
        )
        await s.execute(
            text(
                "INSERT INTO pagamentos.pedido_ajuste "
                "(tenant_id, id_debito, versao_debito, etapa_solicitante, id_usuario_solicitante, "
                " motivo, descricao, transacao_responsavel, tipo, situacao, criado_em) "
                "VALUES (:t, :d, 1, 'VALIDACAO', :u, 'Falta anexo', 'Falta anexo do contrato', "
                " 'pagamento_solicitar', 'NAO_MATERIAL', 'ABERTO', now())"
            ),
            {"t": tenant.id, "d": debito.id, "u": solicitante_id},
        )
        await s.commit()

    try:
        async with _sm(admin_engine)() as s:
            orfaos = (await s.execute(_ORFAOS_SQL, {"t": tenant.id})).scalar_one()
        assert orfaos == 0
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_debito_em_ajuste_sem_pedido_e_encontrado_como_orfao(admin_engine):
    """Inverso do teste acima (prova por inversão): sem inserir o
    pedido_ajuste, a MESMA consulta de invariante acha o débito órfão — isso
    prova que a consulta de fato mede o que o backfill da 0105 resolve, e não
    passa vazia por acidente."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE pagamentos.debito SET situacao_tramitacao='AJUSTE_GESTOR' WHERE id=:id"),
            {"id": debito.id},
        )
        await s.commit()

    try:
        async with _sm(admin_engine)() as s:
            orfaos = (await s.execute(_ORFAOS_SQL, {"t": tenant.id})).scalar_one()
        assert orfaos == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# Task 2 — CAMPOS_MATERIAIS + versionamento em atualizar_debito
# --------------------------------------------------------------------------


def test_toda_coluna_de_debito_tem_decisao_de_materialidade():
    """Guarda de materialidade: toda coluna de `Debito` precisa estar
    classificada em CAMPOS_MATERIAIS, CAMPOS_NAO_MATERIAIS ou CAMPOS_CONTROLE.
    Coluna nova sem decisão reprova este teste."""
    from app.models.pagamentos import Debito
    from app.services import pagamentos_versionamento as pv

    colunas = {c.key for c in Debito.__table__.columns}
    classificadas = pv.CAMPOS_MATERIAIS | pv.CAMPOS_NAO_MATERIAIS | pv.CAMPOS_CONTROLE
    assert colunas - classificadas == set(), (
        f"Colunas sem decisão de materialidade: {colunas - classificadas}. "
        "Coluna nova em Debito exige classificação explícita em pagamentos_versionamento.py"
    )
    assert pv.CAMPOS_MATERIAIS & pv.CAMPOS_NAO_MATERIAIS == set()


async def _levar_ate_ajuste_validacao(engine, tenant_id, debito, solicitante_id, gestor_id, validador_id):
    """Percorre o fluxo real até AJUSTE_VALIDACAO: criar (já feito pelo
    caller) → enviar ao gestor → gestor autoriza → validador solicita ajuste."""
    async with _sm(engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version,
        )
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
    return debito


@pytest.mark.asyncio
async def test_alteracao_material_em_ajuste_cria_versao_e_incrementa(admin_engine):
    """Débito em AJUSTE_VALIDACAO: mudar valor_total (campo material) cria uma
    DebitoVersao com o valor ANTIGO e incrementa debito.versao."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.models.pagamentos import DebitoVersao
    from app.schemas.pagamentos import DebitoUpdate, ParcelaCreate

    tenant, solicitante_id = await _provisionar(admin_engine)
    gestor_id = await _criar_usuario(admin_engine, tenant.id, "Gestor")
    validador_id = await _criar_usuario(admin_engine, tenant.id, "Validador")
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    valor_antigo = debito.valor_total

    debito = await _levar_ate_ajuste_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id, validador_id)
    assert debito.situacao_tramitacao == "AJUSTE_VALIDACAO"
    assert debito.versao == 1

    try:
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_debito(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                payload=DebitoUpdate(
                    valor_total=Decimal("1500.00"),
                    parcelas=[ParcelaCreate(numero=1, valor=Decimal("1500.00"), vencimento="2026-02-01")],
                ),
            )
        assert atualizado.versao == 2
        assert atualizado.valor_total == Decimal("1500.00")

        async with _sm(admin_engine)() as s:
            versoes = (await s.execute(select(DebitoVersao).where(
                DebitoVersao.tenant_id == tenant.id, DebitoVersao.id_debito == debito.id
            ))).scalars().all()
        assert len(versoes) == 1
        assert versoes[0].versao == 1
        assert Decimal(str(versoes[0].dados["valor_total"])) == valor_antigo
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_alteracao_nao_material_nao_cria_versao(admin_engine):
    """Mudar criticidade (não-material) em AJUSTE_VALIDACAO não cria versão
    nem incrementa debito.versao."""
    from sqlalchemy import select

    from app.models.pagamentos import DebitoVersao
    from app.schemas.pagamentos import DebitoUpdate

    tenant, solicitante_id = await _provisionar(admin_engine)
    gestor_id = await _criar_usuario(admin_engine, tenant.id, "Gestor")
    validador_id = await _criar_usuario(admin_engine, tenant.id, "Validador")
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    debito = await _levar_ate_ajuste_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id, validador_id)
    assert debito.criticidade != "ALTA"

    try:
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_debito(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                payload=DebitoUpdate(criticidade="ALTA"),
            )
        assert atualizado.versao == 1
        assert atualizado.criticidade == "ALTA"

        async with _sm(admin_engine)() as s:
            versoes = (await s.execute(select(DebitoVersao).where(
                DebitoVersao.tenant_id == tenant.id, DebitoVersao.id_debito == debito.id
            ))).scalars().all()
        assert versoes == []
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_edicao_em_rascunho_nao_versiona(admin_engine):
    """Débito em RASCUNHO: mudar descricao (material) NÃO versiona —
    versionamento só existe pós-etapa (em ajuste)."""
    from sqlalchemy import select

    from app.models.pagamentos import DebitoVersao
    from app.schemas.pagamentos import DebitoUpdate

    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    assert debito.situacao_tramitacao == "RASCUNHO"

    try:
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_debito(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                payload=DebitoUpdate(descricao="Débito de Teste — revisado"),
            )
        assert atualizado.versao == 1
        assert atualizado.descricao == "Débito de Teste — revisado"

        async with _sm(admin_engine)() as s:
            versoes = (await s.execute(select(DebitoVersao).where(
                DebitoVersao.tenant_id == tenant.id, DebitoVersao.id_debito == debito.id
            ))).scalars().all()
        assert versoes == []
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_edicao_fora_de_rascunho_e_ajuste_e_409(admin_engine):
    """Débito AGUARDANDO_GESTOR (nem rascunho, nem ajuste): atualizar_debito
    devolve 409 — comportamento preservado da F1."""
    from fastapi import HTTPException

    from app.schemas.pagamentos import DebitoUpdate

    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version,
        )
    assert debito.situacao_tramitacao == "AGUARDANDO_GESTOR"

    try:
        with pytest.raises(HTTPException) as exc_info:
            async with _sm(admin_engine)() as s:
                await svc.atualizar_debito(
                    s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                    payload=DebitoUpdate(criticidade="ALTA"),
                )
        assert exc_info.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)
