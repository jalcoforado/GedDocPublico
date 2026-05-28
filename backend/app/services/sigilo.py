"""Sigilo gradual — classificação de acesso à informação (LAI, Lei 12.527/2011).

Cinco níveis ordenados por sensibilidade crescente:
  0. ostensivo     — público, sem restrição (espelhado em `processo.publico`).
  1. interno       — não-público; visível só a servidores. Sem prazo legal.
  2. reservado     — sigilo legal, prazo máximo 5 anos.
  3. secreto       — sigilo legal, prazo máximo 15 anos.
  4. ultrassecreto — sigilo legal, prazo máximo 25 anos.

`interno` não consta da LAI (que tem só ostensivo + 3 graus de sigilo); foi
adicionado pra cobrir documentos administrativos não-públicos que não exigem
TCI formal. Os três graus de sigilo exigem Termo de Classificação da Informação:
fundamento legal + autoridade classificadora + prazo de desclassificação
(LAI art. 24 §1º e art. 28).

Controle de acesso: o usuário tem credencial `nivel_acesso_sigilo`. Pode
acessar processo cujo nível seja <= sua credencial (need-to-know por grau).
Super-usuário ignora a checagem.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import tenant_filter
from ..models import Processo

# Ordem == rank (índice). NÃO reordenar nem inserir no meio — o rank é a base
# da comparação de acesso e a string é persistida no banco.
NIVEIS: tuple[str, ...] = (
    "ostensivo",
    "interno",
    "reservado",
    "secreto",
    "ultrassecreto",
)

NIVEL_RANK: dict[str, int] = {n: i for i, n in enumerate(NIVEIS)}

NIVEL_LABEL: dict[str, str] = {
    "ostensivo": "Ostensivo",
    "interno": "Interno",
    "reservado": "Reservado",
    "secreto": "Secreto",
    "ultrassecreto": "Ultrassecreto",
}

# Graus de sigilo legal (LAI art. 24) que exigem TCI. ostensivo/interno não.
GRAUS_SIGILO_LEGAL: frozenset[str] = frozenset(
    {"reservado", "secreto", "ultrassecreto"}
)

# Prazo máximo de restrição por grau (LAI art. 24 §1º). None = sem prazo legal.
PRAZO_MAX_ANOS: dict[str, int | None] = {
    "ostensivo": None,
    "interno": None,
    "reservado": 5,
    "secreto": 15,
    "ultrassecreto": 25,
}

NIVEL_DEFAULT = "ostensivo"
CREDENCIAL_DEFAULT = "interno"


class SigiloError(Exception):
    """Erro de validação/autorização na classificação de sigilo."""


def is_nivel_valido(nivel: str) -> bool:
    return nivel in NIVEL_RANK


def exige_tci(nivel: str) -> bool:
    """Se o nível é grau de sigilo legal (exige fundamento + autoridade + prazo)."""
    return nivel in GRAUS_SIGILO_LEGAL


def niveis_permitidos(credencial: str) -> list[str]:
    """Níveis que uma credencial pode acessar (do ostensivo até a credencial)."""
    rank = NIVEL_RANK.get(credencial, NIVEL_RANK[CREDENCIAL_DEFAULT])
    return list(NIVEIS[: rank + 1])


def pode_acessar(
    credencial: str, nivel_processo: str, *, is_super: bool = False
) -> bool:
    """True se a credencial alcança o nível do processo. Super-usuário sempre."""
    if is_super:
        return True
    cred_rank = NIVEL_RANK.get(credencial, NIVEL_RANK[CREDENCIAL_DEFAULT])
    proc_rank = NIVEL_RANK.get(nivel_processo, 0)
    return proc_rank <= cred_rank


def resolver_nivel_criacao(nivel_sigilo: str, publico: bool) -> str:
    """Resolve o nível na ABERTURA a partir das duas entradas possíveis.

    `nivel_sigilo` tem precedência quando != 'ostensivo' (cliente novo);
    senão deriva do booleano legado `publico`. Só ostensivo/interno são
    aceitos na abertura — sigilo legal exige TCI (endpoint de classificação).
    """
    nivel = nivel_sigilo if nivel_sigilo != NIVEL_DEFAULT else (
        "ostensivo" if publico else "interno"
    )
    if not is_nivel_valido(nivel):
        raise SigiloError(f"Nível de sigilo inválido: {nivel!r}")
    if exige_tci(nivel):
        raise SigiloError(
            "Na abertura use 'ostensivo' ou 'interno'. "
            "Sigilo legal (reservado/secreto/ultrassecreto) exige classificação com TCI."
        )
    return nivel


def _add_anos(d: date, anos: int) -> date:
    """d + N anos, com fallback de 29/fev → 28/fev em ano não-bissexto."""
    try:
        return d.replace(year=d.year + anos)
    except ValueError:
        return d.replace(year=d.year + anos, day=28)


async def classificar_processo(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    nivel: str,
    usuario_id: int,
    credencial_usuario: str,
    is_super: bool,
    fundamento_legal: str | None = None,
    autoridade: str | None = None,
    prazo_anos: int | None = None,
) -> Processo:
    """Reclassifica o sigilo de um processo, gravando o TCI quando aplicável.

    Regras:
    - O usuário precisa alcançar TANTO o nível atual quanto o alvo (não se
      classifica acima da própria credencial; não se mexe no que não se vê).
    - Graus de sigilo legal exigem fundamento + autoridade; prazo default =
      máximo legal, limitado ao máximo legal.
    - ostensivo/interno limpam os campos de TCI.
    `processo.publico` é coluna gerada (= nivel == 'ostensivo'); não é setada
    aqui — o banco a deriva.
    """
    if not is_nivel_valido(nivel):
        raise SigiloError(f"Nível de sigilo inválido: {nivel!r}")
    if not pode_acessar(credencial_usuario, nivel, is_super=is_super):
        raise SigiloError(
            "Sem credencial para classificar nesse nível de sigilo."
        )

    processo = (
        await db.execute(
            tenant_filter(
                select(Processo).where(
                    Processo.id == processo_id,
                    Processo.excluido.is_(False),
                ),
                Processo,
                tenant_id,
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise SigiloError("Processo não encontrado.")
    # Não se reclassifica o que não se pode sequer ver.
    if not pode_acessar(credencial_usuario, processo.nivel_sigilo, is_super=is_super):
        raise SigiloError("Sem credencial para acessar o sigilo atual do processo.")

    nivel_anterior = processo.nivel_sigilo
    now = datetime.now()

    if exige_tci(nivel):
        fundamento_legal = (fundamento_legal or "").strip()
        autoridade = (autoridade or "").strip()
        if not fundamento_legal:
            raise SigiloError("Fundamento legal é obrigatório para sigilo legal.")
        if not autoridade:
            raise SigiloError("Autoridade classificadora é obrigatória.")
        max_anos = PRAZO_MAX_ANOS[nivel]
        if prazo_anos is None:
            prazo_anos = max_anos
        if prazo_anos < 1 or (max_anos is not None and prazo_anos > max_anos):
            raise SigiloError(
                f"Prazo para {NIVEL_LABEL[nivel]} deve ser de 1 a {max_anos} anos."
            )
        processo.sigilo_fundamento_legal = fundamento_legal
        processo.sigilo_autoridade = autoridade
        processo.sigilo_prazo_anos = prazo_anos
        processo.sigilo_data_classificacao = now
        processo.sigilo_data_desclassificacao = _add_anos(now.date(), prazo_anos)
        processo.sigilo_classificado_por = usuario_id
    else:
        # ostensivo / interno — sem TCI. Limpa metadados de classificação.
        processo.sigilo_fundamento_legal = None
        processo.sigilo_autoridade = None
        processo.sigilo_prazo_anos = None
        processo.sigilo_data_desclassificacao = None
        # Mantém quem mexeu + quando, pra trilha (interno também é decisão).
        processo.sigilo_data_classificacao = now
        processo.sigilo_classificado_por = usuario_id

    processo.nivel_sigilo = nivel

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.classificado_sigilo",
        entidade="processo",
        id_entidade=processo.id,
        payload={
            "nivel_anterior": nivel_anterior,
            "nivel_novo": nivel,
            "fundamento_legal": processo.sigilo_fundamento_legal,
            "autoridade": processo.sigilo_autoridade,
            "prazo_anos": processo.sigilo_prazo_anos,
        },
    )

    await db.commit()
    await db.refresh(processo)
    return processo
