"""Conciliação bancária (Onda B / Fase 3 — RF-EXT-01..10, RN-11/RN-14).

Importa extratos (CSV), sugere baixas casando lançamentos de DÉBITO do extrato
com as movimentações de PAGAMENTO da MESMA conta (RN-11), classifica a
correspondência (EXATA/PROVÁVEL) e concilia — atualizando o saldo conciliado e
levando o débito a CONCILIADO quando todos os pagamentos batem no extrato.
"""
from __future__ import annotations

import dataclasses
import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Conciliacao, ContaBancaria, Debito, Extrato, LancamentoExtrato, MovimentacaoConta, Parcela,
)
from ..schemas.pagamentos import ImportarExtratoIn, SugestaoBaixaOut
from . import pagamentos_estados as est
from .pagamentos_extrato_parsers import Cnab240ParseError, OfxParseError, parse_cnab240, parse_ofx

_PROVAVEL_DIAS = 3  # tolerância de data para correspondência provável


@dataclasses.dataclass
class ResultadoImport:
    """Relato explícito da importação (C2.2). Substitui os atributos
    não-persistidos que antes pendurávamos no `Extrato` (`_total_no_arquivo`
    etc.) — aquele padrão exigia que quem lesse soubesse que o objeto
    devolvido carregava campos fora do mapeamento ORM; aqui o contrato é
    o tipo. `ignorados_por_id_externo` só se aplica a OFX (FIX WAVE: CNAB240
    deixou de preencher `id_externo` — ver docstring de `parse_cnab240`,
    ruling do review final de C2, Important 1; nº de documento CNAB recicla e
    colidia com FITID) — linha cujo `(id_conta, id_externo)` já existe é
    pulada. CNAB240 sobreposto se comporta como o CSV: só o hash do arquivo
    inteiro protege contra reimportação do MESMO arquivo (409).
    `possiveis_duplicatas` é um AVISO (mesma data/valor/tipo já existentes na
    conta) e NÃO pula nada — pular por esses campos esconderia lançamento
    real (dois pagamentos iguais no mesmo dia são legítimos)."""
    extrato: Extrato
    total_no_arquivo: int
    importados: int
    ignorados_por_id_externo: int
    possiveis_duplicatas: int


def _utcnow() -> datetime:
    return datetime.utcnow()


class ConciliacaoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


async def _obter_conta(db: AsyncSession, *, tenant_id: int, conta_id: int) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise ConciliacaoError("Conta não encontrada", status.HTTP_404_NOT_FOUND)
    return c


def _parse_data(v: str) -> date:
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ConciliacaoError(f"Data inválida no extrato: '{v}'", status.HTTP_422_UNPROCESSABLE_ENTITY)


def _parse_valor(v: str) -> Decimal:
    s = v.strip().replace("R$", "").replace(" ", "")
    # aceita 1.234,56 (pt-BR) ou 1234.56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ConciliacaoError(f"Valor inválido no extrato: '{v}'", status.HTTP_422_UNPROCESSABLE_ENTITY)


def _parse_csv(conteudo: str) -> list[dict]:
    """Colunas: data;historico;documento;favorecido;valor;tipo. Separador ; ou ,.
    Cabeçalho opcional (detectado se a 1ª linha contém 'data')."""
    linhas = [ln for ln in conteudo.splitlines() if ln.strip()]
    if not linhas:
        raise ConciliacaoError("Extrato vazio", status.HTTP_422_UNPROCESSABLE_ENTITY)
    sep = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    if "data" in linhas[0].lower() and "valor" in linhas[0].lower():
        linhas = linhas[1:]
    out: list[dict] = []
    for ln in linhas:
        cols = [c.strip() for c in ln.split(sep)]
        if len(cols) < 6:
            raise ConciliacaoError(
                f"Linha com menos de 6 colunas: '{ln}'", status.HTTP_422_UNPROCESSABLE_ENTITY)
        tipo = cols[5].strip().upper()
        if tipo not in ("CREDITO", "DEBITO", "CRÉDITO", "DÉBITO"):
            raise ConciliacaoError(
                f"Tipo inválido (use CREDITO/DEBITO): '{cols[5]}'", status.HTTP_422_UNPROCESSABLE_ENTITY)
        tipo = "CREDITO" if tipo.startswith("CR") else "DEBITO"
        out.append(dict(
            data=_parse_data(cols[0]), historico=cols[1][:255], documento=(cols[2] or None),
            favorecido=(cols[3] or None), valor=_parse_valor(cols[4]), tipo=tipo))
    return out


def _linhas_ofx(conteudo: str) -> list[dict]:
    try:
        parseados = parse_ofx(conteudo)
    except OfxParseError as e:
        raise ConciliacaoError(str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)
    return [dataclasses.asdict(p) for p in parseados]


