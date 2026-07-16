"""Engine de placeholders para templates de documento.

Resolve tokens `{{chave}}` de um template contra dados do processo, UMA ÚNICA VEZ
ao instanciar a minuta (snapshot "mail-merge", não live-binding). Substituição por
WHITELIST — nunca `eval`. Cada valor passa por `html.escape()` porque é injetado em
HTML que depois vira PDF (evita injeção de markup vinda de campos de dados).

Token desconhecido é deixado LITERAL (o admin/usuário percebe que o template tem um
placeholder inválido), nunca levanta erro.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    Manifestante,
    Processo,
    Servico,
    Tenant,
    UnidadeTrabalho,
    Usuario,
)

_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

# Catálogo de placeholders disponíveis (para a UI do admin exibir como chips).
PLACEHOLDERS_DISPONIVEIS: list[dict[str, str]] = [
    {"chave": "processo.numero", "descricao": "Número do processo"},
    {"chave": "processo.data_abertura", "descricao": "Data de abertura (dd/mm/aaaa)"},
    {"chave": "processo.assunto", "descricao": "Assunto do processo"},
    {"chave": "processo.observacao", "descricao": "Observação do processo"},
    {"chave": "requerente.nome", "descricao": "Nome do requerente/manifestante"},
    {"chave": "requerente.cpf_cnpj", "descricao": "CPF/CNPJ do requerente"},
    {"chave": "requerente.email", "descricao": "E-mail do requerente"},
    {"chave": "requerente.telefone", "descricao": "Telefone do requerente"},
    {"chave": "unidade.nome", "descricao": "Unidade proprietária do processo"},
    {"chave": "unidade.sigla", "descricao": "Sigla da unidade"},
    {"chave": "servico.nome", "descricao": "Serviço que originou o processo"},
    {"chave": "data_hoje", "descricao": "Data de hoje (dd/mm/aaaa)"},
    {"chave": "usuario.nome", "descricao": "Nome do redator (usuário atual)"},
    {"chave": "tenant.nome", "descricao": "Nome da prefeitura/tenant"},
]


def _fmt_data(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y") if dt is not None else ""


async def build_context(
    db: AsyncSession, *, tenant_id: int, processo: Processo, usuario: Usuario
) -> dict[str, str]:
    """Monta o dicionário de valores dos placeholders a partir do processo.

    Faz as cargas relacionadas (assunto, requerente, unidade, serviço, tenant)
    filtrando por `tenant_id` — coerência de tenant garantida.
    """

    async def _scalar(model, pk):  # type: ignore[no-untyped-def]
        if pk is None:
            return None
        return (
            await db.execute(
                select(model).where(model.id == pk, model.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()

    assunto = await _scalar(Assunto, processo.id_assunto)
    manifestante = await _scalar(Manifestante, processo.id_manifestante)
    unidade = await _scalar(UnidadeTrabalho, processo.id_unidade_proprietaria)
    servico = await _scalar(Servico, processo.id_servico)
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()

    telefone = ""
    if manifestante is not None:
        telefone = (
            manifestante.telefone_celular
            or manifestante.telefone_residencial
            or manifestante.telefone_comercial
            or ""
        )

    return {
        "processo.numero": processo.numero_processo or "",
        "processo.data_abertura": _fmt_data(processo.data_hora_abertura),
        "processo.assunto": (assunto.assunto if assunto else ""),
        "processo.observacao": processo.observacao or "",
        "requerente.nome": (manifestante.nome if manifestante else "") or "",
        "requerente.cpf_cnpj": (manifestante.cpf_cnpj if manifestante else "") or "",
        "requerente.email": (manifestante.email if manifestante else "") or "",
        "requerente.telefone": telefone,
        "unidade.nome": (unidade.unidade_trabalho if unidade else "") or "",
        "unidade.sigla": (unidade.sigla if unidade else "") or "",
        "servico.nome": (servico.nome if servico else "") or "",
        "data_hoje": _fmt_data(datetime.now()),
        "usuario.nome": usuario.nome or "",
        "tenant.nome": (tenant.nome if tenant else "") or "",
    }


def resolve(corpo_html: str, contexto: dict[str, str]) -> str:
    """Substitui `{{chave}}` por `html.escape(valor)`. Token fora da whitelist fica literal."""

    def _sub(m: re.Match[str]) -> str:
        chave = m.group(1)
        if chave in contexto:
            return html.escape(contexto[chave])
        return m.group(0)  # literal — placeholder desconhecido

    return _TOKEN_RE.sub(_sub, corpo_html)
