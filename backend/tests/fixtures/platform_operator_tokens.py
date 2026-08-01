"""Fixtures de token administrativo para a fronteira de plataforma (SEC-00).

NENHUMA CHAVE REAL VIVE AQUI. O par RSA é gerado em memória a cada execução da
suíte e some com o processo. O issuer e a audience são fictícios e não
correspondem a nenhum ambiente. Copiar um client ID ou um token de produção
para este arquivo é violação direta do ADR-016.

Por que este módulo existe antes do validador:
    `SEC-00` é um PR de decisão. O validador de token administrativo nasce em
    `SEC-01A`. Estes fixtures são o contrato que ele vai consumir — escrevê-los
    agora força a matriz de claims a ser concreta em vez de prosa, e o
    `test_platform_operator_fixtures.py` prova que o próprio fixture faz o que
    diz.

O que ele deliberadamente NÃO faz:
    Não valida nada. Não importa `app.*`. Não toca no banco. É um emissor de
    tokens de teste, e emissor não é validador — misturar os dois produziria um
    teste que só prova que o mesmo código concorda consigo mesmo.

Referências:
    docs/architecture/adr/ADR-016-platform-operator-identity.md
    docs/architecture/security/platform-operator-claims-matrix.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

# Valores fictícios. Nenhum corresponde a ambiente real — ver ADR-016 §2.7.
TEST_ISSUER = "https://operator.test.local"
TEST_AUDIENCE = "aprimora-operator-test"
TEST_HOSTED_DOMAIN = "test.local"
TEST_KID = "operator-test-key-1"

# Realm municipal, para os testes de confusão de token (matriz, cenários 4 e 16).
# Espelham os defaults de `Settings`; ficam aqui como literais de propósito, para
# o fixture não importar a aplicação.
MUNICIPAL_ISSUER = "http://projecttech.com.br"
MUNICIPAL_AUDIENCE = "http://projecttech.com.br"


@dataclass(frozen=True)
class OperatorTestKeys:
    """Par RSA efêmero + o JWKS correspondente."""

    private_pem: str
    public_pem: str
    jwks: dict[str, Any]
    kid: str = TEST_KID


def gerar_chaves(kid: str = TEST_KID) -> OperatorTestKeys:
    """Gera um par RSA novo em memória. Nunca persiste em disco."""
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = chave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        chave.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    numeros = chave.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": _b64u_int(numeros.n),
                "e": _b64u_int(numeros.e),
            }
        ]
    }
    return OperatorTestKeys(private_pem=private_pem, public_pem=public_pem, jwks=jwks, kid=kid)


def _b64u_int(valor: int) -> str:
    import base64

    bruto = valor.to_bytes((valor.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(bruto).rstrip(b"=").decode()


@dataclass
class OperatorTokenFactory:
    """Emite tokens administrativos de teste.

    O default é um token que a matriz de claims aceita. Cada cenário de negação
    é obtido sobrescrevendo exatamente um aspecto — assim o teste que falha
    aponta para uma causa só.
    """

    keys: OperatorTestKeys = field(default_factory=gerar_chaves)

    def token(
        self,
        *,
        subject: str = "operator-test-subject-1",
        issuer: str = TEST_ISSUER,
        audience: str = TEST_AUDIENCE,
        hosted_domain: str | None = TEST_HOSTED_DOMAIN,
        email: str | None = "operador@test.local",
        email_verified: bool = True,
        expira_em: int = 900,
        emitido_ha: int = 0,
        nbf_delta: int | None = None,
        algoritmo: str = "RS256",
        kid: str | None = None,
        claims_extras: dict[str, Any] | None = None,
        omitir: tuple[str, ...] = (),
        segredo_hs256: str | None = None,
    ) -> str:
        """Emite um token. Sem argumentos, emite o caso feliz.

        `claims_extras` serve aos cenários de confusão de token — injetar
        `usuario_id`, `tenant_id`, `cidadao_id` etc., que a matriz manda
        rejeitar em vez de ignorar.

        `segredo_hs256` produz o cenário 7: token HS256 assinado com o segredo
        municipal, que a fronteira de plataforma tem de recusar pelo algoritmo.
        """
        agora = int(time.time())
        payload: dict[str, Any] = {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": agora - emitido_ha,
            "exp": agora - emitido_ha + expira_em,
        }
        if hosted_domain is not None:
            payload["hd"] = hosted_domain
        if email is not None:
            payload["email"] = email
            payload["email_verified"] = email_verified
        if nbf_delta is not None:
            payload["nbf"] = agora + nbf_delta
        if claims_extras:
            payload.update(claims_extras)
        for claim in omitir:
            payload.pop(claim, None)

        if segredo_hs256 is not None:
            return jwt.encode(payload, segredo_hs256, algorithm="HS256")

        headers = {"kid": kid if kid is not None else self.keys.kid}
        return jwt.encode(payload, self.keys.private_pem, algorithm=algoritmo, headers=headers)

    # ---- Atalhos para os cenários nomeados da matriz de claims ----

    def token_valido(self, subject: str = "operator-test-subject-1") -> str:
        """Cenário 1."""
        return self.token(subject=subject)

    def token_expirado(self) -> str:
        """Cenário 9 — expirado além da tolerância de 60 s."""
        return self.token(expira_em=1, emitido_ha=120)

    def token_emitido_no_futuro(self) -> str:
        """Cenário 10."""
        return self.token(emitido_ha=-300)

    def token_de_outro_ambiente(self) -> str:
        """Cenário 6 — audience de outro ambiente."""
        return self.token(audience="aprimora-operator-outro-ambiente")

    def token_de_outro_issuer(self, subject: str = "operator-test-subject-1") -> str:
        """Cenário 15 — mesmo subject, issuer diferente: não é a mesma identidade."""
        return self.token(issuer="https://outro-idp.test.local", subject=subject)

    def token_hd_errado(self) -> str:
        """Cenário 13."""
        return self.token(hosted_domain="dominio-alheio.test")

    def token_email_nao_verificado(self) -> str:
        """Cenário 14."""
        return self.token(email_verified=False)

    def token_kid_desconhecido(self) -> str:
        """Cenário 11."""
        return self.token(kid="kid-que-nao-esta-no-jwks")

    def token_hs256_com_segredo_municipal(self, segredo: str) -> str:
        """Cenário 7 — o segredo municipal não pode valer nesta fronteira."""
        return self.token(segredo_hs256=segredo)

    def token_com_claims_municipais(self) -> str:
        """Seção 2 da matriz — claims que provam que o token não é de plataforma."""
        return self.token(
            claims_extras={
                "usuario_id": 1,
                "tenant_id": 1,
                "conexao": "ged_saas_db",
                "app": "sistemas",
            }
        )


def payload_municipal_falso(
    *, usuario_id: int = 1, tenant_id: int = 1, expira_em: int = 3600
) -> dict[str, Any]:
    """Payload no formato de `app.auth.jwt.build_payload`, para os cenários 4 e 16.

    Replicado como literal em vez de importado: o fixture precisa continuar
    representando o realm municipal mesmo que a aplicação mude, e é justamente a
    divergência entre os dois que o teste de confusão de token deve detectar.
    """
    agora = int(time.time())
    return {
        "iss": MUNICIPAL_ISSUER,
        "aud": MUNICIPAL_AUDIENCE,
        "iat": agora,
        "exp": agora + expira_em,
        "usuario_id": usuario_id,
        "usuario_email": "usuario@municipio.test",
        "conexao": "ged_saas_db",
        "app": "sistemas",
        "tenant_id": tenant_id,
    }
