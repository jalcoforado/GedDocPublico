"""Transporte P5.3 — atraso, faltosos, suspensão, reativação e notificação.

Spec: `docs/superpowers/specs/2026-08-05-transporte-p5.3-atraso-suspensao-design.md`.

Três testes carregam esta fatia:

`test_ajustar_prazo_tira_da_lista_de_faltosos_na_hora` — a prova de que o atraso
é **derivado**. Se um dia alguém persistir o estado numa coluna, este teste fica
vermelho, porque nada recalcularia a coluna no ajuste de prazo.

`test_esta_em_atraso_e_o_sql_concordam` — a mesma regra existe em Python
(`esta_em_atraso`, usada por chamador futuro) e em SQL (`_condicao_em_atraso`,
usada pela consulta). Duas expressões da mesma regra é exatamente o que produz
teste verde e tela errada; este compara as duas sobre o mesmo conjunto.

`test_suspensa_recusa_checklist_e_decisao` — comportamento **herdado**: a
suspensão bloqueia porque `suspenso` não está em `SITUACOES_ABERTAS`, sem uma
linha de código nova. Comportamento que ninguém escreveu é o que some no
próximo refactor, então fica afirmado.

As fixtures vêm do arquivo da P5.2 — duplicá-las faria as duas baterias
divergirem em silêncio sobre o que é um cenário válido.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.models import RecadastramentoDecisao, RecadastramentoNotificacao
from app.schemas.transporte_regulado import (
    RecadastramentoAjustePrazo,
    RecadastramentoCicloCreate,
    RecadastramentoDecisaoInput,
)
from app.main import app
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _convocacao,
    _cria_usuario_comum_transporte,
    _encerrar_arreio,
    _empresa,
    _item,
    _marcar,
    _permissionario,
    _provisionar,
    _sm,
    _um_usuario,
)

HOJE = date.today()
# Ciclo inteiramente no passado: toda convocação nasce com prazo vencido.
VENCIDO_INICIO = HOJE - timedelta(days=60)
VENCIDO_FIM = HOJE - timedelta(days=30)


def _parecer(texto: str = "Não compareceu ao recadastramento.") -> RecadastramentoDecisaoInput:
    return RecadastramentoDecisaoInput(parecer=texto)


async def _com_contato(engine, tenant_id: int, perm):
    """`_permissionario` da P5.2 não preenche contato — e é o padrão certo lá,
    porque `email` e `telefone` são anuláveis de verdade. Aqui o contato tem de
    ser explícito, senão o teste do lote compara sem_contato com sem_contato e
    passa sem provar nada."""
    async with _sm(engine)() as db:
        alvo = await db.get(type(perm), perm.id)
        alvo.email = f"{uuid.uuid4().hex[:8]}@regulado.test"
        alvo.telefone = "5588999990000"
        await db.commit()
    return perm


async def _ciclo_atravessando_hoje(engine, tenant_id: int):
    """Janela do passado ATÉ o futuro.

    `ajustar_prazo` recusa data fora da janela do ciclo, então num ciclo
    inteiramente vencido não há para onde prorrogar — e o teste do atraso
    derivado precisa justamente mover o prazo para o futuro.
    """
    async with _sm(engine)() as db:
        return await tr.criar_ciclo(
            db,
            tenant_id=tenant_id,
            payload=RecadastramentoCicloCreate(
                nome=f"Atravessa {uuid.uuid4().hex[:6]}",
                data_inicio=VENCIDO_INICIO,
                data_fim=HOJE + timedelta(days=30),
                criterio_escalonamento="sem_escalonamento",
            ),
        )


async def _ciclo_vencido(engine, tenant_id: int):
    async with _sm(engine)() as db:
        return await tr.criar_ciclo(
            db,
            tenant_id=tenant_id,
            payload=RecadastramentoCicloCreate(
                nome=f"Vencido {uuid.uuid4().hex[:6]}",
                data_inicio=VENCIDO_INICIO,
                data_fim=VENCIDO_FIM,
                criterio_escalonamento="sem_escalonamento",
            ),
        )


# ============================== atraso derivado ==============================


@pytest.mark.asyncio
async def test_ajustar_prazo_tira_da_lista_de_faltosos_na_hora(admin_engine):
    """A prova de que o atraso é derivado: sem job, sem coluna, sem recálculo."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    # Nasce no prazo (data_fim futura) e é atrasado à mão — assim o mesmo teste
    # prova as duas direções: entrar em atraso e sair dele.
    async with _sm(admin_engine)() as db:
        await tr.ajustar_prazo(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=HOJE - timedelta(days=5),
                justificativa="Prazo retroativo para o cenário do teste",
            ),
            usuario_id=uid,
        )

    async with _sm(admin_engine)() as db:
        antes = await tr.listar_faltosos(db, tenant_id=tid, ciclo_id=ciclo.id)
    assert antes["kpis"]["em_atraso"] == 1
    assert [i["id"] for i in antes["itens"]] == [conv.id]
    assert antes["itens"][0]["dias_atraso"] > 0

    async with _sm(admin_engine)() as db:
        await tr.ajustar_prazo(
            db,
            tenant_id=tid,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=HOJE + timedelta(days=10),
                justificativa="Prorrogado por decisão do gestor",
            ),
            usuario_id=uid,
        )

    async with _sm(admin_engine)() as db:
        depois = await tr.listar_faltosos(db, tenant_id=tid, ciclo_id=ciclo.id)
    assert depois["kpis"]["em_atraso"] == 0, (
        "o atraso não acompanhou o ajuste de prazo — sinal de que virou "
        "estado persistido em vez de derivado"
    )
    assert depois["itens"] == []


