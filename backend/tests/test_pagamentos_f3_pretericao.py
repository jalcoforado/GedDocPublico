"""Pagamentos F3 (Task 5) — 409 ao preterir a ordem cronológica + exceção
formal (LRF/lei de licitações).

`assert_ordem_respeitada` entra no início de `liberar_parcelas` e
`pagar_parcela` (`services/pagamentos_autorizacao.py`), antes de qualquer
escrita: um débito só pode ser selecionado (liberado ou pago) se não houver
outro débito ELEGIVEL à frente, na MESMA chave `(id_unidade,
id_fonte_recursos, categoria, exercicio)`. `registrar_excecao` é o furo
formal (POST `/pagamentos/debitos/{id}/excecao-cronologica`,
`pagamento_autorizar`) — destrava o débito preterido.

Padrão de dados: copiado/adaptado de `test_pagamentos_autorizacao.py`
(`_base`, `_debito_aprovado`, `_debito_autorizado` com `base=` compartilhado
entre dois débitos, para caírem na MESMA chave da fila) e de
`test_rls_usuario_comum_pagamentos_frota.py` (usuário comum por HTTP).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.models.pagamentos import ExcecaoCronologica
from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate, FornecedorUpdate,
    GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_cronologia as cron
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http
from tests.fixtures.pagamentos import id_unidade_padrao

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _provisionar(engine):
    slug = _slug("pagpreter")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Preterição", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.posicao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.excecao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
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


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _fonte_conta(engine, tenant_id, *, saldo_inicial="10000.00"):
    async with _sm(engine)() as s:
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Preter", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
    return fonte, conta


async def _fornecedor(engine, tenant_id, *, nome="Fornecedor Preter LTDA"):
    async with _sm(engine)() as s:
        return await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome=nome))


async def _base_compartilhado(engine, tenant_id, *, saldo_inicial="10000.00"):
    """Fonte + conta + natureza + unidade compartilhadas entre dois débitos —
    é isso que os coloca na MESMA chave da fila cronológica."""
    async with _sm(engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id, saldo_inicial=saldo_inicial)
    return nat, fonte, conta, unidade_id


def _payload_debito(forn, nat, fonte, conta, *, unidade_id: int, valor="1000.00"):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
        id_conta=conta.id, id_unidade=unidade_id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        numero_ne=f"NE-{uuid.uuid4().hex[:8]}", categoria="SERVICOS",
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _debito_aprovado(engine, tenant_id, *, forn, nat, fonte, conta, unidade_id,
                           valor="1000.00"):
    """RASCUNHO → ... → ENVIADO_SECRETARIO (rito v2.0, com liquidação
    confirmada). Retorna (debito, solicitante_id, validador_id)."""
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    gestor = await _novo_usuario(engine, tenant_id, f"ges{uuid.uuid4().hex[:6]}")
    validador = await _novo_usuario(engine, tenant_id, f"val{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, fonte, conta,
                                                           unidade_id=unidade_id, valor=valor))
    async with _sm(engine)() as s:
        d = await deb.enviar_para_gestor(s, tenant_id=tenant_id, debito_id=d.id,
                                         usuario_id=solicitante, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.gestor_autorizar(s, tenant_id=tenant_id, debito_id=d.id,
                                       usuario_id=gestor, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id,
                                           usuario_id=validador)
        d = await deb.validar(s, tenant_id=tenant_id, debito_id=d.id,
                              usuario_id=validador, lock_version=d.lock_version)
    return d, solicitante, validador


async def _debito_autorizado(engine, tenant_id, *, forn, nat, fonte, conta, unidade_id,
                             valor="1000.00"):
    """RASCUNHO → ... → AUTORIZADO (ELEGIVEL na fila, se fornecedor regular e
    saldo suficiente). Retorna o débito atualizado."""
    d, _sol, _val = await _debito_aprovado(engine, tenant_id, forn=forn, nat=nat, fonte=fonte,
                                           conta=conta, unidade_id=unidade_id, valor=valor)
    autorizador = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=autorizador, id_natureza=None, valor_maximo="999999.00"))
    grupo = GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id])
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, grupos=[grupo])
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d


async def _dois_elegiveis(engine, tenant_id, *, saldo_inicial="10000.00", valor="1000.00"):
    """Dois débitos AUTORIZADOS + ELEGIVEL, mesma chave (fonte/unidade/
    categoria/exercicio), fornecedores distintos. `d1` liquidado/autorizado
    ANTES de `d2` — `marco_em` de `d1` fica mais cedo, então `d1` vem
    primeiro na fila. Retorna (d1, d2, fonte, conta)."""
    nat, fonte, conta, unidade_id = await _base_compartilhado(engine, tenant_id,
                                                              saldo_inicial=saldo_inicial)
    forn1 = await _fornecedor(engine, tenant_id, nome="Fornecedor Preter 1 LTDA")
    forn2 = await _fornecedor(engine, tenant_id, nome="Fornecedor Preter 2 LTDA")
    d1 = await _debito_autorizado(engine, tenant_id, forn=forn1, nat=nat, fonte=fonte,
                                  conta=conta, unidade_id=unidade_id, valor=valor)
    d2 = await _debito_autorizado(engine, tenant_id, forn=forn2, nat=nat, fonte=fonte,
                                  conta=conta, unidade_id=unidade_id, valor=valor)
    return d1, d2, fonte, conta


async def _situacao_fila(engine, tenant_id, debito_id) -> str | None:
    from app.models import PosicaoCronologica
    async with _sm(engine)() as s:
        p = (await s.execute(select(PosicaoCronologica).where(
            PosicaoCronologica.tenant_id == tenant_id,
            PosicaoCronologica.id_debito == debito_id,
        ))).scalar_one_or_none()
    return p.situacao if p else None


# ---------------------------------------------------------------------------
# HTTP (exceção cronológica)
# ---------------------------------------------------------------------------

async def _cria_usuario_comum(session, tenant_id: int, *, codigo_transacao: str) -> int:
    """Usuário de nível != 0 cujo grupo concede `codigo_transacao`. Cópia
    deliberada do padrão de `test_rls_usuario_comum_pagamentos_frota.py`."""
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
    transacao_id = (await session.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false LIMIT 1"
    ), {"c": codigo_transacao})).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'Usuario Comum', :email, '', :cpf, true, false,
                :app, 'interno')
        RETURNING id
    """), {
        "t": tenant_id, "email": f"comum-{uuid.uuid4().hex[:8]}@f3pret.test",
        "cpf": uuid.uuid4().hex[:11], "app": APP,
    })).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo Comum F3', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await session.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return int(uid)


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        arreio_tenant_http(tenant_id, tenant_slug)

    return _setup


