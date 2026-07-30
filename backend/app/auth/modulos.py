"""Gate de CONTRATAÇÃO de módulo, sem olhar o usuário.

Diferença para `require_permission` (auth/perms.py): aquele responde "este
usuário pode fazer isto?"; este responde "este tenant contratou este módulo?".
São perguntas diferentes e esta fatia responde só a segunda — por decisão
registrada em docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md.

Consequência deliberada: um usuário sem permissão nenhuma continua lendo o que
lê hoje, desde que o tenant tenha o módulo. Fechar isso é mudança de política
de acesso e tem item próprio no backlog.

Efeito colateral aceito (achado na revisão da Task 2, 2026-07-30): como
`dependencies=[Depends(require_modulo(...))]` fica na lista de dependências da
rota, o FastAPI pode resolvê-la antes de `get_current_user`. Requisição SEM
token, em tenant sem o módulo, recebe 403 em vez do 401 esperado — o que vaza,
para um chamador anônimo, quais módulos aquele tenant contratou. Baixo valor
de exploração (não vaza dado de negócio, só o catálogo de módulos) e aceito
por ora; não é motivo para reordenar as 58 rotas gateadas.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.modulos import slugs_contratados
from .deps import require_tenant_id


def require_modulo(slug: str):
    """Cria uma dependency que exige o módulo `slug` contratado pelo tenant."""

    async def _check_modulo(
        tenant_id: int = Depends(require_tenant_id),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        disponiveis = await slugs_contratados(db, tenant_id)
        if not disponiveis:
            # NÃO é a mesma armadilha de services/modulos.codigos_bloqueados
            # (lá o risco é `not_in(set())` virar cláusula sempre-verdadeira e
            # o WHERE parar de filtrar — aqui `slug not in set()` já dá o 403
            # correto sozinho, sem esse bug). A razão de gritar é outra:
            # catálogo sem nem os módulos NÃO-contratáveis (ex.: 'comum'
            # inativo) é estado impossível em operação normal — indica
            # corrupção de dados. Um 403 aqui mascararia essa corrupção como
            # se fosse decisão de negócio (tenant sem o módulo), em vez de
            # estourar alto o suficiente para alguém investigar o catálogo.
            raise RuntimeError(
                f"Nenhum módulo disponível para o tenant {tenant_id} — nem os "
                "não-contratáveis. Catálogo corrompido; verifique se 'comum' "
                "existe e está ativo."
            )
        if slug not in disponiveis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Módulo '{slug}' não contratado para este tenant",
            )

    # O slug fica legível de fora: a guarda casa a closure por (módulo,
    # qualname), que é igual para qualquer slug, e sem isto não teria como
    # verificar se a rota exige o módulo CERTO — só que exige algum.
    _check_modulo.modulo_slug = slug
    return _check_modulo