@pytest.mark.asyncio
async def test_esta_em_atraso_e_o_sql_concordam(admin_engine):
    """A regra em Python e a regra em SQL têm de dar o mesmo conjunto."""
    t = await _provisionar(admin_engine)
    tid = t.id
    ciclo = await _ciclo_vencido(admin_engine, tid)
    await _permissionario(admin_engine, tid, nome="Atrasado A")
    await _empresa(admin_engine, tid, razao="Atrasada B")
    await _convocacao(
        admin_engine, tid,
        await _permissionario(admin_engine, tid, nome="Atrasado C"),
        ciclo=ciclo,
    )

    async with _sm(admin_engine)() as db:
        todas, _t = await tr.listar_convocacoes(
            db, tenant_id=tid, ciclo_id=ciclo.id, limit=500
        )
        convs = [
            await tr.obter_convocacao(db, tenant_id=tid, convocacao_id=i["id"])
            for i in todas
        ]
        por_python = {c.id for c in convs if tr.esta_em_atraso(c, HOJE)}
        relatorio = await tr.listar_faltosos(
            db, tenant_id=tid, ciclo_id=ciclo.id, hoje=HOJE, limit=500
        )
    por_sql = {i["id"] for i in relatorio["itens"]}

    assert por_python, "cenário montado errado: ninguém em atraso"
    assert por_python == por_sql


@pytest.mark.asyncio
async def test_decidido_nao_conta_como_atraso(admin_engine):
    """Controle: atraso é só de quem ainda está aberto.

    Sem isto, `_condicao_em_atraso` poderia esquecer o filtro de situação e o
    relatório listaria como faltoso quem já foi indeferido — justamente o
    contrário de faltar.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        antes = await tr.listar_faltosos(db, tenant_id=tid, ciclo_id=ciclo.id)
    assert antes["kpis"]["em_atraso"] == 1

    async with _sm(admin_engine)() as db:
        await tr.decidir_recadastramento(
            db, tenant_id=tid, convocacao_id=conv.id, tipo="indeferimento",
            payload=_parecer("Documentação não apresentada."), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        depois = await tr.listar_faltosos(db, tenant_id=tid, ciclo_id=ciclo.id)
    assert depois["kpis"]["em_atraso"] == 0
    assert depois["kpis"]["atendidos"] == 1


# ================================= suspensão =================================


@pytest.mark.asyncio
async def test_suspender_dentro_do_prazo_e_409(admin_engine):
    """Suspender quem está no prazo é erro de operação, não escolha."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm)  # ciclo corrente
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.suspender_convocacao(
                db, tenant_id=tid, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid,
            )
    assert e.value.status_code == 409
    assert "Prazo ainda não venceu" in e.value.detail


