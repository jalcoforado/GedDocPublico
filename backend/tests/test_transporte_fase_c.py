"""Transporte Fase C1 — gate de renovação de alvará para titular suspenso.

Spec: `docs/superpowers/specs/2026-08-23-transporte-p5-pendencias-design.md`
(seção "Fatia C1 — o gate de renovação").

`renovar_alvara` passa a recusar com 409 quando o titular (permissionário OU
empresa) do alvará tem convocação de recadastramento `suspenso` não excluída,
de qualquer ciclo. A mensagem manda para a reativação — não para a reabertura
(lição da P5.3: mensagem que aponta a porta errada custa um chamado por
ocorrência).

**Emitir alvará novo NÃO passa pelo gate** — só `renovar_alvara`. Há teste
afirmando as duas coisas, porque "melhorar" o gate para cobrir emissão é a
deriva mais provável.

As fixtures reaproveitam os helpers da P5.2/P5.3 — duplicá-las faria as
baterias divergirem em silêncio sobre o que é um cenário válido.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import RecadastramentoNotificacao
from app.models.notificacao import Notificacao
from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraRenovarInput,
    EmpresaCreate,
    RecadastramentoAjustePrazo,
)
from app.main import app
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from app.tasks.notificar_recadastramento import notificar_recadastramento
from tests.conftest import WORKER_URL
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _convocacao,
    _cria_usuario_comum_transporte,
    _empresa,
    _encerrar_arreio,
    _permissionario,
    _provisionar,
    _sm,
    _um_usuario,
)
from tests.test_transporte_p5_3_atraso import (
    _ciclo_atravessando_hoje,
    _ciclo_vencido,
    _com_contato,
    _parecer,
)

HOJE = date.today()


async def _alvara_vencido(engine, tenant_id: int, *, id_permissionario=None, id_empresa=None):
    async with _sm(engine)() as db:
        return await tr.criar_alvara(
            db,
            tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=f"ALV-FC-{uuid.uuid4().hex[:8]}",
                data_validade=HOJE - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=id_permissionario,
                id_empresa=id_empresa,
            ),
        )


async def _empresa_ativa(engine, tenant_id: int, *, razao="Empresa Fase C"):
    async with _sm(engine)() as db:
        return await tr.criar_empresa(
            db,
            tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social=razao,
                cnpj=str(uuid.uuid4().int)[:14],
                tipo_servico="taxi",
                situacao="ativa",
            ),
        )


@pytest.mark.asyncio
async def test_suspenso_nao_renova_alvara_e_a_mensagem_aponta_reativacao(admin_engine):
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

    alvara = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.renovar_alvara(
                db, tenant_id=tid, alvara_id=alvara.id,
                payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
            )
    assert e.value.status_code == 409
    assert "reativação" in e.value.detail


@pytest.mark.asyncio
async def test_reativado_volta_a_renovar(admin_engine):
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
        await tr.reativar_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer("Recurso deferido."), usuario_id=uid,
        )

    alvara = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)

    async with _sm(admin_engine)() as db:
        renovado = await tr.renovar_alvara(
            db, tenant_id=tid, alvara_id=alvara.id,
            payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
        )
    assert renovado.id != alvara.id
    assert renovado.renovado_de == alvara.id


@pytest.mark.asyncio
async def test_suspenso_ainda_emite_alvara_novo(admin_engine):
    """ANTI-DERIVA: `criar_alvara` (emissão) não passa pelo gate — só a renovação."""
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

    novo = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)
    assert novo.id is not None


@pytest.mark.asyncio
async def test_empresa_suspensa_bloqueia_renovacao_do_alvara_da_empresa(admin_engine):
    """Convocação de EMPRESA suspensa bloqueia renovação de alvará de empresa.

    Confere o vocabulário feminino `suspensa` (adjetivo em português para
    empresa) contra o valor REAL gravado na convocação — que é `SITUACAO_SUSPENSO`
    ("suspenso", sem flexão de gênero: é constante única do módulo). A armadilha
    nº 1 do módulo é assumir que o texto muda com o gênero do titular.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    emp = await _empresa_ativa(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, emp, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        recarregada = await tr.obter_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id
        )
    assert recarregada.situacao == "suspenso"
    assert recarregada.situacao == tr.SITUACAO_SUSPENSO

    alvara = await _alvara_vencido(admin_engine, tid, id_empresa=emp.id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.renovar_alvara(
                db, tenant_id=tid, alvara_id=alvara.id,
                payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
            )
    assert e.value.status_code == 409
    assert "reativação" in e.value.detail


@pytest.mark.asyncio
async def test_http_usuario_comum_toma_409_na_renovacao(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _permissionario(admin_engine, tenant.id, nome="Suspenso HTTP")
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)
        uid_dec = await _um_usuario(admin_engine, tenant.id)

        async with _sm(admin_engine)() as db:
            await tr.suspender_convocacao(
                db, tenant_id=tenant.id, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid_dec,
            )

        alvara = await _alvara_vencido(admin_engine, tenant.id, id_permissionario=perm.id)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"/api/v2/transporte-regulado/alvaras/{alvara.id}/renovar",
                json={"data_validade": (HOJE + timedelta(days=365)).isoformat()},
            )
        assert r.status_code == 409, r.text
        assert "reativação" in r.json()["detail"]
    finally:
        # `_encerrar_arreio` não conhece `alvara` (nasceu antes desta fatia
        # criar alvará em cima de um cenário HTTP); sem isto o DELETE de
        # permissionario dela esbarra na FK e mascara o resultado do teste.
        async with _sm(admin_engine)() as s:
            await s.execute(
                text("DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t"),
                {"t": tenant.id},
            )
            await s.commit()
        await _encerrar_arreio(admin_engine, tenant.id)


