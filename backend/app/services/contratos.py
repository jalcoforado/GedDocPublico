"""Regras do módulo Contratos (G1): ciclo do contrato, aditivos, apostilas e
o cálculo de valor e vigência.

Spec: docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md

Três ideias sustentam este arquivo:

1. **Aditivo e apostila são atos, não edição.** Depois de assinado, o contrato
   não muda de valor nem de vigência por UPDATE — registra-se o ato.
2. **Valor atualizado e vigência atual são DERIVADOS** (`calcular`), nunca
   gravados. `valor_total`, `vigencia_inicio` e `vigencia_fim` da tabela são os
   originais, congelados na assinatura.
3. **O limite do art. 125 da Lei 14.133 sinaliza, não bloqueia.** Acima dele o
   aditivo exige justificativa; quem julga a legalidade é o gestor, não o
   sistema.

`tenant_id` e o usuário vêm sempre do caller. Carga por id filtra tenant e
`excluido` e devolve 404 — inclusive para registro de outro tenant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Contrato,
    ContratoAditivo,
    ContratoApostila,
    Fornecedor,
    Processo,
    UnidadeTrabalho,
)
from ..schemas.contratos import (
    AditivoCreate,
    AditivoUpdate,
    ApostilaCreate,
    ContratoCreate,
    ContratoUpdate,
)
from .modulos import slugs_contratados
from .sigilo import SigiloAcessoError, assert_acesso_processo

MODULO_SLUG = "contratos"

RASCUNHO = "RASCUNHO"
VIGENTE = "VIGENTE"
ENCERRADO = "ENCERRADO"
RESCINDIDO = "RESCINDIDO"
ANULADO = "ANULADO"

# Tamanho do campo "Número do Contrato" na tabela 511 do SIM.
NUMERO_SIM_MAX = 15

# Aditivos que somam, subtraem ou renovam valor; e os que mexem na vigência.
TIPOS_ACRESCIMO = frozenset({"AA", "PA"})
TIPOS_SUPRESSAO = frozenset({"AR", "PR"})
TIPOS_RENOVACAO = frozenset({"RE"})
TIPOS_COM_PRAZO = frozenset({"AP", "PA", "PR", "RE"})
TIPOS_APOSTILA_COM_VALOR = frozenset({"REAJUSTE", "REPACTUACAO"})

# Art. 125 da Lei 14.133: 25% do valor inicial atualizado; 50% de ACRÉSCIMO em
# reforma de edifício ou de equipamento.
LIMITE_PADRAO = Decimal("25")
LIMITE_ACRESCIMO_REFORMA = Decimal("50")

# Depois de assinado, só isto se edita: dados SOBRE o contrato, que costumam
# chegar depois da assinatura. Todo o resto é do ato de contratar e só muda por
# aditivo ou apostila (spec §5.1). Lista de permitidos, não de proibidos:
# coluna nova nasce travada, que é o lado seguro do esquecimento.
CAMPOS_LIVRES_APOS_ASSINATURA = frozenset({
    "tipo_objeto", "natureza_duracao", "categoria", "id_processo", "processo_numero",
    "processo_data_autuacao", "pncp_id", "pncp_publicado_em",
})

_CENTAVO = Decimal("0.01")


class ContratoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _nao_encontrado(o_que: str = "Contrato") -> ContratoError:
    return ContratoError(f"{o_que} não encontrado", status.HTTP_404_NOT_FOUND)


# ============================ cálculo (puro) ===================================

@dataclass(frozen=True)
class Calculo:
    """Os derivados do §2.4 do spec. Nada aqui é coluna."""
    valor_inicial: Decimal
    valor_inicial_atualizado: Decimal
    acrescimos: Decimal
    supressoes: Decimal
    renovacoes: Decimal
    valor_atualizado: Decimal
    vigencia_fim_atual: date
    percentual_acrescimo: Decimal
    percentual_supressao: Decimal
    limite_acrescimo: Decimal
    limite_supressao: Decimal
    acima_do_limite: bool
    dias_para_vencer: int | None


def _percentual(parte: Decimal, base: Decimal) -> Decimal:
    if base <= 0:
        return Decimal("0.00")
    return (parte * 100 / base).quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def calcular(contrato, aditivos, apostilas, *, hoje: date) -> Calculo:
    """Valor e vigência do contrato a partir dos atos.

    Função pura: recebe o que já foi carregado e não toca o banco. Só aditivo
    `VIGENTE` e não excluído conta; rascunho e anulado ficam de fora.

    Três escolhas de regra, registradas como decisão Q5 do spec e a confirmar
    com a procuradoria antes do piloto real:

    - acréscimo e supressão NÃO se compensam — cada um é medido sozinho;
    - renovação (`RE`) soma ao valor global e NÃO conta no limite;
    - a base do percentual é o valor inicial ATUALIZADO (inicial + reajustes
      por apostila), como diz o art. 125.
    """
    validos = [a for a in aditivos if a.situacao == VIGENTE and not a.excluido]
    vivas = [p for p in apostilas if not p.excluido]

    valor_inicial = Decimal(contrato.valor_total)
    reajustes = sum(
        (Decimal(p.valor_delta) for p in vivas
         if p.tipo in TIPOS_APOSTILA_COM_VALOR and p.valor_delta is not None),
        Decimal("0"),
    )
    base = valor_inicial + reajustes

    def _soma(tipos: frozenset[str]) -> Decimal:
        return sum((Decimal(a.valor) for a in validos if a.tipo in tipos), Decimal("0"))

    acrescimos = _soma(TIPOS_ACRESCIMO)
    supressoes = _soma(TIPOS_SUPRESSAO)
    renovacoes = _soma(TIPOS_RENOVACAO)

    datas = [a.nova_vigencia_fim for a in validos if a.nova_vigencia_fim is not None]
    vigencia_fim_atual = max([contrato.vigencia_fim, *datas])

    pct_acrescimo = _percentual(acrescimos, base)
    pct_supressao = _percentual(supressoes, base)
    limite_acrescimo = LIMITE_ACRESCIMO_REFORMA if contrato.reforma else LIMITE_PADRAO
    limite_supressao = LIMITE_PADRAO

    dias = (vigencia_fim_atual - hoje).days if contrato.situacao == VIGENTE else None

    return Calculo(
        valor_inicial=valor_inicial,
        valor_inicial_atualizado=base,
        acrescimos=acrescimos,
        supressoes=supressoes,
        renovacoes=renovacoes,
        valor_atualizado=base + acrescimos - supressoes + renovacoes,
        vigencia_fim_atual=vigencia_fim_atual,
        percentual_acrescimo=pct_acrescimo,
        percentual_supressao=pct_supressao,
        limite_acrescimo=limite_acrescimo,
        limite_supressao=limite_supressao,
        acima_do_limite=pct_acrescimo > limite_acrescimo or pct_supressao > limite_supressao,
        dias_para_vencer=dias,
    )


# ============================ carga ============================================

async def modulo_contratado(db: AsyncSession, *, tenant_id: int) -> bool:
    """O tenant contratou o módulo `contratos`?

    É o que decide a convivência com o cadastro simples de pagamentos
    (spec §5.2): com o módulo, a escrita por lá é recusada.
    """
    return MODULO_SLUG in await slugs_contratados(db, tenant_id)


async def obter(db: AsyncSession, *, tenant_id: int, contrato_id: int) -> Contrato:
    c = (await db.execute(select(Contrato).where(
        Contrato.id == contrato_id, Contrato.tenant_id == tenant_id,
        Contrato.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise _nao_encontrado()
    return c


async def _atos(db: AsyncSession, *, tenant_id: int, contrato_ids: list[int]):
    """Aditivos e apostilas vivos dos contratos pedidos, agrupados por contrato."""
    aditivos: dict[int, list[ContratoAditivo]] = {i: [] for i in contrato_ids}
    apostilas: dict[int, list[ContratoApostila]] = {i: [] for i in contrato_ids}
    if not contrato_ids:
        return aditivos, apostilas
    for a in (await db.execute(select(ContratoAditivo).where(
            ContratoAditivo.tenant_id == tenant_id, ContratoAditivo.excluido.is_(False),
            ContratoAditivo.id_contrato.in_(contrato_ids),
    ).order_by(ContratoAditivo.sequencial))).scalars().all():
        aditivos[a.id_contrato].append(a)
    for p in (await db.execute(select(ContratoApostila).where(
            ContratoApostila.tenant_id == tenant_id, ContratoApostila.excluido.is_(False),
            ContratoApostila.id_contrato.in_(contrato_ids),
    ).order_by(ContratoApostila.sequencial))).scalars().all():
        apostilas[p.id_contrato].append(p)
    return aditivos, apostilas


async def _nomes(db: AsyncSession, *, tenant_id: int, contratos: list[Contrato]):
    ids_f = {c.id_fornecedor for c in contratos}
    ids_u = {c.id_unidade for c in contratos}
    fornecedores: dict[int, str] = {}
    unidades: dict[int, str] = {}
    if ids_f:
        fornecedores = dict((await db.execute(select(Fornecedor.id, Fornecedor.nome).where(
            Fornecedor.tenant_id == tenant_id, Fornecedor.id.in_(ids_f)))).all())
    if ids_u:
        unidades = dict((await db.execute(
            select(UnidadeTrabalho.id, UnidadeTrabalho.unidade_trabalho).where(
                UnidadeTrabalho.tenant_id == tenant_id, UnidadeTrabalho.id.in_(ids_u)))).all())
    return fornecedores, unidades


def _vigencia_atual_sql():
    """`COALESCE(maior nova data final entre os aditivos vigentes, a original)`.

    Mesma regra de `calcular`, em SQL, só para FILTRAR e ORDENAR a listagem. O
    valor devolvido ao cliente vem sempre de `calcular` — duas fontes para o
    mesmo número seria a divergência que o derivado existe para evitar.
    """
    maior = (
        select(func.max(ContratoAditivo.nova_vigencia_fim))
        .where(
            ContratoAditivo.id_contrato == Contrato.id,
            ContratoAditivo.tenant_id == Contrato.tenant_id,
            ContratoAditivo.situacao == VIGENTE,
            ContratoAditivo.excluido.is_(False),
        )
        .correlate(Contrato)
        .scalar_subquery()
    )
    return func.coalesce(maior, Contrato.vigencia_fim)


def _resumo(c: Contrato, calc: Calculo, fornecedores: dict, unidades: dict) -> dict:
    return {
        "id": c.id, "numero": c.numero, "exercicio": c.exercicio, "situacao": c.situacao,
        "id_fornecedor": c.id_fornecedor, "fornecedor_nome": fornecedores.get(c.id_fornecedor),
        "id_unidade": c.id_unidade, "unidade_nome": unidades.get(c.id_unidade),
        "objeto": c.objeto, "tipo_objeto": c.tipo_objeto,
        "valor_inicial": calc.valor_inicial, "valor_atualizado": calc.valor_atualizado,
        "vigencia_inicio": c.vigencia_inicio, "vigencia_fim_atual": calc.vigencia_fim_atual,
        "percentual_acrescimo": calc.percentual_acrescimo,
        "acima_do_limite": calc.acima_do_limite, "dias_para_vencer": calc.dias_para_vencer,
    }


async def listar(
    db: AsyncSession, *, tenant_id: int, page: int, page_size: int,
    situacao: str | None = None, id_unidade: int | None = None,
    id_fornecedor: int | None = None, exercicio: int | None = None,
    q: str | None = None, vence_ate: date | None = None, hoje: date | None = None,
) -> tuple[list[dict], int]:
    """Página de contratos, do que vence primeiro para o que vence por último."""
    hoje = hoje or date.today()
    vig_atual = _vigencia_atual_sql()
    base = select(Contrato).where(Contrato.tenant_id == tenant_id, Contrato.excluido.is_(False))
    if situacao:
        base = base.where(Contrato.situacao == situacao)
    if id_unidade is not None:
        base = base.where(Contrato.id_unidade == id_unidade)
    if id_fornecedor is not None:
        base = base.where(Contrato.id_fornecedor == id_fornecedor)
    if exercicio is not None:
        base = base.where(Contrato.exercicio == exercicio)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(or_(
            func.lower(Contrato.numero).like(like), func.lower(Contrato.objeto).like(like)))
    if vence_ate is not None:
        # "Vence até" só faz sentido para o que está em vigor.
        base = base.where(Contrato.situacao == VIGENTE, vig_atual <= vence_ate)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    contratos = list((await db.execute(
        base.order_by(vig_atual, Contrato.id).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all())

    aditivos, apostilas = await _atos(db, tenant_id=tenant_id, contrato_ids=[c.id for c in contratos])
    fornecedores, unidades = await _nomes(db, tenant_id=tenant_id, contratos=contratos)
    itens = [
        _resumo(c, calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje), fornecedores, unidades)
        for c in contratos
    ]
    return itens, total


async def painel(db: AsyncSession, *, tenant_id: int, hoje: date | None = None) -> dict:
    """Contagens do painel. Calcula em memória sobre os contratos do tenant —
    escala municipal (centenas a poucos milhares), e assim o número do painel
    sai da MESMA função que o do detalhe."""
    hoje = hoje or date.today()
    contratos = list((await db.execute(select(Contrato).where(
        Contrato.tenant_id == tenant_id, Contrato.excluido.is_(False),
        Contrato.situacao.in_((RASCUNHO, VIGENTE))))).scalars().all())
    aditivos, apostilas = await _atos(db, tenant_id=tenant_id, contrato_ids=[c.id for c in contratos])

    out = {
        "vigentes": 0, "rascunhos": 0, "vencidos": 0, "vencendo_30": 0, "vencendo_60": 0,
        "vencendo_90": 0, "vencendo_120": 0, "acima_do_limite": 0,
        "valor_vigente_total": Decimal("0"),
    }
    for c in contratos:
        if c.situacao == RASCUNHO:
            out["rascunhos"] += 1
            continue
        calc = calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje)
        out["vigentes"] += 1
        out["valor_vigente_total"] += calc.valor_atualizado
        if calc.acima_do_limite:
            out["acima_do_limite"] += 1
        dias = calc.dias_para_vencer
        if dias is None:
            continue
        if dias < 0:
            out["vencidos"] += 1
            continue
        # Faixas CUMULATIVAS: quem vence em 20 dias conta em 30, 60, 90 e 120.
        for limite in (30, 60, 90, 120):
            if dias <= limite:
                out[f"vencendo_{limite}"] += 1
    return out


async def detalhar(db: AsyncSession, *, tenant_id: int, contrato_id: int, usuario,
                   hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    aditivos, apostilas = await _atos(db, tenant_id=tenant_id, contrato_ids=[c.id])
    fornecedores, unidades = await _nomes(db, tenant_id=tenant_id, contratos=[c])
    calc = calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje)
    return {
        "id": c.id, "numero": c.numero, "exercicio": c.exercicio, "situacao": c.situacao,
        "id_fornecedor": c.id_fornecedor, "fornecedor_nome": fornecedores.get(c.id_fornecedor),
        "id_unidade": c.id_unidade, "unidade_nome": unidades.get(c.id_unidade),
        "objeto": c.objeto, "vigencia_inicio": c.vigencia_inicio, "vigencia_fim": c.vigencia_fim,
        "valor_total": c.valor_total, "categoria": c.categoria,
        "data_celebracao": c.data_celebracao, "tipo_objeto": c.tipo_objeto,
        "natureza_duracao": c.natureza_duracao, "reforma": c.reforma,
        "processo": await _processo_visivel(db, tenant_id=tenant_id, contrato=c, usuario=usuario),
        "processo_numero": c.processo_numero,
        "processo_data_autuacao": c.processo_data_autuacao,
        "pncp_id": c.pncp_id, "pncp_publicado_em": c.pncp_publicado_em,
        "data_encerramento": c.data_encerramento, "motivo_rescisao": c.motivo_rescisao,
        "criado_em": c.criado_em, "atualizado_em": c.atualizado_em,
        "calculo": calc, "aditivos": aditivos[c.id], "apostilas": apostilas[c.id],
    }


# ============================ sigilo ===========================================

async def _processo_visivel(db: AsyncSession, *, tenant_id: int, contrato: Contrato,
                            usuario) -> dict | None:
    """O processo vinculado, se o usuário tiver credencial de sigilo para ele.

    Sem credencial o vínculo vem `None` e o contrato aparece normalmente: o
    contrato é ato público, o processo de origem pode não ser. Devolver 404 no
    contrato inteiro esconderia o que a LAI manda publicar.
    """
    if contrato.id_processo is None:
        return None
    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=contrato.id_processo, usuario=usuario)
    except SigiloAcessoError:
        return None
    numero = (await db.execute(select(Processo.numero_processo).where(
        Processo.id == contrato.id_processo, Processo.tenant_id == tenant_id))).scalar_one_or_none()
    return {"id": contrato.id_processo, "numero_processo": numero}


async def _validar_processo(db: AsyncSession, *, tenant_id: int, id_processo: int | None,
                            usuario) -> None:
    """Vínculo com processo: same-tenant e dentro da credencial de sigilo.

    A autorização vem ANTES de resolver o recurso, e as duas falhas devolvem a
    mesma mensagem — senão o erro distinguiria "não existe" de "existe e você
    não pode ver".
    """
    if id_processo is None:
        return
    recusa = ContratoError("Processo não encontrado", status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=id_processo, usuario=usuario)
    except SigiloAcessoError:
        raise recusa from None
    existe = (await db.execute(select(Processo.id).where(
        Processo.id == id_processo, Processo.tenant_id == tenant_id))).scalar_one_or_none()
    if existe is None:
        raise recusa


# ============================ validações =======================================

async def _validar_fornecedor(db: AsyncSession, *, tenant_id: int, id_fornecedor: int) -> None:
    ok = (await db.execute(select(Fornecedor.id).where(
        Fornecedor.id == id_fornecedor, Fornecedor.tenant_id == tenant_id,
        Fornecedor.excluido.is_(False)))).scalar_one_or_none()
    if ok is None:
        raise ContratoError("Fornecedor inválido.", status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _validar_unidade(db: AsyncSession, *, tenant_id: int, id_unidade: int) -> None:
    ok = (await db.execute(select(UnidadeTrabalho.id).where(
        UnidadeTrabalho.id == id_unidade, UnidadeTrabalho.tenant_id == tenant_id,
        UnidadeTrabalho.excluido.is_(False)))).scalar_one_or_none()
    if ok is None:
        raise ContratoError("Unidade (órgão) inválida.", status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _numero_livre(db: AsyncSession, *, tenant_id: int, exercicio: int, numero: str,
                        ignorar_contrato: int | None = None,
                        ignorar_aditivo: int | None = None) -> None:
    """Número único no exercício ENTRE contratos E aditivos.

    No SIM os dois dividem o mesmo campo ("Número do Contrato", tabela 511):
    um aditivo numerado igual a um contrato do mesmo ano derruba a remessa. O
    banco tem um índice único por tabela; a regra cruzada só existe aqui.
    """
    stmt_c = select(Contrato.id).where(
        Contrato.tenant_id == tenant_id, Contrato.exercicio == exercicio,
        Contrato.numero == numero, Contrato.excluido.is_(False))
    if ignorar_contrato is not None:
        stmt_c = stmt_c.where(Contrato.id != ignorar_contrato)
    stmt_a = select(ContratoAditivo.id).where(
        ContratoAditivo.tenant_id == tenant_id, ContratoAditivo.exercicio == exercicio,
        ContratoAditivo.numero == numero, ContratoAditivo.excluido.is_(False))
    if ignorar_aditivo is not None:
        stmt_a = stmt_a.where(ContratoAditivo.id != ignorar_aditivo)
    if (await db.execute(stmt_c.limit(1))).scalar_one_or_none() is not None:
        raise ContratoError(
            f"Já existe contrato número '{numero}' no exercício {exercicio}.",
            status.HTTP_409_CONFLICT)
    if (await db.execute(stmt_a.limit(1))).scalar_one_or_none() is not None:
        raise ContratoError(
            f"Já existe aditivo número '{numero}' no exercício {exercicio} — no SIM, "
            "contrato e aditivo dividem a mesma numeração.",
            status.HTTP_409_CONFLICT)


def _validar_vigencia(inicio: date, fim: date) -> None:
    if fim < inicio:
        raise ContratoError(
            "O fim da vigência não pode ser anterior ao início.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


def _exercicio_de(data_celebracao: date | None, vigencia_inicio: date) -> int:
    return (data_celebracao or vigencia_inicio).year


async def _gravar(db: AsyncSession, obj=None) -> None:
    """Commit convertendo violação de unicidade em 409 — duas requisições
    simultâneas passam pela checagem em memória e a segunda morre no índice."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ContratoError(
            "Conflito ao gravar: número ou sequencial já usado. Recarregue e tente de novo.",
            status.HTTP_409_CONFLICT) from exc
    if obj is not None:
        await db.refresh(obj)


