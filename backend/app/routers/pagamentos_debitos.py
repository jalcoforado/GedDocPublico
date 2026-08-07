"""Rotas de Débitos/Autorização/Pagamento (R2). IP do cliente vai para o histórico."""
from __future__ import annotations

import html as _htmlmod

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_any_permission, require_permission
from ..database import get_db
from ..models import Usuario
from datetime import date

from pydantic import BaseModel, Field

from ..schemas.pagamentos import (
    AutorizarLoteIn, ContaElegivelOut, DashboardOut, DebitoCreate, DebitoDetalheOut,
    DebitoHistoricoOut, DebitoOut, DebitoUpdate, DecisaoIn, DecisaoJustificadaIn, FichaFonteOut,
    FilaAutorizacaoFonteGrupo, ChecklistDebitoItemOut, FilaLiberacaoGrupo, FilaTesourariaOut,
    JustificativaIn, LiquidacaoIn, MarcarChecklistIn, MinhaFilaOut, OrdemPagamentoOut,
    PagarParcelaIn, ParcelaFilaOut, ParcelaOut, SolicitarAjusteIn, SimulacaoAutorizacaoIn,
    SimulacaoAutorizacaoOut,
)
from ..services import pagamentos_autorizacao as aut
from ..services import pagamentos_caixa as caixa
from ..services import pagamentos_checklist as checklist
from ..services import pagamentos_dashboard as dash
from ..services import pagamentos_debitos as svc
from ..services import pagamentos_estados as est
from ..services import pagamentos_excecoes as excecoes
from ..services import pagamentos_export as export
from ..services import pagamentos_filas as filas
from ..services.html_pdf import html_to_pdf_bytes
from ..services.permissoes import load_permissions


class LiberarParcelasIn(BaseModel):
    parcela_ids: list[int] = Field(min_length=1)
    data_prevista: date | None = None

PERMS_LEITURA = ("pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
                 "pagamento_autorizar", "pagamento_pagar", "pagamento_auditar",
                 "pagamento_cadastro")