def _linhas_cnab240(conteudo: str) -> list[dict]:
    try:
        parseados = parse_cnab240(conteudo)
    except Cnab240ParseError as e:
        raise ConciliacaoError(str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)
    return [dataclasses.asdict(p) for p in parseados]


async def importar_extrato(db: AsyncSession, *, tenant_id: int, usuario_id: int | None,
                           payload: ImportarExtratoIn) -> ResultadoImport:
    """Importa o extrato, preservando arquivo/hash (RF-EXT-10) e criando os
    lançamentos. Idempotente por (conta, hash) — reimportar o mesmo arquivo
    inteiro 409 (RN da C1).

    C2.2: dedupe POR LANÇAMENTO quando o formato dá id (`FITID` do OFX) —
    linha cujo `(id_conta, id_externo)` já existe é pulada e contada em
    `ignorados_por_id_externo`. Linha sem id_externo (CSV) segue como
    antes: só o hash do arquivo protege, porque pular por (data, valor)
    esconderia lançamento real (dois pagamentos iguais no mesmo dia são
    legítimos) — por isso o relato só AVISA em `possiveis_duplicatas`,
    sem pular.

    Devolve `ResultadoImport` (dataclass) com o `Extrato` persistido mais o
    relato — nada pendurado em atributo não-mapeado do ORM."""
    await _obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
    if payload.formato == "CSV":
        linhas = _parse_csv(payload.conteudo)
        for ln in linhas:
            ln.setdefault("id_externo", None)
    elif payload.formato == "OFX":
        linhas = _linhas_ofx(payload.conteudo)
    elif payload.formato == "CNAB240":
        linhas = _linhas_cnab240(payload.conteudo)
    else:
        raise ConciliacaoError(
            f"Formato {payload.formato} ainda não suportado (use CSV, OFX ou CNAB240).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if not linhas:
        raise ConciliacaoError("Extrato vazio", status.HTTP_422_UNPROCESSABLE_ENTITY)
    h = hashlib.sha256(payload.conteudo.encode("utf-8")).hexdigest()
    dup = (await db.execute(select(Extrato.id).where(
        Extrato.tenant_id == tenant_id, Extrato.id_conta == payload.id_conta,
        Extrato.hash == h))).scalar_one_or_none()
    if dup is not None:
        raise ConciliacaoError(
            f"Extrato já importado para esta conta (extrato {dup}).", status.HTTP_409_CONFLICT)
    total_no_arquivo = len(linhas)
    datas = [ln["data"] for ln in linhas]
    ex = Extrato(tenant_id=tenant_id, id_conta=payload.id_conta, nome_arquivo=payload.nome_arquivo,
                 hash=h, formato=payload.formato, status_processamento="PROCESSADO",
                 qtd_lancamentos=0, periodo_inicio=min(datas), periodo_fim=max(datas),
                 id_usuario=usuario_id, importado_em=_utcnow())
    db.add(ex); await db.flush()

    ids_existentes = set((await db.execute(select(LancamentoExtrato.id_externo).where(
        LancamentoExtrato.tenant_id == tenant_id, LancamentoExtrato.id_conta == payload.id_conta,
        LancamentoExtrato.id_externo.isnot(None)))).scalars().all())
    tuplas_existentes = set((await db.execute(select(
        LancamentoExtrato.data, LancamentoExtrato.valor, LancamentoExtrato.tipo).where(
        LancamentoExtrato.tenant_id == tenant_id,
        LancamentoExtrato.id_conta == payload.id_conta))).all())

    importados = 0
    ignorados_por_id_externo = 0
    possiveis_duplicatas = 0
    for ln in linhas:
        id_ext = ln.get("id_externo")
        if id_ext is not None and id_ext in ids_existentes:
            ignorados_por_id_externo += 1
            continue
        if (ln["data"], ln["valor"], ln["tipo"]) in tuplas_existentes:
            possiveis_duplicatas += 1
        db.add(LancamentoExtrato(
            tenant_id=tenant_id, id_extrato=ex.id, id_conta=payload.id_conta,
            criado_em=_utcnow(), **ln))
        importados += 1
        if id_ext is not None:
            ids_existentes.add(id_ext)

    ex.qtd_lancamentos = importados
    await db.commit(); await db.refresh(ex)
    return ResultadoImport(
        extrato=ex, total_no_arquivo=total_no_arquivo, importados=importados,
        ignorados_por_id_externo=ignorados_por_id_externo,
        possiveis_duplicatas=possiveis_duplicatas)


async def listar_extratos(db: AsyncSession, *, tenant_id: int, id_conta: int | None = None) -> list[Extrato]:
    stmt = select(Extrato).where(Extrato.tenant_id == tenant_id, Extrato.excluido.is_(False))
    if id_conta is not None:
        stmt = stmt.where(Extrato.id_conta == id_conta)
    return list((await db.execute(stmt.order_by(Extrato.id.desc()))).scalars().all())


async def listar_lancamentos(db: AsyncSession, *, tenant_id: int, id_extrato: int) -> list[LancamentoExtrato]:
    return list((await db.execute(select(LancamentoExtrato).where(
        LancamentoExtrato.tenant_id == tenant_id, LancamentoExtrato.id_extrato == id_extrato)
        .order_by(LancamentoExtrato.data, LancamentoExtrato.id))).scalars().all())


async def _movs_disponiveis(db: AsyncSession, *, tenant_id: int, conta_id: int) -> list[MovimentacaoConta]:
    """Pagamentos (SAIDA/PAGAMENTO) da conta ainda NÃO conciliados (RN-14)."""
    conciliadas = select(Conciliacao.id_movimentacao).where(
        Conciliacao.tenant_id == tenant_id, Conciliacao.id_movimentacao.isnot(None))
    return list((await db.execute(select(MovimentacaoConta).where(
        MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
        MovimentacaoConta.tipo == "SAIDA", MovimentacaoConta.origem == "PAGAMENTO",
        MovimentacaoConta.excluido.is_(False), MovimentacaoConta.id.notin_(conciliadas))
        .order_by(MovimentacaoConta.data))).scalars().all())


async def sugerir_baixas(db: AsyncSession, *, tenant_id: int, id_extrato: int) -> list[SugestaoBaixaOut]:
    """Casa lançamentos de DÉBITO não conciliados do extrato com pagamentos da
    MESMA conta (RN-11). EXATA = mesmo valor e mesma data; PROVÁVEL = mesmo valor
    e data até 3 dias de diferença. Cada movimentação sugerida uma única vez."""
    ex = (await db.execute(select(Extrato).where(
        Extrato.id == id_extrato, Extrato.tenant_id == tenant_id))).scalar_one_or_none()
    if ex is None:
        raise ConciliacaoError("Extrato não encontrado", status.HTTP_404_NOT_FOUND)
    lancs = [l for l in await listar_lancamentos(db, tenant_id=tenant_id, id_extrato=id_extrato)
             if l.tipo == "DEBITO" and not l.conciliado]
    movs = await _movs_disponiveis(db, tenant_id=tenant_id, conta_id=ex.id_conta)

    # nomes de fornecedor por parcela (via débito) para exibir na sugestão
    parcela_ids = [m.id_parcela for m in movs if m.id_parcela]
    forn_por_mov: dict[int, tuple[int | None, int | None, str | None]] = {}
    if parcela_ids:
        rows = (await db.execute(
            select(Parcela.id, Debito.id, Parcela.id_debito, Debito.id_fornecedor)
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.id.in_(parcela_ids)))).all()
        pinfo = {r[0]: (r[1], r[3]) for r in rows}  # parcela -> (id_debito, id_fornecedor)
        from .pagamentos_debitos import nomes_fornecedores
        nomes = await nomes_fornecedores(
            db, tenant_id=tenant_id, ids={r[3] for r in rows})
        for m in movs:
            if m.id_parcela and m.id_parcela in pinfo:
                iddeb, idforn = pinfo[m.id_parcela]
                forn_por_mov[m.id] = (iddeb, m.id_parcela, nomes.get(idforn))

    usados: set[int] = set()
    sugestoes: list[SugestaoBaixaOut] = []
    for l in lancs:
        melhor: tuple[MovimentacaoConta, str] | None = None
        for m in movs:
            if m.id in usados or m.valor != l.valor:
                continue
            delta = abs((m.data - l.data).days)
            tipo = "EXATA" if delta == 0 else ("PROVAVEL" if delta <= _PROVAVEL_DIAS else None)
            if tipo is None:
                continue
            if melhor is None or (tipo == "EXATA" and melhor[1] != "EXATA"):
                melhor = (m, tipo)
        if melhor is not None:
            m, tipo = melhor
            usados.add(m.id)
            iddeb, idparc, nomef = forn_por_mov.get(m.id, (None, m.id_parcela, None))
            sugestoes.append(SugestaoBaixaOut(
                id_lancamento=l.id, lancamento_data=l.data, lancamento_historico=l.historico,
                lancamento_valor=l.valor, id_movimentacao=m.id, id_parcela=idparc, id_debito=iddeb,
                nome_fornecedor=nomef, movimentacao_data=m.data, movimentacao_valor=m.valor,
                tipo_correspondencia=tipo))
    return sugestoes


