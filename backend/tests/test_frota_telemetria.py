"""Frota — telemetria (posições GPS por veículo), backlog §2.3.

Cobre:
- serviço: ingestão em lote, idempotência do reenvio, dedup dentro do lote,
  conversão de fuso para UTC, consulta por período em ordem cronológica,
  período invertido (422) e teto de pontos por consulta (422, não truncado);
- tenant: veículo de outro tenant é 404 na ingestão E na consulta, sem gravar
  nada; RLS da tabela nova sob `aprimora_app` (NOBYPASSRLS);
- HTTP com usuário COMUM (não super-usuário): a suíte só com SU esconderia um
  `action` inválido — o bypass de SU retorna antes do `getattr(item, action)`
  em `auth/perms.py`. Por isso há um grupo que tem `frota` SEM `inserir`: ele
  lê (200) e não grava (403). Com um `action` inexistente na rota, esse teste
  daria 500, não 403.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.main import app
from app.models import VeiculoPosicao
from app.schemas.frota import VeiculoCreate
from app.schemas.frota_telemetria import PosicaoCreate, PosicoesLoteCreate
from app.services import frota as frota_svc
from app.services import frota_telemetria as telemetria_svc
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import as_user_dependency

APP = get_settings().app_name
_placa_seq = itertools.count(1)

# Instante fixo e "redondo": o teste não depende do relógio da máquina.
T0 = datetime(2026, 9, 1, 12, 0, 0)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar(engine, *, modulos: list[str] | None = None):
    slug = f"telem{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura Telemetria", admin_email=f"{slug}@telem.test",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
            modulos=modulos,
        )
    return tenant


async def _veiculo(engine, tenant_id: int) -> int:
    placa = f"TLM{next(_placa_seq) % 10000:04d}"
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id, payload=VeiculoCreate(placa=placa)
        )
        return v.id


def _pos(minutos: int, *, lat="-3.68", lon="-40.35", vel="40.00") -> PosicaoCreate:
    return PosicaoCreate(
        data_hora=T0 + timedelta(minutes=minutos),
        latitude=Decimal(lat), longitude=Decimal(lon),
        velocidade=Decimal(vel), ignicao_ligada=True,
    )


async def _conta(engine, id_veiculo: int) -> int:
    async with _sm(engine)() as s:
        return (await s.execute(
            select(func.count()).select_from(VeiculoPosicao)
            .where(VeiculoPosicao.id_veiculo == id_veiculo)
        )).scalar_one()


# --------------------------------------------------------------------------
# Serviço
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registra_e_consulta_em_ordem_cronologica(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)

    # Chegam fora de ordem: a consulta tem de devolver por `data_hora`.
    lote = PosicoesLoteCreate(posicoes=[_pos(10, vel="50.00"), _pos(0, vel="40.50"), _pos(5)])
    async with _sm(admin_engine)() as s:
        r = await telemetria_svc.registrar_posicoes(s, tenant_id=t.id, id_veiculo=v, payload=lote)
    assert r == {"recebidas": 3, "registradas": 3, "ignoradas": 0}

    async with _sm(admin_engine)() as s:
        rows = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v, inicio=T0, fim=T0 + timedelta(minutes=10)
        )
    assert [p.data_hora for p in rows] == [
        T0, T0 + timedelta(minutes=5), T0 + timedelta(minutes=10)
    ]
    assert rows[0].velocidade == Decimal("40.50")
    assert rows[-1].velocidade == Decimal("50.00")
    assert all(p.tenant_id == t.id and p.id_veiculo == v for p in rows)

    # Período que exclui as pontas: limites são inclusivos, o resto fica fora.
    async with _sm(admin_engine)() as s:
        meio = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v,
            inicio=T0 + timedelta(minutes=1), fim=T0 + timedelta(minutes=9),
        )
        antes = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v,
            inicio=T0 - timedelta(hours=2), fim=T0 - timedelta(hours=1),
        )
    assert [p.data_hora for p in meio] == [T0 + timedelta(minutes=5)]
    assert antes == []


@pytest.mark.asyncio
async def test_reenvio_do_lote_nao_duplica_e_dedup_interno(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    lote = PosicoesLoteCreate(posicoes=[_pos(0), _pos(1)])

    async with _sm(admin_engine)() as s:
        await telemetria_svc.registrar_posicoes(s, tenant_id=t.id, id_veiculo=v, payload=lote)
    # Retry do rastreador: mesmo lote + um ponto novo + um repetido no próprio lote.
    lote2 = PosicoesLoteCreate(posicoes=[_pos(0), _pos(1), _pos(2), _pos(2, vel="99.00")])
    async with _sm(admin_engine)() as s:
        r = await telemetria_svc.registrar_posicoes(s, tenant_id=t.id, id_veiculo=v, payload=lote2)

    assert r == {"recebidas": 4, "registradas": 1, "ignoradas": 3}
    assert await _conta(admin_engine, v) == 3
    async with _sm(admin_engine)() as s:
        rows = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v, inicio=T0, fim=T0 + timedelta(minutes=2)
        )
    # Fica a PRIMEIRA leitura do instante repetido.
    assert rows[-1].velocidade == Decimal("40.00")


@pytest.mark.asyncio
async def test_data_hora_com_fuso_vira_utc(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    fortaleza = timezone(timedelta(hours=-3))
    ponto = PosicaoCreate(
        data_hora=datetime(2026, 9, 1, 9, 0, 0, tzinfo=fortaleza),
        latitude=Decimal("-3.68"), longitude=Decimal("-40.35"),
    )
    async with _sm(admin_engine)() as s:
        await telemetria_svc.registrar_posicoes(
            s, tenant_id=t.id, id_veiculo=v, payload=PosicoesLoteCreate(posicoes=[ponto])
        )
        # Consulta também com fuso: 08:30..09:30 em -03 = 11:30..12:30 UTC.
        rows = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v,
            inicio=datetime(2026, 9, 1, 8, 30, tzinfo=fortaleza),
            fim=datetime(2026, 9, 1, 9, 30, tzinfo=fortaleza),
        )
    assert len(rows) == 1
    assert rows[0].data_hora == T0  # 12:00 UTC, gravado sem fuso


@pytest.mark.asyncio
async def test_periodo_invertido_e_422(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await telemetria_svc.listar_posicoes(
                s, tenant_id=t.id, id_veiculo=v, inicio=T0, fim=T0 - timedelta(seconds=1)
            )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_periodo_acima_do_teto_e_422_e_nao_truncado(admin_engine, monkeypatch):
    monkeypatch.setattr(telemetria_svc, "MAX_POSICOES_POR_CONSULTA", 2)
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    async with _sm(admin_engine)() as s:
        await telemetria_svc.registrar_posicoes(
            s, tenant_id=t.id, id_veiculo=v,
            payload=PosicoesLoteCreate(posicoes=[_pos(0), _pos(1), _pos(2)]),
        )
        # Exatamente no teto: devolve.
        ok = await telemetria_svc.listar_posicoes(
            s, tenant_id=t.id, id_veiculo=v, inicio=T0, fim=T0 + timedelta(minutes=1)
        )
        assert len(ok) == 2
        with pytest.raises(HTTPException) as exc:
            await telemetria_svc.listar_posicoes(
                s, tenant_id=t.id, id_veiculo=v, inicio=T0, fim=T0 + timedelta(minutes=2)
            )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_veiculo_de_outro_tenant_e_404_e_nao_grava(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    va = await _veiculo(admin_engine, a.id)
    async with _sm(admin_engine)() as s:
        await telemetria_svc.registrar_posicoes(
            s, tenant_id=a.id, id_veiculo=va, payload=PosicoesLoteCreate(posicoes=[_pos(0)])
        )

    # Tenant B tentando gravar no veículo de A: a FK aceitaria, o serviço não.
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await telemetria_svc.registrar_posicoes(
                s, tenant_id=b.id, id_veiculo=va, payload=PosicoesLoteCreate(posicoes=[_pos(1)])
            )
    assert exc.value.status_code == 404
    assert await _conta(admin_engine, va) == 1

    # ...nem ler o trajeto dele (404, não lista vazia: não confirma existência).
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await telemetria_svc.listar_posicoes(
                s, tenant_id=b.id, id_veiculo=va, inicio=T0, fim=T0 + timedelta(hours=1)
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_veiculo_excluido_e_404(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    async with _sm(admin_engine)() as s:
        await frota_svc.excluir_veiculo(s, tenant_id=t.id, veiculo_id=v)
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await telemetria_svc.registrar_posicoes(
                s, tenant_id=t.id, id_veiculo=v, payload=PosicoesLoteCreate(posicoes=[_pos(0)])
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rls_isola_posicoes_sob_aprimora_app(admin_engine, app_session):
    """Com o papel do runtime (NOBYPASSRLS), o tenant B não enxerga nem
    consegue gravar posição com `tenant_id` de A. Com `admin_session` este
    teste passaria por engano."""
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    va = await _veiculo(admin_engine, a.id)
    async with _sm(admin_engine)() as s:
        await telemetria_svc.registrar_posicoes(
            s, tenant_id=a.id, id_veiculo=va, payload=PosicoesLoteCreate(posicoes=[_pos(0)])
        )

    async with app_session.begin():
        await app_session.execute(text(f"SET LOCAL app.tenant_id = '{a.id}'"))
        vistas_a = (await app_session.execute(
            text("SELECT count(*) FROM frota.veiculo_posicao WHERE id_veiculo = :v"), {"v": va}
        )).scalar_one()
    assert vistas_a == 1

    async with app_session.begin():
        await app_session.execute(text(f"SET LOCAL app.tenant_id = '{b.id}'"))
        vistas_b = (await app_session.execute(
            text("SELECT count(*) FROM frota.veiculo_posicao WHERE id_veiculo = :v"), {"v": va}
        )).scalar_one()
    assert vistas_b == 0

    with pytest.raises(Exception, match="row-level security"):
        async with app_session.begin():
            await app_session.execute(text(f"SET LOCAL app.tenant_id = '{b.id}'"))
            await app_session.execute(text(
                "INSERT INTO frota.veiculo_posicao "
                "(tenant_id, id_veiculo, data_hora, latitude, longitude) "
                "VALUES (:t, :v, now(), 0, 0)"
            ), {"t": a.id, "v": va})


# --------------------------------------------------------------------------
# HTTP — usuário comum (não super-usuário)
# --------------------------------------------------------------------------


async def _usuario_comum(engine, tenant_id: int, *, inserir: bool, com_frota: bool = True) -> int:
    """Usuário com nível != 0 (não SU) num grupo que tem a transação `frota`
    (ou nenhuma, com `com_frota=False`) — `inserir` controla o flag do grupo."""
    async with _sm(engine)() as s:
        sistema_id = (await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one()
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = (await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Operador Frota', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"op-{uuid.uuid4().hex[:8]}@telem.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one()
        gid = (await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Grupo Telemetria {uuid.uuid4().hex[:6]}"})).scalar_one()
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        if com_frota:
            tr = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo='frota' AND excluido=false LIMIT 1"
            ))).scalar_one()
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                VALUES (:t, :g, :tr, :i, false, false, false)"""),
                {"t": tenant_id, "g": gid, "tr": tr, "i": inserir})
        await s.commit()
    return uid


