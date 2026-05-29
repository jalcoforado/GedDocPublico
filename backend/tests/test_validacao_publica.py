"""Validação pública de assinatura por código/token (PR2e).

Matriz obrigatória (escopo): token válido íntegro, inexistente, revogado,
processo sigiloso, ostensivo→sigiloso (lazy), hash divergente, sem dados
sensíveis na resposta, rate-limit, auditoria sem inundar, comprovante público
sem evidências internas, QR para a URL pública.

Estilo service-level (como test_assinatura_v2): admin_engine (BYPASSRLS),
reusa o env e helpers daquele módulo.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.config import validacao_publica_url
from app.schemas.assinatura import EvidenciasOut, ValidacaoPublicaOut
from app.services import validacao_publica_throttle as throttle
from app.services.assinaturas import assinar, consultar_evidencias
from app.services.pdf_comprovante_assinatura import gerar_comprovante_publico_pdf
from app.services.validacao_publica import (
    revogar_validacao_publica,
    status_validacao_publica,
    validar_publico,
)

# Reusa fixture + helpers do módulo de assinatura v2.
from .test_assinatura_v2 import (  # noqa: F401
    SENHA,
    _conta_audit,
    _criar_solic,
    _session,
    _tornar_secreto,
    _uobj,
    v2_env,
)

IP_ASSINATURA = "203.0.113.42"
UA_ASSINATURA = "agente-secreto-interno/1.0"


async def _assinar(admin_engine, env, uid) -> tuple[int, str]:
    """Cria solicitação, assina (gera o código) e devolve (aa_id, codigo)."""
    _solic, aa_id = await _criar_solic(admin_engine, env, uid)
    async with _session(admin_engine) as s:
        aa = await assinar(
            s, aa_id, tenant_id=env["tenant_id"], usuario_id=uid, senha=SENHA,
            tenant_slug=env["slug"], ip=IP_ASSINATURA, user_agent=UA_ASSINATURA,
        )
        codigo = aa.codigo_validacao
    assert codigo
    return aa_id, codigo


# 1 -------------------------------------------------------------------------
async def test_token_valido_integro(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    _aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert r is not None
    assert r.valido is True and r.integro is True
    assert r.signatario  # nome do servidor exibido
    assert r.hash and len(r.hash) == 64
    assert r.processo_numero  # processo ostensivo → exibe número
    # audita a validação pública positiva
    async with _session(admin_engine) as s:
        assert await _conta_audit(s, v2_env["tenant_id"], "assinatura.validada_publica") == 1


# 2 -------------------------------------------------------------------------
async def test_token_inexistente_neutro(admin_engine, v2_env):
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, "codigo-que-nao-existe-xyz", tenant_id=v2_env["tenant_id"],
            tenant_slug=v2_env["slug"], ip="1.1.1.1",
        )
    assert r is None


# 3 -------------------------------------------------------------------------
async def test_token_revogado_neutro(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await revogar_validacao_publica(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
            motivo="revogação de teste",
        )
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert r is None


# 4 -------------------------------------------------------------------------
async def test_processo_sigiloso_neutro(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    _aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    await _tornar_secreto(admin_engine, v2_env["tenant_id"], v2_env["processo"])
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert r is None


# 5 -------------------------------------------------------------------------
async def test_ostensivo_virou_sigiloso_deixa_de_validar(admin_engine, v2_env):
    """Validava enquanto ostensivo; após virar sigiloso, passa a responder neutro
    (re-check lazy, sem revogação eager)."""
    uid = v2_env["usuario_moderno"]
    _aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        antes = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert antes is not None and antes.valido is True

    await _tornar_secreto(admin_engine, v2_env["tenant_id"], v2_env["processo"])
    async with _session(admin_engine) as s:
        depois = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert depois is None


# 6 -------------------------------------------------------------------------
async def test_hash_divergente_valido_mas_nao_integro(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    _aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    # Altera o conteúdo do arquivo após a assinatura → hash diverge.
    v2_env["path"].write_bytes(b"conteudo adulterado depois de assinar")
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert r is not None
    assert r.valido is True and r.integro is False
    # Não expõe metadados sensíveis nem no caso divergente.
    dump = r.model_dump()
    assert IP_ASSINATURA not in str(dump) and UA_ASSINATURA not in str(dump)


# 7 -------------------------------------------------------------------------
async def test_resposta_sem_dados_sensiveis(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    _aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        r = await validar_publico(
            s, codigo, tenant_id=v2_env["tenant_id"], tenant_slug=v2_env["slug"], ip="1.1.1.1"
        )
    assert r is not None
    campos = set(ValidacaoPublicaOut.model_fields)
    proibidos = {
        "ip", "ip_assinatura", "user_agent", "user_agent_assinatura",
        "metodo_autenticacao", "email", "cpf", "matricula", "evidencias",
    }
    assert campos.isdisjoint(proibidos)
    # Os valores também não vazam o IP/UA usados na assinatura.
    blob = str(r.model_dump())
    for proibido in (IP_ASSINATURA, UA_ASSINATURA):
        assert proibido not in blob


# 8 -------------------------------------------------------------------------
class _FakeRedis:
    def __init__(self, valor=None):
        self._valor = valor

    async def get(self, _k):
        return self._valor

    async def incr(self, _k):
        return 1

    async def expire(self, _k, _s):
        return True

    async def set(self, _k, _v, ex=None, nx=False):  # noqa: A002
        return True

    async def aclose(self):
        return None


async def test_rate_limit_dispara_apos_limite(monkeypatch):
    # Acima do limite → bloqueado.
    monkeypatch.setattr(
        "app.services.validacao_publica_throttle._client",
        lambda: _FakeRedis(valor=str(throttle.LIMITE_IP).encode()),
    )
    assert await throttle.esta_bloqueado_ip("9.9.9.9") is True

    # Abaixo do limite → liberado.
    monkeypatch.setattr(
        "app.services.validacao_publica_throttle._client",
        lambda: _FakeRedis(valor=b"1"),
    )
    assert await throttle.esta_bloqueado_ip("9.9.9.9") is False


async def test_rate_limit_fail_open_sem_redis(monkeypatch):
    def _boom():
        raise RuntimeError("redis down")
    monkeypatch.setattr("app.services.validacao_publica_throttle._client", _boom)
    assert await throttle.esta_bloqueado_ip("9.9.9.9") is False


# 9 -------------------------------------------------------------------------
async def test_auditoria_negativa_nao_inunda(admin_engine, v2_env, monkeypatch):
    """Sob enumeração, a auditoria das respostas neutras é deduplicada por IP:
    muitas tentativas → no máximo 1 linha por janela."""
    chamadas = {"n": 0}

    async def _dedup(_ip):
        chamadas["n"] += 1
        return chamadas["n"] == 1  # True só na 1ª

    monkeypatch.setattr(
        "app.services.validacao_publica_throttle.deve_auditar_negativa", _dedup
    )
    for _ in range(8):
        async with _session(admin_engine) as s:
            r = await validar_publico(
                s, f"inexistente-{uuid.uuid4().hex}", tenant_id=v2_env["tenant_id"],
                tenant_slug=v2_env["slug"], ip="7.7.7.7",
            )
            assert r is None
    async with _session(admin_engine) as s:
        assert await _conta_audit(
            s, v2_env["tenant_id"], "assinatura.validacao_publica_negada"
        ) == 1


# 10 ------------------------------------------------------------------------
def test_comprovante_publico_sem_evidencias_internas():
    """O comprovante público é montado a partir de um modelo minimizado que
    NÃO tem campos sensíveis (ao contrário do EvidenciasOut interno)."""
    pub = set(ValidacaoPublicaOut.model_fields)
    interno = set(EvidenciasOut.model_fields)
    sensiveis = {"ip_assinatura", "user_agent_assinatura", "metodo_autenticacao", "evidencias"}
    assert sensiveis & interno == sensiveis  # o interno tem (controle)
    assert pub.isdisjoint(sensiveis)  # o público não tem

    resultado = ValidacaoPublicaOut(
        valido=True, integro=True, signatario="Fulano de Tal",
        processo_numero="P123/2026", hash="a" * 64, algoritmo="sha256",
        versao_documento=1, status="assinada",
    )
    url = validacao_publica_url("sobral", "tok123")
    pdf = gerar_comprovante_publico_pdf(resultado, codigo="tok123", url_validacao=url)
    assert pdf.startswith(b"%PDF")


# 11 ------------------------------------------------------------------------
def test_url_publica_para_qr():
    # Deriva do subdomínio quando public_base_url está vazio (default dev).
    url = validacao_publica_url("sobral", "abc-XYZ_123")
    assert url == "https://sobral.aprimora.local/validar/abc-XYZ_123"


def test_url_publica_respeita_public_base_url(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://protocolo.sobral.ce.gov.br/")
    try:
        url = validacao_publica_url("sobral", "tok")
        assert url == "https://protocolo.sobral.ce.gov.br/validar/tok"
    finally:
        get_settings.cache_clear()


# ===== PR2f — status na fonte única + evidências internas =====================

def test_helper_status_cobre_os_5_estados():
    base = dict(
        codigo_validacao="tok", documento_hash="h", assinado=True,
        status_assinatura="assinada", validacao_publica_revogada=False,
        nivel_sigilo="ostensivo", anexo_desentranhado=False,
    )
    assert status_validacao_publica(**base) == "ativa"
    assert status_validacao_publica(**{**base, "validacao_publica_revogada": True}) == "revogada"
    assert status_validacao_publica(**{**base, "nivel_sigilo": "secreto"}) == "bloqueada_sigilo"
    assert status_validacao_publica(**{**base, "anexo_desentranhado": True}) == "indisponivel"
    assert status_validacao_publica(**{**base, "codigo_validacao": None}) == "nao_aplicavel"
    assert status_validacao_publica(**{**base, "documento_hash": None}) == "nao_aplicavel"


async def test_evidencias_status_ativa_com_url(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    aa_id, codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        ev = await consultar_evidencias(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
            tenant_slug=v2_env["slug"],
        )
    assert ev.validacao_publica_status == "ativa"
    assert ev.validacao_publica_url and ev.validacao_publica_url.endswith(f"/validar/{codigo}")
    assert ev.codigo_validacao == codigo


async def test_evidencias_status_bloqueada_sigilo_para_autorizado(admin_engine, v2_env, monkeypatch):
    """Usuário com acesso (super) vê status bloqueada_sigilo — sem expor como ativa."""
    uid = v2_env["usuario_moderno"]
    aa_id, _codigo = await _assinar(admin_engine, v2_env, uid)
    await _tornar_secreto(admin_engine, v2_env["tenant_id"], v2_env["processo"])

    async def _fake_super(*a, **k):
        return SimpleNamespace(is_super_usuario=True, nivel_valor=0, items=[])
    monkeypatch.setattr("app.services.permissoes.load_permissions", _fake_super)

    async with _session(admin_engine) as s:
        ev = await consultar_evidencias(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
            tenant_slug=v2_env["slug"],
        )
    assert ev.validacao_publica_status == "bloqueada_sigilo"


async def test_evidencias_negado_sem_acesso_continua_404(admin_engine, v2_env):
    from app.services.assinaturas import AssinaturaError  # noqa: F401
    from app.services.sigilo import SigiloAcessoError

    uid = v2_env["usuario_moderno"]
    aa_id, _codigo = await _assinar(admin_engine, v2_env, uid)
    await _tornar_secreto(admin_engine, v2_env["tenant_id"], v2_env["processo"])
    async with _session(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await consultar_evidencias(
                s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
                tenant_slug=v2_env["slug"],
            )


async def test_revogacao_muda_status_e_audita(admin_engine, v2_env):
    uid = v2_env["usuario_moderno"]
    aa_id, _codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        await revogar_validacao_publica(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
            motivo="documento substituído",
        )
    async with _session(admin_engine) as s:
        ev = await consultar_evidencias(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
            tenant_slug=v2_env["slug"],
        )
        assert ev.validacao_publica_status == "revogada"
        assert await _conta_audit(
            s, v2_env["tenant_id"], "assinatura.validacao_publica_revogada"
        ) == 1


async def test_revogacao_motivo_opcional(admin_engine, v2_env):
    """Revogar sem motivo é permitido (motivo opcional)."""
    uid = v2_env["usuario_moderno"]
    aa_id, _codigo = await _assinar(admin_engine, v2_env, uid)
    async with _session(admin_engine) as s:
        aa = await revogar_validacao_publica(
            s, aa_id, tenant_id=v2_env["tenant_id"], usuario=_uobj(uid, "interno"),
        )
    assert aa.validacao_publica_revogada is True
