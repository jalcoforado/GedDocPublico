"""Serviço de Assinatura Avançada via Gov.br (ICP-Brasil).

Utiliza o pyHanko para manipular o PDF (gerar o hash e embutir a assinatura) e
consome a API do Gov.br para assinar o hash.
"""
from __future__ import annotations

import base64
import httpx
from datetime import datetime
from io import BytesIO

from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.pdf_utils.writer import copy_into_new_writer
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers, fields
from pyhanko.sign.general import load_cert_from_pemder

from pyhanko.sign import signers, fields
from pyhanko.sign.general import load_cert_from_pemder
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.fields import SigSeedSubFilter
import hashlib

# TODO: Configurar client_id, secret, e urls no config.py
GOVBR_API_URL = "https://api.assinatura.gov.br"

class GovBrExternalSigner(signers.Signer):
    def __init__(self, access_token: str):
        self.access_token = access_token
        # O Gov.br Assinatura gera o CMS. Precisamos passar um cert dummy pro pyHanko não falhar,
        # ou ajustar o fluxo para CMS deferred. Como o pyHanko precisa do cert, assumimos
        # que o fluxo deferred_sign é melhor, mas vamos usar um override simples por enquanto.
        super().__init__()

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        if dry_run:
            # Retorna um CMS falso com tamanho suficiente (~8KB é típico para Gov.br)
            return b"0" * 8192
            
        # Hash do conteúdo
        hasher = hashlib.new(digest_algorithm)
        hasher.update(data)
        hash_b64 = base64.b64encode(hasher.digest()).decode("ascii")

        # Chama a API
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GOVBR_API_URL}/assinarPKCS7",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"hashBase64": hash_b64}
            )
            if resp.status_code != 200:
                raise Exception(f"Erro no Gov.br: {resp.text}")
                
            data = resp.json()
            cms_b64 = data["assinaturaBase64"]
            return base64.b64decode(cms_b64)

class GovBrAssinaturaService:
    def __init__(self, access_token: str):
        self.signer = GovBrExternalSigner(access_token)
    
    async def assinar_pdf(self, pdf_bytes: bytes, motivo: str = "Assinatura Digital GOV.BR") -> bytes:
        """Lê um PDF, gera o hash, assina via Gov.br e retorna o PDF assinado."""
        in_stream = BytesIO(pdf_bytes)
        out_stream = BytesIO()
        
        # O pyhanko precisa criar o writer
        writer = IncrementalPdfFileWriter(in_stream)
        
        # Inicia a configuração da assinatura
        meta = signers.PdfSignatureMetadata(
            field_name='AssinaturaGovBr',
            md_algorithm='sha256',
            reason=motivo,
            subfilter=SigSeedSubFilter.ADOBE_PKCS7_DETACHED
        )
        
        # Executa a assinatura usando nosso ExternalSigner que bate na API do governo
        await signers.async_sign_pdf(
            writer,
            meta,
            signer=self.signer,
            out=out_stream
        )
        
        return out_stream.getvalue()