async def _http(engine, tenant, uid, metodo: str, caminho: str, **kwargs):
    as_user_dependency(engine, uid, tenant.id, tenant.slug)()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.request(metodo, caminho, **kwargs)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


def _corpo(*minutos: int) -> dict:
    return {"posicoes": [
        {"data_hora": (T0 + timedelta(minutes=m)).isoformat(),
         "latitude": "-3.68", "longitude": "-40.35", "velocidade": "30.5",
         "ignicao_ligada": True}
        for m in minutos
    ]}


def _periodo(ini_min: int = 0, fim_min: int = 60) -> dict:
    return {"inicio": (T0 + timedelta(minutes=ini_min)).isoformat(),
            "fim": (T0 + timedelta(minutes=fim_min)).isoformat()}


@pytest.mark.asyncio
async def test_http_usuario_comum_registra_e_consulta(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    uid = await _usuario_comum(admin_engine, t.id, inserir=True)
    url = f"/api/v2/frota/veiculos/{v}/telemetria/posicoes"

    resp = await _http(admin_engine, t, uid, "POST", url, json=_corpo(0, 5))
    assert resp.status_code == 201, resp.text
    assert resp.json() == {"recebidas": 2, "registradas": 2, "ignoradas": 0}

    resp = await _http(admin_engine, t, uid, "GET", url, params=_periodo())
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert [p["id_veiculo"] for p in corpo] == [v, v]
    assert corpo[0]["latitude"] == "-3.68000000"
    assert corpo[0]["velocidade"] == "30.50"
    assert "tenant_id" not in corpo[0]


@pytest.mark.asyncio
async def test_http_usuario_comum_sem_inserir_le_mas_nao_grava(admin_engine):
    """Prova que a rota de ingestão confere `inserir` e a de leitura não pede
    action. Com `"operar"`/`"visualizar"` (o WIP original), o usuário comum
    tomaria 500 aqui — `getattr(PermItem, "operar")` não existe."""
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    uid = await _usuario_comum(admin_engine, t.id, inserir=False)
    url = f"/api/v2/frota/veiculos/{v}/telemetria/posicoes"

    resp = await _http(admin_engine, t, uid, "POST", url, json=_corpo(0))
    assert resp.status_code == 403, resp.text
    assert await _conta(admin_engine, v) == 0

    resp = await _http(admin_engine, t, uid, "GET", url, params=_periodo())
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_http_usuario_sem_transacao_frota_e_403(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    uid = await _usuario_comum(admin_engine, t.id, inserir=True, com_frota=False)
    url = f"/api/v2/frota/veiculos/{v}/telemetria/posicoes"

    assert (await _http(admin_engine, t, uid, "GET", url, params=_periodo())).status_code == 403
    assert (await _http(admin_engine, t, uid, "POST", url, json=_corpo(0))).status_code == 403


@pytest.mark.asyncio
async def test_http_veiculo_de_outro_tenant_e_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    va = await _veiculo(admin_engine, a.id)
    uid_b = await _usuario_comum(admin_engine, b.id, inserir=True)
    url = f"/api/v2/frota/veiculos/{va}/telemetria/posicoes"

    resp = await _http(admin_engine, b, uid_b, "POST", url, json=_corpo(0))
    assert resp.status_code == 404, resp.text
    assert await _conta(admin_engine, va) == 0

    resp = await _http(admin_engine, b, uid_b, "GET", url, params=_periodo())
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_http_tenant_sem_modulo_frota_e_403(admin_engine):
    """Transação `frota` concedida, módulo não contratado: o gate de contratação
    nega antes de qualquer outra coisa."""
    t = await _provisionar(admin_engine, modulos=["protocolo"])
    v = await _veiculo(admin_engine, t.id)
    uid = await _usuario_comum(admin_engine, t.id, inserir=True)
    url = f"/api/v2/frota/veiculos/{v}/telemetria/posicoes"

    assert (await _http(admin_engine, t, uid, "POST", url, json=_corpo(0))).status_code == 403
    assert (await _http(admin_engine, t, uid, "GET", url, params=_periodo())).status_code == 403


@pytest.mark.asyncio
async def test_http_validacao_do_payload(admin_engine):
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id)
    uid = await _usuario_comum(admin_engine, t.id, inserir=True)
    url = f"/api/v2/frota/veiculos/{v}/telemetria/posicoes"

    invalidos = [
        {"posicoes": []},                                              # lote vazio
        {"posicoes": [{**_corpo(0)["posicoes"][0], "latitude": "91"}]},  # fora da faixa
        {"posicoes": [{**_corpo(0)["posicoes"][0], "velocidade": "-1"}]},
        {"posicoes": [{**_corpo(0)["posicoes"][0], "tenant_id": 999}]},  # campo server-side
        {**_corpo(0), "id_veiculo": 999},
    ]
    for corpo in invalidos:
        resp = await _http(admin_engine, t, uid, "POST", url, json=corpo)
        assert resp.status_code == 422, (corpo, resp.text)
    assert await _conta(admin_engine, v) == 0

    resp = await _http(admin_engine, t, uid, "GET", url, params=_periodo(10, 0))
    assert resp.status_code == 422, resp.text
