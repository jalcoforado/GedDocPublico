"""Orquestração do assistente: guards → contexto → prompt → stream.

A ORDEM das etapas é a decisão de segurança desta fatia, e não é acidental:

    autorizar  →  resolver o recurso  →  responder

Invertido, a mensagem de erro distingue "não existe" de "existe, mas você não
pode" — e essa distinção é ela própria um vazamento para quem não deveria saber
que o processo existe. Foi a lição do conserto do download de anexo
(item 1.0.02): `assert_acesso_processo` levanta erro que vira **404**, nunca
403.

O que este módulo deliberadamente NÃO tem: ferramentas. O modelo recebe um
texto e devolve um texto. Não há nada que ele possa chamar para alcançar outro
processo — ver `contexto.py` e a spec IA-1 §3.
"""
from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from ..processos import get_processo_detail
from ..sigilo import SigiloAcessoError, assert_acesso_processo
from .conhecimento import GLOSSARIO, REGRAS
from .contexto import montar_contexto
from .llm_client import LLMClient

# Piso e teto da pergunta. O teto não é sobre custo — é sobre injeção: um
# "prompt" de 20 mil caracteres não é pergunta sobre processo, é tentativa de
# afogar as regras do system prompt em instrução contrária.
PERGUNTA_MIN = 3
PERGUNTA_MAX = 1000


class AssistenteError(Exception):
    """Pergunta inválida — vira 400."""


def montar_system_prompt(contexto_processo: str) -> str:
    """Regras → glossário → processo, nessa ordem.

    As regras vêm ANTES do conteúdo de propósito. O processo carrega texto
    escrito por terceiros (despacho de servidor, descrição digitada pelo
    manifestante); pôr as regras depois convidaria a última linha de um
    despacho a parecer a instrução mais recente.
    """
    return f"{REGRAS}\n\n{GLOSSARIO}\n\n---\n\n{contexto_processo}"


async def responder(
    db: AsyncSession,
    *,
    processo_id: int,
    pergunta: str,
    tenant_id: int,
    usuario,
    cliente: LLMClient,
) -> AsyncIterator[str]:
    """Devolve a resposta em pedaços. Levanta antes de streamar qualquer coisa.

    Levantar *antes* do primeiro `yield` é o que permite o router transformar
    erro em status HTTP. Depois que o stream começa, o 200 já foi enviado e a
    falha só aparece como texto no meio da resposta.
    """
    pergunta = (pergunta or "").strip()
    if len(pergunta) < PERGUNTA_MIN:
        raise AssistenteError("Escreva uma pergunta.")
    if len(pergunta) > PERGUNTA_MAX:
        raise AssistenteError(
            f"Pergunta muito longa (máximo {PERGUNTA_MAX} caracteres)."
        )

    # 1. AUTORIZAR. Antes de qualquer carga do recurso.
    await assert_acesso_processo(
        db, tenant_id=tenant_id, processo_id=processo_id, usuario=usuario
    )

    # 2. RESOLVER. Sem `niveis_permitidos`: o guard acima já decidiu, e repetir
    #    o filtro aqui daria a impressão de que ele é opcional lá.
    detalhe = await get_processo_detail(db, processo_id, tenant_id=tenant_id)
    if detalhe is None:
        # Não existe, ou é de outro tenant. Mesma resposta que sigilo negado —
        # os dois casos são indistinguíveis de fora, por construção.
        raise SigiloAcessoError("Processo não encontrado")

    # 3. RESPONDER.
    system = montar_system_prompt(montar_contexto(detalhe))
    async for pedaco in cliente.stream(system=system, pergunta=pergunta):
        yield pedaco