@pytest_asyncio.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagar_o_primeiro_da_fila_passa(admin_engine):
    """Caminho feliz: nada preterido — liberar e pagar o 1º da fila passam."""
    t = await _provisionar(admin_engine)
    try:
        d1, _d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d1.id)
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                       parcela_ids=[parcelas[0].id])
        async with _sm(admin_engine)() as s:
            p = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                        parcela_id=parcelas[0].id, forma_pagamento="PIX")
        assert p.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_liberar_fora_de_ordem_e_409(admin_engine):
    """2 elegíveis; liberar o 2º sem liberar o 1º antes → 409 listando o 1º."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                           parcela_ids=[parcelas2[0].id])
            assert exc.value.status_code == 409
            assert f"#{d1.id}" in exc.value.detail

        # Nada mudou: a parcela do 2º continua A_PAGAR (all-or-nothing, sem
        # escrita nenhuma quando a guarda barra).
        async with _sm(admin_engine)() as s:
            p2 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id))[0]
        assert p2.status == "A_PAGAR"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_pagar_fora_de_ordem_e_409_com_preteridos(admin_engine):
    """2 elegíveis; pagar o 2º (mesmo com a parcela dele ainda A_PAGAR) → 409
    listando o 1º ELEGIVEL à frente. A guarda de ordem entra ANTES da
    validação de status da parcela/débito, então nem precisa liberar o 2º
    para provar o 409 específico de ordem."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                        parcela_id=parcelas2[0].id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
            assert f"#{d1.id}" in exc.value.detail
            assert "posição" in exc.value.detail
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_bloqueado_a_frente_nao_impede(admin_engine):
    """1º BLOQUEADA (fornecedor irregular), 2º ELEGIVEL → liberar e pagar o
    2º passam: só ELEGIVEL à frente bloqueia (Ruling 5)."""
    t = await _provisionar(admin_engine)
    try:
        nat, fonte, conta, unidade_id = await _base_compartilhado(admin_engine, t.id)
        forn1 = await _fornecedor(admin_engine, t.id, nome="Fornecedor Bloqueado LTDA")
        forn2 = await _fornecedor(admin_engine, t.id, nome="Fornecedor Regular LTDA")
        d1 = await _debito_autorizado(admin_engine, t.id, forn=forn1, nat=nat, fonte=fonte,
                                      conta=conta, unidade_id=unidade_id)
        assert await _situacao_fila(admin_engine, t.id, d1.id) == cron.est.ELEGIVEL

        async with _sm(admin_engine)() as s:
            await cad.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=forn1.id,
                payload=FornecedorUpdate(situacao_cadastral="IRREGULAR", motivo_pendencia="CND vencida"))
        assert await _situacao_fila(admin_engine, t.id, d1.id) == cron.est.BLOQUEADA

        d2 = await _debito_autorizado(admin_engine, t.id, forn=forn2, nat=nat, fonte=fonte,
                                      conta=conta, unidade_id=unidade_id)
        assert await _situacao_fila(admin_engine, t.id, d2.id) == cron.est.ELEGIVEL

        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                       parcela_ids=[parcelas2[0].id])
        async with _sm(admin_engine)() as s:
            p = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                        parcela_id=parcelas2[0].id, forma_pagamento="PIX")
        assert p.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excecao_sobre_bloqueada_preserva_motivo(admin_engine):
    """Review (Important): a exceção fura ORDEM cronológica, não cura
    elegibilidade. Débito BLOQUEADA por fornecedor irregular continua
    BLOQUEADA (com o motivo preservado) mesmo depois de registrada a exceção
    — `tem_excecao` só troca o rótulo de quem JÁ chegaria a ELEGIVEL. Quando
    o fornecedor regulariza, a reavaliação seguinte pula direto para
    EXCECAO_AUTORIZADA (nunca passa por ELEGIVEL), porque a exceção já está
    registrada."""
    t = await _provisionar(admin_engine)
    try:
        nat, fonte, conta, unidade_id = await _base_compartilhado(admin_engine, t.id)
        forn = await _fornecedor(admin_engine, t.id, nome="Fornecedor Bloqueado Exc LTDA")
        d = await _debito_autorizado(admin_engine, t.id, forn=forn, nat=nat, fonte=fonte,
                                     conta=conta, unidade_id=unidade_id)
        assert await _situacao_fila(admin_engine, t.id, d.id) == cron.est.ELEGIVEL

        async with _sm(admin_engine)() as s:
            await cad.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=forn.id,
                payload=FornecedorUpdate(situacao_cadastral="IRREGULAR", motivo_pendencia="CND vencida"))
        assert await _situacao_fila(admin_engine, t.id, d.id) == cron.est.BLOQUEADA

        autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await cron.registrar_excecao(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=autoridade,
                justificativa="Urgência de saúde pública.",
                fundamento="Art. 5º, parágrafo único, Lei 8.666/93",
                data_autorizacao=date(2026, 8, 26))
            await s.commit()

        # A exceção FOI criada...
        async with _sm(admin_engine)() as s:
            excecoes = (await s.execute(select(ExcecaoCronologica).where(
                ExcecaoCronologica.tenant_id == t.id, ExcecaoCronologica.id_debito == d.id,
            ))).scalars().all()
        assert len(excecoes) == 1

        # ...mas a fila continua BLOQUEADA, com o motivo real preservado —
        # não mascarado por EXCECAO_AUTORIZADA/motivo=None.
        async with _sm(admin_engine)() as s:
            from app.models import PosicaoCronologica
            posicao = (await s.execute(select(PosicaoCronologica).where(
                PosicaoCronologica.tenant_id == t.id,
                PosicaoCronologica.id_debito == d.id,
            ))).scalar_one()
        assert posicao.situacao == cron.est.BLOQUEADA
        assert posicao.motivo_bloqueio == "Fornecedor com situação cadastral irregular."

        # Regulariza o fornecedor: a reavaliação disparada por
        # `atualizar_fornecedor` já enxerga `tem_excecao=True` e vai DIRETO
        # para EXCECAO_AUTORIZADA — nunca passa por ELEGIVEL.
        async with _sm(admin_engine)() as s:
            await cad.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=forn.id,
                payload=FornecedorUpdate(situacao_cadastral="REGULAR"))
        assert await _situacao_fila(admin_engine, t.id, d.id) == cron.est.EXCECAO_AUTORIZADA
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_filas_diferentes_nao_se_preterem(admin_engine):
    """Dois débitos ELEGIVEL, mas em fontes DISTINTAS (chaves diferentes) —
    pagar qualquer um dos dois primeiro não gera 409: filas independentes."""
    t = await _provisionar(admin_engine)
    try:
        nat, fonte1, conta1, unidade_id = await _base_compartilhado(admin_engine, t.id)
        fonte2, conta2 = await _fonte_conta(admin_engine, t.id)
        forn1 = await _fornecedor(admin_engine, t.id, nome="Fornecedor Fonte 1 LTDA")
        forn2 = await _fornecedor(admin_engine, t.id, nome="Fornecedor Fonte 2 LTDA")

        d1 = await _debito_autorizado(admin_engine, t.id, forn=forn1, nat=nat, fonte=fonte1,
                                      conta=conta1, unidade_id=unidade_id)
        d2 = await _debito_autorizado(admin_engine, t.id, forn=forn2, nat=nat, fonte=fonte2,
                                      conta=conta2, unidade_id=unidade_id)
        assert await _situacao_fila(admin_engine, t.id, d1.id) == cron.est.ELEGIVEL
        assert await _situacao_fila(admin_engine, t.id, d2.id) == cron.est.ELEGIVEL

        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        # Paga o SEGUNDO fisicamente primeiro — não é preterido de d1 porque
        # a chave (fonte) é outra.
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                       parcela_ids=[parcelas2[0].id])
        async with _sm(admin_engine)() as s:
            p2 = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                         parcela_id=parcelas2[0].id, forma_pagamento="PIX")
        assert p2.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excecao_destrava_e_fica_visivel(admin_engine, cliente):
    """HTTP: registrar exceção cronológica (pagamento_autorizar) no débito
    preterido → EXCECAO_AUTORIZADA na fila → liberar/pagar passam; a
    justificativa aparece no GET."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)

        async with _sm(admin_engine)() as s:
            uid = await _cria_usuario_comum(s, t.id, codigo_transacao="pagamento_autorizar")
            await s.commit()

        _as_user(admin_engine, uid, t.id, t.slug)()
        r = await cliente.post(
            f"/api/v2/pagamentos/debitos/{d2.id}/excecao-cronologica",
            json={
                "justificativa": "Urgência de saúde pública — fornecimento de insumos hospitalares.",
                "fundamento": "Art. 5º, parágrafo único, Lei 8.666/93 (LRF/licitações)",
                "data_autorizacao": "2026-08-26",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["fundamento"].startswith("Art. 5º")

        assert await _situacao_fila(admin_engine, t.id, d2.id) == cron.est.EXCECAO_AUTORIZADA

        r_get = await cliente.get(f"/api/v2/pagamentos/debitos/{d2.id}/excecao-cronologica")
        assert r_get.status_code == 200, r_get.text
        excecoes = r_get.json()
        assert len(excecoes) == 1
        assert "Urgência de saúde" in excecoes[0]["justificativa"]

        # Destravado: liberar e pagar o 2º agora passam, mesmo com o 1º ainda
        # ELEGIVEL à frente.
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                       parcela_ids=[parcelas2[0].id])
        async with _sm(admin_engine)() as s:
            p = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                        parcela_id=parcelas2[0].id, forma_pagamento="PIX")
        assert p.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excecao_sem_fundamento_e_422(admin_engine, cliente):
    """`fundamento` é obrigatório — payload sem ele é 422 (validação Pydantic,
    nem chega no service)."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = await _cria_usuario_comum(s, t.id, codigo_transacao="pagamento_autorizar")
            await s.commit()

        _as_user(admin_engine, uid, t.id, t.slug)()
        r = await cliente.post(
            f"/api/v2/pagamentos/debitos/{d2.id}/excecao-cronologica",
            json={
                "justificativa": "Urgência de saúde pública.",
                "data_autorizacao": "2026-08-26",
            },
        )
        assert r.status_code == 422, r.text
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excecao_por_usuario_sem_pagamento_autorizar_e_403(admin_engine, cliente):
    """Usuário comum com OUTRA permissão (não `pagamento_autorizar`) → 403."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = await _cria_usuario_comum(s, t.id, codigo_transacao="pagamento_solicitar")
            await s.commit()

        _as_user(admin_engine, uid, t.id, t.slug)()
        r = await cliente.post(
            f"/api/v2/pagamentos/debitos/{d2.id}/excecao-cronologica",
            json={
                "justificativa": "Urgência de saúde pública.",
                "fundamento": "Art. 5º, parágrafo único, Lei 8.666/93",
                "data_autorizacao": "2026-08-26",
            },
        )
        assert r.status_code == 403, r.text
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------------------
# FIX WAVE F3 item 2 (IMPORTANT) — débito já selecionado não pretere mais
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_selecionado_com_parcela_liberada_nao_pretere(admin_engine):
    """1º com parcela LIBERADA (chamada anterior) → liberar e pagar o 2º
    passam: a vez do 1º foi cumprida ao ser selecionado em ordem."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas1 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d1.id)
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                       parcela_ids=[parcelas1[0].id])

        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            liberadas2 = await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                                     parcela_ids=[parcelas2[0].id])
        assert liberadas2[0].status == "LIBERADA"

        async with _sm(admin_engine)() as s:
            paga2 = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario,
                                            parcela_id=parcelas2[0].id, forma_pagamento="PIX")
        assert paga2.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_lote_libera_dois_debitos_numa_chamada(admin_engine):
    """Lote com o 1º e o 2º da fila NUMA SÓ chamada de `liberar_parcelas` —
    hoje dá 409, porque o 1º só era escrito depois de checar o 2º; a vez do
    1º dentro do próprio lote tem de valer imediatamente."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas1 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d1.id)
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            liberadas = await aut.liberar_parcelas(
                s, tenant_id=t.id, usuario_id=usuario,
                parcela_ids=[parcelas1[0].id, parcelas2[0].id])
        assert len(liberadas) == 2
        assert all(p.status == "LIBERADA" for p in liberadas)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_elegivel_puro_continua_bloqueando_regressao(admin_engine):
    """Regressão: 1º ELEGIVEL "puro" (nenhuma parcela liberada, pagamento não
    iniciado) continua preterindo o 2º — o filtro novo só exclui quem já foi
    selecionado, não quem simplesmente está na frente na fila."""
    t = await _provisionar(admin_engine)
    try:
        d1, d2, _fonte, _conta = await _dois_elegiveis(admin_engine, t.id)
        usuario = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas2 = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario,
                                           parcela_ids=[parcelas2[0].id])
            assert exc.value.status_code == 409
            assert f"#{d1.id}" in exc.value.detail
    finally:
        await _cleanup(admin_engine, t.id)