# ---------------------------------------------------------------------------
# Fase C2 — grants do `aprimora_worker` na migration 0094.
#
# TDD: `INSERT ... id_usuario=NULL` falha ANTES da 0094 (`id_usuario` ainda
# NOT NULL) com `NotNullViolation`, e falha de outro jeito (permission denied)
# se rodado antes dos GRANTs enumerados terem sido aplicados às tabelas que a
# 0078 não alcançou (`recadastramento_ciclo`, `recadastramento_convocacao`,
# `recadastramento_notificacao` nasceram depois do `GRANT ... ALL TABLES`
# daquela migration). Evidência RED capturada no relatório da task.
# ---------------------------------------------------------------------------


def _worker_sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.mark.asyncio
async def test_worker_le_as_quatro_tabelas_e_insere_notificacao_automatica(admin_engine):
    """`aprimora_worker` (0094) lê o necessário e insere envio automático.

    O job da Fase C não tem `id_usuario` (ninguém apertou o botão) — daí o
    INSERT com `id_usuario=None, gatilho='atraso'`. Antes da 0094 isto falha
    de duas formas possíveis: `NotNullViolation` (coluna ainda obrigatória)
    ou `permission denied` (grant ainda não concedido nas tabelas que a 0078
    não alcançou). É essa dupla falha que este teste prova estar corrigida.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)

    # Seed da `Notificacao` real que o motor `notificacoes.enviar` criaria —
    # via admin (bypass), porque semear cenário não é o que este teste prova.
    admin_sm = _sm(admin_engine)
    async with admin_sm() as db:
        db.add(
            Notificacao(
                tenant_id=tid,
                destinatario_email=f"worker-{uuid.uuid4().hex[:8]}@fasec.test",
                canal="email",
                tipo="recadastramento.faltoso",
                titulo="Recadastramento pendente",
                mensagem="Seu prazo venceu.",
                criado_em=datetime.utcnow(),
            )
        )
        await db.commit()
        notif_id = (
            await db.execute(
                text(
                    "SELECT id FROM aprimora_py.notificacao "
                    "WHERE tenant_id=:t ORDER BY id DESC LIMIT 1"
                ),
                {"t": tid},
            )
        ).scalar_one()

    engine = create_async_engine(WORKER_URL)
    notif_recad_id = None
    try:
        Session = _worker_sm(engine)
        async with Session() as s:
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
            for tabela in (
                "recadastramento_ciclo",
                "recadastramento_convocacao",
                "permissionario",
                "empresa",
            ):
                await s.execute(
                    text(f"SELECT count(*) FROM transporte_regulado.{tabela}")
                )

            notif_recad_id = (
                await s.execute(
                    text(
                        "INSERT INTO transporte_regulado.recadastramento_notificacao "
                        "(tenant_id, id_convocacao, id_notificacao, id_usuario, "
                        "gatilho, criado_em) "
                        "VALUES (:t, :c, :n, NULL, 'atraso', now()) RETURNING id"
                    ),
                    {"t": tid, "c": conv.id, "n": notif_id},
                )
            ).scalar_one()
            await s.commit()
    finally:
        await engine.dispose()
        async with admin_sm() as db:
            if notif_recad_id is not None:
                await db.execute(
                    text(
                        "DELETE FROM transporte_regulado.recadastramento_notificacao "
                        "WHERE id=:i"
                    ),
                    {"i": notif_recad_id},
                )
            await db.execute(
                text("DELETE FROM aprimora_py.notificacao WHERE id=:i"), {"i": notif_id}
            )
            await db.commit()
        await _encerrar_arreio(admin_engine, tid)


# ---------------------------------------------------------------------------
# Fase C2 — job diário `notificar_recadastramento` (migration 0094 + este PR).
#
# O ciclo de `_ciclo_atravessando_hoje` (P5.3) vai do passado até
# hoje+30 dias, então um único ciclo cobre as três janelas (atraso, lembrete,
# convocação) — basta mover o prazo com `tr.ajustar_prazo`.
# ---------------------------------------------------------------------------

DIAS_ANTES_PADRAO = 5


async def _prazo(engine, tenant_id: int, conv_id: int, uid: int, prazo):
    async with _sm(engine)() as db:
        await tr.ajustar_prazo(
            db,
            tenant_id=tenant_id,
            convocacao_id=conv_id,
            payload=RecadastramentoAjustePrazo(
                prazo=prazo, justificativa="Ajuste para cenário de teste do job"
            ),
            usuario_id=uid,
        )


async def _registros(engine, tenant_id: int, conv_id: int) -> list[tuple[str, int]]:
    async with _sm(engine)() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT gatilho, id_notificacao FROM "
                    "transporte_regulado.recadastramento_notificacao "
                    "WHERE tenant_id=:t AND id_convocacao=:c"
                ),
                {"t": tenant_id, "c": conv_id},
            )
        ).all()
    return [(g, n) for g, n in rows]


@pytest.mark.asyncio
async def test_job_convocacao_vencida_ganha_atraso(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    await _prazo(admin_engine, tid, conv.id, uid, HOJE - timedelta(days=2))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert [g for g, _n in regs] == ["atraso"]


@pytest.mark.asyncio
async def test_job_rodar_duas_vezes_nao_duplica(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    await _prazo(admin_engine, tid, conv.id, uid, HOJE - timedelta(days=2))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)
    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert [g for g, _n in regs] == ["atraso"], (
        "rodar duas vezes não pode duplicar nem cair para outra janela"
    )


@pytest.mark.asyncio
async def test_job_prazo_proximo_ganha_lembrete_nao_atraso(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    await _prazo(admin_engine, tid, conv.id, uid, HOJE + timedelta(days=3))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert [g for g, _n in regs] == ["lembrete"]


@pytest.mark.asyncio
async def test_job_recem_gerada_ganha_convocacao(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    # Fora da janela de lembrete (padrão 5 dias), mas dentro do ciclo.
    await _prazo(admin_engine, tid, conv.id, uid, HOJE + timedelta(days=20))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert [g for g, _n in regs] == ["convocacao"]


@pytest.mark.asyncio
async def test_job_precedencia_um_aviso_por_rodada(admin_engine):
    """Vencida e nunca avisada -> SÓ 'atraso' nesta rodada (não lembrete/convocacao)."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    await _prazo(admin_engine, tid, conv.id, uid, HOJE - timedelta(days=10))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert len(regs) == 1
    assert regs[0][0] == "atraso"


