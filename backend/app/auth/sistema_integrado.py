"""Realm M2M (C2.3) — sistema integrado autenticado por API key.

Espírito igual ao de `deps.py::get_current_user` / `get_current_cidadao`: um
realm próprio, resolvido a partir do request, que devolve um objeto de
identidade autenticada. A diferença é o transporte — não é JWT em
`Authorization`/cookie, é o header `X-Api-Key` no formato `<prefixo>.<segredo>`
— e o fato de não haver "usuário" nenhum por trás: quem chama é outro sistema.

Fluxo de `get_current_sistema_integrado`:

1. Lê `X-Api-Key`, separa `<prefixo>.<segredo>` (401 se ausente/mal-formado).
2. Busca `pagamentos.sistema_integrado` por `prefixo` — GLOBAL, sem tenant
   ainda conhecido (ver migration 0102 para o porquê da unique não ser por
   tenant).
3. Confere `bcrypt.checkpw(segredo, hash_chave)` — MESMO custo de
   `auth/password.py::hash_password` (usa os mesmos helpers).
4. Exige `ativo=True` e `revogado_em IS NULL`. Qualquer falha nos passos
   2-4 é 401 e usa a MESMA mensagem genérica, para não revelar se o prefixo
   existe (paralelo ao cuidado de sigilo do CLAUDE.md: erro de autorização
   não deve distinguir "existe" de "não existe").
5. **Tenant do host vs. tenant da chave.** O `TenantMiddleware` já resolveu
   `request.state.tenant_id` a partir do `Host` antes desta dependência
   rodar. Se ele resolveu ALGUM tenant e esse tenant diverge do dono da
   chave, é 401 — uma chave válida de um tenant não autentica em nome de
   outro só porque bateu no host errado. Se o host não resolveu tenant
   nenhum (ex.: `STRICT_TENANT_RESOLUTION=false` sem default, ou um cliente
   M2M que não manda `Host` de tenant), o tenant da chave é quem manda: é
   gravado em `request.state.tenant_id` — mas ISSO SOZINHO NÃO basta para as
   rotas M2M lerem/escreverem no tenant certo (ver `get_db_m2m` abaixo).

**Por que `request.state.tenant_id` não basta — o cache de dependências do
FastAPI (achado do review da Task 6).** `get_db` (em `database.py`) também é
uma dependency, e o FastAPI resolve e CACHEIA cada dependency uma única vez
por request, na ordem em que a árvore de dependências é montada. Se uma rota
M2M declarar `db: AsyncSession = Depends(get_db)` como parâmetro irmão de
`sistema: SistemaIntegrado = Depends(get_current_sistema_integrado)`, não há
garantia de que `get_db` seja resolvido DEPOIS desta função — e mesmo
quando é, a sessão que `get_db` abre já fixou `session.info["tenant_id"]`
na sua própria criação, lendo `request.state.tenant_id` NAQUELE instante.
Mutar `request.state.tenant_id` aqui dentro chega tarde para quem já abriu
sessão antes, e cedo demais para depender da ordem entre dependencies
irmãs — é fragilidade de ordenação, não uma garantia do framework.

A correção não é "garantir a ordem": é não depender dela. Toda rota M2M usa
`get_db_m2m` abaixo — que declara `Depends(get_current_sistema_integrado)`
como PARÂMETRO DA PRÓPRIA FUNÇÃO, forçando o FastAPI a resolver a
autenticação primeiro (dependência de dependência, não dependência irmã) — e
abre a sessão já com `session.info["tenant_id"] = sistema.tenant_id`, sem
tocar em `request.state`. Nenhuma rota M2M deve usar `get_db` puro.

Note: a busca do passo 2 usa a sessão de `get_db` normal (mesmo papel de
banco de todo o resto da API). Ela só encontra linhas de QUALQUER tenant
porque hoje (F-12, ver CLAUDE.md) `ged_user` é SUPERUSER/BYPASSRLS e a RLS
não filtra nada em produção. Quando o rollout `SEC-RLS-ROLLOUT` ligar
`APP_DATABASE_URL` (papel `aprimora_app`, NOBYPASSRLS), a policy de RLS de
`sistema_integrado` (`tenant_id = GUC`) vai restringir essa busca ao tenant
da SESSÃO — que para uma chamada M2M pode não ser nenhum ainda. Esse gap é
conhecido e fica registrado aqui para quem ligar o rollout: a busca por
prefixo vai precisar de uma sessão sem tenant fixado (ou de um papel próprio,
como o de plataforma), não da sessão tenant-scoped comum.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import SessionLocal, get_db
from ..models import SistemaIntegrado
from .password import _verify_bcrypt

_DETALHE_INVALIDA = "Chave de API ausente, inválida ou revogada"


async def get_current_sistema_integrado(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SistemaIntegrado:
    api_key = request.headers.get("x-api-key", "")
    prefixo, _sep, segredo = api_key.partition(".")
    if not api_key or not _sep or not prefixo or not segredo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_DETALHE_INVALIDA,
        )

    result = await db.execute(
        select(SistemaIntegrado).where(SistemaIntegrado.prefixo == prefixo)
    )
    sistema = result.scalar_one_or_none()

    if (
        sistema is None
        or not sistema.ativo
        or sistema.revogado_em is not None
        or not _verify_bcrypt(segredo, sistema.hash_chave)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_DETALHE_INVALIDA,
        )

    request_tenant_id = getattr(request.state, "tenant_id", None)
    if request_tenant_id is not None and int(request_tenant_id) != int(sistema.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_DETALHE_INVALIDA,
        )
    request.state.tenant_id = sistema.tenant_id

    return sistema


def require_escopo_leitura(
    sistema: SistemaIntegrado = Depends(get_current_sistema_integrado),
) -> SistemaIntegrado:
    if not sistema.escopo_leitura:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sistema integrado sem escopo de leitura",
        )
    return sistema


def require_escopo_escrita(
    sistema: SistemaIntegrado = Depends(get_current_sistema_integrado),
) -> SistemaIntegrado:
    if not sistema.escopo_escrita:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sistema integrado sem escopo de escrita",
        )
    return sistema


async def get_db_m2m(
    sistema: SistemaIntegrado = Depends(get_current_sistema_integrado),
) -> AsyncIterator[AsyncSession]:
    """Sessão para rotas M2M — mesmo padrão de `database.py::get_db`, mas com
    `session.info["tenant_id"]` fixado a partir do TENANT DA CHAVE
    (`sistema.tenant_id`), nunca de `request.state`.

    Por que não reusar `get_db`: `Depends(get_current_sistema_integrado)`
    aqui em cima é parâmetro da PRÓPRIA função — dependência de dependência —,
    então o FastAPI garante que a autenticação já rodou antes desta sessão
    abrir. Isso resolve o problema de cache/ordem descrito na docstring do
    módulo: `get_db` comum decide `tenant_id` no instante em que É CRIADO, e
    nada garante que isso aconteça depois de `get_current_sistema_integrado`
    quando as duas são dependencies IRMÃs da mesma rota.

    Toda rota de `routers/pagamentos_integracao.py` usa esta função, nunca
    `get_db`."""
    async with SessionLocal() as session:
        session.info["tenant_id"] = int(sistema.tenant_id)
        yield session
