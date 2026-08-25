"""API M2M de Pagamentos (C2.3, Task 7) — escrita idempotente + leitura por cursor.

Prefixo `/api/v2/integracao/pagamentos/*`. Autenticação por `X-Api-Key`
(`auth/sistema_integrado.py`) — NUNCA `require_permission` de usuário: quem
chama não é um usuário do tenant, é outro sistema. Três gates independentes,
todos obrigatórios:

1. **Autenticação** — chave válida (`get_current_sistema_integrado`).
2. **Escopo da chave** — leitura/escrita (`require_escopo_leitura/escrita`).
3. **Contratação do módulo** — `pagamentos` contratado pelo TENANT DA CHAVE
   (`_exigir_modulo_pagamentos` abaixo). Não usa `auth/modulos.py::require_modulo`
   de propósito: aquele lê `request.state.tenant_id` via `require_tenant_id`,
   e a ordem entre essa dependency e `get_current_sistema_integrado` não é
   garantida quando as duas são irmãs no mesmo endpoint — o MESMO problema
   documentado em `sistema_integrado.py::get_db_m2m`. Esta versão depende de
   `get_current_sistema_integrado` como parâmetro da própria função, então o
   tenant já está resolvido quando ela roda.

Toda rota usa `get_db_m2m`, nunca `get_db` puro — ver a docstring dele.

## Quem é o "solicitante" de um débito criado por um sistema externo

`Debito.id_usuario_solicitante` é FK obrigatória para `utils.usuario`; não
existe "usuário" do lado de um sistema integrado. Usamos
`sistema.id_usuario_criador` — o usuário humano que criou a credencial (grava
quem trouxe a integração, não quem "pediu" o débito de fato, mas é a âncora
mais honesta disponível sem inventar um usuário fantasma). Se a credencial
foi criada sem esse vínculo (não deveria acontecer — a rota de criação exige
usuário autenticado), a resposta é 409 em vez de violar a FK.

## Rota literal antes de paramétrica

`/debitos` (POST/GET) vem antes de `/debitos/{debito_id}/liquidar` na leitura
do arquivo por clareza, mas quem importa de verdade é o FastAPI casar por
padrão mais específico primeiro — aqui não há colisão entre um segmento
literal e `{debito_id}` no mesmo nível (guarda de `test_guarda_ordem_rotas.py`
cobre o app inteiro).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.sistema_integrado import (
    SistemaIntegrado,
    get_current_sistema_integrado,
    get_db_m2m,
    require_escopo_escrita,
    require_escopo_leitura,
)
from ..models import (
    Debito,
    DebitoHistorico,
    ExportContabilEvento,
    MovimentacaoConta,
    OrdemPagamento,
)
from ..schemas.pagamentos import DebitoCreate
from ..services import modulos as modulos_svc
from ..services import pagamentos_debitos as debsvc
from ..services import pagamentos_idempotencia as idemsvc

router = APIRouter(prefix="/integracao/pagamentos", tags=["pagamentos-integracao"])

_TIPOS_EVENTO_DEBITO = ("debito_empenhado", "liquidacao", "cancelamento_debito")
_TIPOS_EVENTO_MOVIMENTACAO = ("pagamento", "estorno_parcela")
_LIMITE_MAXIMO = 200


# --------------------------------------------------------------------- gates

async def _exigir_modulo_pagamentos(
    sistema: SistemaIntegrado = Depends(get_current_sistema_integrado),
    db: AsyncSession = Depends(get_db_m2m),
) -> SistemaIntegrado:
    disponiveis = await modulos_svc.slugs_contratados(db, sistema.tenant_id)
    if "pagamentos" not in disponiveis:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Módulo 'pagamentos' não contratado para este tenant",
        )
    return sistema


async def _sistema_leitura(
    _modulo: SistemaIntegrado = Depends(_exigir_modulo_pagamentos),
    sistema: SistemaIntegrado = Depends(require_escopo_leitura),
) -> SistemaIntegrado:
    return sistema


async def _sistema_escrita(
    _modulo: SistemaIntegrado = Depends(_exigir_modulo_pagamentos),
    sistema: SistemaIntegrado = Depends(require_escopo_escrita),
) -> SistemaIntegrado:
    return sistema


async def _idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    chave = (idempotency_key or "").strip()
    if not chave:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Header Idempotency-Key é obrigatório para esta operação.",
        )
    return chave


# ------------------------------------------------------------------- escrita

@router.post("/debitos", status_code=status.HTTP_201_CREATED)
async def criar_debito(
    payload: DebitoCreate,
    request: Request,
    chave: str = Depends(_idempotency_key),
    sistema: SistemaIntegrado = Depends(_sistema_escrita),
    db: AsyncSession = Depends(get_db_m2m),
) -> Any:
    if sistema.id_usuario_criador is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sistema integrado sem usuário criador associado; não é "
                   "possível registrar o solicitante do débito.",
        )
    corpo_bruto = await request.body()
    payload_hash = idemsvc.hash_payload(corpo_bruto)

    async def _executor() -> tuple[int, Any]:
        d = await debsvc.criar_debito(
            db, tenant_id=sistema.tenant_id, usuario_id=sistema.id_usuario_criador,
            payload=payload,
        )
        nomes = await debsvc.nomes_fornecedores(db, tenant_id=sistema.tenant_id,
                                                 ids={d.id_fornecedor})
        corpo = debsvc.debito_out(d, nome_fornecedor=nomes.get(d.id_fornecedor, "?"))
        return status.HTTP_201_CREATED, corpo

    status_code, corpo = await idemsvc.executar_idempotente(
        db, sistema=sistema, chave=chave, payload_hash=payload_hash, executor=_executor,
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=corpo)
    return corpo


@router.post("/debitos/{debito_id}/liquidar")
async def liquidar_debito(
    debito_id: int,
    request: Request,
    chave: str = Depends(_idempotency_key),
    sistema: SistemaIntegrado = Depends(_sistema_escrita),
    db: AsyncSession = Depends(get_db_m2m),
) -> Any:
    corpo_bruto = await request.body()
    payload_hash = idemsvc.hash_payload(corpo_bruto or b"{}")

    async def _executor() -> tuple[int, Any]:
        d = await debsvc.obter_debito(db, tenant_id=sistema.tenant_id, debito_id=debito_id)
        # RN-01 (mesma regra e MESMA mensagem de `pagamentos_autorizacao.autorizar_lote`
        # — número de empenho é pré-requisito antes de liquidar/autorizar; ver
        # docstring do módulo/brief da Task 7 sobre por que este check mora
        # aqui e não dentro de `confirmar_liquidacao`: a porta M2M não expõe
        # `autorizar_lote`, só "liquidar", então é aqui que a regra precisa
        # valer para não haver caminho paralelo sem ela).
        if not (d.numero_ne or "").strip():
            raise debsvc.PagamentoDebitoError(
                f"Débito {debito_id} não pode ser autorizado sem número de empenho (RN-01).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        d = await debsvc.confirmar_liquidacao(
            db, tenant_id=sistema.tenant_id, debito_id=debito_id,
            usuario_id=sistema.id_usuario_criador,
        )
        nomes = await debsvc.nomes_fornecedores(db, tenant_id=sistema.tenant_id,
                                                 ids={d.id_fornecedor})
        corpo = debsvc.debito_out(d, nome_fornecedor=nomes.get(d.id_fornecedor, "?"))
        return status.HTTP_200_OK, corpo

    status_code, corpo = await idemsvc.executar_idempotente(
        db, sistema=sistema, chave=chave, payload_hash=payload_hash, executor=_executor,
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=corpo)
    return corpo


# ------------------------------------------------------------------- leitura

def _cursor_stmt(model, *, tenant_id: int, cursor: int | None, alterado_desde: datetime | None,
                  campo_alterado):
    stmt = select(model).where(model.tenant_id == tenant_id)
    if hasattr(model, "excluido"):
        stmt = stmt.where(model.excluido.is_(False))
    if cursor is not None:
        stmt = stmt.where(model.id > cursor)
    if alterado_desde is not None:
        stmt = stmt.where(campo_alterado >= alterado_desde)
    return stmt.order_by(model.id.asc())


async def _paginar(db: AsyncSession, model, *, tenant_id: int, cursor: int | None, limite: int,
                    alterado_desde: datetime | None, campo_alterado) -> tuple[list, int | None]:
    stmt = _cursor_stmt(model, tenant_id=tenant_id, cursor=cursor,
                         alterado_desde=alterado_desde, campo_alterado=campo_alterado).limit(limite + 1)
    linhas = list((await db.execute(stmt)).scalars().all())
    proximo_cursor = None
    if len(linhas) > limite:
        linhas = linhas[:limite]
        proximo_cursor = linhas[-1].id
    return linhas, proximo_cursor


async def _ids_evento_debitos(db: AsyncSession, *, tenant_id: int, debito_ids: set[int]) -> dict[int, int]:
    """`{debito_id: id_evento}` para os débitos já exportados (ver
    `services/pagamentos_contabil.py` — `id_origem` de `debito_empenhado`/
    `liquidacao`/`cancelamento_debito` é `debito_historico.id`, não
    `debito.id` diretamente). Ausente = nunca exportado."""
    if not debito_ids:
        return {}
    stmt = (
        select(DebitoHistorico.id_debito, func.max(ExportContabilEvento.id))
        .select_from(DebitoHistorico)
        .join(
            ExportContabilEvento,
            (ExportContabilEvento.tenant_id == tenant_id)
            & (ExportContabilEvento.id_origem == DebitoHistorico.id)
            & (ExportContabilEvento.tipo_evento.in_(_TIPOS_EVENTO_DEBITO)),
        )
        .where(DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito.in_(debito_ids))
        .group_by(DebitoHistorico.id_debito)
    )
    return {row[0]: row[1] for row in (await db.execute(stmt)).all()}


async def _ids_evento_movimentacoes(db: AsyncSession, *, tenant_id: int,
                                     mov_ids: set[int]) -> dict[int, int]:
    """`{movimentacao_id: id_evento}` — aqui `id_origem` É `movimentacao_conta.id`
    diretamente (`pagamento`/`estorno_parcela`), sem indireção via histórico."""
    if not mov_ids:
        return {}
    stmt = select(ExportContabilEvento.id_origem, ExportContabilEvento.id).where(
        ExportContabilEvento.tenant_id == tenant_id,
        ExportContabilEvento.tipo_evento.in_(_TIPOS_EVENTO_MOVIMENTACAO),
        ExportContabilEvento.id_origem.in_(mov_ids),
    )
    return {row[0]: row[1] for row in (await db.execute(stmt)).all()}


@router.get("/debitos")
async def listar_debitos(
    cursor: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, gt=0, le=_LIMITE_MAXIMO),
    alterado_desde: datetime | None = Query(default=None),
    sistema: SistemaIntegrado = Depends(_sistema_leitura),
    db: AsyncSession = Depends(get_db_m2m),
) -> dict:
    campo = func.coalesce(Debito.atualizado_em, Debito.criado_em)
    linhas, proximo = await _paginar(
        db, Debito, tenant_id=sistema.tenant_id, cursor=cursor, limite=limite,
        alterado_desde=alterado_desde, campo_alterado=campo,
    )
    nomes = await debsvc.nomes_fornecedores(db, tenant_id=sistema.tenant_id,
                                             ids={d.id_fornecedor for d in linhas})
    eventos = await _ids_evento_debitos(db, tenant_id=sistema.tenant_id,
                                         debito_ids={d.id for d in linhas})
    items = [
        {**debsvc.debito_out(d, nome_fornecedor=nomes.get(d.id_fornecedor, "?")),
         "id_evento": eventos.get(d.id)}
        for d in linhas
    ]
    return {"items": items, "proximo_cursor": proximo}


@router.get("/ordens")
async def listar_ordens(
    cursor: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, gt=0, le=_LIMITE_MAXIMO),
    alterado_desde: datetime | None = Query(default=None),
    sistema: SistemaIntegrado = Depends(_sistema_leitura),
    db: AsyncSession = Depends(get_db_m2m),
) -> dict:
    # `OrdemPagamento` não tem `atualizado_em` (é imutável após criada — ver
    # o model): `alterado_desde` aqui filtra por `criado_em`, documentado.
    linhas, proximo = await _paginar(
        db, OrdemPagamento, tenant_id=sistema.tenant_id, cursor=cursor, limite=limite,
        alterado_desde=alterado_desde, campo_alterado=OrdemPagamento.criado_em,
    )
    items = [
        {
            "id": o.id, "numero": o.numero, "valor_total": o.valor_total,
            "id_usuario_autorizador": o.id_usuario_autorizador,
            "id_conta_pagadora": o.id_conta_pagadora, "valor_reservado": o.valor_reservado,
            "saldo_antes": o.saldo_antes, "saldo_projetado_apos": o.saldo_projetado_apos,
            "excecao_saldo": o.excecao_saldo, "criado_em": o.criado_em,
            # Nenhum dos 5 tipos de `export_contabil_evento` hoje é ancorado em
            # `ordem_pagamento` (ver services/pagamentos_contabil.py) — sempre
            # None até o export contábil ganhar um evento de autorização.
            "id_evento": None,
        }
        for o in linhas
    ]
    return {"items": items, "proximo_cursor": proximo}


@router.get("/baixas")
async def listar_baixas(
    cursor: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, gt=0, le=_LIMITE_MAXIMO),
    alterado_desde: datetime | None = Query(default=None),
    sistema: SistemaIntegrado = Depends(_sistema_leitura),
    db: AsyncSession = Depends(get_db_m2m),
) -> dict:
    campo = func.coalesce(MovimentacaoConta.atualizado_em, MovimentacaoConta.criado_em)
    linhas, proximo = await _paginar(
        db, MovimentacaoConta, tenant_id=sistema.tenant_id, cursor=cursor, limite=limite,
        alterado_desde=alterado_desde, campo_alterado=campo,
    )
    eventos = await _ids_evento_movimentacoes(db, tenant_id=sistema.tenant_id,
                                               mov_ids={m.id for m in linhas})
    items = [
        {
            "id": m.id, "id_conta": m.id_conta, "tipo": m.tipo, "valor": m.valor,
            "origem": m.origem, "id_debito": m.id_debito, "id_parcela": m.id_parcela,
            "data": m.data, "descricao": m.descricao, "criado_em": m.criado_em,
            "id_evento": eventos.get(m.id),
        }
        for m in linhas
    ]
    return {"items": items, "proximo_cursor": proximo}
