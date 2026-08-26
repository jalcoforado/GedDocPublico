"""Materialidade e versionamento do `Debito` (F2, spec §4.3).

Nem toda alteração num débito em ajuste é igual: mudar o valor total ou o
credor reabre o mérito que gestor/validador/autoridade já examinaram, e por
isso precisa deixar rastro — um snapshot em `DebitoVersao` — antes de ser
sobrescrita. Mudar a criticidade ou a conta pagadora sugerida não reabre
nada. A linha entre as duas categorias é este módulo.

Toda coluna de `Debito` tem que estar classificada em uma das três listas —
`CAMPOS_MATERIAIS`, `CAMPOS_NAO_MATERIAIS` ou `CAMPOS_CONTROLE` (campo que o
próprio fluxo escreve, nunca o payload de edição) — e
`test_toda_coluna_de_debito_tem_decisao_de_materialidade` reprova coluna
nova sem decisão.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder

from sqlalchemy import select

from ..models.pagamentos import Debito, DebitoVersao

CAMPOS_MATERIAIS: frozenset[str] = frozenset({
    "id_fornecedor", "valor_total", "numero_nf", "numero_ne",
    "id_fonte_recursos", "id_contrato", "descricao", "data_liquidacao",
    "id_unidade", "categoria",
})

CAMPOS_NAO_MATERIAIS: frozenset[str] = frozenset({
    "id_natureza", "id_conta", "id_conta_pagadora", "competencia",
    "criticidade", "urgente", "justificativa_urgencia",
    "liquidacao_confirmada",
})

# Campos que o próprio fluxo escreve (nunca o payload de edição do usuário) —
# não entram na comparação de materialidade.
CAMPOS_CONTROLE: frozenset[str] = frozenset({
    "id", "tenant_id", "status", "situacao_tramitacao", "situacao_fila",
    "situacao_pagamento", "versao", "lock_version", "id_gestor_decisor",
    "id_validador", "id_usuario_solicitante", "criado_em", "atualizado_em",
    "excluido",
})


def campos_materiais_alterados(debito: Debito, payload: dict[str, Any]) -> set[str]:
    """Chaves de `payload` que são materiais e cujo valor difere do atual.

    Compara só chaves PRESENTES em `payload` (o caller já aplicou
    `exclude_unset`) — campo material que o payload não menciona não é
    "alteração", é ausência.
    """
    return {
        campo for campo in CAMPOS_MATERIAIS & payload.keys()
        if payload[campo] != getattr(debito, campo)
    }


async def congelar_versao(db, *, debito: Debito, motivo: str, usuario_id: int,
                          id_pedido_ajuste: int | None = None) -> DebitoVersao:
    """Grava o snapshot dos campos materiais ATUAIS (antes da mudança) como a
    versão corrente de `debito`, e incrementa `debito.versao`.

    Não comita — participa da transação do caller (`atualizar_debito`).
    """
    dados = jsonable_encoder({campo: getattr(debito, campo) for campo in CAMPOS_MATERIAIS})
    versao_congelada = DebitoVersao(
        tenant_id=debito.tenant_id, id_debito=debito.id, versao=debito.versao,
        dados=dados, id_pedido_ajuste=id_pedido_ajuste, motivo=motivo,
        id_usuario=usuario_id, criado_em=datetime.utcnow(),
    )
    db.add(versao_congelada)
    debito.versao += 1
    await db.flush()
    return versao_congelada


async def listar_versoes(db, *, tenant_id: int, debito_id: int) -> list[DebitoVersao]:
    """Versões congeladas do débito, mais recente primeiro — é o que prova
    que a versão anterior a uma alteração material é recuperável."""
    stmt = select(DebitoVersao).where(
        DebitoVersao.tenant_id == tenant_id, DebitoVersao.id_debito == debito_id,
    ).order_by(DebitoVersao.versao.desc(), DebitoVersao.id.desc())
    return list((await db.execute(stmt)).scalars().all())