# ============================ contrato =========================================

async def criar(db: AsyncSession, *, tenant_id: int, usuario, payload: ContratoCreate) -> Contrato:
    _validar_vigencia(payload.vigencia_inicio, payload.vigencia_fim)
    await _validar_fornecedor(db, tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor)
    await _validar_unidade(db, tenant_id=tenant_id, id_unidade=payload.id_unidade)
    await _validar_processo(db, tenant_id=tenant_id, id_processo=payload.id_processo, usuario=usuario)
    exercicio = _exercicio_de(payload.data_celebracao, payload.vigencia_inicio)
    await _numero_livre(db, tenant_id=tenant_id, exercicio=exercicio, numero=payload.numero)
    c = Contrato(
        tenant_id=tenant_id, criado_em=_utcnow(), situacao=RASCUNHO, exercicio=exercicio,
        **payload.model_dump())
    db.add(c)
    await _gravar(db, c)
    return c


async def atualizar(db: AsyncSession, *, tenant_id: int, contrato_id: int, usuario,
                    payload: ContratoUpdate) -> Contrato:
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    dados = payload.model_dump(exclude_unset=True)

    if c.situacao != RASCUNHO:
        travados = sorted(
            k for k, v in dados.items()
            if k not in CAMPOS_LIVRES_APOS_ASSINATURA and v != getattr(c, k))
        if travados:
            raise ContratoError(
                "Contrato assinado: " + ", ".join(travados) + " não se edita. "
                "Altere por aditivo ou apostila.",
                status.HTTP_409_CONFLICT)
        dados = {k: v for k, v in dados.items() if k in CAMPOS_LIVRES_APOS_ASSINATURA}

    if "id_fornecedor" in dados:
        await _validar_fornecedor(db, tenant_id=tenant_id, id_fornecedor=dados["id_fornecedor"])
    if "id_unidade" in dados:
        await _validar_unidade(db, tenant_id=tenant_id, id_unidade=dados["id_unidade"])
    if dados.get("id_processo") is not None:
        await _validar_processo(
            db, tenant_id=tenant_id, id_processo=dados["id_processo"], usuario=usuario)

    inicio = dados.get("vigencia_inicio", c.vigencia_inicio)
    fim = dados.get("vigencia_fim", c.vigencia_fim)
    _validar_vigencia(inicio, fim)

    if c.situacao == RASCUNHO:
        exercicio = _exercicio_de(dados.get("data_celebracao", c.data_celebracao), inicio)
        numero = dados.get("numero", c.numero)
        if exercicio != c.exercicio or numero != c.numero:
            await _numero_livre(
                db, tenant_id=tenant_id, exercicio=exercicio, numero=numero,
                ignorar_contrato=c.id)
        c.exercicio = exercicio

    for k, v in dados.items():
        setattr(c, k, v)
    c.atualizado_em = _utcnow()
    await _gravar(db, c)
    return c