@pytest.mark.asyncio
async def test_job_sem_email_pula_sem_registro_e_recupera_depois(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)  # sem contato de propósito
    ciclo = await _ciclo_atravessando_hoje(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    await _prazo(admin_engine, tid, conv.id, uid, HOJE - timedelta(days=2))

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)
    regs = await _registros(admin_engine, tid, conv.id)
    assert regs == [], "sem e-mail não pode registrar nada"

    await _com_contato(admin_engine, tid, perm)

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)
    regs = await _registros(admin_engine, tid, conv.id)
    assert [g for g, _n in regs] == ["atraso"], (
        "assim que o e-mail existe, a mesma janela tem de ser recuperada"
    )


@pytest.mark.asyncio
async def test_job_suspensa_nao_recebe_lembrete_nem_atraso(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    perm = await _com_contato(admin_engine, tid, perm)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )

    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tid)

    regs = await _registros(admin_engine, tid, conv.id)
    assert regs == [], "convocação suspensa não recebe aviso automático nenhum"


@pytest.mark.asyncio
async def test_job_isola_tenants(admin_engine):
    ta = await _provisionar(admin_engine)
    tb = await _provisionar(admin_engine)

    perm_a = await _permissionario(admin_engine, ta.id, nome="Perm A")
    perm_a = await _com_contato(admin_engine, ta.id, perm_a)
    ciclo_a = await _ciclo_atravessando_hoje(admin_engine, ta.id)
    _c, conv_a = await _convocacao(admin_engine, ta.id, perm_a, ciclo=ciclo_a)
    uid_a = await _um_usuario(admin_engine, ta.id)
    await _prazo(admin_engine, ta.id, conv_a.id, uid_a, HOJE - timedelta(days=2))

    perm_b = await _permissionario(admin_engine, tb.id, nome="Perm B")
    perm_b = await _com_contato(admin_engine, tb.id, perm_b)
    ciclo_b = await _ciclo_atravessando_hoje(admin_engine, tb.id)
    _c, conv_b = await _convocacao(admin_engine, tb.id, perm_b, ciclo=ciclo_b)
    uid_b = await _um_usuario(admin_engine, tb.id)
    await _prazo(admin_engine, tb.id, conv_b.id, uid_b, HOJE - timedelta(days=2))

    # Duas chamadas, uma por tenant — scan completo (tenant_id=None) é
    # inviável em teste (ver docstring de `notificar_recadastramento`), mas
    # cada chamada exercita exatamente o mesmo `_processar_tenant` que o scan
    # completo usaria, e é isso que a asserção abaixo prova: o tenant_id da
    # `Notificacao` criada é sempre o do tenant processado, nunca o outro.
    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=ta.id)
    await notificar_recadastramento(dias_antes=DIAS_ANTES_PADRAO, tenant_id=tb.id)

    regs_a = await _registros(admin_engine, ta.id, conv_a.id)
    regs_b = await _registros(admin_engine, tb.id, conv_b.id)
    assert [g for g, _n in regs_a] == ["atraso"]
    assert [g for g, _n in regs_b] == ["atraso"]

    async with _sm(admin_engine)() as db:
        notif_a_id = regs_a[0][1]
        notif_b_id = regs_b[0][1]
        tenant_notif_a = (
            await db.execute(
                text("SELECT tenant_id FROM aprimora_py.notificacao WHERE id=:i"),
                {"i": notif_a_id},
            )
        ).scalar_one()
        tenant_notif_b = (
            await db.execute(
                text("SELECT tenant_id FROM aprimora_py.notificacao WHERE id=:i"),
                {"i": notif_b_id},
            )
        ).scalar_one()
    assert tenant_notif_a == ta.id
    assert tenant_notif_b == tb.id


