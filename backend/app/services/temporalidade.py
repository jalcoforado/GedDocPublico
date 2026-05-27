"""Serviço de temporalidade documental — Fase P4.

Dado um processo (com `id_ccd_classe` opcional e `id_especie_documental`
opcional), busca a regra TTD aplicável e calcula:
- fim da fase corrente (data_referencia + anos_corrente)
- fim da fase intermediária (fim_corrente + anos_intermediario)
- destino final (ELIMINACAO ou GUARDA_PERMANENTE)

Resolução da regra (prioridade alta → baixa):
1. Regra específica (classe + espécie)
2. Regra catch-all da classe (id_especie_documental IS NULL)
3. Subir na hierarquia até achar alguma regra (classe pai, pai do pai, …)
4. Se nada, retorna `motivo_sem_regra` populado

Também expõe `sugerir_ccd_por_assunto(texto_assunto)` que faz match de
palavras-chave do assunto contra `ccd_classe.palavras_chave` (CSV) e o
próprio `ccd_classe.nome`. Retorna até 5 sugestões com score 0..1.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Assunto, CcdClasse, EspecieDocumental, Processo, TtdRegra
from ..schemas.ccd import (
    SugestaoCcdOut,
    TemporalidadeOut,
    TtdRegraOut,
)


async def _achar_regra(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_classe: int,
    id_especie: int | None,
) -> TtdRegra | None:
    """Tenta achar regra específica → catch-all da classe.

    NÃO sobe na hierarquia aqui — quem chama itera nas classes ancestrais.
    """
    if id_especie is not None:
        especifica = (
            await db.execute(
                select(TtdRegra).where(
                    TtdRegra.tenant_id == tenant_id,
                    TtdRegra.id_ccd_classe == id_classe,
                    TtdRegra.id_especie_documental == id_especie,
                    TtdRegra.excluido.is_(False),
                    TtdRegra.ativo.is_(True),
                )
            )
        ).scalar_one_or_none()
        if especifica is not None:
            return especifica

    catch_all = (
        await db.execute(
            select(TtdRegra).where(
                TtdRegra.tenant_id == tenant_id,
                TtdRegra.id_ccd_classe == id_classe,
                TtdRegra.id_especie_documental.is_(None),
                TtdRegra.excluido.is_(False),
                TtdRegra.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    return catch_all


async def _resolver_regra_com_hierarquia(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_classe: int,
    id_especie: int | None,
) -> tuple[TtdRegra | None, list[int]]:
    """Itera na hierarquia: classe → pai → pai do pai. Retorna (regra, path).

    `path` é a lista de ids visitados (útil pra debug/explicação ao usuário).
    """
    visitados: list[int] = []
    classe_atual: int | None = id_classe
    while classe_atual is not None:
        if classe_atual in visitados:  # proteção contra ciclo
            break
        visitados.append(classe_atual)
        regra = await _achar_regra(
            db, tenant_id=tenant_id, id_classe=classe_atual, id_especie=id_especie
        )
        if regra is not None:
            return regra, visitados
        pai = (
            await db.execute(
                select(CcdClasse.id_classe_pai).where(
                    CcdClasse.id == classe_atual,
                    CcdClasse.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        classe_atual = pai
    return None, visitados


async def calcular_temporalidade(
    db: AsyncSession,
    processo_id: int,
    *,
    tenant_id: int,
) -> TemporalidadeOut:
    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        # Caller decide HTTP status; aqui só sinaliza ausência.
        raise ValueError(f"Processo {processo_id} não encontrado")

    classe_codigo: str | None = None
    classe_nome: str | None = None
    if processo.id_ccd_classe:
        row = (
            await db.execute(
                select(CcdClasse.codigo, CcdClasse.nome).where(
                    CcdClasse.id == processo.id_ccd_classe
                )
            )
        ).first()
        if row:
            classe_codigo = row.codigo
            classe_nome = row.nome

    especie_nome: str | None = None
    if processo.id_especie_documental:
        especie_nome = (
            await db.execute(
                select(EspecieDocumental.nome).where(
                    EspecieDocumental.id == processo.id_especie_documental
                )
            )
        ).scalar_one_or_none()

    base = TemporalidadeOut(
        id_processo=processo.id,
        numero_processo=processo.numero_processo,
        id_ccd_classe=processo.id_ccd_classe,
        classe_codigo=classe_codigo,
        classe_nome=classe_nome,
        id_especie_documental=processo.id_especie_documental,
        especie_nome=especie_nome,
        regra_aplicada=None,
        data_referencia=processo.data_recepcao or processo.data_hora_abertura,
        fim_fase_corrente=None,
        fim_fase_intermediaria=None,
        destino_final=None,
        motivo_sem_regra=None,
    )

    if processo.id_ccd_classe is None:
        base.motivo_sem_regra = "Processo sem CCD atribuído"
        return base

    regra, _path = await _resolver_regra_com_hierarquia(
        db,
        tenant_id=tenant_id,
        id_classe=processo.id_ccd_classe,
        id_especie=processo.id_especie_documental,
    )
    if regra is None:
        base.motivo_sem_regra = (
            "Nenhuma regra TTD encontrada na classe atribuída nem em ancestrais"
        )
        return base

    ref_dt = base.data_referencia
    ref_date: date | None = ref_dt.date() if ref_dt else None
    fim_corrente = None
    fim_inter = None
    if ref_date:
        # Aproxima 1 ano = 365 dias. Suficiente pra previsão; arquivo real
        # usa data exata do encerramento que é off-system.
        fim_corrente = ref_date + timedelta(days=365 * regra.anos_corrente)
        fim_inter = fim_corrente + timedelta(days=365 * regra.anos_intermediario)

    base.regra_aplicada = TtdRegraOut.model_validate(regra)
    base.fim_fase_corrente = fim_corrente
    base.fim_fase_intermediaria = fim_inter
    base.destino_final = regra.destino_final  # type: ignore[assignment]
    return base


# ============================================================================
#  Sugestão automática de CCD baseada em palavras do assunto
# ============================================================================

_STOPWORDS_PT = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os",
    "em", "no", "na", "para", "por", "com", "sem", "que",
}


def _strip_accents(s: str) -> str:
    """Remove acentos (NFD + remove combining marks). 'aquisição' → 'aquisicao'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _tokenize(text: str) -> set[str]:
    """Tokens lowercase + sem acento + sem stopword + sem pontuação."""
    normalized = _strip_accents(text.lower())
    out: set[str] = set()
    buf = []
    for ch in normalized:
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                tok = "".join(buf)
                if len(tok) >= 3 and tok not in _STOPWORDS_PT:
                    out.add(tok)
                buf = []
    if buf:
        tok = "".join(buf)
        if len(tok) >= 3 and tok not in _STOPWORDS_PT:
            out.add(tok)
    return out