async def _talvez_conciliar_debito(db: AsyncSession, *, tenant_id: int, id_parcela: int,
                                   usuario_id: int | None) -> None:
    """Se o débito da parcela está PAGO e todas as movimentações de pagamento das
    suas parcelas estão conciliadas, leva o débito a CONCILIADO (RF-EXT-09)."""
    parc = (await db.execute(select(Parcela).where(
        Parcela.id == id_parcela, Parcela.tenant_id == tenant_id))).scalar_one_or_none()
    if parc is None:
        return
    from .pagamentos_debitos import ST_PAGO, _registrar_transicao, obter_debito
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=parc.id_debito, for_update=True)
    if d.status != ST_PAGO:
        return
    movs = (await db.execute(select(MovimentacaoConta.id).join(
        Parcela, Parcela.id_movimentacao == MovimentacaoConta.id).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito == d.id, Parcela.status == "PAGA",
        MovimentacaoConta.excluido.is_(False)))).scalars().all()
    if not movs:
        return
    conc = (await db.execute(select(func.count()).select_from(Conciliacao).where(
        Conciliacao.tenant_id == tenant_id, Conciliacao.id_movimentacao.in_(movs)))).scalar_one()
    if conc >= len(movs):
        _registrar_transicao(
            db, debito=d, acao="CONCILIADO", pagamento=est.CONCILIADA,
            usuario_id=usuario_id, justificativa="Pagamento conciliado no extrato")
        d.atualizado_em = _utcnow()


