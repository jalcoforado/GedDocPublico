"""Assistente conversacional — IA-1, escopo de UM processo já aberto.

Uma rota só, de propósito. Não há `/ia/chat` genérico, não há busca: o
assistente responde sobre o processo cujo id está na URL, e o usuário já
atravessou toda a autorização que existe para abrir aquele processo. Ver
`docs/superpowers/specs/2026-08-07-ia-1-assistente-do-processo-design.md` §2
para por que a busca ficou de fora (resumo: ela transforma o item 1.0.8 de
buraco latente em buraco explorável).

Os três eixos de acesso aparecem juntos aqui, e é raro isso — vale a leitura:

- `require_permission("processo")` — o eixo do USUÁRIO
- `require_modulo("protocolo")`    — o eixo do TENANT (contratação)
- `assert_acesso_processo`         — o eixo do PROCESSO (sigilo), no service

Nenhum substitui o outro. O primeiro pergunta "esta pessoa pode?", o segundo
"este município contratou?", o terceiro "esta credencial alcança este nível?".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..services.ia.assistente import (
    PERGUNTA_MAX,
    AssistenteError,
    responder,
)
from ..services.ia.llm_client import IAIndisponivelError, LLMClient, obter_cliente
from ..services.sigilo import SigiloAcessoError

router = APIRouter(prefix="/ia", tags=["ia"])


class PerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=1, max_length=PERGUNTA_MAX)


def get_llm_client() -> LLMClient:
    """Dependency para o cliente — é o ponto de injeção do dublê nos testes.

    Sem isto, testar o assistente exigiria chave e rede, e um teste assim não
    roda no CI. `app.dependency_overrides[get_llm_client]` resolve.
    """
    try:
        return obter_cliente()
    except IAIndisponivelError as e:
        # 503, não 500: a função não está ligada neste ambiente, o sistema não
        # quebrou. Hoje este é o caminho normal — `ANTHROPIC_API_KEY` não está
        # definida em lugar nenhum.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        )


@router.get("/disponivel")
async def assistente_disponivel(
    _perm=Depends(require_permission("processo")),
) -> dict[str, bool]:
    """A tela chama isto para decidir se mostra o assistente.

    Sem esta rota o frontend só descobriria a indisponibilidade ao enviar a
    primeira pergunta — ou seja, o usuário digitaria, esperaria, e levaria um
    erro. Melhor não oferecer o que não funciona.

    Sem gate de módulo de propósito: é uma pergunta sobre a INFRAESTRUTURA
    ("há chave configurada?"), não sobre dado de processo. Não revela nada do
    tenant.
    """
    try:
        obter_cliente()
    except IAIndisponivelError:
        return {"disponivel": False}
    return {"disponivel": True}


@router.post(
    "/processos/{processo_id}/perguntar",
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def perguntar_sobre_processo(
    processo_id: int,
    payload: PerguntaRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(require_tenant_id),
    usuario: Usuario = Depends(get_current_user),
    cliente: LLMClient = Depends(get_llm_client),
    _perm=Depends(require_permission("processo")),
) -> StreamingResponse:
    """Responde em streaming (SSE) sobre o processo `processo_id`.

    **O primeiro pedaço é consumido aqui dentro, antes de devolver a resposta.**
    Parece detalhe e não é: `responder()` valida a pergunta e roda os guards
    antes do primeiro `yield`, mas num gerador assíncrono nada disso executa
    até alguém pedir o primeiro item. Se eu passasse o gerador direto para o
    `StreamingResponse`, o FastAPI já teria emitido `200 OK` quando o guard de
    sigilo levantasse — e um 404 viraria texto de erro no meio de uma resposta
    bem-sucedida. Puxar o primeiro pedaço aqui traz a exceção para onde ainda
    dá para transformá-la em status HTTP.
    """
    gerador = responder(
        db,
        processo_id=processo_id,
        pergunta=payload.pergunta,
        tenant_id=tenant_id,
        usuario=usuario,
        cliente=cliente,
    )

    try:
        primeiro = await anext(gerador, None)
    except SigiloAcessoError:
        # 404, nunca 403 — 403 confirmaria que o processo existe para quem não
        # pode saber disso.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )
    except AssistenteError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def _sse():
        if primeiro is not None:
            yield _evento(primeiro)
            async for pedaco in gerador:
                yield _evento(pedaco)
        yield "event: fim\ndata: {}\n\n"

    return StreamingResponse(
        _sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Sem isto o nginx bufferiza a resposta inteira e o streaming vira
            # uma pausa longa seguida do texto completo de uma vez — o efeito
            # que o SSE existe para evitar.
            "X-Accel-Buffering": "no",
        },
    )


def _evento(texto: str) -> str:
    """Serializa um pedaço como evento SSE.

    `json.dumps` e não interpolação crua: o texto do modelo contém quebras de
    linha, e `\\n` num campo `data:` é o separador de eventos do próprio
    protocolo. Concatenar direto partiria a mensagem ao meio.
    """
    import json

    return f"data: {json.dumps({'texto': texto}, ensure_ascii=False)}\n\n"