debitos_router = APIRouter(prefix="/pagamentos/debitos", tags=["pagamentos-debitos"])
operacoes_router = APIRouter(prefix="/pagamentos", tags=["pagamentos-operacoes"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _out(db, tenant_id: int, debitos) -> list[DebitoOut]:
    nomes = await svc.nomes_fornecedores(db, tenant_id=tenant_id,
                                         ids={d.id_fornecedor for d in debitos})
    return [DebitoOut.model_validate(svc.debito_out(d, nome_fornecedor=nomes.get(d.id_fornecedor, "?")))
            for d in debitos]


@debitos_router.get("", response_model=list[DebitoOut])
async def list_debitos(status_f: str | None = None, situacao_tramitacao: str | None = None,
                       meus: bool = False,
                       id_fonte: int | None = None, id_natureza: int | None = None,
                       id_fornecedor: int | None = None, id_contrato: int | None = None,
                       urgente: bool | None = None, competencia: str | None = None,
                       usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    rows = await svc.listar_debitos(
        db, tenant_id=tenant_id, status_f=status_f, tramitacao_f=situacao_tramitacao,
        solicitante_id=usuario.id if meus else None, id_fonte=id_fonte, id_natureza=id_natureza,
        id_fornecedor=id_fornecedor, id_contrato=id_contrato, urgente=urgente, competencia=competencia)
    return await _out(db, tenant_id, rows)


# Onda C (C1.1). Precisa vir ANTES de `/{debito_id}`: registrada depois, a rota
# dinâmica capturaria "exportar.csv" e devolveria 422 ao tentar convertê-la em int.
@debitos_router.get("/exportar.csv")
async def exportar_debitos_csv(status_f: str | None = None, meus: bool = False,
                               id_fonte: int | None = None, id_natureza: int | None = None,
                               id_fornecedor: int | None = None, id_contrato: int | None = None,
                               urgente: bool | None = None, competencia: str | None = None,
                               usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                               tenant_id: int = Depends(require_tenant_id),
                               db: AsyncSession = Depends(get_db)):
    """Exporta a lista de débitos no MESMO recorte da tela.

    Os filtros são idênticos aos de `GET /pagamentos/debitos` de propósito: o
    que o usuário vê é o que ele baixa. CSV `;` + BOM abre direto no Excel
    pt-BR (ver `services/pagamentos_export`).
    """
    filtros = dict(
        status_f=status_f, solicitante_id=usuario.id if meus else None,
        id_fonte=id_fonte, id_natureza=id_natureza, id_fornecedor=id_fornecedor,
        id_contrato=id_contrato, urgente=urgente, competencia=competencia,
    )
    conteudo = await export.csv_debitos(db, tenant_id=tenant_id, **filtros)
    nome = export.nome_arquivo_debitos(status_f=status_f, competencia=competencia)
    return Response(
        content=conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@debitos_router.get("/{debito_id}", response_model=DebitoDetalheOut)
async def get_debito(debito_id: int,
                     _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    d = await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    base = (await _out(db, tenant_id, [d]))[0].model_dump()
    parcelas = await svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=debito_id)
    hist = await svc.listar_historico(db, tenant_id=tenant_id, debito_id=debito_id)
    nomes_u = await svc.nomes_usuarios(db, tenant_id=tenant_id,
                                       ids={h.id_usuario for h in hist if h.id_usuario})
    base["parcelas"] = [ParcelaOut.model_validate(p) for p in parcelas]
    base["historico"] = [DebitoHistoricoOut(
        id=h.id, acao=h.acao, status_anterior=h.status_anterior, status_novo=h.status_novo,
        justificativa=h.justificativa, id_usuario=h.id_usuario,
        nome_usuario=nomes_u.get(h.id_usuario), criado_em=h.criado_em) for h in hist]
    return DebitoDetalheOut.model_validate(base)


@debitos_router.post("", response_model=DebitoOut, status_code=status.HTTP_201_CREATED)
async def create_debito(payload: DebitoCreate,
                        usuario: Usuario = Depends(require_permission("pagamento_solicitar", "inserir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    d = await svc.criar_debito(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.put("/{debito_id}", response_model=DebitoOut)
async def update_debito(debito_id: int, payload: DebitoUpdate,
                        usuario: Usuario = Depends(require_permission("pagamento_solicitar", "atualizar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    d = await svc.atualizar_debito(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, payload=payload)
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.delete("/{debito_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debito(debito_id: int,
                        _: Usuario = Depends(require_permission("pagamento_solicitar", "excluir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    await svc.excluir_debito(db, tenant_id=tenant_id, debito_id=debito_id)


# Endpoints antigos substituídos pelo novo fluxo (retornam 410 Gone)
@debitos_router.post("/{debito_id}/encaminhar", status_code=status.HTTP_410_GONE)
async def encaminhar_deprecated(debito_id: int):
    """Endpoint descontinuado. Use o novo fluxo de pagamentos: gestor-autorizar, validar, etc."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Este endpoint foi descontinuado. Use o novo fluxo de pagamentos."
    )


@debitos_router.post("/{debito_id}/devolver", status_code=status.HTTP_410_GONE)
async def devolver_deprecated(debito_id: int):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint descontinuado. Use solicitar-ajuste na etapa responsável.",
    )


@debitos_router.post("/{debito_id}/rejeitar", status_code=status.HTTP_410_GONE)
async def rejeitar_deprecated(debito_id: int):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=("Endpoint descontinuado. A validação financeira não pode rejeitar; "
                "use gestor-rejeitar ou autoridade-indeferir na etapa correspondente."),
    )


@debitos_router.post("/{debito_id}/cancelar", response_model=DebitoOut)
async def cancelar(debito_id: int, payload: DecisaoJustificadaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    d = await svc.cancelar(db, tenant_id=tenant_id, debito_id=debito_id, usuario_id=usuario.id,
                           lock_version=payload.lock_version, justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/confirmar-liquidacao", response_model=DebitoOut)
async def confirmar_liquidacao(debito_id: int, payload: LiquidacaoIn, request: Request,
                               usuario: Usuario = Depends(require_permission("pagamento_validar")),
                               tenant_id: int = Depends(require_tenant_id),
                               db: AsyncSession = Depends(get_db)):
    d = await svc.confirmar_liquidacao(db, tenant_id=tenant_id, debito_id=debito_id,
                                       usuario_id=usuario.id, data_liquidacao=payload.data_liquidacao,
                                       ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.get("/{debito_id}/checklist", response_model=list[ChecklistDebitoItemOut])
async def get_checklist(debito_id: int,
                        _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    return await checklist.checklist_do_debito(db, tenant_id=tenant_id, debito_id=debito_id)


@debitos_router.post("/{debito_id}/checklist", response_model=list[ChecklistDebitoItemOut])
async def marcar_checklist(debito_id: int, payload: MarcarChecklistIn,
                           usuario: Usuario = Depends(require_permission("pagamento_validar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    await checklist.marcar(db, tenant_id=tenant_id, debito_id=debito_id,
                           id_checklist_item=payload.id_checklist_item, marcado=payload.marcado,
                           observacao=payload.observacao, usuario_id=usuario.id)
    return await checklist.checklist_do_debito(db, tenant_id=tenant_id, debito_id=debito_id)


@debitos_router.post("/{debito_id}/suspender", status_code=status.HTTP_410_GONE)
async def suspender_deprecated(debito_id: int):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint descontinuado. Bloqueios passam a pertencer à ordem cronológica.",
    )


@debitos_router.post("/{debito_id}/reativar", status_code=status.HTTP_410_GONE)
async def reativar_deprecated(debito_id: int):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint descontinuado. Resolva o bloqueio na ordem cronológica.",
    )


# ===== Fluxo completo com etapas de gestor, validação e autoridade (F1, Tarefa 7) =====

# Endpoints do gestor (5 total)
@debitos_router.post("/{debito_id}/enviar-gestor", response_model=DebitoOut)
async def enviar_gestor(debito_id: int, payload: DecisaoIn, request: Request,
                        usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    """Unidade setorial envia solicitação ao gestor da pasta para juízo de mérito."""
    d = await svc.enviar_para_gestor(db, tenant_id=tenant_id, debito_id=debito_id,
                                     usuario_id=usuario.id, lock_version=payload.lock_version,
                                     ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/gestor-autorizar", response_model=DebitoOut)
async def gestor_autorizar(debito_id: int, payload: DecisaoIn, request: Request,
                           usuario: Usuario = Depends(require_permission("pagamento_gerir")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    """Gestor da pasta autoriza o mérito e a conveniência da despesa."""
    d = await svc.gestor_autorizar(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, lock_version=payload.lock_version,
                                   ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/gestor-rejeitar", response_model=DebitoOut)
async def gestor_rejeitar(debito_id: int, payload: DecisaoJustificadaIn, request: Request,
                          usuario: Usuario = Depends(require_permission("pagamento_gerir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    """Gestor rejeita a despesa por falta de mérito ou conveniência."""
    d = await svc.gestor_rejeitar(db, tenant_id=tenant_id, debito_id=debito_id,
                                  usuario_id=usuario.id, lock_version=payload.lock_version,
                                  justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/solicitar-ajuste", response_model=DebitoOut)
async def solicitar_ajuste(debito_id: int, payload: SolicitarAjusteIn, request: Request,
                           usuario: Usuario = Depends(require_any_permission(
                               "pagamento_gerir", "pagamento_validar", "pagamento_autorizar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    """Solicita ajuste na despesa a partir de qualquer etapa decisória."""
    codigo_por_etapa = {
        "GESTOR": "pagamento_gerir",
        "VALIDACAO": "pagamento_validar",
        "AUTORIDADE": "pagamento_autorizar",
    }
    codigo = codigo_por_etapa[payload.etapa]
    permissoes = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    autorizado = (
        codigo not in permissoes.codigos_bloqueados
        and (
            permissoes.is_super_usuario
            or any(item.codigo == codigo for item in permissoes.items)
        )
    )
    if not autorizado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissão para solicitar ajuste na etapa '{payload.etapa}'.",
        )
    d = await svc.solicitar_ajuste(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, lock_version=payload.lock_version,
                                   etapa=payload.etapa, justificativa=payload.justificativa,
                                   ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/responder-ajuste", response_model=DebitoOut)
async def responder_ajuste(debito_id: int, payload: DecisaoIn, request: Request,
                           usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    """Unidade responde o ajuste solicitado e volta à etapa que o pediu."""
    d = await svc.responder_ajuste(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, lock_version=payload.lock_version,
                                   ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


# Endpoints de validação e autoridade (4 total)
@debitos_router.post("/{debito_id}/validar", response_model=DebitoOut)
async def validar(debito_id: int, payload: DecisaoIn, request: Request,
                  usuario: Usuario = Depends(require_permission("pagamento_validar")),
                  tenant_id: int = Depends(require_tenant_id),
                  db: AsyncSession = Depends(get_db)):
    """Validador da Secretaria de Finanças aprova a conformidade documental e financeira."""
    d = await svc.validar(db, tenant_id=tenant_id, debito_id=debito_id,
                          usuario_id=usuario.id, lock_version=payload.lock_version,
                          ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/autoridade-aprovar", response_model=DebitoOut)
async def autoridade_aprovar(debito_id: int, payload: DecisaoIn, request: Request,
                             usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    """Autoridade competente aprova a despesa; segue para o pagador."""
    d = await svc.autoridade_aprovar(db, tenant_id=tenant_id, debito_id=debito_id,
                                     usuario_id=usuario.id, lock_version=payload.lock_version,
                                     ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/autoridade-indeferir", response_model=DebitoOut)
async def autoridade_indeferir(debito_id: int, payload: DecisaoJustificadaIn, request: Request,
                               usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                               tenant_id: int = Depends(require_tenant_id),
                               db: AsyncSession = Depends(get_db)):
    """Autoridade competente indeferiu a despesa por falta de disponibilidade orçamentária ou legal."""
    d = await svc.autoridade_indeferir(db, tenant_id=tenant_id, debito_id=debito_id,
                                       usuario_id=usuario.id, lock_version=payload.lock_version,
                                       justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


# Endpoint deprecado: /autorizar (nunca existiu com novo serviço)
@debitos_router.post("/{debito_id}/autorizar")
async def autorizar_deprecated(debito_id: int):
    """Endpoint descontinuado. Use autoridade-aprovar."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Este endpoint foi descontinuado. Use o novo fluxo de pagamentos."
    )


async def _op_out(db, tenant_id: int, ops) -> list[OrdemPagamentoOut]:
    nomes = await svc.nomes_usuarios(db, tenant_id=tenant_id,
                                     ids={o.id_usuario_autorizador for o in ops})
    out = []
    for o in ops:
        debs = await aut.debitos_da_ordem(db, tenant_id=tenant_id, ordem_id=o.id)
        out.append(OrdemPagamentoOut(
            id=o.id, numero=o.numero, valor_total=o.valor_total,
            id_usuario_autorizador=o.id_usuario_autorizador,
            nome_autorizador=nomes.get(o.id_usuario_autorizador),
            qtd_debitos=len(debs), criado_em=o.criado_em,
            id_conta_pagadora=o.id_conta_pagadora, valor_reservado=o.valor_reservado))
    return out


@operacoes_router.post("/autorizacoes", response_model=list[OrdemPagamentoOut],
                       status_code=status.HTTP_201_CREATED)
async def autorizar(payload: AutorizarLoteIn, request: Request,
                    usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    ops = await aut.autorizar_lote(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                   grupos=payload.grupos, ip=_ip(request))
    return await _op_out(db, tenant_id, ops)


# Onda C (C1.2) — relatório de exceções. Leitura ampla de propósito: quem
# audita não é necessariamente quem autoriza ou paga.
@operacoes_router.get("/relatorios/excecoes")
async def relatorio_excecoes(limite_por_regra: int = 50,
                             _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    """Consolida os estados que merecem conferência humana.

    Nenhuma regra nova: cada exceção corresponde a algo que o modelo já
    registra. `limite_por_regra` corta a lista exibida, nunca o total — ver
    "exibindo" vs "total" na resposta.
    """
    return await excecoes.relatorio_excecoes(
        db, tenant_id=tenant_id, limite_por_regra=limite_por_regra)


@operacoes_router.get("/ordens-pagamento", response_model=list[OrdemPagamentoOut])
async def list_ordens(_: Usuario = Depends(require_any_permission("pagamento_autorizar", "pagamento_pagar")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return await _op_out(db, tenant_id, await aut.listar_ordens(db, tenant_id=tenant_id))


@operacoes_router.get("/ordens-pagamento/{ordem_id}/pdf")
async def op_pdf(ordem_id: int,
                 _: Usuario = Depends(require_any_permission("pagamento_autorizar", "pagamento_pagar")),
                 tenant_id: int = Depends(require_tenant_id),
                 db: AsyncSession = Depends(get_db)):
    op = await aut.obter_ordem(db, tenant_id=tenant_id, ordem_id=ordem_id)
    debs = await aut.debitos_da_ordem(db, tenant_id=tenant_id, ordem_id=ordem_id)
    nomes_f = await svc.nomes_fornecedores(db, tenant_id=tenant_id,
                                           ids={d.id_fornecedor for d in debs})
    nomes_u = await svc.nomes_usuarios(db, tenant_id=tenant_id, ids={op.id_usuario_autorizador})
    esc = _htmlmod.escape
    linhas = "".join(
        f"<tr><td>{d.id}</td><td>{esc(nomes_f.get(d.id_fornecedor, '?'))}</td>"
        f"<td>{esc(d.descricao)}</td><td>{esc(d.competencia)}</td>"
        f"<td style='text-align:right'>R$ {d.valor_total:,.2f}</td></tr>" for d in debs)
    corpo = f"""
    <p><strong>Autorizador:</strong> {esc(nomes_u.get(op.id_usuario_autorizador, '?'))}<br>
    <strong>Data:</strong> {op.criado_em.strftime('%d/%m/%Y %H:%M')}<br>
    <strong>Valor total:</strong> R$ {op.valor_total:,.2f}</p>
    <table style="width:100%; border-collapse:collapse" border="1" cellpadding="6">
      <tr><th>Débito</th><th>Fornecedor</th><th>Descrição</th><th>Competência</th><th>Valor</th></tr>
      {linhas}
    </table>
    <p style="margin-top:40px">Autorizo o pagamento das despesas acima relacionadas
    (art. 64, Lei nº 4.320/64).</p>
    <p style="margin-top:60px; text-align:center">_______________________________<br>
    {esc(nomes_u.get(op.id_usuario_autorizador, '?'))}<br>Autorizador de Despesa</p>
    """
    pdf = html_to_pdf_bytes(corpo, titulo=f"Ordem de Pagamento {op.numero}")
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{op.numero}.pdf"'})


@operacoes_router.post("/parcelas/{parcela_id}/pagar", response_model=ParcelaOut)
async def pagar(parcela_id: int, payload: PagarParcelaIn, request: Request,
                usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                tenant_id: int = Depends(require_tenant_id),
                db: AsyncSession = Depends(get_db)):
    p = await aut.pagar_parcela(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                parcela_id=parcela_id, forma_pagamento=payload.forma_pagamento,
                                data_pagamento=payload.data_pagamento, ip=_ip(request))
    return ParcelaOut.model_validate(p)


@operacoes_router.post("/parcelas/{parcela_id}/estornar", response_model=ParcelaOut)
async def estornar(parcela_id: int, payload: JustificativaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    p = await aut.estornar_parcela(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                   parcela_id=parcela_id, justificativa=payload.justificativa,
                                   ip=_ip(request))
    return ParcelaOut.model_validate(p)


@debitos_router.post("/{debito_id}/em-processamento", response_model=DebitoOut)
async def marcar_em_processamento(debito_id: int, request: Request,
                                  usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                                  tenant_id: int = Depends(require_tenant_id),
                                  db: AsyncSession = Depends(get_db)):
    d = await aut.marcar_em_processamento(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                          debito_id=debito_id, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@operacoes_router.get("/autorizacao/fila", response_model=list[FilaAutorizacaoFonteGrupo])
async def fila_autorizacao(_: Usuario = Depends(require_permission("pagamento_autorizar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await filas.fila_autorizacao(db, tenant_id=tenant_id)


@operacoes_router.get("/fontes/{fonte_id}/contas-elegiveis", response_model=list[ContaElegivelOut])
async def contas_elegiveis(fonte_id: int,
                           _: Usuario = Depends(require_permission("pagamento_autorizar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await aut.contas_elegiveis(db, tenant_id=tenant_id, id_fonte=fonte_id)


@operacoes_router.get("/fontes/{fonte_id}/ficha", response_model=FichaFonteOut)
async def ficha_fonte(fonte_id: int,
                      _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return await caixa.ficha_fonte(db, tenant_id=tenant_id, id_fonte=fonte_id)


@operacoes_router.post("/simular-autorizacao", response_model=SimulacaoAutorizacaoOut)
async def simular_autorizacao(payload: SimulacaoAutorizacaoIn,
                              _: Usuario = Depends(require_permission("pagamento_autorizar")),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    return await caixa.simular_autorizacao(
        db, tenant_id=tenant_id, id_conta=payload.id_conta,
        debito_ids=payload.debito_ids, valor=payload.valor)


@operacoes_router.get("/liberacao/fila", response_model=list[FilaLiberacaoGrupo])
async def fila_liberacao(_: Usuario = Depends(require_permission("pagamento_autorizar")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return await filas.fila_liberacao(db, tenant_id=tenant_id)


@operacoes_router.get("/tesouraria/fila", response_model=FilaTesourariaOut)
async def fila_tesouraria(_: Usuario = Depends(require_permission("pagamento_pagar")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return await filas.fila_tesouraria(db, tenant_id=tenant_id)


@operacoes_router.post("/parcelas/liberar", response_model=list[ParcelaOut])
async def liberar_parcelas(payload: LiberarParcelasIn, request: Request,
                           usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    parcelas = await aut.liberar_parcelas(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                          parcela_ids=payload.parcela_ids,
                                          data_prevista=payload.data_prevista, ip=_ip(request))
    return [ParcelaOut.model_validate(p) for p in parcelas]


@operacoes_router.post("/parcelas/{parcela_id}/revogar-liberacao", response_model=ParcelaOut)
async def revogar_liberacao(parcela_id: int, payload: JustificativaIn, request: Request,
                            usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                            tenant_id: int = Depends(require_tenant_id),
                            db: AsyncSession = Depends(get_db)):
    p = await aut.revogar_liberacao(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                    parcela_id=parcela_id, justificativa=payload.justificativa,
                                    ip=_ip(request))
    return ParcelaOut.model_validate(p)


@operacoes_router.get("/dashboard", response_model=DashboardOut)
async def dashboard(meses: int = 12,
                    _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    return await dash.montar_dashboard(db, tenant_id=tenant_id, meses=meses)


@operacoes_router.get("/minha-fila", response_model=MinhaFilaOut)
async def minha_fila(usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    from datetime import date as _date
    perms = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    tem = (lambda c: True) if perms.is_super_usuario else \
        (lambda c: any(p.codigo == c for p in perms.items))
    fila = MinhaFilaOut()
    if tem("pagamento_solicitar"):
        rows = []
        for situacao in (est.RASCUNHO, est.AJUSTE_GESTOR, est.AJUSTE_VALIDACAO,
                         est.AJUSTE_AUTORIDADE):
            rows.extend(await svc.listar_debitos(
                db, tenant_id=tenant_id, tramitacao_f=situacao,
                solicitante_id=usuario.id))
        fila.solicitar = await _out(db, tenant_id, rows)
    if tem("pagamento_validar"):
        rows = await svc.listar_debitos(
            db, tenant_id=tenant_id, tramitacao_f=est.AGUARDANDO_VALIDACAO)
        fila.validar = await _out(db, tenant_id, rows)
    if tem("pagamento_gerir"):
        rows = await svc.listar_debitos(
            db, tenant_id=tenant_id, tramitacao_f=est.AGUARDANDO_GESTOR)
        fila.encaminhar = await _out(db, tenant_id, rows)
    if tem("pagamento_autorizar"):
        rows = await svc.listar_debitos(
            db, tenant_id=tenant_id, tramitacao_f=est.AGUARDANDO_AUTORIDADE)
        fila.autorizar = await _out(db, tenant_id, rows)
    if tem("pagamento_autorizar") or tem("pagamento_pagar"):
        debitos_ativos = []
        for st in (svc.ST_AUTORIZADO, *svc.EM_TESOURARIA):
            debitos_ativos.extend(await svc.listar_debitos(db, tenant_id=tenant_id, status_f=st))
        nomes = await svc.nomes_fornecedores(db, tenant_id=tenant_id,
                                             ids={d.id_fornecedor for d in debitos_ativos})

        if tem("pagamento_autorizar"):
            parcelas_liberar = []
            for d in debitos_ativos:
                for p in await svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
                    if p.status == "A_PAGAR":
                        parcelas_liberar.append(ParcelaFilaOut(
                            id=p.id, id_debito=d.id, numero=p.numero, valor=p.valor,
                            vencimento=p.vencimento, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
                            descricao_debito=d.descricao, vencida=p.vencimento < _date.today()))
            fila.liberar = sorted(parcelas_liberar, key=lambda x: x.vencimento)
        if tem("pagamento_pagar"):
            parcelas_pagar = []
            for d in debitos_ativos:
                for p in await svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
                    if p.status == "LIBERADA":
                        parcelas_pagar.append(ParcelaFilaOut(
                            id=p.id, id_debito=d.id, numero=p.numero, valor=p.valor,
                            vencimento=p.vencimento, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
                            descricao_debito=d.descricao, vencida=p.vencimento < _date.today()))
            fila.pagar = sorted(parcelas_pagar, key=lambda x: x.vencimento)
    return fila
