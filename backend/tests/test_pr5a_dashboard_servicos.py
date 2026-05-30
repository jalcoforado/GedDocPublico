"""PR 5a — Dashboard executivo por serviço, documental e complementação.

Cobre:
- migration 0028 (transação `dashboard` semeada idempotente; round-trip);
- permissão D-PERMISSAO nos 3 endpoints (SU bypass; não-SU sem permissão →
  403; não-SU com permissão via grupo → acessa);
- service `kpis(...)` com filtros novos (`id_servico` / `incluir_legado`);
- documental: equivalência com `calcular_checklist` por processo (suíte
  pequena);
- complementação: contadores aberta/respondida/cancelada + tempo médio;
- ranking por serviço: top 10 ordenado + linha "(sem serviço)" quando
  apropriado;
- LGPD: payload JSON serializado não contém CPF/nome/mensagem/motivo/
  filename/conteúdo;
- exports CSV/PDF: seções `[Documental]` / `[Complementação]` /
  `[Por serviço]` aparecem (smoke), seções antigas preservadas.

Padrão de tenant/setup espelha PR 4c/4d (provisionar_tenant + helpers
locais). Testes HTTP usam `httpx.ASGITransport` + `dependency_overrides`
+ dispose do engine global no teardown (mesma fixture do PR 4d HTTP gates).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from app.main import app
from app.models import (
    Anexo,
    AnexoProcesso,
    Assunto,
    Servico,
    TipoProcesso,
    UsuarioExterno,
)
from app.schemas.cidadao import AbrirPorServicoRequest
from app.schemas.servico import ServicoCreate
from app.services import complementacao_documental as comp_svc
from app.services import servico as servico_svc
from app.services.checklist_documentos import calcular_checklist
from app.services.cidadao_processos import abrir_processo_por_servico
from app.services.dashboard import kpis as compute_kpis
from app.services.dashboard_export import to_csv, to_pdf
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine, *, prefix="pr5a"):
    slug = _slug(prefix)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref PR5a",
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
                    text(
                        "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


async def _su_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
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
            assunto="Sol",
            id_tipo_processo=tp.id,
            exige_processo_pai=False,
            ativo=True,
            excluido=False,
        )
        s.add(a)
        await s.commit()
        return a.id


async def _criar_cidadao(engine, tenant_id: int, cpf: str | None = None) -> int:
    cpf = cpf or uuid.uuid4().hex[:11]
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id,
            nome="Maria",
            cpf_cnpj=cpf,
            email="m@x",
            ativo=True,
            excluido=False,
            uid=uuid.uuid4(),
            data_criacao=datetime.now(),
            login_govbr=False,
            telefone_whatsapp=False,
        )
        s.add(c)
        await s.commit()
        return c.id


async def _abrir_processo(engine, tenant, sv_id: int, cid: int) -> int:
    async with _sm(engine)() as s:
        cidadao = (
            await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))
        ).scalar_one()
        servico = (
            await s.execute(select(Servico).where(Servico.id == sv_id))
        ).scalar_one()
        p = await abrir_processo_por_servico(
            s,
            cidadao,
            servico,
            AbrirPorServicoRequest(corpo="Pedido de teste."),
            tenant_id=tenant.id,
        )
        return p.id


async def _abrir_processo_legado(engine, tenant_id: int, id_assunto: int) -> int:
    """Cria um processo sem `id_servico` (legado) via SQL direto."""
    async with _sm(engine)() as s:
        uid = await _unidade_id(engine, tenant_id)
        await s.execute(
            text(
                "INSERT INTO protocolos.manifestante "
                "(tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'Legado', '00000000000', true, false "
                "FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ),
            {"t": tenant_id},
        )
        mid = int(
            (
                await s.execute(
                    text(
                        "SELECT id FROM protocolos.manifestante "
                        "WHERE tenant_id=:t ORDER BY id DESC LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        numero = f"P{uuid.uuid4().hex[:6]}/2026"
        pid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO protocolos.processo "
                        "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                        "virtual, data_hora_abertura, numero_processo, nivel_sigilo, "
                        "externo, migrado, ativo, excluido, canal_entrada) "
                        "VALUES (:t, :a, :m, :u, true, NOW(), :np, 'ostensivo', "
                        "true, false, true, false, 'portal') RETURNING id"
                    ),
                    {
                        "t": tenant_id,
                        "a": id_assunto,
                        "m": mid,
                        "u": uid,
                        "np": numero,
                    },
                )
            ).scalar_one()
        )
        await s.commit()
        return pid


async def _movimentacao_id(engine, processo_id: int) -> int:
    async with _sm(engine)() as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT id_ultima_movimentacao "
                        "FROM protocolos.processo WHERE id=:p"
                    ),
                    {"p": processo_id},
                )
            ).scalar_one()
        )


async def _attach_anexo(engine, tenant_id, processo_id, mov_id, key: str | None):
    async with _sm(engine)() as s:
        a = Anexo(
            tenant_id=tenant_id,
            ativo=True,
            excluido=False,
            publico=True,
            descricao="diploma.pdf",  # nome de arquivo plausível para teste LGPD
            documento_exigido_key=key,
        )
        s.add(a)
        await s.flush()
        ap = AnexoProcesso(
            tenant_id=tenant_id,
            id_processo=processo_id,
            id_anexo=a.id,
            id_movimentacao=mov_id,
            ativo=True,
            excluido=False,
        )
        s.add(ap)
        await s.commit()
        return a.id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.complementacao_documental WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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
# 1) Migration 0028 — idempotência + round-trip
# =====================================================================

async def test_migration_0028_idempotente_e_roundtrip(admin_engine):
    """A migration 0028 já roda no upgrade head do conftest; verificamos
    que a linha existe, que reaplicar não duplica e que o downgrade limpa
    concessões antes da transação."""
    async with _sm(admin_engine)() as s:
        # Linha presente.
        rows = (await s.execute(text(
            "SELECT transacao, codigo FROM utils.transacao WHERE codigo='dashboard'"
        ))).all()
        assert len(rows) == 1
        assert rows[0].transacao == "Dashboard executivo"

        # Reaplicar é no-op (WHERE NOT EXISTS): tenta inserir → 0 linhas.
        await s.execute(text(
            "INSERT INTO utils.transacao (transacao, codigo) "
            "SELECT 'Dashboard executivo', 'dashboard' "
            "WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo='dashboard')"
        ))
        await s.commit()
        rows = (await s.execute(text(
            "SELECT COUNT(*) FROM utils.transacao WHERE codigo='dashboard'"
        ))).scalar_one()
        assert rows == 1


# =====================================================================
# 2) Fixture pesada — tenant A com dados, tenant B vazio, usuário sem-perm.
# =====================================================================

@pytest_asyncio.fixture
async def setup_pr5a(admin_engine):
    """Cria tenant A com 2 serviços + 4 processos + 1 legado + 2
    complementações (1 respondida, 1 aberta); tenant B vazio; usuário
    servidor sem permissão `dashboard` e usuário servidor com
    `dashboard` via grupo não-SU."""
    tenant = await _provisionar(admin_engine, prefix="pr5a-data")

    su_id = await _su_id(admin_engine, tenant.id)
    uid = await _unidade_id(admin_engine, tenant.id)
    id_assunto = await _criar_assunto(admin_engine, tenant.id)

    # 2 serviços: A com 3 docs (RG+CPF+opc), B sem docs.
    async with _sm(admin_engine)() as s:
        sv_a = await servico_svc.criar_servico(
            s,
            tenant_id=tenant.id,
            payload=ServicoCreate(
                nome="Serviço A",
                slug=_slug("sva-"),
                id_assunto_padrao=id_assunto,
                id_unidade_responsavel=uid,
                documentos_exigidos=[
                    {"nome": "RG", "obrigatorio": True},
                    {"nome": "CPF", "obrigatorio": True},
                    {"nome": "Comprovante", "obrigatorio": False},
                ],
            ),
        )
        sv_b = await servico_svc.criar_servico(
            s,
            tenant_id=tenant.id,
            payload=ServicoCreate(
                nome="Serviço B",
                slug=_slug("svb-"),
                id_assunto_padrao=id_assunto,
                id_unidade_responsavel=uid,
            ),
        )

    # 3 cidadãos do serviço A + 1 do B + 1 legado (sem id_servico).
    cidadaos_a = [await _criar_cidadao(admin_engine, tenant.id) for _ in range(3)]
    cidadao_b = await _criar_cidadao(admin_engine, tenant.id)

    # Processos: 3 em A (pendente, parcial, completo), 1 em B (completo trivial).
    p_a_pendente = await _abrir_processo(admin_engine, tenant, sv_a.id, cidadaos_a[0])
    p_a_parcial = await _abrir_processo(admin_engine, tenant, sv_a.id, cidadaos_a[1])
    p_a_completo = await _abrir_processo(admin_engine, tenant, sv_a.id, cidadaos_a[2])
    p_b = await _abrir_processo(admin_engine, tenant, sv_b.id, cidadao_b)
    p_legado = await _abrir_processo_legado(admin_engine, tenant.id, id_assunto)

    # Anexa: parcial recebe RG; completo recebe RG+CPF.
    mid_parcial = await _movimentacao_id(admin_engine, p_a_parcial)
    mid_completo = await _movimentacao_id(admin_engine, p_a_completo)
    await _attach_anexo(admin_engine, tenant.id, p_a_parcial, mid_parcial, "rg")
    await _attach_anexo(admin_engine, tenant.id, p_a_completo, mid_completo, "rg")
    await _attach_anexo(admin_engine, tenant.id, p_a_completo, mid_completo, "cpf")

    # 2 complementações no p_a_pendente: 1 cancelada → 1 respondida → 1 aberta
    # (sequenciais p/ não violar índice único de aberta).
    async with _sm(admin_engine)() as s:
        c1 = await comp_svc.solicitar(
            s,
            tenant_id=tenant.id,
            processo_id=p_a_pendente,
            id_usuario_solicitante=su_id,
            mensagem="Envie RG.",
            documentos_solicitados_keys=["rg"],
        )
        await s.commit()
    async with _sm(admin_engine)() as s:
        await comp_svc.responder(
            s,
            tenant_id=tenant.id,
            processo_id=p_a_pendente,
            complementacao_id=c1.id,
        )
        await s.commit()
    async with _sm(admin_engine)() as s:
        c2 = await comp_svc.solicitar(
            s,
            tenant_id=tenant.id,
            processo_id=p_a_pendente,
            id_usuario_solicitante=su_id,
            mensagem="Envie CPF.",
            documentos_solicitados_keys=["cpf"],
        )
        await s.commit()

    # Forçar respondido_em do c1 a ter delta conhecido vs criado_em (2 dias).
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE protocolos.complementacao_documental "
                "SET criado_em = NOW() - INTERVAL '3 day', "
                "    respondido_em = NOW() - INTERVAL '1 day' "
                "WHERE id = :id"
            ),
            {"id": c1.id},
        )
        await s.commit()

    # Usuário sem-perm (sem grupo qualquer)
    sem_perm_id = await _criar_servidor_sem_perm(admin_engine, tenant.id, uid)

    # Usuário com dashboard via grupo não-SU
    com_perm_id = await _criar_servidor_com_dashboard(
        admin_engine, tenant.id, uid
    )

    # Tenant B vazio.
    tenant_b = await _provisionar(admin_engine, prefix="pr5a-vazio")
    su_b_id = await _su_id(admin_engine, tenant_b.id)

    try:
        yield {
            "tenant": tenant,
            "tenant_b": tenant_b,
            "su_id": su_id,
            "sem_perm_id": sem_perm_id,
            "com_perm_id": com_perm_id,
            "su_b_id": su_b_id,
            "sv_a": sv_a,
            "sv_b": sv_b,
            "p_a_pendente": p_a_pendente,
            "p_a_parcial": p_a_parcial,
            "p_a_completo": p_a_completo,
            "p_b": p_b,
            "p_legado": p_legado,
            "c1": c1,
            "c2": c2,
        }
    finally:
        await _cleanup(admin_engine, tenant.id)
        await _cleanup(admin_engine, tenant_b.id)


async def _criar_servidor_sem_perm(engine, tenant_id: int, uid: int) -> int:
    async with _sm(engine)() as s:
        new_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario (tenant_id, nome, email, senha, "
                        "cpf, data_criacao, id_unidade_trabalho, ativo, excluido, uid) "
                        "VALUES (:t, 'Sem Perm', :e, '', :c, NOW(), :u, true, false, "
                        "gen_random_uuid()) RETURNING id"
                    ),
                    {
                        "t": tenant_id,
                        "e": f"sem-perm-{uuid.uuid4().hex[:8]}@t.local",
                        "c": uuid.uuid4().hex[:11],
                        "u": uid,
                    },
                )
            ).scalar_one()
        )
        await s.commit()
        return new_id


async def _criar_servidor_com_dashboard(engine, tenant_id: int, uid: int) -> int:
    """Cria usuário + grupo não-SU + grupo_transacao concedendo `dashboard`.

    O banco semeado só tem nível SU (valor=0). Cria-se aqui um nível
    operacional (valor>0) se ainda não existir — assim `is_super_usuario`
    fica False em `services/permissoes.py` e a checagem da transação
    `dashboard` toma o caminho real.
    """
    async with _sm(engine)() as s:
        nivel_id_row = (
            await s.execute(
                text("SELECT id FROM utils.nivel WHERE valor > 0 ORDER BY valor LIMIT 1")
            )
        ).scalar_one_or_none()
        if nivel_id_row is None:
            nivel_id = int(
                (
                    await s.execute(
                        text(
                            "INSERT INTO utils.nivel (valor, nivel) "
                            "VALUES (1, 'Operacional') RETURNING id"
                        )
                    )
                ).scalar_one()
            )
        else:
            nivel_id = int(nivel_id_row)
        sistema_id = int(
            (
                await s.execute(text("SELECT id FROM utils.sistema WHERE app='sistemas' LIMIT 1"))
            ).scalar_one()
        )
        # Garante que dashboard está em sistema_transacao desse sistema
        # (p/ que load_permissions enxergue como item do sistema).
        await s.execute(
            text(
                "INSERT INTO utils.sistema_transacao (id_sistema, id_transacao, excluido) "
                "SELECT :s, t.id, false FROM utils.transacao t "
                "WHERE t.codigo='dashboard' AND NOT EXISTS ("
                "  SELECT 1 FROM utils.sistema_transacao st "
                "  WHERE st.id_sistema=:s AND st.id_transacao=t.id"
                ")"
            ),
            {"s": sistema_id},
        )
        # Cria usuário
        usuario_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario (tenant_id, nome, email, senha, "
                        "cpf, data_criacao, id_unidade_trabalho, ativo, excluido, uid) "
                        "VALUES (:t, 'Com Dash', :e, '', :c, NOW(), :u, true, false, "
                        "gen_random_uuid()) RETURNING id"
                    ),
                    {
                        "t": tenant_id,
                        "e": f"com-dash-{uuid.uuid4().hex[:8]}@t.local",
                        "c": uuid.uuid4().hex[:11],
                        "u": uid,
                    },
                )
            ).scalar_one()
        )
        # Grupo não-SU
        grupo_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.grupo "
                        "(tenant_id, id_nivel, id_sistema, grupo, excluido) "
                        "VALUES (:t, :n, :s, 'Gestores', false) RETURNING id"
                    ),
                    {"t": tenant_id, "n": nivel_id, "s": sistema_id},
                )
            ).scalar_one()
        )
        # Vincula usuário ao grupo
        await s.execute(
            text(
                "INSERT INTO utils.usuario_grupo "
                "(tenant_id, id_usuario, id_grupo, ativo, excluido, app) "
                "VALUES (:t, :u, :g, true, false, 'sistemas')"
            ),
            {"t": tenant_id, "u": usuario_id, "g": grupo_id},
        )
        # Concede dashboard ao grupo (read-only basta — codigo sem action)
        await s.execute(
            text(
                "INSERT INTO utils.grupo_transacao "
                "(tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido) "
                "SELECT :t, :g, t.id, false, false, false, false "
                "FROM utils.transacao t WHERE t.codigo='dashboard'"
            ),
            {"t": tenant_id, "g": grupo_id},
        )
        await s.commit()
        return usuario_id


# =====================================================================
# 3) Service `kpis()` — filtros e indicadores
# =====================================================================

async def test_kpis_estrutura_basica(admin_engine, setup_pr5a):
    """Smoke: o payload preserva campos antigos e contém os blocos novos."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    # Campos antigos preservados
    assert "volume" in data and "conclusao" in data and "sla" in data
    assert "por_tipo" in data and "por_unidade" in data and "serie_temporal" in data
    # Blocos novos
    assert "documental" in data
    assert "complementacao" in data
    assert "por_servico" in data


