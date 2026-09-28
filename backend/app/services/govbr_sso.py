"""Serviço de SSO com GOV.BR (OIDC).

Integra com acesso.gov.br para autenticação de cidadãos, usando OAuth 2.0 / OIDC.
"""
from __future__ import annotations

import httpx
from typing import TypedDict
from urllib.parse import urlencode

from ..config import get_settings


class GovBrUserInfo(TypedDict):
    cpf: str
    nome: str
    email: str | None
    nivel_confiabilidade: str | None # bronze, prata, ouro


class GovBrOAuthFlow:
    """Implementa o fluxo de Code Grant do Gov.br.
    
    Por enquanto, pode operar em modo mock (se GOVBR_CLIENT_ID='mock')
    para testes automatizados locais.
    """

    def __init__(self, redirect_uri: str):
        self.settings = get_settings()
        self.redirect_uri = redirect_uri
        self.client_id = getattr(self.settings, "govbr_client_id", "mock")
        self.client_secret = getattr(self.settings, "govbr_client_secret", "mock-secret")
        # URLs de homologação por padrão (podem vir do config)
        self.authorize_url = "https://sso.acesso.gov.br/authorize"
        self.token_url = "https://sso.acesso.gov.br/token"
        self.userinfo_url = "https://sso.acesso.gov.br/userinfo"

    def is_mock(self) -> bool:
        return self.client_id == "mock"

    def get_authorization_url(self, state: str) -> str:
        if self.is_mock():
            # URL de bypass em ambiente de dev/teste
            return f"http://localhost:8000/api/v2/auth/govbr/mock-login?state={state}"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": "openid profile email govbr_confiabilidades",
            "redirect_uri": self.redirect_uri,
            "nonce": state,
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def fetch_token_and_userinfo(self, code: str) -> GovBrUserInfo:
        if self.is_mock():
            # No mock, o code próprio carrega o CPF para facilitar testes (ex: "mock-code-12345678909")
            cpf = code.split("-")[-1] if "-" in code else "00000000000"
            return {
                "cpf": cpf,
                "nome": "Cidadão Mock da Silva",
                "email": f"cidadao.{cpf}@mock.local",
                "nivel_confiabilidade": "prata"
            }

        # Fluxo real
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                auth=(self.client_id, self.client_secret)
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data["access_token"]

            user_resp = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            return {
                "cpf": user_data.get("sub", ""),
                "nome": user_data.get("name", "Cidadão"),
                "email": user_data.get("email"),
                "nivel_confiabilidade": user_data.get("nivel_confiabilidade", "bronze"),
            }