async def excluir(db: AsyncSession, *, tenant_id: int, contrato_id: int) -> None:
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    if c.situacao != RASCUNHO:
        raise ContratoError(
            "Só contrato em rascunho pode ser excluído — contrato assinado é ato "
            "administrativo. Encerre ou rescinda.",
            status.HTTP_409_CONFLICT)
    c.excluido = True
    c.atualizado_em = _utcnow()
    await _gravar(db)


def _exigir_situacao(c: Contrato, esperada: str, acao: str) -> None:
    if c.situacao != esperada:
        raise ContratoError(
            f"Não é possível {acao}: o contrato está {c.situacao}.", status.HTTP_409_CONFLICT)


async def assinar(db: AsyncSession, *, tenant_id: int, contrato_id: int) -> Contrato:
    """RASCUNHO → VIGENTE. É aqui que os dados que o Tribunal cobra viram
    obrigatórios: rascunho pode nascer incompleto, contrato assinado não."""
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, RASCUNHO, "assinar")
    faltam = [
        rotulo for campo, rotulo in (
            ("data_celebracao", "data de celebração"),
            ("tipo_objeto", "tipo de objeto"),
            ("natureza_duracao", "natureza da duração"),
        ) if getattr(c, campo) is None
    ]
    if faltam:
        raise ContratoError(
            "Para assinar, informe: " + ", ".join(faltam) + ".",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if len(c.numero) > NUMERO_SIM_MAX:
        raise ContratoError(
            f"O número do contrato vai ao SIM do TCE-CE com até {NUMERO_SIM_MAX} "
            f"caracteres; '{c.numero}' tem {len(c.numero)}.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    exercicio = c.data_celebracao.year
    await _numero_livre(
        db, tenant_id=tenant_id, exercicio=exercicio, numero=c.numero, ignorar_contrato=c.id)
    c.exercicio = exercicio
    c.situacao = VIGENTE
    c.atualizado_em = _utcnow()
    await _gravar(db, c)
    return c


async def encerrar(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                   data_encerramento: date) -> Contrato:
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, VIGENTE, "encerrar")
    _validar_data_fim(c, data_encerramento)
    c.situacao = ENCERRADO
    c.data_encerramento = data_encerramento
    c.atualizado_em = _utcnow()
    await _gravar(db, c)
    return c


async def rescindir(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                    data_encerramento: date, motivo: str) -> Contrato:
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, VIGENTE, "rescindir")
    _validar_data_fim(c, data_encerramento)
    c.situacao = RESCINDIDO
    c.data_encerramento = data_encerramento
    c.motivo_rescisao = motivo
    c.atualizado_em = _utcnow()
    await _gravar(db, c)
    return c