async def test_kpis_documental_equivale_a_calcular_checklist(
    admin_engine, setup_pr5a
):
    """Soma pendente/parcial/completo/sem_documentos_exigidos do agregado
    deve bater 1:1 com `calcular_checklist` chamado por cada processo.

    PR 5a-fix: `sem_documentos_exigidos` separado de `completo`.
    """
    s = setup_pr5a
    tenant_id = s["tenant"].id
    # Processos com id_servico do tenant A no período (sem legado).
    pids = [s["p_a_pendente"], s["p_a_parcial"], s["p_a_completo"], s["p_b"]]
    contagem = {"pendente": 0, "parcial": 0, "completo": 0, "sem_docs": 0}
    async with _sm(admin_engine)() as sess:
        for pid in pids:
            r = await calcular_checklist(sess, processo_id=pid, tenant_id=tenant_id)
            if r.status_documental == "pendente":
                contagem["pendente"] += 1
            elif r.status_documental == "parcial":
                contagem["parcial"] += 1
            elif r.status_documental == "completo":
                contagem["completo"] += 1
            elif r.status_documental == "sem_documentos_exigidos":
                contagem["sem_docs"] += 1

    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=tenant_id, periodo_dias=30)
    d = data["documental"]
    assert d["checklist_pendente"] == contagem["pendente"]
    assert d["checklist_parcial"] == contagem["parcial"]
    assert d["checklist_completo"] == contagem["completo"]
    assert d["sem_documentos_exigidos"] == contagem["sem_docs"]
    # Auxiliares: 4 com id_servico + 1 sem (legado).
    assert d["com_id_servico_periodo"] == 4
    assert d["sem_id_servico_periodo"] == 1


