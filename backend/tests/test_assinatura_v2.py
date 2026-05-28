"""Assinatura v2 — núcleo backend (PR2a).

Matriz do escopo: hash, evidências, audit, bloqueio MD5-only, tentativa falha,
throttle, fail-open de Redis, imutabilidade de anexo assinado, validação
on-demand, isolamento de tenant, compatibilidade legado.

Usa admin_engine (BYPASSRLS). Catálogos criados do zero. O arquivo do anexo é
escrito no storage do tenant pra o hash poder ser calculado.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import hash_md5, hash_password
from app.config import tenant_anexos_dir
from app.routers.processos import require_acesso_processo
from app.schemas.assinatura import EvidenciasOut, SolicitarAssinaturaRequest, ValidacaoOut
from app.services import assinatura_throttle as throttle
from app.services.assinaturas import (
    AssinaturaCredencialLegadaError,
    AssinaturaError,
    AssinaturaThrottleError,
    assinar,
    cancelar_solicitacao,
    consultar_evidencias,
    recusar_assinatura,
    solicitar_assinatura,
    validar_assinatura,
)
from app.services.desentranhamento import DesentranhamentoError, desentranhar_anexo
from app.services.pdf_comprovante_assinatura import gerar_comprovante_assinatura_pdf
from app.services.sigilo import SigiloAcessoError, assert_acesso_processo


def _uobj(uid: int, credencial: str = "interno"):
    """Objeto leve de usuário para os serviços (id + credencial de sigilo)."""
    return SimpleNamespace(id=uid, nivel_acesso_sigilo=credencial)

SENHA = "senha-v2-teste"
CONTEUDO = b"conteudo do documento assinado v2"


async def _setup(s: AsyncSession, tenant_id: int, slug: str) -> dict:
    suf = uuid.uuid4().hex[:8]

    async def _sc(sql: str, **p) -> int:
        return int((await s.execute(text(sql), p)).scalar_one())

    categoria = await _sc("INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) VALUES (:n,'PF',true,false) RETURNING id", n=f"V2 {suf}")
    tipo_manif = await _sc("INSERT INTO protocolos.tipo_manifestante (tenant_id, tipo_manifestante, id_categoria, ativo, excluido) VALUES (:t,:n,:c,true,false) RETURNING id", t=tenant_id, n=f"V2 {suf}", c=categoria)
    manifestante = await _sc("INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, ativo, excluido) VALUES (:t,:tm,:n,true,false) RETURNING id", t=tenant_id, tm=tipo_manif, n=f"V2 {suf}")
    unidade = await _sc("INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) VALUES (:t,:n,false) RETURNING id", t=tenant_id, n=f"Unid {suf}")
    tipo_proc = await _sc("INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) VALUES (:t,:n,true,false) RETURNING id", t=tenant_id, n=f"Tipo {suf}")
    assunto = await _sc("INSERT INTO protocolos.assunto (tenant_id, assunto, id_tipo_processo, ativo, excluido) VALUES (:t,:n,:tp,true,false) RETURNING id", t=tenant_id, n=f"Assunto {suf}", tp=tipo_proc)

    async def _user(nome_suf, bcrypt: bool) -> int:
        return await _sc(
            "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, cpf, id_unidade_trabalho, ativo, excluido) "
            "VALUES (:t,:n,:e,:senha,:bc,:cpf,:u,true,false) RETURNING id",
            t=tenant_id, n=f"V2 {nome_suf}", e=f"{nome_suf}-{suf}@v2.local",
            senha=hash_md5(SENHA), bc=(hash_password(SENHA) if bcrypt else None),
            cpf=uuid.uuid4().hex[:11], u=unidade,
        )

    usuario_moderno = await _user("moderno", bcrypt=True)
    usuario_md5 = await _user("md5", bcrypt=False)
    usuario_outro = await _user("outro", bcrypt=True)

    processo = await _sc(
        "INSERT INTO protocolos.processo (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, numero_processo, virtual, externo, ativo, excluido, migrado, data_hora_abertura) "
        "VALUES (:t,:a,:m,:u,:num,true,false,true,false,false,NOW()) RETURNING id",
        t=tenant_id, a=assunto, m=manifestante, u=unidade, num=f"P{suf}/2026",
    )
    acao = await _sc("INSERT INTO protocolos.acao (flag, acao, status_acao, status_movimentacao, ativo, excluido) VALUES (:f,'Abertura','aberto','aberto',true,false) RETURNING id", f=f"TST_{suf}")
    movimentacao = await _sc("INSERT INTO protocolos.movimentacao (tenant_id, id_processo, id_unidade_responsavel, id_acao, data_hora_movimentacao, ativo, excluido) VALUES (:t,:p,:u,:ac,NOW(),true,false) RETURNING id", t=tenant_id, p=processo, u=unidade, ac=acao)

    e_doc = f"v2-{suf}.txt"
    anexo = await _sc(
        "INSERT INTO protocolos.anexo (tenant_id, publico, ativo, excluido, e_doc, descricao, qtd_paginas) "
        "VALUES (:t,true,true,false,:edoc,:desc,1) RETURNING id",
        t=tenant_id, edoc=e_doc, desc=f"Doc {suf}",
    )
    anexo_processo = await _sc(
        "INSERT INTO protocolos.anexo_processo (tenant_id, id_processo, id_anexo, id_movimentacao, ativo, excluido, anexo_herdado) "
        "VALUES (:t,:p,:an,:mv,true,false,false) RETURNING id",
        t=tenant_id, p=processo, an=anexo, mv=movimentacao,
    )

    # Escreve o arquivo físico no storage do tenant (para o hash).
    path = tenant_anexos_dir(slug) / e_doc
    path.write_bytes(CONTEUDO)

    return {
        "tenant_id": tenant_id, "slug": slug,
        "categoria": categoria, "tipo_manifestante": tipo_manif, "manifestante": manifestante,
        "unidade": unidade, "tipo_processo": tipo_proc, "assunto": assunto,
        "usuario_moderno": usuario_moderno, "usuario_md5": usuario_md5, "usuario_outro": usuario_outro,
        "processo": processo, "acao": acao, "movimentacao": movimentacao,
        "anexo": anexo, "anexo_processo": anexo_processo, "e_doc": e_doc, "path": path,
    }


@pytest_asyncio.fixture
async def v2_env(admin_engine, two_tenants):
    tid, _ = two_tenants
    slug = f"test-rls-a-v2-{uuid.uuid4().hex[:6]}"
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        ids = await _setup(s, tid, slug)
        await s.commit()

    yield ids

    async with Session() as s:
        await s.execute(text("UPDATE protocolos.assinatura_anexo SET id_audit_log = NULL WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM aprimora_py.audit_log WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.assinatura_anexo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.usuario_assinatura WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.solicitacao_assinatura WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo_processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.movimentacao WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.acao WHERE id = :id"), {"id": ids["acao"]})
        await s.execute(text("DELETE FROM utils.usuario WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.assunto WHERE id = :id"), {"id": ids["assunto"]})
        await s.execute(text("DELETE FROM protocolos.tipo_processo WHERE id = :id"), {"id": ids["tipo_processo"]})
        await s.execute(text("DELETE FROM utils.unidade_trabalho WHERE id = :id"), {"id": ids["unidade"]})
        await s.execute(text("DELETE FROM protocolos.manifestante WHERE id = :id"), {"id": ids["manifestante"]})
        await s.execute(text("DELETE FROM protocolos.tipo_manifestante WHERE id = :id"), {"id": ids["tipo_manifestante"]})
        await s.execute(text("DELETE FROM protocolos.categoria WHERE id = :id"), {"id": ids["categoria"]})
        await s.commit()
    try:
        ids["path"].unlink(missing_ok=True)
    except Exception:
        pass


def _session(admin_engine):
    return async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)()


async def _criar_solic(admin_engine, env, assinante_id) -> tuple[int, int]:
    """Cria solicitação para 1 assinante × 1 anexo. Retorna (solic_id, aa_id)."""
    async with _session(admin_engine) as s:
        solic = await solicitar_assinatura(
            s, env["processo"],
            SolicitarAssinaturaRequest(id_assinantes=[assinante_id], id_anexos=[env["anexo"]]),
            tenant_id=env["tenant_id"], usuario_id=assinante_id,
            unidade_solicitante_id=env["unidade"],
        )
        solic_id = solic.id
    async with _session(admin_engine) as s:
        aa_id = int((await s.execute(
            text(
                "SELECT aa.id FROM protocolos.assinatura_anexo aa "
                "JOIN protocolos.usuario_assinatura ua ON ua.id = aa.id_usuario_assinatura "
                "WHERE aa.tenant_id = :t AND ua.id_assinante = :u AND ua.id_solicitacao_assinatura = :s"
            ),
            {"t": env["tenant_id"], "u": assinante_id, "s": solic_id},
        )).scalar_one())
    return solic_id, aa_id


async def _conta_audit(s, tenant_id, acao) -> int:
    return int((await s.execute(
        text("SELECT count(*) FROM aprimora_py.audit_log WHERE tenant_id=:t AND acao=:a"),
        {"t": tenant_id, "a": acao},
    )).scalar_one())


# -------- assinatura + hash + evidências + audit --------


async def test_assinar_grava_hash_e_evidencias(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        aa = await assinar(
            s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA,
            tenant_slug=v2_env["slug"], ip="203.0.113.7", user_agent="pytest-UA",
        )
        assert aa.status == "assinada"
        assert aa.nivel_assinatura == "simples"
        assert aa.metodo_autenticacao == "senha_bcrypt"
        assert aa.hash_algoritmo == "sha256"
        assert aa.documento_hash and len(aa.documento_hash) == 64
        assert aa.ip_assinatura == "203.0.113.7"
        assert aa.evidencias and aa.evidencias["documento_hash"] == aa.documento_hash
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, tid, "assinatura.assinada") == 1


async def test_validar_detecta_alteracao(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])
    # íntegro logo após assinar
    async with _session(admin_engine) as s:
        v = await validar_assinatura(s, aa_id, tenant_id=tid, tenant_slug=v2_env["slug"], usuario=_uobj(uid))
        assert v.integro is True and v.legado is False
    # altera o arquivo → deve divergir
    v2_env["path"].write_bytes(CONTEUDO + b" ALTERADO")
    async with _session(admin_engine) as s:
        v = await validar_assinatura(s, aa_id, tenant_id=tid, tenant_slug=v2_env["slug"], usuario=_uobj(uid))
        assert v.integro is False
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, tid, "assinatura.validada") >= 1


async def test_recusar_gera_audit(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    solic_id, _aa = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await recusar_assinatura(s, solic_id, tenant_id=tid, usuario_id=uid, motivo="documento incorreto")
    async with _session(admin_engine) as s:
        st = (await s.execute(
            text("SELECT status FROM protocolos.usuario_assinatura WHERE id_solicitacao_assinatura=:s AND id_assinante=:u"),
            {"s": solic_id, "u": uid},
        )).scalar_one()
        assert st == "recusada"
        assert await _conta_audit(s, tid, "assinatura.recusada") == 1


async def test_cancelar_propaga_status(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    solic_id, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await cancelar_solicitacao(s, solic_id, tenant_id=tid, usuario_id=uid)
    async with _session(admin_engine) as s:
        st = (await s.execute(
            text("SELECT status FROM protocolos.assinatura_anexo WHERE id=:id"), {"id": aa_id}
        )).scalar_one()
        assert st == "cancelada"


# -------- bloqueios / segurança --------


async def test_md5_only_bloqueado(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_md5"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaCredencialLegadaError):
            await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])
    # não assinou
    async with _session(admin_engine) as s:
        st = (await s.execute(text("SELECT status FROM protocolos.assinatura_anexo WHERE id=:id"), {"id": aa_id})).scalar_one()
        assert st == "pendente"


async def test_usuario_moderno_assina(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        aa = await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])
        assert aa.status == "assinada"


async def test_tentativa_falha_auditada(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaError, match="Senha incorreta"):
            await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha="errada", tenant_slug=v2_env["slug"])
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, tid, "assinatura.tentativa_falha") == 1


async def test_throttle_bloqueia(admin_engine, v2_env, monkeypatch):
    """Com o throttle indicando bloqueio, assinar levanta 429-equivalente."""
    async def _bloqueado(*a, **k):
        return True
    monkeypatch.setattr("app.services.assinatura_throttle.esta_bloqueado", _bloqueado)
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaThrottleError):
            await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])


async def test_redis_indisponivel_fail_open(monkeypatch):
    """Se o Redis falhar, esta_bloqueado=False e registrar_falha=0 (fail-open)."""
    def _boom():
        raise RuntimeError("redis down")
    monkeypatch.setattr("app.services.assinatura_throttle._client", _boom)
    assert await throttle.esta_bloqueado(1, 1, 1) is False
    assert await throttle.registrar_falha(1, 1, 1) == 0


async def test_nao_destinatario_nao_assina(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    dono = v2_env["usuario_moderno"]
    outro = v2_env["usuario_outro"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, dono)
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaError, match="destinatário"):
            await assinar(s, aa_id, tenant_id=tid, usuario_id=outro, senha=SENHA, tenant_slug=v2_env["slug"])


async def test_outro_tenant_bloqueado(admin_engine, v2_env, two_tenants):
    _tid_a, tid_b = two_tenants
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaError, match="não encontrada"):
            await assinar(s, aa_id, tenant_id=tid_b, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])


async def test_imutabilidade_anexo_assinado(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await assinar(s, aa_id, tenant_id=tid, usuario_id=uid, senha=SENHA, tenant_slug=v2_env["slug"])
    async with _session(admin_engine) as s:
        with pytest.raises(DesentranhamentoError, match="assinatura"):
            await desentranhar_anexo(
                s, tenant_id=tid, usuario_id=uid,
                processo_id=v2_env["processo"], anexo_processo_id=v2_env["anexo_processo"],
                motivo="tentativa", autoridade="x",
            )


async def test_legado_nao_quebra_validacao(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    # Simula um registro legado (sem hash).
    async with _session(admin_engine) as s:
        await s.execute(
            text("UPDATE protocolos.assinatura_anexo SET nivel_assinatura='legado', status='assinada', documento_hash=NULL WHERE id=:id"),
            {"id": aa_id},
        )
        await s.commit()
    async with _session(admin_engine) as s:
        v = await validar_assinatura(s, aa_id, tenant_id=tid, tenant_slug=v2_env["slug"], usuario=_uobj(uid))
        assert v.legado is True and v.integro is None


# -------- guard de sigilo/permissão (PR2b) --------


async def _tornar_secreto(admin_engine, tenant_id, processo_id):
    async with _session(admin_engine) as s:
        await s.execute(
            text("UPDATE protocolos.processo SET nivel_sigilo='secreto' WHERE id=:p"),
            {"p": processo_id},
        )
        await s.commit()


async def test_validar_negado_sem_credencial(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    await _tornar_secreto(admin_engine, tid, v2_env["processo"])
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await validar_assinatura(
                s, aa_id, tenant_id=tid, tenant_slug=v2_env["slug"], usuario=_uobj(uid, "interno")
            )


async def test_evidencias_negado_sem_credencial(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    await _tornar_secreto(admin_engine, tid, v2_env["processo"])
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await consultar_evidencias(s, aa_id, tenant_id=tid, usuario=_uobj(uid, "interno"))


async def test_evidencias_autorizado(admin_engine, v2_env):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    _solic, aa_id = await _criar_solic(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        ev = await consultar_evidencias(s, aa_id, tenant_id=tid, usuario=_uobj(uid, "interno"))
        assert ev.id_assinatura_anexo == aa_id
        assert ev.numero_processo is not None


async def test_assert_super_bypass(admin_engine, v2_env, monkeypatch):
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    await _tornar_secreto(admin_engine, tid, v2_env["processo"])

    async def _fake_super(*a, **k):
        return SimpleNamespace(is_super_usuario=True, nivel_valor=0, items=[])
    monkeypatch.setattr("app.services.permissoes.load_permissions", _fake_super)

    async with _session(admin_engine) as s:
        # não levanta — super-usuário ignora o nível
        await assert_acesso_processo(
            s, tenant_id=tid, processo_id=v2_env["processo"], usuario=_uobj(uid, "interno")
        )


async def test_require_acesso_processo_regressao(admin_engine, v2_env):
    """Regressão da delegação: 404 para sigiloso sem credencial, ok p/ ostensivo."""
    tid = v2_env["tenant_id"]
    uid = v2_env["usuario_moderno"]
    # ostensivo (default) → não levanta
    async with _session(admin_engine) as s:
        await require_acesso_processo(
            v2_env["processo"], user=_uobj(uid, "interno"), tenant_id=tid, db=s
        )
    # secreto → 404
    await _tornar_secreto(admin_engine, tid, v2_env["processo"])
    async with _session(admin_engine) as s:
        with pytest.raises(HTTPException) as ei:
            await require_acesso_processo(
                v2_env["processo"], user=_uobj(uid, "interno"), tenant_id=tid, db=s
            )
        assert ei.value.status_code == 404


def test_comprovante_pdf_gerado():
    ev = EvidenciasOut(
        id_assinatura_anexo=1, id_anexo=2, id_processo=3,
        numero_processo="P1/2026", anexo_descricao="Doc",
        nome_assinante="Fulano", nivel="simples", status="assinada",
        metodo_autenticacao="senha_bcrypt", documento_hash="a" * 64,
        hash_algoritmo="sha256", documento_versao=1, ip_assinatura="203.0.113.7",
        user_agent_assinatura="UA", dt_assinatura=None, id_audit_log=99, evidencias={},
    )
    val = ValidacaoOut(
        id_assinatura_anexo=1, legado=False, integro=True, nivel="simples",
        status="assinada", documento_hash="a" * 64, hash_atual="a" * 64,
        dt_assinatura=None, detalhe="Conteúdo íntegro.",
    )
    pdf = gerar_comprovante_assinatura_pdf(ev, val)
    assert pdf[:4] == b"%PDF"
