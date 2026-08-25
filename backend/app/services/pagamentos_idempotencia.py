"""Idempotência de escrita M2M (C2.3, Task 7).

`executar_idempotente` é o único caminho pelo qual as rotas de escrita de
`routers/pagamentos_integracao.py` chamam os services de negócio (criar
débito, liquidar). Contrato:

- Chave nova (miss) → roda `executor()`, grava `(status_code, corpo)` e
  devolve.
- Mesma chave, MESMO payload (hit, hash igual) → devolve a resposta GRAVADA
  na primeira vez, sem rodar `executor()` de novo (replay idempotente — não
  cria um segundo débito, não liquida duas vezes).
- Mesma chave, payload DIFERENTE (hit, hash diferente) → 409. Reuso da chave
  para uma operação distinta é erro de uso do integrador, não uma segunda
  operação.
- Corrida da MESMA chave (duas requisições concorrentes, nenhuma linha
  gravada ainda) → só uma GANHA o INSERT (protegido pelo unique
  `(tenant_id, id_sistema, chave)`, migration 0102); a perdedora relê a
  linha do vencedor. Ver `_INSERT_ANTECIPADO` abaixo para o mecanismo.

## Insert antecipado — por que a linha nasce com status/corpo NULL

Sem reservar a chave ANTES de rodar `executor()`, duas requisições
concorrentes rodariam o service de negócio DUAS vezes (dois débitos) e só a
escrita final da linha de idempotência colidiria — tarde demais. O algoritmo
insere a linha primeiro, como placeholder (`status_code`/`corpo_resposta`
NULL — migration 0103 tornou as colunas nullable para isto), dentro da MESMA
transação/sessão que vai rodar `executor()`. Duas consequências:

1. Se o INSERT colide (unique violation), esta chamada PERDEU a corrida:
   fizemos rollback do que quer que tivesse sido flushado e relemos a linha
   do vencedor — que pode já estar completa (replay normal) ou ainda NULL
   (o vencedor ainda está processando; ver próximo parágrafo).
2. Se o INSERT passa, esta chamada é dona da chave. Roda `executor()` NA
   MESMA sessão — o commit de `executor()` (os services de pagamentos
   commitam a própria transação) grava o placeholder JUNTO com o efeito de
   negócio, atomicamente. Depois fazemos um segundo UPDATE+commit para
   preencher `status_code`/`corpo_resposta`.

## Linha travada em NULL — limitação documentada, não um bug

Entre o primeiro commit (placeholder + efeito de negócio) e o segundo
(preencher a resposta) o processo pode morrer. Uma leitura nesse intervalo — ou
para sempre, se o processo não voltar — encontra `status_code IS NULL` e
devolve 409 "requisição em processamento". Não há retry automático aqui: o
integrador decide (nova chave = nova tentativa; mesma chave = espera). Se
`executor()` lançar uma exceção ANTES do seu próprio commit, o rollback desfaz
TAMBÉM o placeholder (mesma transação) — a chave fica livre para uma nova
tentativa, então falhas de validação (422/409 de regra de negócio) não
travam a chave para sempre, só sucessos parcialmente escritos travam.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Idempotencia, SistemaIntegrado


def _utcnow() -> datetime:
    return datetime.utcnow()


def hash_payload(corpo: bytes | str | dict) -> str:
    """Hash estável do payload de uma requisição de escrita. `dict` é
    serializado com chaves ordenadas para não depender da ordem de inserção
    do JSON recebido."""
    if isinstance(corpo, dict):
        corpo = json.dumps(corpo, sort_keys=True, default=str, ensure_ascii=False)
    if isinstance(corpo, str):
        corpo = corpo.encode("utf-8")
    return hashlib.sha256(corpo).hexdigest()


async def _buscar(db: AsyncSession, *, tenant_id: int, id_sistema: int, chave: str) -> Idempotencia | None:
    stmt = select(Idempotencia).where(
        Idempotencia.tenant_id == tenant_id,
        Idempotencia.id_sistema == id_sistema,
        Idempotencia.chave == chave,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _responder_existente(linha: Idempotencia, payload_hash: str) -> tuple[int, Any]:
    if linha.hash_payload != payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key já usada com um payload diferente.",
        )
    if linha.status_code is None:
        # Vencedor da corrida ainda não terminou de escrever a resposta (ou
        # morreu no meio do caminho) — ver docstring do módulo.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requisição com esta Idempotency-Key ainda em processamento.",
        )
    return linha.status_code, linha.corpo_resposta


async def executar_idempotente(
    db: AsyncSession,
    *,
    sistema: SistemaIntegrado,
    chave: str,
    payload_hash: str,
    executor: Callable[[], Awaitable[tuple[int, Any]]],
) -> tuple[int, Any]:
    existente = await _buscar(db, tenant_id=sistema.tenant_id, id_sistema=sistema.id, chave=chave)
    if existente is not None:
        return _responder_existente(existente, payload_hash)

    placeholder = Idempotencia(
        tenant_id=sistema.tenant_id, id_sistema=sistema.id, chave=chave,
        hash_payload=payload_hash, status_code=None, corpo_resposta=None,
        criado_em=_utcnow(),
    )
    db.add(placeholder)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Perdemos a corrida: a linha do vencedor já existe (completa ou
        # ainda em processamento).
        existente = await _buscar(db, tenant_id=sistema.tenant_id, id_sistema=sistema.id, chave=chave)
        if existente is None:
            # Janela improvável (o vencedor deu rollback entre o nosso
            # IntegrityError e esta releitura) — tratamos como "tente de novo".
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requisição com esta Idempotency-Key ainda em processamento.",
            )
        return _responder_existente(existente, payload_hash)

    try:
        status_code, corpo = await executor()
        # JSONB não serializa `Decimal`/`datetime` nativos — normaliza para o
        # mesmo formato que o replay vai devolver (senão a primeira resposta
        # e o replay divergiriam em tipo, além de o INSERT/UPDATE falhar).
        corpo = jsonable_encoder(corpo)
    except Exception:
        # `executor()` pode já ter commitado parte do trabalho (os services de
        # pagamentos fazem commit próprio) OU pode ter falhado antes de
        # qualquer commit. `rollback()` só desfaz o que ainda está pendente —
        # se `executor()` já commitou, o commit dele já é definitivo, e o
        # ÚNICO efeito deste rollback é não deixar o placeholder pendurado sem
        # commit algum (linha nunca chega a existir para outra leitura).
        await db.rollback()
        raise

    placeholder.status_code = status_code
    placeholder.corpo_resposta = corpo
    await db.commit()
    return status_code, corpo