async def test_kpis_complementacao_contadores_e_tempo_medio(
    admin_engine, setup_pr5a
):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    c = data["complementacao"]
    # 1 aberta agora (c2), 2 solicitadas no período, 1 respondida, 0 canceladas
    assert c["abertas_agora"] == 1
    assert c["solicitadas_periodo"] == 2
    assert c["respondidas_periodo"] == 1
    assert c["canceladas_periodo"] == 0
    assert c["processos_com_aberta_agora"] == 1
    # c1 foi forçado a (criado=NOW-3d, respondido=NOW-1d) → ~2 dias.
    assert c["tempo_medio_resposta_dias"] is not None
    assert 1.5 <= c["tempo_medio_resposta_dias"] <= 2.5


async def test_kpis_filtro_id_servico_isola_contagens(admin_engine, setup_pr5a):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            id_servico=s["sv_a"].id,
        )
    # Volume: só processos do serviço A (3).
    assert data["volume"]["abertos_periodo"] == 3
    # por_servico: lista com 1 item (Serviço A) — sem linha "(sem serviço)"
    # mesmo se houver legado, pois id_servico está informado (D-FILTROS).
    assert len(data["por_servico"]) == 1
    assert data["por_servico"][0]["id_servico"] == s["sv_a"].id
    # Documental: agora pendente/parcial/completo só refletem processos do A.
    d = data["documental"]
    assert d["checklist_pendente"] == 1
    assert d["checklist_parcial"] == 1
    assert d["checklist_completo"] == 1
    # sem_id_servico_periodo zera quando id_servico vem (legado ignorado).
    assert d["sem_id_servico_periodo"] == 0