@pytest.mark.asyncio
async def test_suspender_vencido_e_depois_ja_suspensa_e_409(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        decisao = await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    assert decisao.tipo == "suspensao"

    async with _sm(admin_engine)() as db:
        recarregada = await tr.obter_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id
        )
    assert recarregada.situacao == tr.SITUACAO_SUSPENSO

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.suspender_convocacao(
                db, tenant_id=tid, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid,
            )
    assert e.value.status_code == 409
    assert "já está suspensa" in e.value.detail


@pytest.mark.asyncio
async def test_suspensa_recusa_checklist_e_decisao(admin_engine):
    """Comportamento HERDADO de `SITUACOES_ABERTAS`, afirmado de propósito.

    E a mensagem tem de mandar REATIVAR, não reabrir: a antiga mandaria o
    operador para a porta errada.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    item = await _item(admin_engine, tid)
    uid = await _um_usuario(admin_engine, tid)

    # Controle positivo: antes de suspender, marcar funciona.
    await _marcar(admin_engine, tid, conv.id, item.id, uid=uid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )

    with pytest.raises(HTTPException) as e_marca:
        await _marcar(admin_engine, tid, conv.id, item.id, uid=uid)
    assert e_marca.value.status_code == 409
    assert "reative" in e_marca.value.detail.lower()

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e_dec:
            await tr.decidir_recadastramento(
                db, tenant_id=tid, convocacao_id=conv.id, tipo="deferimento",
                payload=_parecer("Tudo certo."), usuario_id=uid,
            )
    assert e_dec.value.status_code == 409
    assert "reative" in e_dec.value.detail.lower()


@pytest.mark.asyncio
async def test_reabrir_suspensa_manda_reativar(admin_engine):
    """Reabertura e reativação não são portas alternativas para o mesmo estado."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.reabrir_recadastramento(
                db, tenant_id=tid, convocacao_id=conv.id,
                payload=_parecer("Revisão."), usuario_id=uid,
            )
    assert e.value.status_code == 409
    assert "reativar" in e.value.detail.lower()


# ================================= reativação =================================


@pytest.mark.asyncio
async def test_reativar_o_que_nao_esta_suspenso_e_409(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.reativar_convocacao(
                db, tenant_id=tid, convocacao_id=conv.id,
                payload=_parecer("Recurso deferido."), usuario_id=uid,
            )
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_reativacao_volta_para_convocado_e_preserva_a_trilha(admin_engine):
    """Reativar recomeça o atendimento, mas não apaga marca nem decisão."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    item = await _item(admin_engine, tid)
    uid = await _um_usuario(admin_engine, tid)

    await _marcar(admin_engine, tid, conv.id, item.id, uid=uid)
    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        decisao = await tr.reativar_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer("Recurso deferido."), usuario_id=uid,
        )
    assert decisao.tipo == "reativacao"

    async with _sm(admin_engine)() as db:
        recarregada = await tr.obter_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id
        )
        trilha = await tr.listar_decisoes(
            db, tenant_id=tid, convocacao_id=conv.id
        )
        estado = await tr.estado_do_checklist(
            db, tenant_id=tid, convocacao_id=conv.id
        )
    assert recarregada.situacao == "convocado"
    assert [d.tipo for d in trilha] == ["suspensao", "reativacao"]
    marcados = [i for i in estado if i["marcado"] is True]
    assert marcados, "a reativação apagou a marcação — deveria preservar"


# =============================== notificação ===============================


@pytest.mark.asyncio
async def test_faltoso_sem_contato_nao_derruba_o_lote(admin_engine):
    """`email` e `telefone` são anuláveis: cadastro incompleto é caso comum."""
    t = await _provisionar(admin_engine)
    tid = t.id
    com_contato = await _com_contato(
        admin_engine, tid,
        await _permissionario(admin_engine, tid, nome="Com Contato"),
    )
    sem_contato = await _permissionario(admin_engine, tid, nome="Sem Contato")
    async with _sm(admin_engine)() as db:
        alvo = await db.get(type(sem_contato), sem_contato.id)
        alvo.email = None
        alvo.telefone = None
        await db.commit()

    ciclo = await _ciclo_vencido(admin_engine, tid)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=tid, ciclo_id=ciclo.id)
    async with _sm(admin_engine)() as db:
        convs, _t = await tr.listar_convocacoes(
            db, tenant_id=tid, ciclo_id=ciclo.id, limit=500
        )
    por_nome = {c["nome_regulado"]: c["id"] for c in convs}
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        resultados = await tr.notificar_faltosos(
            db,
            tenant_id=tid,
            ciclo_id=ciclo.id,
            convocacao_ids=[
                por_nome[sem_contato.nome], por_nome[com_contato.nome]
            ],
            usuario_id=uid,
        )

    por_conv = {r["id_convocacao"]: r["resultado"] for r in resultados}
    assert por_conv[por_nome[sem_contato.nome]] == "sem_contato"
    assert por_conv[por_nome[com_contato.nome]] == "enviada", (
        "o cadastro incompleto derrubou o resto do lote"
    )

    async with _sm(admin_engine)() as db:
        linhas = (
            await db.execute(
                select(RecadastramentoNotificacao.id_convocacao).where(
                    RecadastramentoNotificacao.tenant_id == tid
                )
            )
        ).scalars().all()
    assert set(linhas) == {por_nome[com_contato.nome]}, (
        "registrou envio para quem não tinha contato"
    )


@pytest.mark.asyncio
async def test_notificar_duas_vezes_cria_duas_linhas(admin_engine):
    """O log não deduplica: é a contagem de avisos que justifica a suspensão."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _com_contato(
        admin_engine, tid, await _permissionario(admin_engine, tid)
    )
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    for _ in range(2):
        async with _sm(admin_engine)() as db:
            await tr.notificar_faltosos(
                db, tenant_id=tid, ciclo_id=ciclo.id,
                convocacao_ids=[conv.id], usuario_id=uid,
            )

    async with _sm(admin_engine)() as db:
        total = (
            await db.execute(
                select(func.count(RecadastramentoNotificacao.id)).where(
                    RecadastramentoNotificacao.tenant_id == tid,
                    RecadastramentoNotificacao.id_convocacao == conv.id,
                )
            )
        ).scalar_one()
        relatorio = await tr.listar_faltosos(
            db, tenant_id=tid, ciclo_id=ciclo.id
        )
    assert total >= 2
    assert relatorio["itens"][0]["ultima_notificacao"] is not None


