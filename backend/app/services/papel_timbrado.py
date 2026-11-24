"""Papel timbrado da prefeitura nos documentos redigidos no processo (SI-53).

Todo documento que nasce do editor (finalização de minuta e despacho, via
`minutas.virar_anexo_sem_commit`) sai com:

- **cabeçalho** — o brasão da prefeitura e o nome dela, centralizados, no topo
  da primeira página;
- **rodapé fixo** — endereço, telefone, e-mail e site, em todas as páginas.

Por que no PDF e não dentro do texto do modelo: no texto, quem redige pode
apagar o cabeçalho sem querer, e o título do documento (`<h1 class=
"doc-titulo">`, montado por `html_pdf`) sairia ACIMA do brasão. O timbre é da
prefeitura, não do documento.

O que fica de fora de propósito: os PDFs de pagamentos (ordem de pagamento,
exportações), que também usam `html_to_pdf_bytes` mas não passam `timbre`.

**De onde vem o brasão.** `tenant.logo_url` aponta para uma imagem do frontend
(`/brand/<arquivo>`, em `frontend/public/brand/`), que o backend não enxerga.
A cópia que o PDF usa mora em `app/static/brand/` com o MESMO nome de arquivo.
Sem a cópia, o timbre sai só com o nome — degrada, não quebra. Ao trocar o
brasão de um município, troque os dois arquivos.

A pré-visualização da tela recebe este mesmo HTML por
`GET /templates-documento/estilo-impressao` — uma fonte só, para a tela não
mostrar um timbre e o PDF imprimir outro.
"""
from __future__ import annotations

import base64
import html as _html
import re
from dataclasses import dataclass
from pathlib import Path

from ..models import Tenant

PASTA_BRASOES = Path(__file__).resolve().parent.parent / "static" / "brand"

# Só `/brand/<nome simples>.png|jpg` vira caminho de disco — nada de `..`,
# subpasta ou URL externa chega ao `Path`.
_LOGO_URL_RE = re.compile(r"^/brand/([a-z0-9][a-z0-9._-]*\.(png|jpe?g))$", re.IGNORECASE)
_MIME = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg"}


@dataclass(frozen=True)
class PapelTimbrado:
    nome: str
    brasao_data_uri: str | None
    linhas_rodape: tuple[str, ...]

    def cabecalho_html(self) -> str:
        brasao = (
            f'<img class="timbre-brasao" src="{self.brasao_data_uri}" alt="Brasão">'
            if self.brasao_data_uri
            else ""
        )
        return (
            f'<header class="timbre">{brasao}'
            f'<p class="timbre-nome">{_html.escape(self.nome)}</p></header>'
        )

    def rodape_html(self) -> str:
        if not self.linhas_rodape:
            return ""
        texto = " · ".join(_html.escape(linha) for linha in self.linhas_rodape)
        return f'<footer class="timbre-rodape">{texto}</footer>'


def _brasao_data_uri(logo_url: str | None) -> str | None:
    m = _LOGO_URL_RE.match(logo_url or "")
    if not m:
        return None
    caminho = PASTA_BRASOES / m.group(1)
    if not caminho.is_file():
        return None
    dados = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:image/{_MIME[m.group(2).lower()]};base64,{dados}"


def _site_sem_protocolo(site: str) -> str:
    return re.sub(r"^https?://", "", site).rstrip("/")


def papel_timbrado(tenant: Tenant) -> PapelTimbrado:
    linhas = [
        tenant.endereco,
        tenant.telefone_institucional,
        tenant.email_institucional,
        _site_sem_protocolo(tenant.site_oficial) if tenant.site_oficial else None,
    ]
    return PapelTimbrado(
        nome=tenant.nome,
        brasao_data_uri=_brasao_data_uri(tenant.logo_url),
        linhas_rodape=tuple(linha.strip() for linha in linhas if linha and linha.strip()),
    )