# ---------------------------------------------------------------------------
# Fase C2 — e-mail no ATO (suspensão/reativação), não no job.
#
# Diferente do job (`notificar_recadastramento`), aqui o destinatário é o
# próprio suspenso e o e-mail leva o PARECER no corpo — é o julgamento do
# operador, não um aviso neutro de prazo. A notificação sai do ROUTER, depois
# do commit do ato (mesmo padrão pós-commit do `POST /{id}/decidir` de
# ocorrências, P7): falha de e-mail nunca desfaz a suspensão/reativação já
# persistida.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspensao_via_http_notifica_com_parecer(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _com_contato(
            admin_engine, tenant.id,
            await _permissionario(admin_engine, tenant.id, nome="Suspenso Email"),
        )
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        base = "/api/v2/transporte-regulado/recadastramento"
        parecer_texto = "Faltou ao recadastramento apos duas notificacoes."

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"{base}/convocacoes/{conv.id}/suspender",
                json={"parecer": parecer_texto},
            )
        assert r.status_code == 200, r.text

        async with _sm(admin_engine)() as db:
            notif = (
                await db.execute(
                    select(Notificacao).where(
                        Notificacao.tenant_id == tenant.id,
                        Notificacao.canal == "email",
                        Notificacao.tipo == "recadastramento.suspensao",
                    )
                )
            ).scalar_one()
            registro = (
                await db.execute(
                    select(RecadastramentoNotificacao).where(
                        RecadastramentoNotificacao.tenant_id == tenant.id,
                        RecadastramentoNotificacao.id_convocacao == conv.id,
                        RecadastramentoNotificacao.gatilho == "suspensao",
                    )
                )
            ).scalar_one()
            atual = await db.get(type(perm), perm.id)

        assert notif.destinatario_email == atual.email
        assert parecer_texto in notif.mensagem
        assert registro.id_usuario == uid
        assert registro.id_notificacao == notif.id
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
async def test_reativacao_via_http_notifica(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _com_contato(
            admin_engine, tenant.id,
            await _permissionario(admin_engine, tenant.id, nome="Reativado Email"),
        )
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)
        uid_susp = await _um_usuario(admin_engine, tenant.id)

        async with _sm(admin_engine)() as db:
            await tr.suspender_convocacao(
                db, tenant_id=tenant.id, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid_susp,
            )

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        base = "/api/v2/transporte-regulado/recadastramento"
        parecer_texto = "Recurso deferido pelo gestor."

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"{base}/convocacoes/{conv.id}/reativar",
                json={"parecer": parecer_texto},
            )
        assert r.status_code == 200, r.text

        async with _sm(admin_engine)() as db:
            notif = (
                await db.execute(
                    select(Notificacao).where(
                        Notificacao.tenant_id == tenant.id,
                        Notificacao.canal == "email",
                        Notificacao.tipo == "recadastramento.reativacao",
                    )
                )
            ).scalar_one()
            registro = (
                await db.execute(
                    select(RecadastramentoNotificacao).where(
                        RecadastramentoNotificacao.tenant_id == tenant.id,
                        RecadastramentoNotificacao.id_convocacao == conv.id,
                        RecadastramentoNotificacao.gatilho == "reativacao",
                    )
                )
            ).scalar_one()
            atual = await db.get(type(perm), perm.id)

        assert notif.destinatario_email == atual.email
        assert parecer_texto in notif.mensagem
        assert registro.id_usuario == uid
        assert registro.id_notificacao == notif.id
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
async def test_suspensao_sem_email_nao_explode(admin_engine):
    """Titular sem e-mail: o ato passa, e não sobra `Notificacao` nenhuma."""
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _permissionario(
            admin_engine, tenant.id, nome="Suspenso Sem Email"
        )  # sem contato de propósito
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        base = "/api/v2/transporte-regulado/recadastramento"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"{base}/convocacoes/{conv.id}/suspender",
                json={"parecer": "Sem contato cadastrado."},
            )
        assert r.status_code == 200, r.text
        assert r.json()["tipo"] == "suspensao"

        async with _sm(admin_engine)() as db:
            notifs = (
                await db.execute(
                    select(RecadastramentoNotificacao).where(
                        RecadastramentoNotificacao.tenant_id == tenant.id,
                        RecadastramentoNotificacao.id_convocacao == conv.id,
                    )
                )
            ).scalars().all()
        assert notifs == []
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)