async def conciliar(db: AsyncSession, *, tenant_id: int, id_lancamento: int, id_movimentacao: int,
                    usuario_id: int | None, tipo: str = "PROVAVEL") -> Conciliacao:
    """Baixa manual/validada: liga o lançamento à movimentação (RF-EXT-07).
    RN-11: só na conta do extrato. RN-14: nem lançamento nem movimentação já conciliados."""
    l = (await db.execute(select(LancamentoExtrato).where(
        LancamentoExtrato.id == id_lancamento, LancamentoExtrato.tenant_id == tenant_id)
        .with_for_update())).scalar_one_or_none()
    if l is None:
        raise ConciliacaoError("Lançamento não encontrado", status.HTTP_404_NOT_FOUND)
    if l.conciliado:
        raise ConciliacaoError("Lançamento já conciliado (RN-14).", status.HTTP_409_CONFLICT)
    m = (await db.execute(select(MovimentacaoConta).where(
        MovimentacaoConta.id == id_movimentacao, MovimentacaoConta.tenant_id == tenant_id)
        .with_for_update())).scalar_one_or_none()
    if m is None:
        raise ConciliacaoError("Movimentação não encontrada", status.HTTP_404_NOT_FOUND)
    ex = (await db.execute(select(Extrato).where(Extrato.id == l.id_extrato))).scalar_one()
    if m.id_conta != ex.id_conta:  # RN-11 / RF-EXT-08
        raise ConciliacaoError(
            "A movimentação não pertence à conta do extrato (RN-11).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    ja = (await db.execute(select(Conciliacao.id).where(
        Conciliacao.tenant_id == tenant_id, Conciliacao.id_movimentacao == id_movimentacao))
        ).scalar_one_or_none()
    if ja is not None:
        raise ConciliacaoError("Movimentação já conciliada (RN-14).", status.HTTP_409_CONFLICT)
    c = Conciliacao(tenant_id=tenant_id, id_lancamento=l.id, id_movimentacao=m.id,
                    id_parcela=m.id_parcela, tipo_correspondencia=tipo, id_usuario=usuario_id,
                    criado_em=_utcnow())
    db.add(c); l.conciliado = True
    if m.id_parcela:
        await _talvez_conciliar_debito(db, tenant_id=tenant_id, id_parcela=m.id_parcela,
                                       usuario_id=usuario_id)
    await db.commit(); await db.refresh(c)
    return c


async def baixa_automatica(db: AsyncSession, *, tenant_id: int, id_extrato: int,
                           usuario_id: int | None) -> int:
    """Concilia automaticamente todas as correspondências EXATAS (RF-EXT-06).
    Retorna o número de baixas efetuadas."""
    n = 0
    for s in await sugerir_baixas(db, tenant_id=tenant_id, id_extrato=id_extrato):
        if s.tipo_correspondencia == "EXATA":
            await conciliar(db, tenant_id=tenant_id, id_lancamento=s.id_lancamento,
                            id_movimentacao=s.id_movimentacao, usuario_id=usuario_id, tipo="EXATA")
            n += 1
    return n