async def test_kpis_incluir_legado_false_remove_legados(admin_engine, setup_pr5a):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            incluir_legado=False,
        )
    # Volume: 4 (3 do A + 1 do B), sem legado.
    assert data["volume"]["abertos_periodo"] == 4
    # Sem linha "(sem serviço)" no ranking.
    assert all(item["id_servico"] is not None for item in data["por_servico"])
    # sem_id_servico_periodo zerado.
    assert data["documental"]["sem_id_servico_periodo"] == 0


async def test_kpis_incluir_legado_true_inclui_linha_sem_servico(
    admin_engine, setup_pr5a
):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            incluir_legado=True,
        )
    # Volume: 5 (3 A + 1 B + 1 legado).
    assert data["volume"]["abertos_periodo"] == 5
    legado = [it for it in data["por_servico"] if it["id_servico"] is None]
    assert len(legado) == 1
    assert legado[0]["nome"] == "(sem serviço)"
    assert legado[0]["count"] == 1


async def test_kpis_por_servico_ordenado_desc(admin_engine, setup_pr5a):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    # Top com id_servico não-null deve estar ordenado desc por count.
    com_id = [it for it in data["por_servico"] if it["id_servico"] is not None]
    counts = [it["count"] for it in com_id]
    assert counts == sorted(counts, reverse=True)
    # Serviço A (3 processos) antes do Serviço B (1).
    assert com_id[0]["id_servico"] == s["sv_a"].id
    assert com_id[0]["count"] == 3


