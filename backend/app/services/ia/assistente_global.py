from __future__ import annotations

import json
import re
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from ..processos import list_processos
from .llm_client import LLMClient
from .assistente import PERGUNTA_MIN, PERGUNTA_MAX, AssistenteError
from .conhecimento import REGRAS, GLOSSARIO
from ..sigilo import niveis_permitidos

SYSTEM_PROMPT_GLOBAL = f"""{REGRAS}

{GLOSSARIO}

---

Você é o Assistente Virtual Global do Aprimora.
Sua função é ajudar o usuário a encontrar e entender processos na base de dados.
Abaixo você receberá os resultados da busca que o sistema realizou nos processos a que o usuário tem acesso, com base na pergunta dele.
Apresente os resultados de forma clara, amigável e resumida.
Se os resultados vierem vazios, informe que não encontrou nenhum processo com esses critérios."""

async def _extrair_parametros(pergunta: str, cliente: LLMClient) -> dict:
    """Extrai intenção de busca usando o próprio LLM e devolve dict de filtros."""
    system_extractor = (
        "Você é um classificador de intenção de busca. "
        "O usuário quer buscar processos (ex: processos atrasados, processos do João, processo 123). "
        "Extraia 'busca' (termo geral de texto/número/nome) e 'status' (pode ser 'tramitacao', 'arquivado', 'todos'). "
        "Retorne APENAS um JSON válido e estrito. "
        "Exemplo: {\"busca\": \"João\", \"status\": \"tramitacao\"}. "
        "Se não encontrar um filtro claro, retorne null para o campo."
    )

    resposta_texto = ""
    try:
        async for pedaco in cliente.stream(system=system_extractor, pergunta=pergunta):
            resposta_texto += pedaco
            
        # Tenta parsear JSON da resposta
        match = re.search(r'\{.*\}', resposta_texto, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(resposta_texto)
    except Exception:
        return {}


async def responder_global(
    db: AsyncSession,
    *,
    pergunta: str,
    tenant_id: int,
    usuario,
    cliente: LLMClient,
) -> AsyncIterator[str]:
    pergunta = (pergunta or "").strip()
    if len(pergunta) < PERGUNTA_MIN:
        raise AssistenteError("Escreva uma pergunta.")
    if len(pergunta) > PERGUNTA_MAX:
        raise AssistenteError(
            f"Pergunta muito longa (máximo {PERGUNTA_MAX} caracteres)."
        )

    # 1. Usar o LLM rapidamente para interpretar a intenção de busca
    parametros = await _extrair_parametros(pergunta, cliente)
    
    # 2. Executar a busca segura no banco de dados (o service já aplica RLS e Sigilo do usuário)
    # limitamos a 10 resultados para não afogar o prompt
    status_filtro = parametros.get("status")
    busca_filtro = parametros.get("busca")
    
    situacao = None
    if status_filtro in ["tramitacao", "arquivado", "todos"]:
        situacao = status_filtro
    
    niveis = None if getattr(usuario, "is_super", False) else niveis_permitidos(usuario.nivel_acesso_sigilo)
        
    resultados, _ = await list_processos(
        db, 
        tenant_id=tenant_id,
        page=1,
        page_size=10,
        q=str(busca_filtro) if busca_filtro else None,
        situacao=situacao,
        niveis_permitidos=niveis,
        id_usuario_contexto=usuario.id,
    )
    
    # 3. Montar contexto com os resultados encontrados
    if not resultados:
        contexto_resultados = "Nenhum processo encontrado na base de dados para estes critérios."
    else:
        linhas = []
        for p in resultados:
            linhas.append(f"- Processo {p.numero_processo}: {p.assunto} (Status: {p.situacao})")
        contexto_resultados = "Resultados encontrados no sistema:\n" + "\n".join(linhas)

    # 4. Streamar a resposta final para o usuário
    mensagens = [
        {"role": "user", "content": pergunta},
        {"role": "system", "content": f"[Resultados do Banco de Dados injetados automaticamente]\n{contexto_resultados}"}
    ]
    
    async for pedaco in cliente.stream(system=SYSTEM_PROMPT_GLOBAL, messages=mensagens):
        yield pedaco