@pytest.mark.asyncio
async def test_notificar_convocacao_de_outro_ciclo_e_400(admin_engine):
    """Controle do lote: id solto não pode ser notificado sob o ciclo errado."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo_a = await _ciclo_vencido(admin_engine, tid)
    _c, conv_a = await _convocacao(admin_engine, tid, perm, ciclo=ciclo_a)
    ciclo_b = await _ciclo_vencido(admin_engine, tid)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.notificar_faltosos(
                db, tenant_id=tid, ciclo_id=ciclo_b.id,
                convocacao_ids=[conv_a.id], usuario_id=uid,
            )
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_suspensao_nao_muda_a_situacao_do_permissionario(admin_engine):
    """Decisão do Jorge: a suspensão atinge SÓ a convocação.

    Sem este teste, "melhorar" a suspensão para refletir no cadastro passaria
    despercebido — e teria efeito em alvará, veículo e nas telas do módulo
    inteiro.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    situacao_antes = perm.situacao
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        recarregado = await db.get(type(perm), perm.id)
        assert recarregado.situacao == situacao_antes


@pytest.mark.asyncio
async def test_suspensao_exige_parecer_nas_duas_camadas(admin_engine):
    """Parecer em branco não vira suspensão — e são duas barreiras, não uma.

    O schema tem validador próprio que recusa branco, então pela API a
    requisição morre em 422 antes do serviço. O `if not parecer` do serviço é
    segunda linha, alcançável só por chamada direta (teste, CLI, rotina
    futura). Afirmar só uma das duas deixaria a outra livre para sumir: se
    alguém relaxar o schema, o teste do serviço segura; se alguém apagar a
    checagem do serviço, o teste do schema segura.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    # Camada 1 — o schema.
    with pytest.raises(ValidationError):
        RecadastramentoDecisaoInput(parecer="      ")

    # Camada 2 — o serviço, com o schema deliberadamente contornado.
    em_branco = RecadastramentoDecisaoInput.model_construct(parecer="      ")
    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.suspender_convocacao(
                db, tenant_id=tid, convocacao_id=conv.id,
                payload=em_branco, usuario_id=uid,
            )
    assert e.value.status_code == 400

    async with _sm(admin_engine)() as db:
        nenhuma = (
            await db.execute(
                select(func.count(RecadastramentoDecisao.id)).where(
                    RecadastramentoDecisao.tenant_id == tid
                )
            )
        ).scalar_one()
    assert nenhuma == 0


# ============================== HTTP (P5.3) ==============================


@pytest.mark.asyncio
async def test_http_rito_da_suspensao_com_usuario_comum(admin_engine):
    """Faltosos → notificar → suspender → tentar mexer → reativar.

    Usuário COMUM, não super-usuário. Em `auth/perms.py` o bypass de SU retorna
    antes do `getattr(item, action)`, e foi assim que 10 rotas do transporte
    devolveram 500 por meses sem nenhum teste acusar. Toda rota nova desta
    fatia passa por aqui.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _com_contato(
            admin_engine, tenant.id,
            await _permissionario(admin_engine, tenant.id, nome="Faltoso HTTP"),
        )
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        base = "/api/v2/transporte-regulado/recadastramento"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(f"{base}/ciclos/{ciclo.id}/faltosos")
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert corpo["kpis"]["em_atraso"] == 1
            assert corpo["itens"][0]["id"] == conv.id
            assert corpo["itens"][0]["dias_atraso"] > 0
            assert corpo["itens"][0]["ultima_notificacao"] is None

            r = await client.post(
                f"{base}/ciclos/{ciclo.id}/notificar",
                json={"convocacao_ids": [conv.id]},
            )
            assert r.status_code == 200, r.text
            assert r.json()[0]["resultado"] == "enviada"

            r = await client.get(f"{base}/ciclos/{ciclo.id}/faltosos")
            assert r.json()["itens"][0]["ultima_notificacao"] is not None

            r = await client.post(
                f"{base}/convocacoes/{conv.id}/suspender",
                json={"parecer": "Nao compareceu apos notificacao."},
            )
            assert r.status_code == 200, r.text
            assert r.json()["tipo"] == "suspensao"

            # Suspensa sai dos faltosos e entra no contador de suspensos.
            r = await client.get(f"{base}/ciclos/{ciclo.id}/faltosos")
            assert r.json()["kpis"]["em_atraso"] == 0
            assert r.json()["kpis"]["suspensos"] == 1

            # E recusa deferimento, mandando REATIVAR e não reabrir.
            r = await client.post(
                f"{base}/convocacoes/{conv.id}/deferir",
                json={"parecer": "Tentativa indevida."},
            )
            assert r.status_code == 409, r.text
            assert "reative" in r.json()["detail"].lower()

            r = await client.post(
                f"{base}/convocacoes/{conv.id}/reativar",
                json={"parecer": "Recurso deferido pelo gestor."},
            )
            assert r.status_code == 200, r.text
            assert r.json()["tipo"] == "reativacao"

            # Reativada volta a contar como falta — o prazo segue vencido.
            r = await client.get(f"{base}/ciclos/{ciclo.id}/faltosos")
            assert r.json()["kpis"]["em_atraso"] == 1
            assert r.json()["kpis"]["suspensos"] == 0

            # A trilha inteira ficou registrada.
            r = await client.get(f"{base}/convocacoes/{conv.id}/decisoes")
            assert [d["tipo"] for d in r.json()] == ["suspensao", "reativacao"]
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(
                text(
                    "DELETE FROM transporte_regulado.recadastramento_notificacao "
                    "WHERE tenant_id=:t"
                ),
                {"t": tenant.id},
            )
            await s.execute(
                text("DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t"),
                {"t": tenant.id},
            )
            await s.commit()
        await _encerrar_arreio(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_suspender_no_prazo_e_409_e_nao_500(admin_engine):
    """Controle do usuário comum: a recusa tem de ser 409, nunca 500.

    O defeito histórico do módulo foi `action` inexistente devolvendo
    AttributeError → 500 só para não-SU. Um teste que aceitasse "deu erro"
    passaria por cima disso.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        perm = await _permissionario(admin_engine, tenant.id, nome="No Prazo")
        _c, conv = await _convocacao(admin_engine, tenant.id, perm)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/v2/transporte-regulado/recadastramento"
                f"/convocacoes/{conv.id}/suspender",
                json={"parecer": "Suspensao prematura."},
            )
        assert r.status_code == 409, r.text
        assert "Prazo ainda não venceu" in r.json()["detail"]
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)