def _validar_data_fim(c: Contrato, data_encerramento: date) -> None:
    if data_encerramento < c.vigencia_inicio:
        raise ContratoError(
            "A data de encerramento não pode ser anterior ao início da vigência.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


# ============================ aditivo ==========================================

def validar_combinacao_aditivo(tipo: str, valor: Decimal, nova_vigencia_fim: date | None) -> None:
    """A tabela do §2.2 do spec — a mesma dos CHECKs da migration 0133.

    Validar aqui dá mensagem que o usuário entende; o CHECK do banco é a
    última linha, para o que não passar por este service.
    """
    if tipo == "AP":
        if valor != 0:
            raise ContratoError(
                "Aditivo só de prazo vai com valor zero.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    elif valor <= 0:
        raise ContratoError(
            "Informe o valor do aditivo: a diferença, sempre positiva — inclusive em redução.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if tipo in TIPOS_COM_PRAZO and nova_vigencia_fim is None:
        raise ContratoError(
            "Este tipo de aditivo altera o prazo: informe a nova data final da vigência.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if tipo not in TIPOS_COM_PRAZO and nova_vigencia_fim is not None:
        raise ContratoError(
            "Aditivo só de valor não altera a vigência — use um tipo com prazo.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _obter_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                         aditivo_id: int) -> ContratoAditivo:
    a = (await db.execute(select(ContratoAditivo).where(
        ContratoAditivo.id == aditivo_id, ContratoAditivo.id_contrato == contrato_id,
        ContratoAditivo.tenant_id == tenant_id,
        ContratoAditivo.excluido.is_(False)))).scalar_one_or_none()
    if a is None:
        raise _nao_encontrado("Aditivo")
    return a


async def _proximo_sequencial(db: AsyncSession, modelo, *, tenant_id: int, contrato_id: int) -> int:
    atual = (await db.execute(select(func.max(modelo.sequencial)).where(
        modelo.tenant_id == tenant_id, modelo.id_contrato == contrato_id,
        modelo.excluido.is_(False)))).scalar_one_or_none()
    return (atual or 0) + 1


async def criar_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int, usuario_id: int,
                        payload: AditivoCreate) -> ContratoAditivo:
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, VIGENTE, "aditar")
    validar_combinacao_aditivo(payload.tipo, payload.valor, payload.nova_vigencia_fim)
    exercicio = payload.data_assinatura.year
    await _numero_livre(db, tenant_id=tenant_id, exercicio=exercicio, numero=payload.numero)
    a = ContratoAditivo(
        tenant_id=tenant_id, id_contrato=c.id, criado_em=_utcnow(), situacao=RASCUNHO,
        exercicio=exercicio, id_usuario_registro=usuario_id,
        sequencial=await _proximo_sequencial(
            db, ContratoAditivo, tenant_id=tenant_id, contrato_id=c.id),
        **payload.model_dump())
    db.add(a)
    await _gravar(db, a)
    return a


async def atualizar_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                            aditivo_id: int, payload: AditivoUpdate) -> ContratoAditivo:
    await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    a = await _obter_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id)
    if a.situacao != RASCUNHO:
        raise ContratoError(
            "Aditivo assinado não se edita. Anule e registre outro.", status.HTTP_409_CONFLICT)
    dados = payload.model_dump(exclude_unset=True)
    tipo = dados.get("tipo", a.tipo)
    valor = dados.get("valor", a.valor)
    nova = dados.get("nova_vigencia_fim", a.nova_vigencia_fim)
    validar_combinacao_aditivo(tipo, Decimal(valor), nova)
    exercicio = dados.get("data_assinatura", a.data_assinatura).year
    numero = dados.get("numero", a.numero)
    if exercicio != a.exercicio or numero != a.numero:
        await _numero_livre(
            db, tenant_id=tenant_id, exercicio=exercicio, numero=numero, ignorar_aditivo=a.id)
    for k, v in dados.items():
        setattr(a, k, v)
    a.exercicio = exercicio
    a.atualizado_em = _utcnow()
    await _gravar(db, a)
    return a


async def excluir_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                          aditivo_id: int) -> None:
    await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    a = await _obter_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id)
    if a.situacao != RASCUNHO:
        raise ContratoError(
            "Só aditivo em rascunho pode ser excluído. Assinado, anule.",
            status.HTTP_409_CONFLICT)
    a.excluido = True
    a.atualizado_em = _utcnow()
    await _gravar(db)


