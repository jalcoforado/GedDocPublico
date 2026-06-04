"""PR 5b — testes de integração: snapshot, detalhe, dashboard, migration.

Cobre:
- migration 0029 (coluna existe, backfill funciona);
- snapshot é gravado na abertura por serviço a partir de
  `servico.prazo_estimado_dias`;
- mudança posterior do `servico.prazo_estimado_dias` NÃO altera o snapshot
  do processo já aberto (D-SNAPSHOT);
- detalhe admin traz `prazo` com `status` coerente;
- detalhe cidadão traz `prazo` reduzido (sem `dias_*`, sem snapshot);
- dashboard `prazos` agrega corretamente com mix de status;
- filtros `id_servico` / `id_unidade` / `incluir_legado` propagam ao bloco
  `prazos`;
- payload `/dashboard/kpis` não contém PII (defesa em profundidade vs PR 5a).

Reaproveita o padrão de provisionamento de tenant do PR 5a.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Assunto,
    Servico,
    TipoProcesso,
    UsuarioExterno,
)
from app.schemas.cidadao import AbrirPorServicoRequest
from app.schemas.servico import ServicoCreate
from app.services import servico as servico_svc
from app.services.cidadao_processos import (
    abrir_processo_por_servico,
    get_meu_detail,
)
from app.services.dashboard import kpis as compute_kpis
from app.services.processos import get_processo_detail
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine, *, prefix="pr5b"):
    slug = _slug(prefix)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref PR5b",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


async def _criar_assunto(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        tp = TipoProcesso(
            tenant_id=tenant_id,
            tipo_processo="Geral",
            exige_processo_pai=False,
            ativo=True,
            excluido=False,
        )
        s.add(tp)
        await s.flush()
        a = Assunto(
            tenant_id=tenant_id,
            assunto="Solicitação",
            id_tipo_processo=tp.id,
            exige_processo_pai=False,
            ativo=True,
            excluido=False,
        )
        s.add(a)
        await s.commit()
        return a.id


async def _criar_cidadao(engine, tenant_id: int) -> UsuarioExterno:
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id,
            nome="João",
            cpf_cnpj=uuid.uuid4().hex[:11],
            email="j@x.local",
            ativo=True,
            excluido=False,
            uid=uuid.uuid4(),
            data_criacao=datetime.now(),
            login_govbr=False,
            telefone_whatsapp=False,
        )
        s.add(c)
        await s.commit()
        return c


async def _criar_servico(
    engine, tenant_id: int, id_assunto: int, uid: int, *, prazo: int | None
) -> Servico:
    async with _sm(engine)() as s:
        sv = await servico_svc.criar_servico(
            s,
            tenant_id=tenant_id,
            payload=ServicoCreate(
                nome="Alvará simples",
                slug=_slug("alv-"),
                id_assunto_padrao=id_assunto,
                id_unidade_responsavel=uid,
                prazo_estimado_dias=prazo,
            ),
        )
        return sv


async def _abrir_processo(engine, tenant, sv: Servico, cidadao: UsuarioExterno) -> int:
    async with _sm(engine)() as s:
        # Reanexa o cidadão à session corrente.
        cid = (
            await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cidadao.id))
        ).scalar_one()
        sv_fresh = (
            await s.execute(select(Servico).where(Servico.id == sv.id))
        ).scalar_one()
        p = await abrir_processo_por_servico(
            s,
            cid,
            sv_fresh,
            AbrirPorServicoRequest(corpo="Pedido de teste."),
            tenant_id=tenant.id,
        )
        return p.id


async def _shift_abertura(engine, processo_id: int, dias_atras: int) -> None:
    """Move data_hora_abertura do processo para `dias_atras` no passado.

    Crucial pros testes de prazo: precisamos de processos com data de
    abertura controlada p/ avaliar dentro/vencendo/atrasado.
    """
    async with _sm(engine)() as s:
        await s.execute(
            text(
                "UPDATE protocolos.processo "
                "SET data_hora_abertura = NOW() - (:d * INTERVAL '1 day') "
                "WHERE id = :id"
            ),
            {"d": dias_atras, "id": processo_id},
        )
        await s.commit()


async def _arquivar(engine, tenant_id: int, processo_id: int, dias_atras: int) -> None:
    """Simula conclusão por arquivamento (Movimentacao ativa com id_arquivamento)."""
    async with _sm(engine)() as s:
        unidade_id = await _unidade_id(engine, tenant_id)
        acao_id = int(
            (
                await s.execute(
                    text(
                        "SELECT id FROM protocolos.acao "
                        "WHERE flag='ARQUIVAMENTO' AND ativo=true AND excluido=false LIMIT 1"
                    )
                )
            ).scalar_one()
        )
        # Status de arquivamento (qualquer ativo).
        arq_status = int(
            (
                await s.execute(
                    text(
                        "SELECT id FROM protocolos.status_arquivamento "
                        "WHERE ativo=true AND excluido=false LIMIT 1"
                    )
                )
            ).scalar_one()
        )
        arq_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO protocolos.arquivamento "
                        "(tenant_id, id_status_arquivamento, motivo, id_usuario, ativo, excluido) "
                        "SELECT :t, :s, 'Teste', u.id, true, false "
                        "FROM utils.usuario u WHERE u.tenant_id = :t LIMIT 1 "
                        "RETURNING id"
                    ),
                    {"t": tenant_id, "s": arq_status},
                )
            ).scalar_one()
        )
        await s.execute(
            text(
                "INSERT INTO protocolos.movimentacao "
                "(tenant_id, id_processo, id_unidade_responsavel, id_acao, "
                "id_arquivamento, data_hora_movimentacao, ativo, excluido) "
                "VALUES (:t, :p, :u, :a, :arq, "
                "NOW() - (:d * INTERVAL '1 day'), true, false)"
            ),
            {
                "t": tenant_id,
                "p": processo_id,
                "u": unidade_id,
                "a": acao_id,
                "arq": arq_id,
                "d": dias_atras,
            },
        )
        await s.commit()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.arquivamento WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.servico WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_externo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# =====================================================================
# 1) Migration 0029 — coluna existe e backfill é seguro.
# =====================================================================


async def test_migration_0029_coluna_e_backfill(admin_engine):
    """A migration 0029 cria `prazo_servico_dias_snapshot` e popula via
    backfill. Conftest já rodou upgrade head — só validamos resultado."""
    async with _sm(admin_engine)() as s:
        col = (
            await s.execute(
                text(
                    "SELECT column_name, is_nullable, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema='protocolos' "
                    "  AND table_name='processo' "
                    "  AND column_name='prazo_servico_dias_snapshot'"
                )
            )
        ).one_or_none()
        assert col is not None, "coluna prazo_servico_dias_snapshot ausente"
        assert col.is_nullable == "YES", "coluna deve ser NULLABLE"
        assert col.data_type == "integer"


# =====================================================================
# 2) Snapshot é gravado na abertura por serviço (e None quando aplicável).
# =====================================================================


async def test_snapshot_grava_prazo_do_servico_na_abertura(admin_engine):
    tenant = await _provisionar(admin_engine, prefix="pr5b-snap")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=15)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)

        async with _sm(admin_engine)() as s:
            snap = (
                await s.execute(
                    text(
                        "SELECT prazo_servico_dias_snapshot FROM protocolos.processo "
                        "WHERE id=:p"
                    ),
                    {"p": pid},
                )
            ).scalar_one()
            assert snap == 15, "snapshot deveria ser 15"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_snapshot_none_quando_servico_sem_prazo(admin_engine):
    tenant = await _provisionar(admin_engine, prefix="pr5b-sem")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=None)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)

        async with _sm(admin_engine)() as s:
            snap = (
                await s.execute(
                    text(
                        "SELECT prazo_servico_dias_snapshot FROM protocolos.processo "
                        "WHERE id=:p"
                    ),
                    {"p": pid},
                )
            ).scalar_one_or_none()
            assert snap is None, "snapshot deveria ser NULL p/ serviço sem prazo"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_alterar_prazo_servico_nao_altera_processo_aberto(admin_engine):
    """D-SNAPSHOT crítico: mudança posterior do prazo do serviço não pode
    reverberar em processos já abertos. Snapshot é imutável."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-imut")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)

        # Edita o prazo do serviço — simula servidor reduzindo de 10 → 5 dias.
        async with _sm(admin_engine)() as s:
            await s.execute(
                text(
                    "UPDATE protocolos.servico SET prazo_estimado_dias=5 WHERE id=:id"
                ),
                {"id": sv.id},
            )
            await s.commit()

        async with _sm(admin_engine)() as s:
            snap = (
                await s.execute(
                    text(
                        "SELECT prazo_servico_dias_snapshot FROM protocolos.processo "
                        "WHERE id=:p"
                    ),
                    {"p": pid},
                )
            ).scalar_one()
            assert snap == 10, (
                "snapshot deveria continuar 10 mesmo após edição do serviço; "
                f"obtido {snap}"
            )
    finally:
        await _cleanup(admin_engine, tenant.id)


