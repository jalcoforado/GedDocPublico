"""Validates that the JWT we emit is decodable by an independent JWT library
using the same secret/algorithm/claims that Positiv\\LoginGlobal expects.

We use PyJWT (independent of python-jose) as a stand-in for the PHP-side
firebase/php-jwt 5.0.0 decoder: both implement RFC 7519 HS256.
"""
import jwt as pyjwt  # PyJWT

from app.auth.jwt import build_payload, encode_token


SECRET = "aprimora_dev_jwt_secret_change_in_prod_2026"


def test_emitted_token_has_required_claims():
    payload = build_payload(usuario_id=2, usuario_email="admin@local.test")
    token = encode_token(payload, SECRET)

    decoded = pyjwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        audience="http://projecttech.com.br",
        issuer="http://projecttech.com.br",
    )

    # Mirrors LoginGlobal::getTokenJwt() payload contract
    assert decoded["usuario_id"] == 2
    assert decoded["usuario_email"] == "admin@local.test"
    assert decoded["iss"] == "http://projecttech.com.br"
    assert decoded["aud"] == "http://projecttech.com.br"
    assert decoded["app"] == "sistemas"
    assert "conexao" in decoded
    assert decoded["exp"] - decoded["iat"] == 3600  # PHP fixes TTL at 3600s


def test_token_rejected_with_wrong_secret():
    payload = build_payload(usuario_id=2, usuario_email="admin@local.test")
    token = encode_token(payload, SECRET)

    try:
        pyjwt.decode(token, "wrong-secret", algorithms=["HS256"], options={"verify_aud": False})
    except pyjwt.InvalidSignatureError:
        return
    raise AssertionError("Expected InvalidSignatureError with wrong secret")