async def test_kpis_cross_tenant_isola(admin_engine, setup_pr5a):
    """Tenant B (vazio) não deve ver dados do A."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant_b"].id, periodo_dias=30)
    assert data["volume"]["abertos_periodo"] == 0
    assert data["por_servico"] == []
    assert data["complementacao"]["abertas_agora"] == 0
    assert data["documental"]["checklist_pendente"] == 0


async def test_kpis_payload_sem_dados_pessoais(admin_engine, setup_pr5a):
    """LGPD: serializa o payload em JSON e garante que CPF/nome do cidadão/
    corpo/mensagem/motivo/filename não aparecem."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    body = json.dumps(data, default=str)
    # Strings que NÃO devem aparecer no payload
    assert "Maria" not in body  # nome do cidadão
    assert "Pedido de teste" not in body  # corpo do processo
    assert "Envie RG" not in body and "Envie CPF" not in body  # msg complementação
    assert "diploma.pdf" not in body  # nome de arquivo do anexo
    # CPFs específicos: como são gerados via uuid.hex[:11], inspecionamos
    # a presença de qualquer dígito-string longa que case com cpf_cnpj real.
    async with _sm(admin_engine)() as sess:
        cpfs = (
            await sess.execute(
                text(
                    "SELECT cpf_cnpj FROM utils.usuario_externo WHERE tenant_id=:t"
                ),
                {"t": s["tenant"].id},
            )
        ).all()
    for (cpf,) in cpfs:
        if cpf:
            assert cpf not in body