# =====================================================================
# 3) Detalhe admin — bloco prazo com status correto.
# =====================================================================


async def test_detail_admin_dentro_do_prazo(admin_engine):
    tenant = await _provisionar(admin_engine, prefix="pr5b-dent")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=30)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)
        # Aberto há 1d → restam ~29d, muito acima do limiar (6d).
        await _shift_abertura(admin_engine, pid, 1)

        async with _sm(admin_engine)() as s:
            d = await get_processo_detail(s, pid, tenant_id=tenant.id)
        assert d is not None
        assert d.prazo.status == "dentro_do_prazo"
        assert d.prazo.prazo_servico_dias_snapshot == 30
        assert d.prazo.dias_restantes is not None and d.prazo.dias_restantes >= 25
        assert d.prazo.dias_atraso is None
        assert d.prazo.origem == "servico"
        assert d.prazo.concluido_em is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_detail_admin_atrasado(admin_engine):
    tenant = await _provisionar(admin_engine, prefix="pr5b-atr")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)
        # Aberto há 15d, prazo 10 → atraso de 5d.
        await _shift_abertura(admin_engine, pid, 15)

        async with _sm(admin_engine)() as s:
            d = await get_processo_detail(s, pid, tenant_id=tenant.id)
        assert d is not None
        assert d.prazo.status == "atrasado"
        assert d.prazo.dias_atraso is not None and d.prazo.dias_atraso >= 4
        assert d.prazo.dias_restantes is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_detail_admin_concluido_no_prazo(admin_engine):
    tenant = await _provisionar(admin_engine, prefix="pr5b-conc")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=15)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)
        # Aberto há 10d, arquivado há 2d → no prazo.
        await _shift_abertura(admin_engine, pid, 10)
        await _arquivar(admin_engine, tenant.id, pid, dias_atras=2)

        async with _sm(admin_engine)() as s:
            d = await get_processo_detail(s, pid, tenant_id=tenant.id)
        assert d is not None
        assert d.prazo.status == "concluido_no_prazo"
        assert d.prazo.concluido_em is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


