"""Cabeçalho e rodapé comuns dos relatórios em PDF (Processos, Tramitação,
Assinaturas).

Os três PDFs saíam com "APRIMORA — Relatório de …" no alto e "Página N" no pé:
o nome do sistema no lugar do órgão, sem dizer quem emitiu e sem o total de
páginas — um relatório impresso e grampeado não deixava conferir se estava
completo. Agora o título leva o nome do órgão (o `tenant.nome`), a linha de
emissão diz quando e por quem, e o rodapé numera "Página X de Y".

O brasão fica de fora por falta de fonte: o sistema só guarda `logo_url`, uma
URL, e buscar URL no servidor para montar PDF é o vetor de SSRF que o
`html_pdf` fecha de propósito. Entra quando houver brasão salvo em disco.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

GRAY = HexColor("#6b7280")


@dataclass(frozen=True)
class Emissao:
    orgao: str = ""
    emitido_por: str | None = None
    emitido_em: datetime = field(default_factory=datetime.now)

    def titulo(self, relatorio: str) -> str:
        return f"{self.orgao or 'Aprimora'} — {relatorio}"

    def linha(self) -> str:
        quando = self.emitido_em.strftime("%d/%m/%Y %H:%M")
        return f"Emitido em {quando} por {self.emitido_por}" if self.emitido_por else f"Emitido em {quando}"


async def emissao_de(db: AsyncSession, *, tenant_id: int, usuario) -> Emissao:
    from ..models import Tenant  # lazy: evita ciclo de import

    orgao = (
        await db.execute(select(Tenant.nome).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    return Emissao(orgao=orgao or "", emitido_por=getattr(usuario, "nome", None))


def canvas_numerado(emissao: Emissao, margem: float = 1.5 * cm):
    """Canvas que guarda as páginas e só desenha o rodapé no `save`, quando o
    total já é conhecido ("Página X de Y")."""

    class _Canvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas: list[dict] = []

        def showPage(self):  # noqa: N802 — API do reportlab
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                self._rodape(total)
                super().showPage()
            super().save()

        def _rodape(self, total: int):
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(GRAY)
            esquerda = "Documento gerado eletronicamente pelo Aprimora"
            if emissao.orgao:
                esquerda += f" · {emissao.orgao}"
            self.drawString(margem, 1.0 * cm, esquerda)
            self.drawRightString(
                self._pagesize[0] - margem,
                1.0 * cm,
                f"Página {self._pageNumber} de {total}",
            )
            self.restoreState()

    return _Canvas