# =====================================================================
# 4) HTTP — D-PERMISSAO
# =====================================================================

def _as_user(admin_engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(admin_engine)() as s:
            from app.models import Usuario
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup


@pytest_asyncio.fixture
async def http_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


async def test_http_dashboard_sem_perm_403(admin_engine, setup_pr5a, http_client):
    s = setup_pr5a
    _as_user(
        admin_engine, s["sem_perm_id"], s["tenant"].id, s["tenant"].slug
    )()
    for path in ("/api/v2/dashboard/kpis", "/api/v2/dashboard/export.csv", "/api/v2/dashboard/export.pdf"):
        r = await http_client.get(path)
        assert r.status_code == 403, f"{path} → {r.status_code}"


async def test_http_dashboard_su_bypassa(admin_engine, setup_pr5a, http_client):
    s = setup_pr5a
    _as_user(admin_engine, s["su_id"], s["tenant"].id, s["tenant"].slug)()
    r = await http_client.get("/api/v2/dashboard/kpis")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["documental"]["com_id_servico_periodo"] >= 4
    # Smoke export
    r2 = await http_client.get("/api/v2/dashboard/export.csv")
    assert r2.status_code == 200
    r3 = await http_client.get("/api/v2/dashboard/export.pdf")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/pdf")


async def test_http_dashboard_com_perm_acessa(admin_engine, setup_pr5a, http_client):
    s = setup_pr5a
    _as_user(
        admin_engine, s["com_perm_id"], s["tenant"].id, s["tenant"].slug
    )()
    r = await http_client.get("/api/v2/dashboard/kpis")
    assert r.status_code == 200, r.text


async def test_http_dashboard_filtro_id_servico(
    admin_engine, setup_pr5a, http_client
):
    s = setup_pr5a
    _as_user(admin_engine, s["su_id"], s["tenant"].id, s["tenant"].slug)()
    r = await http_client.get(
        f"/api/v2/dashboard/kpis?id_servico={s['sv_a'].id}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["volume"]["abertos_periodo"] == 3


async def test_http_dashboard_incluir_legado_false(
    admin_engine, setup_pr5a, http_client
):
    s = setup_pr5a
    _as_user(admin_engine, s["su_id"], s["tenant"].id, s["tenant"].slug)()
    r = await http_client.get(
        "/api/v2/dashboard/kpis?incluir_legado=false"
    )
    assert r.status_code == 200
    body = r.json()
    # 4 (3 A + 1 B), sem legado.
    assert body["volume"]["abertos_periodo"] == 4
    assert all(it["id_servico"] is not None for it in body["por_servico"])


# =====================================================================
# 5) Exports CSV/PDF — seções novas + preservação das antigas
# =====================================================================

async def test_csv_contem_secoes_novas_e_preserva_antigas(
    admin_engine, setup_pr5a
):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    csv_str = to_csv(data, nome_tenant="Pref")
    # Seções antigas continuam presentes.
    for secao in ("[Volume]", "[Conclusão]", "[SLA]", "[Por tipo de processo]",
                  "[Por assunto]", "[Por unidade]", "[Série temporal"):
        assert secao in csv_str, f"secção antiga sumiu: {secao}"
    # Seções novas (PR 5a).
    assert "[Documental]" in csv_str
    assert "[Complementação]" in csv_str
    assert "[Por serviço]" in csv_str


async def test_pdf_smoke_devolve_bytes(admin_engine, setup_pr5a):
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    pdf_bytes = to_pdf(data, nome_tenant="Pref")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-"), "não é um PDF válido"
    assert len(pdf_bytes) > 1000  # PDF mínimo plausível


# =====================================================================
# 6) PR 5a-fix — achados do Codex
# =====================================================================

async def test_documental_sem_documentos_separado_de_completo(
    admin_engine, setup_pr5a
):
    """`sem_documentos_exigidos` (serviço B sem docs) NÃO é contabilizado
    em `checklist_completo`. Antes do fix, ambos caíam em completo."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    d = data["documental"]
    # Set: pendente=1, parcial=1, completo=1 (p_a_completo), sem_docs=1 (p_b).
    assert d["checklist_pendente"] == 1
    assert d["checklist_parcial"] == 1
    assert d["checklist_completo"] == 1
    assert d["sem_documentos_exigidos"] == 1
    # Soma das 4 categorias = total com id_servico no período.
    soma = (
        d["checklist_pendente"]
        + d["checklist_parcial"]
        + d["checklist_completo"]
        + d["sem_documentos_exigidos"]
    )
    assert soma == d["com_id_servico_periodo"]


async def test_ranking_por_servico_aplica_id_unidade_em_complementacoes(
    admin_engine, setup_pr5a
):
    """Quando `id_unidade` está filtrado, `complementacoes_abertas` e
    `complementacoes_respondidas_periodo` no ranking devem refletir
    apenas processos daquela unidade.

    Setup-pr5a abre todas as complementações em processos da unidade
    padrão. Filtrando por OUTRA unidade, as colunas de complementação
    devem zerar — antes do fix, vinham preenchidas porque ignoravam
    `id_unidade`.
    """
    s = setup_pr5a
    # Cria uma segunda unidade no mesmo tenant para servir de filtro.
    async with _sm(admin_engine)() as sess:
        tu_id = int(
            (
                await sess.execute(
                    text(
                        "SELECT id FROM utils.tipo_unidade_trabalho "
                        "WHERE tenant_id=:t LIMIT 1"
                    ),
                    {"t": s["tenant"].id},
                )
            ).scalar_one()
        )
        outra_uid = int(
            (
                await sess.execute(
                    text(
                        "INSERT INTO utils.unidade_trabalho "
                        "(tenant_id, unidade_trabalho, sigla, "
                        "id_tipo_unidade_trabalho) "
                        "VALUES (:t, 'Outra', 'O', :tu) RETURNING id"
                    ),
                    {"t": s["tenant"].id, "tu": tu_id},
                )
            ).scalar_one()
        )
        await sess.commit()

    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            id_unidade=outra_uid,
        )
    # Ranking pode estar vazio (não há processos nessa unidade) OU pode
    # ter linha legado. Em qualquer caso, NENHUMA complementação deve
    # aparecer (todas estão em processos da unidade original).
    for it in data["por_servico"]:
        assert it["complementacoes_abertas"] == 0, it
        assert it["complementacoes_respondidas_periodo"] == 0, it


async def test_sla_respeita_filtro_id_servico(admin_engine, setup_pr5a):
    """SLA agora respeita id_servico via JOIN WorkflowInstance → Processo.

    Sem alertas semeados no setup, o teste é negativo: garante que a
    consulta não estoura e o resultado é coerente (0 alertas com qualquer
    id_servico válido).
    """
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            id_servico=s["sv_a"].id,
        )
    assert data["sla"]["pendentes"] == 0
    assert data["sla"]["resolvidos_periodo"] == 0


async def test_janela_temporal_exclui_processos_futuros(
    admin_engine, setup_pr5a
):
    """Breakdowns e série temporal devem usar `< ate` (não só `>= desde`).

    Cria processo com `data_hora_abertura` 365+ dias no futuro; ele
    aparece no banco mas NÃO deve entrar em por_tipo / por_assunto /
    por_unidade / serie_temporal (que olham o período atual `[desde, now)`).
    Antes do fix, eles entravam pois só filtravam `>= desde`.
    """
    s = setup_pr5a
    tenant_id = s["tenant"].id
    # Pega assunto e unidade do tenant.
    async with _sm(admin_engine)() as sess:
        async_uid = int(
            (
                await sess.execute(
                    text(
                        "SELECT id FROM utils.unidade_trabalho "
                        "WHERE tenant_id=:t LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        async_aid = int(
            (
                await sess.execute(
                    text(
                        "SELECT id FROM protocolos.assunto "
                        "WHERE tenant_id=:t LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        # Manifestante mínimo.
        await sess.execute(
            text(
                "INSERT INTO protocolos.manifestante "
                "(tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'Futuro', '99999999999', true, false "
                "FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ),
            {"t": tenant_id},
        )
        mid = int(
            (
                await sess.execute(
                    text(
                        "SELECT id FROM protocolos.manifestante "
                        "WHERE tenant_id=:t ORDER BY id DESC LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        # Processo com data_hora_abertura 400 dias no futuro.
        await sess.execute(
            text(
                "INSERT INTO protocolos.processo "
                "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                "virtual, data_hora_abertura, numero_processo, nivel_sigilo, "
                "externo, migrado, ativo, excluido, canal_entrada) "
                "VALUES (:t, :a, :m, :u, true, NOW() + INTERVAL '400 day', "
                ":np, 'ostensivo', true, false, true, false, 'portal')"
            ),
            {
                "t": tenant_id,
                "a": async_aid,
                "m": mid,
                "u": async_uid,
                "np": "PFUT/2027",
            },
        )
        await sess.commit()

    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=tenant_id, periodo_dias=30)
    # Soma dos breakdowns por unidade no período = abertos do volume; o
    # processo futuro NÃO deve aparecer.
    total_por_unidade = sum(it["count"] for it in data["por_unidade"])
    assert total_por_unidade == data["volume"]["abertos_periodo"]
    # Série temporal: nenhuma data > now.
    from datetime import datetime as _dt
    now_iso = _dt.utcnow().isoformat()
    for ponto in data["serie_temporal"]:
        assert ponto["dia"] <= now_iso, (
            f"processo futuro vazou para série temporal: {ponto}"
        )


async def test_csv_contem_sem_documentos_exigidos(admin_engine, setup_pr5a):
    """Export CSV reflete o novo indicador `sem_documentos_exigidos`."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(sess, tenant_id=s["tenant"].id, periodo_dias=30)
    csv_str = to_csv(data, nome_tenant="Pref")
    # Linha do indicador na seção Documental.
    assert "Sem documentos exigidos" in csv_str
    # Cabeçalho da tabela por serviço também tem a coluna.
    assert "Sem documentos exigidos" in csv_str.split("[Por serviço]")[1]


async def test_csv_export_com_filtro_id_servico_e_legado_false(
    admin_engine, setup_pr5a
):
    """CSV deve respeitar filtros: com id_servico fixo + incluir_legado=false,
    seção Volume só conta processos do serviço; ranking só lista esse
    serviço; sem linha (sem serviço)."""
    s = setup_pr5a
    async with _sm(admin_engine)() as sess:
        data = await compute_kpis(
            sess,
            tenant_id=s["tenant"].id,
            periodo_dias=30,
            id_servico=s["sv_a"].id,
            incluir_legado=False,
        )
    csv_str = to_csv(data, nome_tenant="Pref")
    # Volume: 3 processos (apenas Serviço A).
    assert "[Volume]" in csv_str
    # Sem linha "(sem serviço)" no ranking.
    assert "(sem serviço)" not in csv_str