async def assinar_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                          aditivo_id: int, hoje: date | None = None) -> ContratoAditivo:
    """RASCUNHO → VIGENTE. Aqui o aditivo passa a contar no valor e na vigência,
    então é aqui que a nova data e o limite do art. 125 são conferidos."""
    hoje = hoje or date.today()
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, VIGENTE, "assinar aditivo")
    a = await _obter_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id)
    if a.situacao != RASCUNHO:
        raise ContratoError(f"O aditivo já está {a.situacao}.", status.HTTP_409_CONFLICT)

    aditivos, apostilas = await _atos(db, tenant_id=tenant_id, contrato_ids=[c.id])
    antes = calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje)

    if a.nova_vigencia_fim is not None and a.nova_vigencia_fim <= antes.vigencia_fim_atual:
        raise ContratoError(
            "A nova data final tem de ser posterior à vigência atual do contrato "
            f"({antes.vigencia_fim_atual.isoformat()}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if a.tipo in TIPOS_SUPRESSAO and Decimal(a.valor) >= antes.valor_atualizado:
        raise ContratoError(
            "A redução não pode zerar nem ultrapassar o valor atual do contrato.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Simula o contrato COM este aditivo: o limite é do acumulado, não do ato.
    a.situacao = VIGENTE
    depois = calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje)
    if depois.acima_do_limite and not (a.justificativa or "").strip():
        a.situacao = RASCUNHO
        raise ContratoError(
            f"Com este aditivo o contrato chega a {depois.percentual_acrescimo}% de acréscimo "
            f"e {depois.percentual_supressao}% de supressão, acima do limite do art. 125 da "
            f"Lei 14.133 ({depois.limite_acrescimo}% / {depois.limite_supressao}%). "
            "Registre a justificativa no aditivo para assinar.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    a.atualizado_em = _utcnow()
    await _gravar(db, a)
    return a


async def anular_aditivo(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                         aditivo_id: int, motivo: str) -> ContratoAditivo:
    await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    a = await _obter_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id)
    if a.situacao != VIGENTE:
        raise ContratoError(
            f"Só aditivo vigente pode ser anulado; este está {a.situacao}.",
            status.HTTP_409_CONFLICT)
    a.situacao = ANULADO
    a.motivo_anulacao = motivo
    a.atualizado_em = _utcnow()
    await _gravar(db, a)
    return a


# ============================ apostila =========================================

async def criar_apostila(db: AsyncSession, *, tenant_id: int, contrato_id: int, usuario_id: int,
                         payload: ApostilaCreate, hoje: date | None = None) -> ContratoApostila:
    hoje = hoje or date.today()
    c = await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    _exigir_situacao(c, VIGENTE, "apostilar")
    com_valor = payload.tipo in TIPOS_APOSTILA_COM_VALOR
    if com_valor and payload.valor_delta is None:
        raise ContratoError(
            "Reajuste e repactuação exigem o valor da variação.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if not com_valor and payload.valor_delta is not None:
        raise ContratoError(
            "Só reajuste e repactuação alteram valor. Mudança de valor do objeto é aditivo.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if com_valor:
        aditivos, apostilas = await _atos(db, tenant_id=tenant_id, contrato_ids=[c.id])
        base = calcular(c, aditivos[c.id], apostilas[c.id], hoje=hoje).valor_inicial_atualizado
        if base + Decimal(payload.valor_delta) <= 0:
            raise ContratoError(
                "A variação não pode zerar nem negativar o valor do contrato.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    p = ContratoApostila(
        tenant_id=tenant_id, id_contrato=c.id, criado_em=_utcnow(),
        id_usuario_registro=usuario_id,
        sequencial=await _proximo_sequencial(
            db, ContratoApostila, tenant_id=tenant_id, contrato_id=c.id),
        **payload.model_dump())
    db.add(p)
    await _gravar(db, p)
    return p


async def excluir_apostila(db: AsyncSession, *, tenant_id: int, contrato_id: int,
                           apostila_id: int) -> None:
    await obter(db, tenant_id=tenant_id, contrato_id=contrato_id)
    p = (await db.execute(select(ContratoApostila).where(
        ContratoApostila.id == apostila_id, ContratoApostila.id_contrato == contrato_id,
        ContratoApostila.tenant_id == tenant_id,
        ContratoApostila.excluido.is_(False)))).scalar_one_or_none()
    if p is None:
        raise _nao_encontrado("Apostila")
    p.excluido = True
    p.atualizado_em = _utcnow()
    await _gravar(db)