def _iter_class_terms(classe: CcdClasse) -> Iterable[str]:
    """Tokens que representam a classe (nome + palavras_chave CSV)."""
    yield from _tokenize(classe.nome or "")
    if classe.palavras_chave:
        for kw in classe.palavras_chave.split(","):
            kw = kw.strip()
            if kw:
                yield from _tokenize(kw)


async def sugerir_ccd_por_assunto(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_assunto: int | None = None,
    texto_extra: str | None = None,
    limit: int = 5,
) -> list[SugestaoCcdOut]:
    """Sugere até `limit` classes CCD com maior overlap de tokens.

    Faz `tokens(assunto) ∩ tokens(classe.nome + palavras_chave)` e ranqueia
    por count. Score = matches / total_tokens_assunto (normalizado 0..1).
    """
    texto_partes: list[str] = []
    if id_assunto is not None:
        nome = (
            await db.execute(select(Assunto.assunto).where(Assunto.id == id_assunto))
        ).scalar_one_or_none()
        if nome:
            texto_partes.append(nome)
    if texto_extra:
        texto_partes.append(texto_extra)

    tokens_assunto = _tokenize(" ".join(texto_partes))
    if not tokens_assunto:
        return []

    classes = (
        await db.execute(
            select(CcdClasse).where(
                CcdClasse.tenant_id == tenant_id,
                CcdClasse.excluido.is_(False),
                CcdClasse.ativo.is_(True),
            )
        )
    ).scalars().all()

    rankings: list[SugestaoCcdOut] = []
    total = len(tokens_assunto)
    for c in classes:
        class_tokens = set(_iter_class_terms(c))
        matched = tokens_assunto & class_tokens
        if not matched:
            continue
        score = len(matched) / total
        rankings.append(
            SugestaoCcdOut(
                id_ccd_classe=c.id,
                codigo=c.codigo,
                nome=c.nome,
                score=round(score, 3),
                matched_keywords=sorted(matched),
            )
        )

    rankings.sort(key=lambda r: (-r.score, r.codigo))
    return rankings[:limit]