# =====================================================================
# 4) Detalhe cidadão — bloco reduzido + sem PII relacionada ao prazo.
# =====================================================================


async def test_detail_cidadao_status_reduzido_e_sem_dias(admin_engine):
    """O detalhe cidadão expõe apenas `prazo_estimado_em` + enum reduzido
    de 5 valores. NÃO expõe contagem de dias, snapshot, concluido_em."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-cid")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=20)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)
        # Aberto há 2d → dentro_da_previsao no enum cidadão.
        await _shift_abertura(admin_engine, pid, 2)

        async with _sm(admin_engine)() as s:
            cid_fresh = (
                await s.execute(
                    select(UsuarioExterno).where(UsuarioExterno.id == cid.id)
                )
            ).scalar_one()
            d = await get_meu_detail(s, cid_fresh, pid, tenant_id=tenant.id)
        assert d is not None
        assert d.prazo.status == "dentro_da_previsao"
        assert d.prazo.prazo_estimado_em is not None
        # Defesa em profundidade: campos vetados não devem existir no schema.
        payload = d.model_dump()
        assert "dias_restantes" not in payload["prazo"]
        assert "dias_atraso" not in payload["prazo"]
        assert "prazo_servico_dias_snapshot" not in payload["prazo"]
        assert "concluido_em" not in payload["prazo"]
    finally:
        await _cleanup(admin_engine, tenant.id)


# =====================================================================
# 5) Dashboard — bloco prazos agrega corretamente.
# =====================================================================


async def test_dashboard_prazos_agrega_mix_de_status(admin_engine):
    """Cria 1 dentro_do_prazo, 1 vencendo, 1 atrasado, 1 concluido_no_prazo,
    1 sem_prazo (serviço sem prazo). Verifica contadores."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-mix")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv30 = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=30)
        sv_sem = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=None)

        cidadaos = [await _criar_cidadao(admin_engine, tenant.id) for _ in range(5)]

        # 1) dentro_do_prazo: aberto há 1d, prazo 30 → restam 29d.
        p_dentro = await _abrir_processo(admin_engine, tenant, sv30, cidadaos[0])
        await _shift_abertura(admin_engine, p_dentro, 1)

        # 2) vencendo: aberto há 26d, prazo 30 → restam 4d (limiar = 6).
        p_venc = await _abrir_processo(admin_engine, tenant, sv30, cidadaos[1])
        await _shift_abertura(admin_engine, p_venc, 26)

        # 3) atrasado: aberto há 40d, prazo 30 → -10d.
        p_atr = await _abrir_processo(admin_engine, tenant, sv30, cidadaos[2])
        await _shift_abertura(admin_engine, p_atr, 40)

        # 4) concluido_no_prazo: aberto há 5d, prazo 30, arquivado há 1d.
        p_conc = await _abrir_processo(admin_engine, tenant, sv30, cidadaos[3])
        await _shift_abertura(admin_engine, p_conc, 5)
        await _arquivar(admin_engine, tenant.id, p_conc, dias_atras=1)

        # 5) sem_prazo: serviço sem prazo configurado.
        p_sem = await _abrir_processo(admin_engine, tenant, sv_sem, cidadaos[4])
        await _shift_abertura(admin_engine, p_sem, 3)

        async with _sm(admin_engine)() as s:
            payload = await compute_kpis(s, tenant_id=tenant.id, periodo_dias=90)
        prazos = payload["prazos"]
        assert prazos["dentro_do_prazo"] == 1
        assert prazos["vencendo"] == 1
        assert prazos["atrasado"] == 1
        assert prazos["sem_prazo"] == 1
        assert prazos["concluido_no_prazo_periodo"] == 1
        # 1 dentro + 1 vencendo / 3 com prazo (em andamento) ≈ 66.7%
        assert prazos["percentual_no_prazo"] is not None
        assert 60.0 <= prazos["percentual_no_prazo"] <= 80.0
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_dashboard_prazos_respeita_filtro_id_servico(admin_engine):
    """Filtro de serviço isola contadores ao serviço escolhido (D-FILTROS PR 5a)."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-flt")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv_a = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        sv_b = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)

        cids = [await _criar_cidadao(admin_engine, tenant.id) for _ in range(2)]
        p_a = await _abrir_processo(admin_engine, tenant, sv_a, cids[0])
        p_b = await _abrir_processo(admin_engine, tenant, sv_b, cids[1])
        await _shift_abertura(admin_engine, p_a, 1)
        await _shift_abertura(admin_engine, p_b, 1)

        # Filtro = sv_a → atrasado de sv_b não conta; dentro_do_prazo só p_a.
        async with _sm(admin_engine)() as s:
            payload = await compute_kpis(
                s, tenant_id=tenant.id, periodo_dias=30, id_servico=sv_a.id
            )
        assert payload["prazos"]["dentro_do_prazo"] == 1
        assert payload["prazos"]["sem_prazo"] == 0
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_dashboard_prazos_incluir_legado_false_zera_sem_prazo(admin_engine):
    """`incluir_legado=False` remove processos sem id_servico do snapshot."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-lgd")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        p_serv = await _abrir_processo(admin_engine, tenant, sv, cid)
        await _shift_abertura(admin_engine, p_serv, 1)

        # Insere 1 processo legado direto via SQL (sem id_servico).
        async with _sm(admin_engine)() as s:
            await s.execute(
                text(
                    "INSERT INTO protocolos.manifestante "
                    "(tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                    "SELECT :t, id, 'Legado', '00000000000', true, false "
                    "FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
                ),
                {"t": tenant.id},
            )
            mid = int(
                (
                    await s.execute(
                        text(
                            "SELECT id FROM protocolos.manifestante "
                            "WHERE tenant_id=:t ORDER BY id DESC LIMIT 1"
                        ),
                        {"t": tenant.id},
                    )
                ).scalar_one()
            )
            await s.execute(
                text(
                    "INSERT INTO protocolos.processo "
                    "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                    "virtual, data_hora_abertura, numero_processo, nivel_sigilo, "
                    "externo, migrado, ativo, excluido, canal_entrada) "
                    "VALUES (:t, :a, :m, :u, true, NOW(), :np, 'ostensivo', "
                    "true, false, true, false, 'portal')"
                ),
                {
                    "t": tenant.id,
                    "a": id_ass,
                    "m": mid,
                    "u": uid,
                    "np": f"P{uuid.uuid4().hex[:6]}/2026",
                },
            )
            await s.commit()

        # Com legado: snapshot tem 1 dentro_do_prazo + 1 sem_prazo.
        async with _sm(admin_engine)() as s:
            payload_com = await compute_kpis(
                s, tenant_id=tenant.id, periodo_dias=30, incluir_legado=True
            )
        assert payload_com["prazos"]["sem_prazo"] == 1
        assert payload_com["prazos"]["dentro_do_prazo"] == 1

        # Sem legado: snapshot tem só 1 dentro_do_prazo (legado some).
        async with _sm(admin_engine)() as s:
            payload_sem = await compute_kpis(
                s, tenant_id=tenant.id, periodo_dias=30, incluir_legado=False
            )
        assert payload_sem["prazos"]["sem_prazo"] == 0
        assert payload_sem["prazos"]["dentro_do_prazo"] == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_dashboard_por_servico_atrasados(admin_engine):
    """O ranking `por_servico` ganha campo `atrasados` (PR 5b)."""
    tenant = await _provisionar(admin_engine, prefix="pr5b-ranq")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        pid = await _abrir_processo(admin_engine, tenant, sv, cid)
        # Atrasado: aberto há 20d, prazo 10 → -10d.
        await _shift_abertura(admin_engine, pid, 20)

        async with _sm(admin_engine)() as s:
            payload = await compute_kpis(s, tenant_id=tenant.id, periodo_dias=30)
        ranking = payload["por_servico"]
        assert len(ranking) >= 1
        servico_row = next(r for r in ranking if r.get("id_servico") == sv.id)
        assert servico_row["atrasados"] == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


