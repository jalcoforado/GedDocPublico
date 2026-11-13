"""Endpoints de relatórios.

Cada relatório sai em JSON (para a tela), CSV e PDF, com os mesmos filtros na
query string. O recorte comum (unidade, assunto, tipo, serviço, período) é uma
dependência só (`recorte_comum`): os relatórios não podem divergir no que
"filtro de serviço" ou "período" quer dizer.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Servico, Usuario
from ..schemas.relatorio import (
    FiltroOrigem,
    FiltroSigilo,
    ModoUnidade,
    RelatorioFiltro,
    RelatorioResposta,
    Situacao,
    StatusPrazoRelatorio,
)
from ..schemas.relatorio_assinaturas import (
    AssinaturasFiltro,
    RelatorioAssinaturasResposta,
    StatusSolicitacao,
)
from ..schemas.relatorio_documentacao import RelatorioDocumentacaoResposta, VisaoDocumentacao
from ..schemas.relatorio_gerencial import GerencialResposta
from ..schemas.relatorio_montado import (
    CatalogoMontado,
    DefinicaoMontado,
    RelatorioSalvoAtualizar,
    RelatorioSalvoCriar,
    RelatorioSalvoOut,
    RelatorioSalvoResumo,
    ResultadoMontado,
)
from ..schemas.relatorio_tramitacao import RelatorioTramitacaoResposta
from ..services.pdf_relatorio import gerar_relatorio_pdf
from ..services.pdf_relatorio_assinaturas import gerar_assinaturas_pdf
from ..services.pdf_relatorio_gerencial import gerar_gerencial_pdf
from ..services.pdf_relatorio_tramitacao import gerar_tramitacao_pdf
from ..services.relatorios import gerar_relatorio
from ..services.relatorios_assinaturas import gerar_assinaturas
from ..services.relatorios_comum import ROTULO_SITUACAO
from ..services.pdf_relatorio_documentacao import gerar_documentacao_pdf
from ..services.relatorios_documentacao import (
    ROTULO_COMPLEMENTACAO,
    ROTULO_STATUS_DOC,
    gerar_documentacao,
)
from ..services import relatorios_salvos
from ..services.pdf_relatorio_montado import formatar_valor, gerar_montado_pdf
from ..services.relatorios_gerencial import gerar_gerencial
from ..services.relatorios_montado import catalogo as catalogo_montado
from ..services.relatorios_montado import executar_montado
from ..services.relatorios_tramitacao import RecorteGrandeDemais, gerar_tramitacao
from ..services.sigilo import niveis_acesso_usuario

router = APIRouter(prefix="/relatorios", tags=["relatorios"])

ACESSO = [Depends(require_modulo("protocolo")), Depends(require_permission("processo"))]

# Por qual data o período conta, por relatório (SI-34). O schema aceita as
# três; cada rota estreita para as que fazem sentido nela.
DataBaseProcessos = Literal["abertura", "arquivamento"]
DataBaseTramitacao = Literal["abertura", "chegada"]
CAMPOS_COMUNS = {
    "id_unidade", "modo_unidade", "id_assunto", "id_tipo_processo", "id_servico", "desde", "ate",
}


def recorte_comum(
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    id_servico: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
) -> RelatorioFiltro:
    if desde and ate and desde > ate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A data inicial do período é posterior à final.",
        )
    return RelatorioFiltro(
        id_unidade=id_unidade,
        modo_unidade=modo_unidade,
        id_assunto=id_assunto,
        id_tipo_processo=id_tipo_processo,
        id_servico=id_servico,
        desde=desde,
        ate=ate,
    )


def filtro_processos(
    rc: RelatorioFiltro = Depends(recorte_comum),
    data_base: DataBaseProcessos = "abertura",
    situacao: Situacao | None = None,
    parado_ha_dias: int | None = Query(None, ge=1, le=3650),
    prazo: StatusPrazoRelatorio | None = None,
    sigilo: FiltroSigilo | None = None,
    origem: FiltroOrigem | None = None,
) -> RelatorioFiltro:
    return rc.model_copy(update={
        "data_base": data_base, "situacao": situacao, "parado_ha_dias": parado_ha_dias,
        "prazo": prazo, "sigilo": sigilo, "origem": origem,
    })


def filtro_tramitacao(
    rc: RelatorioFiltro = Depends(recorte_comum),
    data_base: DataBaseTramitacao = "abertura",
    com_atraso: bool = False,
) -> RelatorioFiltro:
    return rc.model_copy(update={"data_base": data_base, "com_atraso": com_atraso})


def filtro_assinaturas(
    rc: RelatorioFiltro = Depends(recorte_comum),
    data_base: Literal["pedido", "conclusao"] = "pedido",
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
) -> AssinaturasFiltro:
    return AssinaturasFiltro(
        **rc.model_dump(include=CAMPOS_COMUNS),
        data_base=data_base,
        id_solicitante=id_solicitante,
        id_assinante=id_assinante,
        status=status,
    )


def _exige_completo(cortado: bool, total: int, teto: int, formato: str) -> None:
    """Exportação não corta em silêncio: acima do teto, recusa e diz por quê.

    Um CSV com 10 mil linhas de um recorte de 12 mil parece o recorte inteiro
    — quem soma a planilha erra sem saber.
    """
    if cortado:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"O recorte tem {total} processos e o {formato} vai até {teto}. "
                "Diminua o período ou filtre por unidade, tipo, assunto ou serviço."
            ),
        )


def _cabecalho_csv(w, descricao: list[str]) -> None:
    """O recorte no topo do CSV, como na tela e no PDF, e uma linha em branco."""
    for linha in descricao:
        w.writerow([linha])
    w.writerow([])


def _csv(buf: StringIO, nome: str) -> Response:
    fname = f"{nome}-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _pdf(conteudo: bytes, nome: str, inline: bool) -> Response:
    fname = f"{nome}-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


def _novo_csv() -> tuple[StringIO, "csv._writer"]:
    buf = StringIO()
    buf.write("﻿")
    return buf, csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)


# ---------- Processos ----------


@router.get("/processos.json", response_model=RelatorioResposta, dependencies=ACESSO)
async def relatorio_json(
    f: RelatorioFiltro = Depends(filtro_processos),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(1000, ge=1, le=10000),
) -> RelatorioResposta:
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )


@router.get("/processos.csv", dependencies=ACESSO)
async def relatorio_csv(
    f: RelatorioFiltro = Depends(filtro_processos),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(50000, ge=1, le=50000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )

    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")

    buf, w = _novo_csv()
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow(
        [
            "id",
            "numero_processo",
            "data_hora_abertura",
            "data_hora_arquivamento",
            "situacao",
            "manifestante",
            "tipo_processo",
            "assunto",
            "unidade_proprietaria",
            "local_atual",
            "publico",
            "externo",
        ]
    )
    for p in r.processos:
        w.writerow(
            [
                p.id,
                p.numero_processo,
                p.data_hora_abertura.strftime("%Y-%m-%d %H:%M:%S"),
                p.data_hora_arquivamento.strftime("%Y-%m-%d %H:%M:%S")
                if p.data_hora_arquivamento
                else "",
                ROTULO_SITUACAO[p.situacao],
                p.manifestante or "",
                p.tipo_processo or "",
                p.assunto or "",
                p.unidade_proprietaria or "",
                p.local_atual or "",
                "1" if p.publico else "0",
                "1" if p.externo else "0",
            ]
        )
    return _csv(buf, "relatorio-processos")


@router.get("/processos.pdf", dependencies=ACESSO)
async def relatorio_pdf(
    f: RelatorioFiltro = Depends(filtro_processos),
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(1000, ge=1, le=5000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    return _pdf(gerar_relatorio_pdf(r), "relatorio-processos", inline)


# ---------- Página gerencial (SI-34) ----------


async def _gerencial(db, user, tenant_id, f: RelatorioFiltro, dias_parado: int) -> GerencialResposta:
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_gerencial(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, dias_parado=dias_parado
    )


@router.get("/gerencial.json", response_model=GerencialResposta, dependencies=ACESSO)
async def gerencial_json(
    f: RelatorioFiltro = Depends(recorte_comum),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    dias_parado: int = Query(15, ge=1, le=3650),
) -> GerencialResposta:
    return await _gerencial(db, user, tenant_id, f, dias_parado)


@router.get("/gerencial.pdf", dependencies=ACESSO)
async def gerencial_pdf(
    f: RelatorioFiltro = Depends(recorte_comum),
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    dias_parado: int = Query(15, ge=1, le=3650),
):
    r = await _gerencial(db, user, tenant_id, f, dias_parado)
    return _pdf(gerar_gerencial_pdf(r), "relatorio-gerencial", inline)


# ---------- Tramitação ----------


async def _tramitacao(db, user, tenant_id, f: RelatorioFiltro, max_processos: int):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    try:
        return await gerar_tramitacao(
            db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_processos=max_processos
        )
    except RecorteGrandeDemais as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.get("/tramitacao.json", response_model=RelatorioTramitacaoResposta, dependencies=ACESSO)
async def tramitacao_json(
    f: RelatorioFiltro = Depends(filtro_tramitacao),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_processos: int = Query(200, ge=1, le=2000),
) -> RelatorioTramitacaoResposta:
    return await _tramitacao(db, user, tenant_id, f, max_processos)


@router.get("/tramitacao.csv", dependencies=ACESSO)
async def tramitacao_csv(
    f: RelatorioFiltro = Depends(filtro_tramitacao),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_processos: int = Query(10000, ge=1, le=10000),
):
    r = await _tramitacao(db, user, tenant_id, f, max_processos)

    _exige_completo(r.cortado, r.qtd_processos, max_processos, "CSV")

    buf, w = _novo_csv()
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow(
        [
            "id_processo",
            "numero_processo",
            "data_hora_abertura",
            "manifestante",
            "assunto",
            "local_atual",
            "qtd_encaminhamentos",
            "qtd_unidades_visitadas",
            "minutos_total",
            "minutos_em_andamento",
            "teve_atraso",
            "qtd_atrasos",
            "etapa_unidade",
            "etapa_chegou_em",
            "etapa_saiu_em",
            "etapa_minutos_no_local",
            "etapa_prazo",
            "etapa_atrasou",
        ]
    )
    for p in r.processos:
        comum = [
            p.id,
            p.numero_processo,
            p.data_hora_abertura.strftime("%Y-%m-%d %H:%M"),
            p.manifestante or "",
            p.assunto or "",
            p.local_atual or "",
            p.qtd_encaminhamentos,
            p.qtd_unidades_visitadas,
            p.minutos_total,
            p.minutos_em_andamento,
            "1" if p.teve_atraso else "0",
            p.qtd_atrasos,
        ]
        if not p.etapas:
            w.writerow(comum + ["", "", "", "", "", ""])
        for e in p.etapas:
            w.writerow(
                comum
                + [
                    e.unidade or "",
                    e.chegou_em.strftime("%Y-%m-%d %H:%M") if e.chegou_em else "",
                    e.saiu_em.strftime("%Y-%m-%d %H:%M") if e.saiu_em else "",
                    e.minutos_no_local if e.minutos_no_local is not None else "",
                    e.prazo_estipulado.strftime("%Y-%m-%d") if e.prazo_estipulado else "",
                    "1" if e.atrasou else "0",
                ]
            )
    return _csv(buf, "tramitacao")


@router.get("/tramitacao.pdf", dependencies=ACESSO)
async def tramitacao_pdf(
    f: RelatorioFiltro = Depends(filtro_tramitacao),
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_processos: int = Query(200, ge=1, le=1000),
):
    r = await _tramitacao(db, user, tenant_id, f, max_processos)
    return _pdf(gerar_tramitacao_pdf(r), "tramitacao", inline)


# ---------- Assinaturas ----------


@router.get("/assinaturas.json", response_model=RelatorioAssinaturasResposta, dependencies=ACESSO)
async def assinaturas_json(
    f: AssinaturasFiltro = Depends(filtro_assinaturas),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(500, ge=1, le=5000),
) -> RelatorioAssinaturasResposta:
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )


@router.get("/assinaturas.csv", dependencies=ACESSO)
async def assinaturas_csv(
    f: AssinaturasFiltro = Depends(filtro_assinaturas),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(50000, ge=1, le=50000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )

    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")

    buf, w = _novo_csv()
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow(
        [
            "id_solicitacao",
            "id_processo",
            "numero_processo",
            "solicitante",
            "status",
            "iniciada_em",
            "concluida_em",
            "minutos_decorridos",
            "qtd_assinantes",
            "qtd_assinantes_concluidos",
            "qtd_anexos",
            "qtd_anexos_assinados",
            "assinantes",
        ]
    )
    for s in r.solicitacoes:
        w.writerow(
            [
                s.id,
                s.id_processo,
                s.numero_processo or "",
                s.nome_solicitante or "",
                {"pendente": "Pendente", "concluida": "Concluída", "cancelada": "Cancelada"}[s.status],
                s.dt_inicio.strftime("%Y-%m-%d %H:%M"),
                s.dt_fim.strftime("%Y-%m-%d %H:%M") if s.dt_fim else "",
                s.minutos_decorridos if s.minutos_decorridos is not None else "",
                s.qtd_assinantes,
                s.qtd_assinantes_concluidos,
                s.qtd_anexos,
                s.qtd_anexos_assinados,
                " · ".join(s.assinantes_resumo),
            ]
        )
    return _csv(buf, "assinaturas")


@router.get("/assinaturas.pdf", dependencies=ACESSO)
async def assinaturas_pdf(
    f: AssinaturasFiltro = Depends(filtro_assinaturas),
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(500, ge=1, le=5000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    return _pdf(gerar_assinaturas_pdf(r), "assinaturas", inline)


# ---------- Opções do filtro de serviço ----------


class ServicoOpcao(BaseModel):
    id: int
    nome: str
    ativo: bool


@router.get("/servicos.json", response_model=list[ServicoOpcao], dependencies=ACESSO)
async def servicos_do_filtro(
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[ServicoOpcao]:
    """Id e nome dos serviços, para o filtro dos relatórios.

    `GET /servicos` exige a transação `servico` (administrar o catálogo); quem
    só consulta relatórios tem `processo` e levaria 403 — o filtro ficaria
    vazio sem aviso. Inativos entram: processo antigo pode ser de um serviço
    que saiu do catálogo. Nome de serviço já é público no portal do cidadão.
    """
    rows = await db.execute(
        select(Servico.id, Servico.nome, Servico.ativo)
        .where(Servico.tenant_id == tenant_id, Servico.excluido.is_(False))
        .order_by(Servico.nome)
    )
    return [ServicoOpcao(id=i, nome=n, ativo=a) for i, n, a in rows.all()]


# ---------- Documentação (SI-34) ----------


@router.get(
    "/documentacao.json", response_model=RelatorioDocumentacaoResposta, dependencies=ACESSO
)
async def documentacao_json(
    f: RelatorioFiltro = Depends(recorte_comum),
    visao: VisaoDocumentacao = "documentos",
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(1000, ge=1, le=10000),
) -> RelatorioDocumentacaoResposta:
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_documentacao(
        db, f, visao, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )


@router.get("/documentacao.csv", dependencies=ACESSO)
async def documentacao_csv(
    f: RelatorioFiltro = Depends(recorte_comum),
    visao: VisaoDocumentacao = "documentos",
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(50000, ge=1, le=50000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_documentacao(
        db, f, visao, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")

    buf, w = _novo_csv()
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow([
        "id", "numero_processo", "data_hora_abertura", "servico", "documentos",
        "obrigatorios_enviados", "obrigatorios_total", "complementacao",
        "complementacao_pedida_em", "complementacao_respondida_em", "local_atual",
    ])
    for p in r.processos:
        w.writerow([
            p.id,
            p.numero_processo,
            p.data_hora_abertura.strftime("%Y-%m-%d %H:%M:%S"),
            p.servico or "",
            ROTULO_STATUS_DOC[p.status_documental],
            p.obrigatorios_enviados,
            p.obrigatorios_total,
            ROTULO_COMPLEMENTACAO.get(p.complementacao_status or "", ""),
            p.complementacao_pedida_em.strftime("%Y-%m-%d %H:%M") if p.complementacao_pedida_em else "",
            p.complementacao_respondida_em.strftime("%Y-%m-%d %H:%M")
            if p.complementacao_respondida_em else "",
            p.local_atual or "",
        ])
    return _csv(buf, "documentacao")


@router.get("/documentacao.pdf", dependencies=ACESSO)
async def documentacao_pdf(
    f: RelatorioFiltro = Depends(recorte_comum),
    visao: VisaoDocumentacao = "documentos",
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(1000, ge=1, le=5000),
):
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_documentacao(
        db, f, visao, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    return _pdf(gerar_documentacao_pdf(r), "documentacao", inline)


# ---------- Relatório montado pela própria pessoa (SI-35) ----------
#
# A definição (colunas, filtros, período, agrupamento, ordem) vai em JSON no
# parâmetro `d`, nas três saídas: assim o CSV e o PDF são links comuns, como
# nas outras listas, e a tela guarda o que está montando na URL. Schema
# fechado (`schemas/relatorio_montado.py`): coluna fora do catálogo é 422.


def definicao_da_query(d: str = Query(..., max_length=8000)) -> DefinicaoMontado:
    try:
        return DefinicaoMontado.model_validate_json(d)
    except ValidationError as e:
        msgs = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" if err["loc"] else err["msg"]
            for err in e.errors()
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Definição do relatório inválida — {msgs}",
        ) from e


async def _montado(db, user, tenant_id, d: DefinicaoMontado, max_rows: int) -> ResultadoMontado:
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    try:
        return await executar_montado(
            db, d, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
        )
    except RecorteGrandeDemais as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.get("/montado/catalogo.json", response_model=CatalogoMontado, dependencies=ACESSO)
async def montado_catalogo() -> CatalogoMontado:
    """As colunas, ordens e agrupamentos que o montador oferece."""
    return catalogo_montado()


@router.get("/montado.json", response_model=ResultadoMontado, dependencies=ACESSO)
async def montado_json(
    d: DefinicaoMontado = Depends(definicao_da_query),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(200, ge=1, le=1000),
) -> ResultadoMontado:
    return await _montado(db, user, tenant_id, d, max_rows)


@router.get("/montado.csv", dependencies=ACESSO)
async def montado_csv(
    d: DefinicaoMontado = Depends(definicao_da_query),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(50000, ge=1, le=50000),
):
    r = await _montado(db, user, tenant_id, d, max_rows)
    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")
    buf, w = _novo_csv()
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow(["Número", *(c.rotulo for c in r.colunas)])
    for ln in r.linhas:
        w.writerow([ln.numero_processo, *(formatar_valor(ln.valores.get(c.chave), c.tipo) for c in r.colunas)])
    return _csv(buf, "relatorio-montado")


@router.get("/montado.pdf", dependencies=ACESSO)
async def montado_pdf(
    d: DefinicaoMontado = Depends(definicao_da_query),
    nome: str | None = Query(None, max_length=120),
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    max_rows: int = Query(1000, ge=1, le=5000),
):
    r = await _montado(db, user, tenant_id, d, max_rows)
    return _pdf(gerar_montado_pdf(r, nome), "relatorio-montado", inline)


# Os salvos são da pessoa: toda rota passa o `user.id`, e o de outra pessoa
# responde 404 (`services/relatorios_salvos.py`).


@router.get("/salvos", response_model=list[RelatorioSalvoResumo], dependencies=ACESSO)
async def salvos_listar(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[RelatorioSalvoResumo]:
    return await relatorios_salvos.listar(db, tenant_id=tenant_id, id_usuario=user.id)


@router.post(
    "/salvos", response_model=RelatorioSalvoOut, status_code=status.HTTP_201_CREATED,
    dependencies=ACESSO,
)
async def salvos_criar(
    dados: RelatorioSalvoCriar,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RelatorioSalvoOut:
    return await relatorios_salvos.criar(db, dados, tenant_id=tenant_id, id_usuario=user.id)


@router.get("/salvos/{id_salvo}", response_model=RelatorioSalvoOut, dependencies=ACESSO)
async def salvos_obter(
    id_salvo: int,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RelatorioSalvoOut:
    return await relatorios_salvos.obter(db, id_salvo, tenant_id=tenant_id, id_usuario=user.id)


@router.put("/salvos/{id_salvo}", response_model=RelatorioSalvoOut, dependencies=ACESSO)
async def salvos_atualizar(
    id_salvo: int,
    dados: RelatorioSalvoAtualizar,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> RelatorioSalvoOut:
    return await relatorios_salvos.atualizar(
        db, id_salvo, dados, tenant_id=tenant_id, id_usuario=user.id
    )


@router.delete("/salvos/{id_salvo}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ACESSO)
async def salvos_excluir(
    id_salvo: int,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await relatorios_salvos.excluir(db, id_salvo, tenant_id=tenant_id, id_usuario=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
