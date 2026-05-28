"""Sigilo gradual — testes de integração (Postgres).

Cobre:
- coluna gerada `publico` sincroniza com `nivel_sigilo`;
- `classificar_processo`: validação de TCI, cálculo de desclassificação,
  limpeza ao voltar pra ostensivo, e bloqueio por credencial;
- enforcement de leitura: `list_processos` e `get_processo_detail` filtram
  pelos níveis acessíveis da credencial.

Usa ``admin_engine`` (BYPASSRLS) — RLS já é coberto em test_rls_isolation.
Foco aqui é a lógica de sigilo. Catálogos criados do zero pra rodar em CI.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.processos import get_processo_detail, list_processos
from app.services.sigilo import (
    PRAZO_MAX_ANOS,
    SigiloError,
    _add_anos,
    classificar_processo,
    niveis_permitidos,
)


async def _setup_catalogs(s: AsyncSession, tenant_id: int) -> dict[str, int]:
    suffix = uuid.uuid4().hex[:8]
    categoria_id = int(
        (await s.execute(
            text(
                "INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) "
                "VALUES (:nome, 'PF', true, false) RETURNING id"
            ),
            {"nome": f"Sig {suffix}"},
        )).scalar_one()
    )
    tipo_manif_id = int(
        (await s.execute(
            text(
                "INSERT INTO protocolos.tipo_manifestante "
                "(tenant_id, tipo_manifestante, id_categoria, ativo, excluido) "
                "VALUES (:tid, :nome, :cat, true, false) RETURNING id"
            ),
            {"tid": tenant_id, "nome": f"Sig {suffix}", "cat": categoria_id},
        )).scalar_one()
    )
    manifestante_id = int(
        (await s.execute(
            text(
                "INSERT INTO protocolos.manifestante "
                "(tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
                "VALUES (:tid, :tm, :nome, true, false) RETURNING id"
            ),
            {"tid": tenant_id, "tm": tipo_manif_id, "nome": f"Sig {suffix}"},
        )).scalar_one()
    )
    unidade_id = int(
        (await s.execute(
            text(
                "INSERT INTO utils.unidade_trabalho "
                "(tenant_id, unidade_trabalho, excluido) "
                "VALUES (:tid, :nome, false) RETURNING id"
            ),
            {"tid": tenant_id, "nome": f"Unid {suffix}"},
        )).scalar_one()
    )
    tipo_proc_id = int(
        (await s.execute(
            text(
                "INSERT INTO protocolos.tipo_processo "
                "(tenant_id, tipo_processo, ativo, excluido) "
                "VALUES (:tid, :nome, true, false) RETURNING id"
            ),
            {"tid": tenant_id, "nome": f"Tipo {suffix}"},
        )).scalar_one()
    )
    assunto_id = int(
        (await s.execute(
            text(
                "INSERT INTO protocolos.assunto "
                "(tenant_id, assunto, id_tipo_processo, ativo, excluido) "
                "VALUES (:tid, :nome, :tp, true, false) RETURNING id"
            ),
            {"tid": tenant_id, "nome": f"Assunto {suffix}", "tp": tipo_proc_id},
        )).scalar_one()
    )
    usuario_id = int(
        (await s.execute(
            text(
                "INSERT INTO utils.usuario "
                "(tenant_id, nome, email, senha, cpf, ativo, excluido) "
                "VALUES (:tid, :nome, :email, 'x', :cpf, true, false) RETURNING id"
            ),
            {
                "tid": tenant_id,
                "nome": f"Sig {suffix}",
                "email": f"{suffix}@sig.local",
                "cpf": uuid.uuid4().hex[:11],
            },
        )).scalar_one()
    )
    return {
        "categoria": categoria_id,
        "tipo_manifestante": tipo_manif_id,
        "manifestante": manifestante_id,
        "unidade": unidade_id,
        "tipo_processo": tipo_proc_id,
        "assunto": assunto_id,
        "usuario": usuario_id,
    }


async def _insert_processo(
    s: AsyncSession, tenant_id: int, cat: dict[str, int], nivel: str = "ostensivo"
) -> int:
    """Insere processo direto (sem publico — é coluna gerada)."""
    return int(
        (await s.execute(
            text(
                """
                INSERT INTO protocolos.processo
                    (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                     numero_processo, nivel_sigilo,
                     virtual, externo, ativo, excluido, migrado, data_hora_abertura)
                VALUES
                    (:tid, :assunto, :manif, :unid, :num, :nivel,
                     true, false, true, false, false, NOW())
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "assunto": cat["assunto"],
                "manif": cat["manifestante"],
                "unid": cat["unidade"],
                "num": f"P{uuid.uuid4().hex[:6]}/2026",
                "nivel": nivel,
            },
        )).scalar_one()
    )


