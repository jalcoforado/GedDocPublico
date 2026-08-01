"""SEC-00 — prova que os fixtures de token administrativo fazem o que dizem.

Estes testes NÃO validam a fronteira de plataforma: ela não existe ainda,
nasce em `SEC-01A`. O que eles travam é a qualidade do próprio fixture, porque
um fixture errado produziria em `SEC-01A` testes verdes que não provam nada.

Três propriedades importam aqui:
  1. o par de chaves é efêmero e nada real está versionado;
  2. cada cenário nomeado da matriz produz de fato o desvio que o nome promete;
  3. o realm municipal e o de plataforma são distinguíveis só pelos claims —
     que é a premissa inteira do ADR-016.

Referência: docs/architecture/security/platform-operator-claims-matrix.md
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from jose import jwt

from tests.fixtures.platform_operator_tokens import (
    MUNICIPAL_AUDIENCE,
    MUNICIPAL_ISSUER,
    TEST_AUDIENCE,
    TEST_HOSTED_DOMAIN,
    TEST_ISSUER,
    OperatorTokenFactory,
    gerar_chaves,
    payload_municipal_falso,
)

CLAIMS_MUNICIPAIS = ("usuario_id", "cidadao_id", "tenant_id", "conexao", "app")


@pytest.fixture()
def fabrica() -> OperatorTokenFactory:
    return OperatorTokenFactory()


def _sem_verificar(token: str) -> dict:
    """Lê os claims sem validar assinatura — é o fixture que está sob teste."""
    return jwt.get_unverified_claims(token)


def test_chaves_sao_efemeras_e_diferentes_a_cada_geracao():
    """Chave fixa em repositório vira chave de produção por acidente."""
    assert gerar_chaves().private_pem != gerar_chaves().private_pem


def test_nenhuma_chave_privada_versionada_no_modulo_de_fixtures():
    """A regra do ADR-016 é 'nenhuma chave real no repo' — isto a torna executável."""
    fonte = Path(__file__).parent / "fixtures" / "platform_operator_tokens.py"
    conteudo = fonte.read_text(encoding="utf-8")
    for marcador in ("BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY", "BEGIN EC PRIVATE KEY"):
        assert marcador not in conteudo, f"chave privada versionada em {fonte}"


def test_token_valido_traz_todos_os_claims_obrigatorios(fabrica: OperatorTokenFactory):
    claims = _sem_verificar(fabrica.token_valido())
    for obrigatorio in ("iss", "aud", "sub", "iat", "exp", "hd", "email_verified"):
        assert obrigatorio in claims, f"claim obrigatório ausente: {obrigatorio}"
    assert claims["iss"] == TEST_ISSUER
    assert claims["aud"] == TEST_AUDIENCE
    assert claims["hd"] == TEST_HOSTED_DOMAIN
    assert claims["email_verified"] is True


def test_token_valido_nao_carrega_nenhum_claim_municipal(fabrica: OperatorTokenFactory):
    """Se o caso feliz já trouxesse claim municipal, o cenário de confusão não distinguiria nada."""
    claims = _sem_verificar(fabrica.token_valido())
    presentes = [c for c in CLAIMS_MUNICIPAIS if c in claims]
    assert presentes == [], f"token de plataforma contaminado com claims municipais: {presentes}"


def test_token_valido_e_verificavel_pela_chave_publica_do_jwks(fabrica: OperatorTokenFactory):
    """O caso feliz precisa ser genuinamente verificável — senão `SEC-01A` negaria tudo."""
    claims = jwt.decode(
        fabrica.token_valido(),
        fabrica.keys.public_pem,
        algorithms=["RS256"],
        audience=TEST_AUDIENCE,
        issuer=TEST_ISSUER,
    )
    assert claims["sub"] == "operator-test-subject-1"


def test_header_declara_rs256_e_o_kid_do_jwks(fabrica: OperatorTokenFactory):
    header = jwt.get_unverified_header(fabrica.token_valido())
    assert header["alg"] == "RS256"
    assert header["kid"] == fabrica.keys.jwks["keys"][0]["kid"]


def test_jwks_expoe_exatamente_a_chave_que_assina(fabrica: OperatorTokenFactory):
    chaves = fabrica.keys.jwks["keys"]
    assert len(chaves) == 1
    assert chaves[0]["kty"] == "RSA"
    assert chaves[0]["alg"] == "RS256"
    assert chaves[0]["use"] == "sig"


def test_token_expirado_esta_realmente_no_passado(fabrica: OperatorTokenFactory):
    """Cenário 9 — além da tolerância de 60 s da matriz."""
    assert _sem_verificar(fabrica.token_expirado())["exp"] < int(time.time()) - 60


def test_token_emitido_no_futuro_tem_iat_adiante(fabrica: OperatorTokenFactory):
    """Cenário 10."""
    assert _sem_verificar(fabrica.token_emitido_no_futuro())["iat"] > int(time.time()) + 60


def test_token_de_outro_ambiente_muda_so_a_audience(fabrica: OperatorTokenFactory):
    """Cenário 6 — o desvio precisa ser só o `aud`, senão o teste de SEC-01A fica ambíguo."""
    claims = _sem_verificar(fabrica.token_de_outro_ambiente())
    assert claims["aud"] != TEST_AUDIENCE
    assert claims["iss"] == TEST_ISSUER


def test_token_de_outro_issuer_preserva_o_subject(fabrica: OperatorTokenFactory):
    """Cenário 15 — mesmo `sub`, issuer diferente: não é a mesma identidade."""
    claims = _sem_verificar(fabrica.token_de_outro_issuer())
    assert claims["iss"] != TEST_ISSUER
    assert claims["sub"] == "operator-test-subject-1"


def test_token_hd_errado_muda_so_o_dominio(fabrica: OperatorTokenFactory):
    """Cenário 13."""
    claims = _sem_verificar(fabrica.token_hd_errado())
    assert claims["hd"] != TEST_HOSTED_DOMAIN
    assert claims["iss"] == TEST_ISSUER and claims["aud"] == TEST_AUDIENCE


def test_token_email_nao_verificado(fabrica: OperatorTokenFactory):
    """Cenário 14."""
    assert _sem_verificar(fabrica.token_email_nao_verificado())["email_verified"] is False


def test_token_kid_desconhecido_nao_esta_no_jwks(fabrica: OperatorTokenFactory):
    """Cenário 11."""
    kid = jwt.get_unverified_header(fabrica.token_kid_desconhecido())["kid"]
    assert kid not in {k["kid"] for k in fabrica.keys.jwks["keys"]}


def test_token_hs256_usa_algoritmo_simetrico_com_o_segredo_municipal(
    fabrica: OperatorTokenFactory,
):
    """Cenário 7 — quem conhece o segredo do PHP não pode alcançar a plataforma."""
    token = fabrica.token_hs256_com_segredo_municipal("segredo-municipal-de-teste")
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    # E ele é genuinamente válido sob HS256 — é justamente por isso que o
    # validador de plataforma precisa recusar pelo ALGORITMO, não pela assinatura.
    assert jwt.decode(
        token,
        "segredo-municipal-de-teste",
        algorithms=["HS256"],
        audience=TEST_AUDIENCE,
        issuer=TEST_ISSUER,
    )["sub"] == "operator-test-subject-1"


def test_token_com_claims_municipais_carrega_os_marcadores_de_confusao(
    fabrica: OperatorTokenFactory,
):
    """Seção 2 da matriz: estes claims são motivo de rejeição, não de ignorar."""
    claims = _sem_verificar(fabrica.token_com_claims_municipais())
    for esperado in ("usuario_id", "tenant_id", "conexao", "app"):
        assert esperado in claims


def test_payload_municipal_falso_e_distinguivel_do_de_plataforma():
    """Cenários 4 e 16 — a premissa do ADR-016 é que iss/aud separam os realms."""
    municipal = payload_municipal_falso()
    assert municipal["iss"] == MUNICIPAL_ISSUER != TEST_ISSUER
    assert municipal["aud"] == MUNICIPAL_AUDIENCE != TEST_AUDIENCE
    assert "usuario_id" in municipal
    assert "sub" not in municipal


def test_omitir_remove_claim_obrigatorio(fabrica: OperatorTokenFactory):
    """Permite a SEC-01A testar ausência de claim obrigatório sem token artesanal."""
    assert "hd" not in _sem_verificar(fabrica.token(omitir=("hd",)))