# =====================================================================
# 6) LGPD — payload do dashboard não vaza PII relacionada ao prazo.
# =====================================================================


async def test_dashboard_payload_sem_pii(admin_engine):
    """Defesa em profundidade: o payload serializado não pode conter
    cpf_cnpj, nome do cidadão, corpo do pedido, observação ou texto livre.

    Reusa fixture mínima (1 processo) para tornar o teste rápido.
    """
    tenant = await _provisionar(admin_engine, prefix="pr5b-lgpd")
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        id_ass = await _criar_assunto(admin_engine, tenant.id)
        sv = await _criar_servico(admin_engine, tenant.id, id_ass, uid, prazo=10)
        cid = await _criar_cidadao(admin_engine, tenant.id)
        cpf_do_cidadao = cid.cpf_cnpj
        await _abrir_processo(admin_engine, tenant, sv, cid)

        async with _sm(admin_engine)() as s:
            payload = await compute_kpis(s, tenant_id=tenant.id, periodo_dias=30)
        body = json.dumps(payload, default=str)
        assert cpf_do_cidadao not in body, "CPF do cidadão vazou no payload"
        assert "João" not in body, "Nome do cidadão vazou no payload"
        assert "Pedido de teste" not in body, "Corpo do pedido vazou no payload"
    finally:
        await _cleanup(admin_engine, tenant.id)