@pytest_asyncio.fixture
async def sigilo_env(admin_engine, two_tenants):
    """tenant + catálogos. Retorna dict; limpa processos+catálogos no fim."""
    tid, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        cat = await _setup_catalogs(s, tid)
        await s.commit()

    yield {"tenant_id": tid, **cat}

    async with Session() as s:
        await s.execute(
            text("DELETE FROM aprimora_py.audit_log WHERE tenant_id = :t"), {"t": tid}
        )
        await s.execute(
            text("DELETE FROM protocolos.processo WHERE tenant_id = :t"), {"t": tid}
        )
        await s.execute(
            text("DELETE FROM utils.usuario WHERE id = :id"), {"id": cat["usuario"]}
        )
        await s.execute(
            text("DELETE FROM protocolos.assunto WHERE id = :id"), {"id": cat["assunto"]}
        )
        await s.execute(
            text("DELETE FROM protocolos.tipo_processo WHERE id = :id"),
            {"id": cat["tipo_processo"]},
        )
        await s.execute(
            text("DELETE FROM utils.unidade_trabalho WHERE id = :id"),
            {"id": cat["unidade"]},
        )
        await s.execute(
            text("DELETE FROM protocolos.manifestante WHERE id = :id"),
            {"id": cat["manifestante"]},
        )
        await s.execute(
            text("DELETE FROM protocolos.tipo_manifestante WHERE id = :id"),
            {"id": cat["tipo_manifestante"]},
        )
        await s.execute(
            text("DELETE FROM protocolos.categoria WHERE id = :id"),
            {"id": cat["categoria"]},
        )
        await s.commit()


def _session(admin_engine):
    return async_sessionmaker(
        admin_engine, expire_on_commit=False, class_=AsyncSession
    )()


# -------- coluna gerada --------


