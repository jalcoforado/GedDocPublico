"""Endpoint PÚBLICO de validação de assinatura por código/token (PR2e).

Sem autenticação. O tenant vem do subdomínio (TenantMiddleware), então o
lookup é tenant-scoped. Respostas negativas são neutras e indistinguíveis
(404 `{valido:false}`) — não vazam a existência de processos/assinaturas.

Rate-limit por IP no app (defesa em profundidade; a borda dura é o `limit_req`
do nginx no path `/api/v2/publico/`).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id, require_tenant_slug
from ..config import validacao_publica_url
from ..database import get_db
from ..schemas.assinatura import ValidacaoPublicaOut
from ..services import validacao_publica_throttle as throttle
from ..services.pdf_comprovante_assinatura import gerar_comprovante_publico_pdf
from ..services.validacao_publica import validar_publico

router = APIRouter(tags=["validacao-publica"])

_NEUTRO = {"valido": False}


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def _rate_limit(request: Request) -> str | None:
    ip = _client_ip(request)
    if await throttle.esta_bloqueado_ip(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas consultas. Tente novamente em instantes.",
        )
    await throttle.registrar_consulta_ip(ip)
    return ip


@router.get("/publico/validacao/{codigo}", response_model=ValidacaoPublicaOut)
async def validar_publico_endpoint(
    codigo: str,
    request: Request,
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
):
    ip = await _rate_limit(request)
    resultado = await validar_publico(
        db, codigo, tenant_id=tenant_id, tenant_slug=tenant_slug, ip=ip
    )
    if resultado is None:
        # Resposta neutra — idêntica para inexistente/revogado/sigiloso/etc.
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_NEUTRO)
    return resultado


@router.get("/publico/validacao/{codigo}/comprovante.pdf")
async def comprovante_publico_endpoint(
    codigo: str,
    request: Request,
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
):
    ip = await _rate_limit(request)
    resultado = await validar_publico(
        db, codigo, tenant_id=tenant_id, tenant_slug=tenant_slug, ip=ip
    )
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovante não disponível.",
        )
    url = validacao_publica_url(tenant_slug, codigo)
    pdf = gerar_comprovante_publico_pdf(resultado, codigo=codigo, url_validacao=url)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="validacao-{codigo}.pdf"'},
    )
