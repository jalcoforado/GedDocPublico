"""Sugestão de CCD por assunto + resolução de regra TTD com hierarquia.

Sugestão (sugerir_ccd_por_assunto):
- Match único, múltiplo, sem match, com texto_extra, limit aplicado.

Hierarquia (_resolver_regra_com_hierarquia):
- Regra direta na classe → retorna imediato.
- Regra só no pai → walking 1 nível.
- Regra só no avô → walking 2 níveis.
- Sem regra em ancestral algum → retorna (None, path completo).
- Ciclo (A→B→A) → walk para sem loop infinito.
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.temporalidade import (
    _resolver_regra_com_hierarquia,
    sugerir_ccd_por_assunto,
)


# -------- helpers --------


async def _insert_ccd(
    session: AsyncSession,
    *,
    tenant_id: int,
    codigo: str,
    nome: str,
    palavras_chave: str | None = None,
    id_classe_pai: int | None = None,
) -> int:
    res = await session.execute(
        text(
            """
            INSERT INTO protocolos.ccd_classe
                (tenant_id, codigo, nome, palavras_chave, id_classe_pai, ativo, excluido)
            VALUES (:tid, :cod, :nome, :pc, :pai, true, false)
            RETURNING id
            """
        ),
        {
            "tid": tenant_id,
            "cod": codigo,
            "nome": nome,
            "pc": palavras_chave,
            "pai": id_classe_pai,
        },
    )
    return int(res.scalar_one())


async def _insert_ttd(
    session: AsyncSession,
    *,
    tenant_id: int,
    id_ccd_classe: int,
    anos_corrente: int = 5,
    anos_intermediario: int = 10,
    destino_final: str = "GUARDA_PERMANENTE",
    id_especie: int | None = None,
) -> int:
    res = await session.execute(
        text(
            """
            INSERT INTO protocolos.ttd_regra
                (tenant_id, id_ccd_classe, id_especie_documental,
                 anos_corrente, anos_intermediario, destino_final,
                 ativo, excluido)
            VALUES (:tid, :cls, :esp, :ac, :ai, :df, true, false)
            RETURNING id
            """
        ),
        {
            "tid": tenant_id,
            "cls": id_ccd_classe,
            "esp": id_especie,
            "ac": anos_corrente,
            "ai": anos_intermediario,
            "df": destino_final,
        },
    )
    return int(res.scalar_one())


async def _insert_tipo_processo(
    session: AsyncSession, *, tenant_id: int, nome: str = "Tipo teste"
) -> int:
    res = await session.execute(
        text(
            """
            INSERT INTO protocolos.tipo_processo
                (tenant_id, tipo_processo, ativo, excluido)
            VALUES (:tid, :nome, true, false)
            RETURNING id
            """
        ),
        {"tid": tenant_id, "nome": nome},
    )
    return int(res.scalar_one())


async def _insert_assunto(
    session: AsyncSession,
    *,
    tenant_id: int,
    nome: str,
    id_tipo_processo: int,
) -> int:
    res = await session.execute(
        text(
            """
            INSERT INTO protocolos.assunto
                (tenant_id, assunto, id_tipo_processo, ativo, excluido)
            VALUES (:tid, :nome, :tp, true, false)
            RETURNING id
            """
        ),
        {"tid": tenant_id, "nome": nome, "tp": id_tipo_processo},
    )
    return int(res.scalar_one())


@pytest_asyncio.fixture
async def ccd_setup(admin_engine, two_tenants):
    """Tenant temp com classes CCD + assunto pra testes de sugestão.

    Hierarquia criada:
        root (AQUISICAO, palavras_chave='aquisicao,licitacao,compras')
        ├── mid (CONTRATO, palavras_chave='contrato,fornecedor')
        │   └── leaf (PAGAMENTO, palavras_chave='pagamento,nota')
        outra (RH, palavras_chave='ferias,folha,trabalhador')
    """
    tid_a, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        tp = await _insert_tipo_processo(s, tenant_id=tid_a)
        root = await _insert_ccd(
            s,
            tenant_id=tid_a,
            codigo="010",
            nome="Aquisição",
            palavras_chave="aquisicao, licitacao, compras",
        )
        mid = await _insert_ccd(
            s,
            tenant_id=tid_a,
            codigo="010.1",
            nome="Contratos",
            palavras_chave="contrato, fornecedor",
            id_classe_pai=root,
        )
        leaf = await _insert_ccd(
            s,
            tenant_id=tid_a,
            codigo="010.1.1",
            nome="Pagamentos",
            palavras_chave="pagamento, nota",
            id_classe_pai=mid,
        )
        outra = await _insert_ccd(
            s,
            tenant_id=tid_a,
            codigo="050",
            nome="Recursos Humanos",
            palavras_chave="ferias, folha, trabalhador",
        )
        assunto_aq = await _insert_assunto(
            s,
            tenant_id=tid_a,
            nome="Aquisição de licenças de software",
            id_tipo_processo=tp,
        )
        await s.commit()

    yield {
        "tid": tid_a,
        "tp": tp,
        "root": root,
        "mid": mid,
        "leaf": leaf,
        "outra": outra,
        "assunto_aq": assunto_aq,
    }


# ============================================================================
#  sugerir_ccd_por_assunto
# ============================================================================


async def test_sugerir_ccd_match_unico(admin_engine, ccd_setup):
    """Assunto 'Aquisição de licenças' bate forte com classe AQUISICAO."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        sugs = await sugerir_ccd_por_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            id_assunto=ccd_setup["assunto_aq"],
            limit=5,
        )

    assert len(sugs) >= 1
    assert sugs[0].id_ccd_classe == ccd_setup["root"]
    assert sugs[0].score > 0
    assert "aquisicao" in sugs[0].matched_keywords


