"""Testes do pedido de ajuste como entidade (F2, Task 3).

Até aqui (F1) o ajuste era só a transição `AJUSTE_*` mais uma justificativa
solta no histórico. Esta fatia dá ao pedido vida própria — `PedidoAjuste` —
com responsável (`transacao_responsavel`), materialidade (`tipo`), prazo e
ciclo `ABERTO -> RESPONDIDO/CANCELADO`.

Padrão de dados: `_provisionar`/`_criar_usuario`/`_setup_debito` copiados de
`test_pagamentos_fluxo_gestor.py` (atores reais — FK para `utils.usuario` não
aceita id fixo). Padrão HTTP: `_usuario_com`/`_get`/`_post`/`arreio_tenant_http`
copiados de `test_pagamentos_export_c13.py`.
"""
from __future__ import annotations

import uuid
from datetime import date as _date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_ajustes as ajustes
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


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
    slug = _slug("pagf2aj")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F2 Ajustes", admin_email=f"{slug}@t.local",
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

    Cópia do helper homônimo em `test_pagamentos_fluxo_gestor.py`."""
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
    return debito


async def _levar_ate_aguardando_validacao(engine, tenant_id, debito, solicitante_id, gestor_id):
    """Fluxo real: enviar ao gestor -> gestor autoriza -> AGUARDANDO_VALIDACAO."""
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


async def _levar_ate_aguardando_autoridade(engine, tenant_id, debito, solicitante_id, gestor_id,
                                           validador_id):
    """Fluxo real completo: gestor -> validador confirma liquidação + valida
    -> AGUARDANDO_AUTORIDADE. Usado pela Task 4 para exercitar AJUSTE_AUTORIDADE."""
    debito = await _levar_ate_aguardando_validacao(engine, tenant_id, debito, solicitante_id, gestor_id)
    async with _sm(engine)() as s:
        debito = await svc.confirmar_liquidacao(
            s, tenant_id=tenant_id, debito_id=debito.id, usuario_id=validador_id)
        debito = await svc.validar(
            s, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
        )
    return debito


# --------------------------------------------------------------------------
# Service — criação, pedido adicional, materialização
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solicitar_ajuste_cria_pedido_estruturado(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        result = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante",
            descricao="Falta o comprovante de liquidação anexado ao processo.",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    assert result.situacao_tramitacao == "AJUSTE_VALIDACAO"

    async with _sm(admin_engine)() as s:
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.situacao == "ABERTO"
    assert pedido.etapa_solicitante == "VALIDACAO"
    assert pedido.versao_debito == result.versao
    assert pedido.motivo == "Falta comprovante"
    assert pedido.transacao_responsavel == "pagamento_solicitar"
    assert pedido.tipo == "NAO_MATERIAL"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_pedido_adicional_na_mesma_etapa(admin_engine):
    """Débito já em AJUSTE_VALIDACAO: mais um pedido ABERTO, sem transição de
    estado — `ajustes.criar_pedido` é chamado direto (é o que o endpoint de
    pedido adicional faz depois de resolver a etapa)."""
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        assert d.situacao_tramitacao == "AJUSTE_VALIDACAO"
        pedido2 = await ajustes.criar_pedido(
            s, tenant_id=tenant.id, debito=d, usuario_id=validador_id, etapa="VALIDACAO",
            motivo="Falta também a nota", descricao="Segunda pendência da validação.",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        d2 = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
    assert len(pedidos) == 2
    assert {p.situacao for p in pedidos} == {"ABERTO"}
    assert d2.situacao_tramitacao == "AJUSTE_VALIDACAO", "pedido adicional não transiciona o débito"
    assert pedido2.id in {p.id for p in pedidos}
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_pedido_adicional_de_outra_etapa_e_409(admin_engine):
    """Débito fora de qualquer `AJUSTE_*` (ex.: AGUARDANDO_VALIDACAO): a rota
    de pedido adicional não sabe de qual etapa é responsável — 409, via HTTP."""
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)
    assert debito.situacao_tramitacao == "AGUARDANDO_VALIDACAO"

    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_validar"])
    body = {
        "motivo": "Tentativa fora de ajuste", "descricao": "Não deveria funcionar",
        "transacao_responsavel": "pagamento_solicitar", "tipo": "NAO_MATERIAL",
    }
    r = await _post(admin_engine, tenant.id, tenant.slug, uid,
                    f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste", body)
    assert r.status_code == 409, (r.status_code, r.text)
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_transacao_responsavel_desconhecida_e_422(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await svc.solicitar_ajuste(
                s, tenant_id=tenant.id, debito_id=debito.id,
                usuario_id=validador_id, lock_version=debito.lock_version,
                etapa="VALIDACAO", motivo="Motivo qualquer", descricao="Descrição qualquer",
                transacao_responsavel="transacao_que_nao_existe", tipo="NAO_MATERIAL",
            )
    assert exc.value.status_code == 422
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_responder_pedido_grava_resposta(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    async with _sm(admin_engine)() as s:
        resultado = await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=solicitante_id, resposta="Comprovante anexado ao processo.")
        await s.commit()

    assert resultado.situacao == "RESPONDIDO"
    assert resultado.resposta == "Comprovante anexado ao processo."
    assert resultado.id_usuario_resposta == solicitante_id
    assert resultado.respondido_em is not None
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_responder_pedido_ja_respondido_e_409(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    async with _sm(admin_engine)() as s:
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=solicitante_id, resposta="Primeira resposta.")
        await s.commit()

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await ajustes.responder_pedido(
                s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
                usuario_id=solicitante_id, resposta="Segunda resposta.")
    assert exc.value.status_code == 409
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_cancelar_pedido_pelo_solicitante(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    async with _sm(admin_engine)() as s:
        resultado = await ajustes.cancelar_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=validador_id)
        await s.commit()

    assert resultado.situacao == "CANCELADO"
    assert resultado.resolvido_em is not None
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_pedidos_pendentes_da_etapa_encontra_pedido_sintetico(admin_engine):
    """A invariante que a Task 3 assume (backfill 0105): um pedido inserido
    diretamente em SQL — como o backfill faz para débitos pré-F2 — sem passar
    por `criar_pedido`, ainda é achado por `pedidos_pendentes_da_etapa` desde
    que `situacao='ABERTO'` e `etapa_solicitante` batam."""
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE pagamentos.debito SET situacao_tramitacao='AJUSTE_VALIDACAO' WHERE id=:id"),
            {"id": debito.id},
        )
        await s.execute(
            text(
                "INSERT INTO pagamentos.pedido_ajuste "
                "(tenant_id, id_debito, versao_debito, etapa_solicitante, id_usuario_solicitante, "
                " motivo, descricao, transacao_responsavel, tipo, situacao, criado_em) "
                "VALUES (:t, :d, 1, 'VALIDACAO', :u, 'Pedido sintético', "
                " 'Pedido sintético criado pela migration 0105 (F2).', "
                " 'pagamento_solicitar', 'NAO_MATERIAL', 'ABERTO', now())"
            ),
            {"t": tenant.id, "d": debito.id, "u": solicitante_id},
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        pendentes = await ajustes.pedidos_pendentes_da_etapa(
            s, tenant_id=tenant.id, debito_id=debito.id, etapa="VALIDACAO")
    assert len(pendentes) == 1
    assert pendentes[0].situacao == "ABERTO"
    await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


async def _usuario_com(engine, tenant_id: int, codigos: list[str]) -> int:
    """Usuário NÃO super-usuário, com exatamente as transações pedidas."""
    async with _sm(engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one())
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Usuario Comum Ajuste', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"ajuste-{uuid.uuid4().hex[:8]}@f2.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Grupo Ajuste {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        for codigo in codigos:
            tr = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo=:c AND excluido=false LIMIT 1"
            ), {"c": codigo})).scalar_one()
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                VALUES (:t, :g, :tr, false, false, false, false)"""),
                {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


async def _get(engine, tenant_id, slug, usuario_id, caminho):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _post(engine, tenant_id, slug, usuario_id, caminho, body):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(caminho, json=body)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_http_usuario_comum_lista_pedidos(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, solicitante_id, gestor_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        slug = tenant.slug

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        r = await _get(admin_engine, tenant.id, slug, uid,
                       f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste")
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        assert len(corpo) == 1
        assert corpo[0]["situacao"] == "ABERTO"
        assert corpo[0]["etapa_solicitante"] == "VALIDACAO"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_pedido_cross_tenant_e_404(admin_engine):
    """Pedido do tenant A não é alcançável com o tenant B na sessão HTTP —
    mesmo com `debito_id`/`pedido_id` válidos NO OUTRO tenant."""
    tenant_a, sol_a, gestor_a, validador_a, _ = await _provisionar(admin_engine)
    debito_a = await _setup_debito(admin_engine, tenant_a.id, sol_a)
    debito_a = await _levar_ate_aguardando_validacao(
        admin_engine, tenant_a.id, debito_a, sol_a, gestor_a)

    async with _sm(admin_engine)() as s:
        debito_a = await svc.solicitar_ajuste(
            s, tenant_id=tenant_a.id, debito_id=debito_a.id,
            usuario_id=validador_a, lock_version=debito_a.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant_a.id, debito_id=debito_a.id)
        pedido_id = pedidos[0].id

    tenant_b, sol_b, gestor_b, validador_b, _ = await _provisionar(admin_engine)
    try:
        uid_b = await _usuario_com(admin_engine, tenant_b.id, ["pagamento_validar"])
        body = {"resposta": "Não deveria alcançar o pedido do outro tenant."}
        r = await _post(
            admin_engine, tenant_b.id, tenant_b.slug, uid_b,
            f"/api/v2/pagamentos/debitos/{debito_a.id}/pedidos-ajuste/{pedido_id}/responder",
            body)
        assert r.status_code == 404, (r.status_code, r.text[:300])
    finally:
        await _cleanup(admin_engine, tenant_a.id)
        await _cleanup(admin_engine, tenant_b.id)


@pytest.mark.asyncio
async def test_http_responder_pedido_sucesso_e_403_para_outra_transacao(admin_engine):
    """Fecha o buraco apontado no review: `responder` e `cancelar` são
    estruturalmente quase idênticos no router (mesmo padrão de 404 + checagem
    dinâmica) — só um teste HTTP prova que cada um está checando a
    permissão CERTA. Aqui: quem tem `transacao_responsavel` do pedido
    (`pagamento_solicitar`) responde com sucesso; quem só tem OUTRA
    permissão de pagamentos (`pagamento_gerir`) leva 403."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    try:
        # Usuário SEM a transacao_responsavel do pedido (tem só pagamento_gerir,
        # que passa pelo Depends de leitura mas não é 'pagamento_solicitar') → 403.
        uid_errado = await _usuario_com(admin_engine, tenant.id, ["pagamento_gerir"])
        r_403 = await _post(
            admin_engine, tenant.id, tenant.slug, uid_errado,
            f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste/{pedido_id}/responder",
            {"resposta": "Não deveria conseguir."})
        assert r_403.status_code == 403, (r_403.status_code, r_403.text[:300])

        # Usuário COM a transacao_responsavel do pedido ('pagamento_solicitar') → 200.
        uid_certo = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        r_200 = await _post(
            admin_engine, tenant.id, tenant.slug, uid_certo,
            f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste/{pedido_id}/responder",
            {"resposta": "Comprovante anexado ao processo."})
        assert r_200.status_code == 200, (r_200.status_code, r_200.text[:300])
        corpo = r_200.json()
        assert corpo["situacao"] == "RESPONDIDO"
        assert corpo["resposta"] == "Comprovante anexado ao processo."
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_cancelar_pedido_sucesso_pela_etapa_solicitante(admin_engine):
    """Par de `test_http_responder_pedido_...`: `cancelar` confere a permissão
    da etapa SOLICITANTE do pedido (`VALIDACAO` -> `pagamento_validar`), não a
    `transacao_responsavel` que `responder` usa — são checagens DIFERENTES, e
    só HTTP prova que o endpoint certo olha para o campo certo."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    try:
        # etapa_solicitante do pedido é VALIDACAO -> exige pagamento_validar.
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_validar"])
        r = await _post(
            admin_engine, tenant.id, tenant.slug, uid,
            f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste/{pedido_id}/cancelar",
            {})
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        assert corpo["situacao"] == "CANCELADO"
        assert corpo["resolvido_em"] is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_criar_pedido_adicional_sucesso(admin_engine):
    """O par positivo de `test_pedido_adicional_de_outra_etapa_e_409`: débito
    já em AJUSTE_VALIDACAO, POST /pedidos-ajuste via router com usuário que
    tem a transação da etapa ATUAL do débito (VALIDACAO -> pagamento_validar)
    → 201, pedido novo ABERTO, sem transicionar o débito."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_validar"])
        body = {
            "motivo": "Falta também a nota", "descricao": "Segunda pendência da validação.",
            "transacao_responsavel": "pagamento_solicitar", "tipo": "NAO_MATERIAL",
        }
        r = await _post(
            admin_engine, tenant.id, tenant.slug, uid,
            f"/api/v2/pagamentos/debitos/{debito.id}/pedidos-ajuste", body)
        assert r.status_code == 201, (r.status_code, r.text[:300])
        corpo = r.json()
        assert corpo["situacao"] == "ABERTO"
        assert corpo["etapa_solicitante"] == "VALIDACAO"

        async with _sm(admin_engine)() as s:
            pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
            d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        assert len(pedidos) == 2
        assert d.situacao_tramitacao == "AJUSTE_VALIDACAO", "pedido adicional não transiciona o débito"
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# Task 4 — reenvio com retorno correto + invalidação de aprovações
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reenvio_nao_material_volta_a_etapa_que_pediu(admin_engine):
    """AJUSTE_VALIDACAO, responder o pedido (sem alterar nada material),
    reenviar -> volta a AGUARDANDO_VALIDACAO (a etapa que pediu); o pedido
    fica RESOLVIDO."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    async with _sm(admin_engine)() as s:
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=sol, resposta="Comprovante anexado.")
        await s.commit()

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        resultado = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=d.lock_version)

    assert resultado.situacao_tramitacao == "AGUARDANDO_VALIDACAO"

    async with _sm(admin_engine)() as s:
        pedido = await ajustes.obter_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id)
    assert pedido.situacao == "RESOLVIDO"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_reenvio_com_alteracao_material_volta_ao_gestor(admin_engine):
    """AJUSTE_AUTORIDADE (débito já passou por gestor+validação): a unidade
    altera `valor_total` (materialidade -> versiona), responde e reenvia ->
    volta a AGUARDANDO_GESTOR, NÃO à autoridade que pediu; as aprovações de
    gestor e validador são invalidadas; histórico ganha a linha
    APROVACOES_INVALIDADAS citando a versão nova."""
    tenant, sol, gestor, validador, autoridade = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_autoridade(
        admin_engine, tenant.id, debito, sol, gestor, validador)
    assert debito.situacao_tramitacao == "AGUARDANDO_AUTORIDADE"

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=autoridade, lock_version=debito.lock_version,
            etapa="AUTORIDADE", motivo="Valor divergente", descricao="Confira o valor total",
            transacao_responsavel="pagamento_solicitar", tipo="MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id
    assert debito.situacao_tramitacao == "AJUSTE_AUTORIDADE"
    assert debito.versao == 1

    async with _sm(admin_engine)() as s:
        from app.schemas.pagamentos import DebitoUpdate
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        d = await svc.atualizar_debito(
            s, tenant_id=tenant.id, debito_id=d.id, usuario_id=sol,
            payload=DebitoUpdate(valor_total=Decimal("2000.00"),
                                 parcelas=[ParcelaCreate(numero=1, valor=Decimal("2000.00"),
                                                          vencimento="2026-02-01")]))
    assert d.versao == 2, "alteração material tem de versionar"

    async with _sm(admin_engine)() as s:
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=sol, resposta="Valor corrigido.")
        await s.commit()

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        resultado = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=d.lock_version)

    assert resultado.situacao_tramitacao == "AGUARDANDO_GESTOR"
    assert resultado.id_gestor_decisor is None
    assert resultado.id_validador is None

    async with _sm(admin_engine)() as s:
        hist = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
    invalidacao = [h for h in hist if h.acao == "APROVACOES_INVALIDADAS"]
    assert len(invalidacao) == 1
    assert "invalidadas pela versão 2" in invalidacao[0].justificativa
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_reenvio_material_com_pedido_cancelado_e_reaberto_volta_ao_gestor(admin_engine):
    """Cenário de fuga do review final: a autoridade abre um pedido (v1); a
    unidade edita `valor_total` (versiona -> v2); a autoridade CANCELA o
    pedido original e abre outro, que nasce já em v2; a unidade responde o
    novo pedido e reenvia. A materialidade não pode "esquecer" a edição só
    porque o pedido que a testemunhou foi cancelado e substituído — reenvio
    tem de voltar ao GESTOR com os decisores zerados, exatamente como no
    caso sem cancelamento (`test_reenvio_com_alteracao_material_volta_ao_gestor`).
    """
    tenant, sol, gestor, validador, autoridade = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_autoridade(
        admin_engine, tenant.id, debito, sol, gestor, validador)
    assert debito.situacao_tramitacao == "AGUARDANDO_AUTORIDADE"

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=autoridade, lock_version=debito.lock_version,
            etapa="AUTORIDADE", motivo="Valor divergente", descricao="Confira o valor total",
            transacao_responsavel="pagamento_solicitar", tipo="MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido1_id = pedidos[0].id
    assert debito.versao == 1

    async with _sm(admin_engine)() as s:
        from app.schemas.pagamentos import DebitoUpdate
        d = await svc.atualizar_debito(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=sol,
            payload=DebitoUpdate(valor_total=Decimal("2000.00"),
                                 parcelas=[ParcelaCreate(numero=1, valor=Decimal("2000.00"),
                                                          vencimento="2026-02-01")]))
    assert d.versao == 2, "alteração material tem de versionar"

    async with _sm(admin_engine)() as s:
        # A validação cancela o pedido que testemunhou a edição e abre outro
        # — este novo já nasce em versao_debito=2, "pós-edição".
        await ajustes.cancelar_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido1_id,
            usuario_id=autoridade)
        d2 = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido2 = await ajustes.criar_pedido(
            s, tenant_id=tenant.id, debito=d2, usuario_id=autoridade, etapa="AUTORIDADE",
            motivo="Valor ainda divergente", descricao="Confira de novo o valor total.",
            transacao_responsavel="pagamento_solicitar", tipo="MATERIAL",
        )
        await s.commit()
    assert pedido2.versao_debito == 2

    async with _sm(admin_engine)() as s:
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido2.id,
            usuario_id=sol, resposta="Valor corrigido de novo.")
        await s.commit()

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        resultado = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=d.lock_version)

    assert resultado.situacao_tramitacao == "AGUARDANDO_GESTOR", (
        "a edição material aconteceu antes do reenvio; cancelar e reabrir o "
        "pedido não pode apagar essa materialidade")
    assert resultado.id_gestor_decisor is None
    assert resultado.id_validador is None
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_reenvio_todos_cancelados_sem_alteracao_volta_a_etapa_de_origem(admin_engine):
    """Todos os pedidos da etapa foram CANCELADOS (nenhum RESPONDIDO) e não
    houve edição alguma no meio tempo -> reenvio não é material e volta à
    etapa que pediu o ajuste, como sempre. Cobre o minor deferido da T4:
    antes só havia teste para "um respondido + um cancelado", nunca para
    "todos cancelados"."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    async with _sm(admin_engine)() as s:
        await ajustes.cancelar_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id,
            usuario_id=validador)
        await s.commit()

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        resultado = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=d.lock_version)

    assert resultado.situacao_tramitacao == "AGUARDANDO_VALIDACAO"

    async with _sm(admin_engine)() as s:
        pedido = await ajustes.obter_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido_id)
    assert pedido.situacao == "CANCELADO", "pedido cancelado não é 'resolvido' pelo reenvio"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_reenvio_com_pedido_aberto_e_409(admin_engine):
    """Pedido ABERTO ainda não respondido -> responder_ajuste levanta 409 com
    a lista dos pendentes."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        with pytest.raises(HTTPException) as exc:
            await svc.responder_ajuste(
                s, tenant_id=tenant.id, debito_id=debito.id,
                usuario_id=sol, lock_version=d.lock_version)
    assert exc.value.status_code == 409
    assert "Falta comprovante" in exc.value.detail
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_reenvio_resolve_os_respondidos(admin_engine):
    """Dois pedidos abertos na mesma etapa: um respondido, outro cancelado.
    Reenvio passa (o cancelado não bloqueia); o RESPONDIDO vira RESOLVIDO."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido2 = await ajustes.criar_pedido(
            s, tenant_id=tenant.id, debito=d, usuario_id=validador, etapa="VALIDACAO",
            motivo="Falta também a nota", descricao="Segunda pendência.",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        await s.commit()
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido1_id = [p.id for p in pedidos if p.id != pedido2.id][0]

    async with _sm(admin_engine)() as s:
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido1_id,
            usuario_id=sol, resposta="Comprovante anexado.")
        await ajustes.cancelar_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido2.id,
            usuario_id=validador)
        await s.commit()

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        resultado = await svc.responder_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=d.lock_version)
    assert resultado.situacao_tramitacao == "AGUARDANDO_VALIDACAO"

    async with _sm(admin_engine)() as s:
        p1 = await ajustes.obter_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido1_id)
        p2 = await ajustes.obter_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedido2.id)
    assert p1.situacao == "RESOLVIDO"
    assert p2.situacao == "CANCELADO"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_historico_registra_dimensoes_e_versao(admin_engine):
    """Qualquer transição pós-F2 preenche versao_debito e os pares
    situacao_*_anterior/nova em DebitoHistorico."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=sol, lock_version=debito.lock_version)

    async with _sm(admin_engine)() as s:
        hist = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
    enviado = [h for h in hist if h.acao == "ENVIADO"][0]
    assert enviado.versao_debito == 1
    assert enviado.situacao_tramitacao_anterior == "RASCUNHO"
    assert enviado.situacao_tramitacao_nova == "AGUARDANDO_GESTOR"
    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_versao_anterior_recuperavel(admin_engine):
    """Após uma alteração material: GET /debitos/{id}/versoes devolve a
    versão 1, com o valor_total antigo, no corpo `dados`."""
    tenant, sol, gestor, validador, autoridade = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_autoridade(
        admin_engine, tenant.id, debito, sol, gestor, validador)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=autoridade, lock_version=debito.lock_version,
            etapa="AUTORIDADE", motivo="Valor divergente", descricao="Confira o valor",
            transacao_responsavel="pagamento_solicitar", tipo="MATERIAL",
        )

    async with _sm(admin_engine)() as s:
        from app.schemas.pagamentos import DebitoUpdate
        await svc.atualizar_debito(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=sol,
            payload=DebitoUpdate(valor_total=Decimal("2000.00"),
                                 parcelas=[ParcelaCreate(numero=1, valor=Decimal("2000.00"),
                                                          vencimento="2026-02-01")]))

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        r = await _get(admin_engine, tenant.id, tenant.slug, uid,
                       f"/api/v2/pagamentos/debitos/{debito.id}/versoes")
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        assert len(corpo) == 1
        assert corpo[0]["versao"] == 1
        assert Decimal(str(corpo[0]["dados"]["valor_total"])) == Decimal("1000.00")
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# minha-fila — pendências de ajuste endereçadas às transações do usuário (Task 6)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_minha_fila_lista_pendencia_ajuste_da_transacao_do_usuario(admin_engine):
    """Usuário comum com `pagamento_solicitar` vê, em `minha-fila`, o pedido
    ABERTO endereçado a essa transação."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
            prazo=_date(2026, 9, 1),
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        pedido_id = pedidos[0].id

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        r = await _get(admin_engine, tenant.id, tenant.slug, uid,
                       "/api/v2/pagamentos/minha-fila")
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        pendencias = corpo.get("pendencias_ajuste") or []
        assert len(pendencias) == 1
        item = pendencias[0]
        assert item["id_pedido"] == pedido_id
        assert item["id_debito"] == debito.id
        assert item["descricao_debito"] == "Débito de Teste"
        assert item["motivo"] == "Falta comprovante"
        assert item["prazo"] == "2026-09-01"
        assert item["etapa_solicitante"] == "VALIDACAO"
        assert item["criado_em"]
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_minha_fila_nao_lista_pendencia_de_transacao_que_usuario_nao_tem(admin_engine):
    """Usuário sem `pagamento_solicitar` (só `pagamento_validar`) não vê o
    pedido endereçado a `pagamento_solicitar`."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_validar"])
        r = await _get(admin_engine, tenant.id, tenant.slug, uid,
                       "/api/v2/pagamentos/minha-fila")
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        pendencias = corpo.get("pendencias_ajuste") or []
        assert len(pendencias) == 0
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_minha_fila_nao_lista_pendencia_respondida(admin_engine):
    """Pedido `RESPONDIDO` some da lista de pendências."""
    tenant, sol, gestor, validador, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, sol)
    debito = await _levar_ate_aguardando_validacao(
        admin_engine, tenant.id, debito, sol, gestor)

    async with _sm(admin_engine)() as s:
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
        await ajustes.responder_pedido(
            s, tenant_id=tenant.id, debito_id=debito.id, pedido_id=pedidos[0].id,
            usuario_id=sol, resposta="Comprovante anexado.")
        await s.commit()

    try:
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        r = await _get(admin_engine, tenant.id, tenant.slug, uid,
                       "/api/v2/pagamentos/minha-fila")
        assert r.status_code == 200, (r.status_code, r.text[:300])
        corpo = r.json()
        pendencias = corpo.get("pendencias_ajuste") or []
        assert len(pendencias) == 0
    finally:
        await _cleanup(admin_engine, tenant.id)