async def test_publico_gerado_sincroniza_com_nivel(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid_ost = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        pid_int = await _insert_processo(s, tid, sigilo_env, "interno")
        await s.commit()
        pub_ost = (
            await s.execute(
                text("SELECT publico FROM protocolos.processo WHERE id = :id"),
                {"id": pid_ost},
            )
        ).scalar_one()
        pub_int = (
            await s.execute(
                text("SELECT publico FROM protocolos.processo WHERE id = :id"),
                {"id": pid_int},
            )
        ).scalar_one()
    assert pub_ost is True
    assert pub_int is False


# -------- classificar: validação de TCI --------


async def test_classificar_sigilo_legal_exige_fundamento(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await s.commit()
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloError, match="Fundamento"):
            await classificar_processo(
                s,
                tenant_id=tid,
                processo_id=pid,
                nivel="reservado",
                usuario_id=sigilo_env["usuario"],
                credencial_usuario="ultrassecreto",
                is_super=False,
                autoridade="Secretário",
            )


async def test_classificar_reservado_calcula_desclassificacao(
    admin_engine, sigilo_env
):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await s.commit()
    async with _session(admin_engine) as s:
        p = await classificar_processo(
            s,
            tenant_id=tid,
            processo_id=pid,
            nivel="reservado",
            usuario_id=sigilo_env["usuario"],
            credencial_usuario="ultrassecreto",
            is_super=False,
            fundamento_legal="Art. 23, VIII da LAI",
            autoridade="Secretário de Administração",
        )
        assert p.nivel_sigilo == "reservado"
        assert p.publico is False
        assert p.sigilo_prazo_anos == PRAZO_MAX_ANOS["reservado"]
        esperado = _add_anos(date.today(), PRAZO_MAX_ANOS["reservado"])
        assert p.sigilo_data_desclassificacao == esperado
        assert p.sigilo_fundamento_legal == "Art. 23, VIII da LAI"


async def test_classificar_prazo_acima_do_maximo_rejeita(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await s.commit()
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloError, match="1 a 5"):
            await classificar_processo(
                s,
                tenant_id=tid,
                processo_id=pid,
                nivel="reservado",
                usuario_id=sigilo_env["usuario"],
                credencial_usuario="ultrassecreto",
                is_super=False,
                fundamento_legal="x",
                autoridade="y",
                prazo_anos=10,
            )


async def test_classificar_voltar_ostensivo_limpa_tci(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await s.commit()
    # reservado
    async with _session(admin_engine) as s:
        await classificar_processo(
            s,
            tenant_id=tid,
            processo_id=pid,
            nivel="reservado",
            usuario_id=sigilo_env["usuario"],
            credencial_usuario="ultrassecreto",
            is_super=False,
            fundamento_legal="x",
            autoridade="y",
        )
    # volta pra ostensivo
    async with _session(admin_engine) as s:
        p = await classificar_processo(
            s,
            tenant_id=tid,
            processo_id=pid,
            nivel="ostensivo",
            usuario_id=sigilo_env["usuario"],
            credencial_usuario="ultrassecreto",
            is_super=False,
        )
        assert p.nivel_sigilo == "ostensivo"
        assert p.publico is True
        assert p.sigilo_fundamento_legal is None
        assert p.sigilo_data_desclassificacao is None


async def test_classificar_sem_credencial_bloqueia(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await s.commit()
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloError, match="credencial"):
            await classificar_processo(
                s,
                tenant_id=tid,
                processo_id=pid,
                nivel="reservado",
                usuario_id=sigilo_env["usuario"],
                credencial_usuario="interno",  # não alcança reservado
                is_super=False,
                fundamento_legal="x",
                autoridade="y",
            )


# -------- enforcement de leitura --------


async def test_listagem_filtra_por_credencial(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        await _insert_processo(s, tid, sigilo_env, "ostensivo")
        await _insert_processo(s, tid, sigilo_env, "reservado")
        await s.commit()

    async with _session(admin_engine) as s:
        # credencial interno → só ostensivo (1)
        itens, total = await list_processos(
            s,
            tenant_id=tid,
            page=1,
            page_size=50,
            niveis_permitidos=niveis_permitidos("interno"),
        )
        assert total == 1
        assert all(i.nivel_sigilo == "ostensivo" for i in itens)

        # super (None) → vê os 2
        _itens, total_super = await list_processos(
            s, tenant_id=tid, page=1, page_size=50, niveis_permitidos=None
        )
        assert total_super == 2


async def test_detalhe_bloqueia_acima_da_credencial(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    async with _session(admin_engine) as s:
        pid = await _insert_processo(s, tid, sigilo_env, "reservado")
        await s.commit()

    async with _session(admin_engine) as s:
        # credencial interno não vê reservado → None (404)
        bloqueado = await get_processo_detail(
            s, pid, tenant_id=tid, niveis_permitidos=niveis_permitidos("interno")
        )
        assert bloqueado is None
        # super (None) vê
        ok = await get_processo_detail(s, pid, tenant_id=tid, niveis_permitidos=None)
        assert ok is not None
        assert ok.nivel_sigilo == "reservado"