async def test_sugerir_ccd_sem_match_retorna_vazio(admin_engine, ccd_setup):
    """Assunto totalmente não-relacionado às classes → []."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        outro_assunto = await _insert_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            nome="Reforma do estacionamento subterrâneo",
            id_tipo_processo=ccd_setup["tp"],
        )
        await s.commit()

        sugs = await sugerir_ccd_por_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            id_assunto=outro_assunto,
        )
    assert sugs == []


async def test_sugerir_ccd_texto_extra_contribui(admin_engine, ccd_setup):
    """texto_extra adiciona tokens ao match — assunto 'qualquer' + extra
    'contrato fornecedor' deve achar a classe Contratos."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        a_neutro = await _insert_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            nome="Documento administrativo",
            id_tipo_processo=ccd_setup["tp"],
        )
        await s.commit()
        sugs = await sugerir_ccd_por_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            id_assunto=a_neutro,
            texto_extra="solicitacao de contrato com fornecedor",
        )
    assert any(s.id_ccd_classe == ccd_setup["mid"] for s in sugs)


async def test_sugerir_ccd_limit_aplicado(admin_engine, ccd_setup):
    """limit=1 retorna apenas top-1 mesmo com múltiplos matches."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        # Texto extra com termos de root, mid e leaf — todos batem
        a = await _insert_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            nome="aquisicao contrato pagamento processo",
            id_tipo_processo=ccd_setup["tp"],
        )
        await s.commit()
        sugs_5 = await sugerir_ccd_por_assunto(
            s, tenant_id=ccd_setup["tid"], id_assunto=a, limit=5
        )
        sugs_1 = await sugerir_ccd_por_assunto(
            s, tenant_id=ccd_setup["tid"], id_assunto=a, limit=1
        )
    assert len(sugs_5) >= 2
    assert len(sugs_1) == 1
    # Top-1 deve ser o mesmo nos dois rankings
    assert sugs_1[0].id_ccd_classe == sugs_5[0].id_ccd_classe


async def test_sugerir_ccd_ranking_por_score(admin_engine, ccd_setup):
    """Match em 3 keywords > match em 1 — ordem decrescente."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        # 'aquisicao licitacao compras' bate 3 termos da root; 'contrato' bate
        # só 1 termo da mid.
        a = await _insert_assunto(
            s,
            tenant_id=ccd_setup["tid"],
            nome="aquisicao licitacao compras contrato",
            id_tipo_processo=ccd_setup["tp"],
        )
        await s.commit()
        sugs = await sugerir_ccd_por_assunto(
            s, tenant_id=ccd_setup["tid"], id_assunto=a, limit=5
        )

    # Pelo menos root e mid devem aparecer
    ids = [s.id_ccd_classe for s in sugs]
    assert ccd_setup["root"] in ids
    assert ccd_setup["mid"] in ids
    # root tem mais matches → score maior → vem antes
    pos_root = ids.index(ccd_setup["root"])
    pos_mid = ids.index(ccd_setup["mid"])
    assert pos_root < pos_mid


# ============================================================================
#  _resolver_regra_com_hierarquia
# ============================================================================


async def test_resolver_regra_direta_na_classe(admin_engine, ccd_setup):
    """Regra criada exatamente na leaf → encontra imediato, path=[leaf]."""
    tid = ccd_setup["tid"]
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await _insert_ttd(
            s,
            tenant_id=tid,
            id_ccd_classe=ccd_setup["leaf"],
            anos_corrente=3,
            destino_final="ELIMINACAO",
        )
        await s.commit()

    async with Session() as s:
        regra, path = await _resolver_regra_com_hierarquia(
            s, tenant_id=tid, id_classe=ccd_setup["leaf"], id_especie=None
        )

    assert regra is not None
    assert regra.id_ccd_classe == ccd_setup["leaf"]
    assert regra.anos_corrente == 3
    assert path == [ccd_setup["leaf"]]


async def test_resolver_regra_no_pai(admin_engine, ccd_setup):
    """Regra só no mid → walking sobe da leaf, path=[leaf, mid]."""
    tid = ccd_setup["tid"]
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await _insert_ttd(
            s,
            tenant_id=tid,
            id_ccd_classe=ccd_setup["mid"],
            anos_corrente=7,
        )
        await s.commit()

    async with Session() as s:
        regra, path = await _resolver_regra_com_hierarquia(
            s, tenant_id=tid, id_classe=ccd_setup["leaf"], id_especie=None
        )

    assert regra is not None
    assert regra.id_ccd_classe == ccd_setup["mid"]
    assert path == [ccd_setup["leaf"], ccd_setup["mid"]]


async def test_resolver_regra_no_avo(admin_engine, ccd_setup):
    """Regra só na root → walking sobe 2 níveis, path=[leaf, mid, root]."""
    tid = ccd_setup["tid"]
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await _insert_ttd(
            s,
            tenant_id=tid,
            id_ccd_classe=ccd_setup["root"],
            anos_corrente=10,
            destino_final="GUARDA_PERMANENTE",
        )
        await s.commit()

    async with Session() as s:
        regra, path = await _resolver_regra_com_hierarquia(
            s, tenant_id=tid, id_classe=ccd_setup["leaf"], id_especie=None
        )

    assert regra is not None
    assert regra.id_ccd_classe == ccd_setup["root"]
    assert regra.destino_final == "GUARDA_PERMANENTE"
    assert path == [ccd_setup["leaf"], ccd_setup["mid"], ccd_setup["root"]]


async def test_resolver_sem_regra_retorna_none(admin_engine, ccd_setup):
    """Nenhuma regra em ancestral → (None, path completo até a root)."""
    tid = ccd_setup["tid"]
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        regra, path = await _resolver_regra_com_hierarquia(
            s, tenant_id=tid, id_classe=ccd_setup["leaf"], id_especie=None
        )

    assert regra is None
    assert path == [ccd_setup["leaf"], ccd_setup["mid"], ccd_setup["root"]]


async def test_resolver_ciclo_nao_loopa(admin_engine, ccd_setup):
    """Ciclo A→B→A — walk para por causa do guard `cur not in visitados`."""
    tid = ccd_setup["tid"]
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        a = await _insert_ccd(
            s, tenant_id=tid, codigo="CYC.A", nome="Ciclo A"
        )
        b = await _insert_ccd(
            s,
            tenant_id=tid,
            codigo="CYC.B",
            nome="Ciclo B",
            id_classe_pai=a,
        )
        # Fecha o ciclo: A.pai = B
        await s.execute(
            text(
                "UPDATE protocolos.ccd_classe SET id_classe_pai = :b WHERE id = :a"
            ),
            {"a": a, "b": b},
        )
        await s.commit()

    async with Session() as s:
        regra, path = await _resolver_regra_com_hierarquia(
            s, tenant_id=tid, id_classe=a, id_especie=None
        )

    # Sem regra criada — só queremos garantir que terminou (guard funcionou)
    assert regra is None
    # Path visita ambos uma vez antes de detectar ciclo
    assert set(path) == {a, b}
    assert len(path) == 2  # cada um visitado exatamente 1 vez
