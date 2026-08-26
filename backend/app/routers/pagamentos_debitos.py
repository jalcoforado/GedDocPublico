"""Rotas de Débitos/Autorização/Pagamento (R2). IP do cliente vai para o histórico."""
from __future__ import annotations

import html as _htmlmod
import mimetypes
import urllib.parse

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id, require_tenant_slug
from ..auth.perms import require_any_permission, require_permission
from ..config import resolve_anexo_path
from ..database import get_db
from ..models import Anexo, Usuario
from datetime import date

from pydantic import BaseModel, Field

from ..schemas.pagamentos import (
    AnexoDebitoOut, AutorizarLoteIn, ContaElegivelOut, DashboardOut, DebitoCreate, DebitoDetalheOut,
    DebitoHistoricoOut, DebitoOut, DebitoUpdate, DecisaoIn, DecisaoJustificadaIn, FichaFonteOut,
    FilaAutorizacaoFonteGrupo, ChecklistDebitoItemOut, FilaLiberacaoGrupo, FilaTesourariaOut,
    JustificativaIn, LiquidacaoIn, MarcarChecklistIn, MinhaFilaOut, OrdemPagamentoOut,
    PagarParcelaIn, ParcelaFilaOut, ParcelaOut, PedidoAjusteCreate, PedidoAjusteOut,
    PedidoAjusteResponderIn, PendenciaAjusteOut, SolicitarAjusteIn, SimulacaoAutorizacaoIn,
    SimulacaoAutorizacaoOut, DebitoVersaoOut, FilaCronologicaGrupo, PosicaoDebitoOut,
)
from ..services import pagamentos_ajustes as ajustes
from ..services import pagamentos_anexos as anexos_debito
from ..services import pagamentos_autorizacao as aut
from ..services import pagamentos_caixa as caixa
from ..services import pagamentos_checklist as checklist
from ..services import pagamentos_cronologia as cronologia
from ..services import pagamentos_dashboard as dash
from ..services import pagamentos_debitos as svc
from ..services import pagamentos_estados as est
from ..services import pagamentos_excecoes as excecoes
from ..services import pagamentos_export as export
from ..services import pagamentos_filas as filas
from ..services import audit
from ..services.anexos import AnexoError
from ..services.html_pdf import html_to_pdf_bytes
from ..services.permissoes import load_permissions

# Etapa do rito -> transação que representa aquela etapa. Compartilhado por
# `solicitar-ajuste`, pedido adicional, responder e cancelar: em todos, "quem
# pode agir" é definido pela mesma tabela etapa -> transação.
CODIGO_POR_ETAPA = {
    "GESTOR": "pagamento_gerir",
    "VALIDACAO": "pagamento_validar",
    "AUTORIDADE": "pagamento_autorizar",
}


async def _assert_permissao_dinamica(db, usuario: Usuario, tenant_id: int, codigo: str,
                                     mensagem: str) -> None:
    """Confere se `usuario` tem `codigo` — checagem dinâmica (não amarrada a
    um `Depends` fixo, porque o código depende de dado carregado em runtime:
    a etapa do pedido, não a etapa do payload)."""
    permissoes = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    autorizado = (
        codigo not in permissoes.codigos_bloqueados
        and (
            permissoes.is_super_usuario
            or any(item.codigo == codigo for item in permissoes.items)
        )
    )
    if not autorizado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=mensagem)


class LiberarParcelasIn(BaseModel):
    parcela_ids: list[int] = Field(min_length=1)
    data_prevista: date | None = None

PERMS_LEITURA = ("pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
                 "pagamento_autorizar", "pagamento_pagar", "pagamento_auditar",
                 "pagamento_cadastro")

debitos_router = APIRouter(prefix="/pagamentos/debitos", tags=["pagamentos-debitos"])
operacoes_router = APIRouter(prefix="/pagamentos", tags=["pagamentos-operacoes"])


# Rota literal ANTES de qualquer paramétrica irmã em `operacoes_router` (F3,
# Task 3) — hoje nenhuma delas casaria `/fila-cronologica`, mas a declaração
# antecipada é o padrão do módulo (ver `download_anexo_debito` acima) e evita
# a armadilha de rota engolida se uma paramétrica de primeiro segmento nascer.
@operacoes_router.get("/fila-cronologica", response_model=list[FilaCronologicaGrupo])
async def fila_cronologica(id_fonte: int | None = None, id_unidade: int | None = None,
                           categoria: str | None = None, exercicio: int | None = None,
                           incluir_concluidas: bool = False,
                           _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await cronologia.listar_fila(
        db, tenant_id=tenant_id, id_fonte=id_fonte, id_unidade=id_unidade,
        categoria=categoria, exercicio=exercicio, incluir_concluidas=incluir_concluidas)


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


# `/fila` é literal SOB a paramétrica `/{debito_id}` — não colide com ela
# (segmentos diferentes: `/{debito_id}` casa 1 segmento, `/{debito_id}/fila`
# casa 2) e por isso não precisa vir antes; a guarda `test_guarda_ordem_rotas`
# confere isso.
@debitos_router.get("/{debito_id}/fila", response_model=PosicaoDebitoOut)
async def fila_do_debito(debito_id: int,
                         _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    posicao = await cronologia.posicao_do_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if posicao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Débito não tem posição na fila cronológica.")
    return posicao


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


# Endpoints antigos substituídos pelo novo fluxo (retornam 410 Gone). Mantêm o
# gate de permissão que tinham antes de virar stub: sem isso a varredura de
# `test_guarda_modularizacao.py` os marca como desprotegidos, e um tenant sem
# o módulo pagamentos conseguiria bater neles.
@debitos_router.post("/{debito_id}/encaminhar", status_code=status.HTTP_410_GONE)
async def encaminhar_deprecated(debito_id: int,
                                _: Usuario = Depends(require_permission("pagamento_solicitar"))):
    """Endpoint descontinuado. Use o novo fluxo de pagamentos: gestor-autorizar, validar, etc."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Este endpoint foi descontinuado. Use o novo fluxo de pagamentos."
    )


@debitos_router.post("/{debito_id}/devolver", status_code=status.HTTP_410_GONE)
async def devolver_deprecated(debito_id: int,
                              _: Usuario = Depends(require_permission("pagamento_validar"))):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint descontinuado. Use solicitar-ajuste na etapa responsável.",
    )


@debitos_router.post("/{debito_id}/rejeitar", status_code=status.HTTP_410_GONE)
async def rejeitar_deprecated(debito_id: int,
                              _: Usuario = Depends(require_permission("pagamento_validar"))):
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
async def suspender_deprecated(debito_id: int,
                               _: Usuario = Depends(require_permission("pagamento_pagar"))):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint descontinuado. Bloqueios passam a pertencer à ordem cronológica.",
    )


@debitos_router.post("/{debito_id}/reativar", status_code=status.HTTP_410_GONE)
async def reativar_deprecated(debito_id: int,
                              _: Usuario = Depends(require_permission("pagamento_pagar"))):
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
    codigo = CODIGO_POR_ETAPA[payload.etapa]
    await _assert_permissao_dinamica(
        db, usuario, tenant_id, codigo,
        f"Sem permissão para solicitar ajuste na etapa '{payload.etapa}'.")
    d = await svc.solicitar_ajuste(
        db, tenant_id=tenant_id, debito_id=debito_id,
        usuario_id=usuario.id, lock_version=payload.lock_version,
        etapa=payload.etapa, motivo=payload.motivo, descricao=payload.descricao,
        transacao_responsavel=payload.transacao_responsavel, tipo=payload.tipo,
        prazo=payload.prazo, campos_relacionados=payload.campos_relacionados,
        ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.get("/{debito_id}/pedidos-ajuste", response_model=list[PedidoAjusteOut])
async def listar_pedidos_ajuste(debito_id: int,
                                _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                tenant_id: int = Depends(require_tenant_id),
                                db: AsyncSession = Depends(get_db)):
    await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return await ajustes.listar_pedidos(db, tenant_id=tenant_id, debito_id=debito_id)


@debitos_router.post("/{debito_id}/pedidos-ajuste", response_model=PedidoAjusteOut,
                     status_code=status.HTTP_201_CREATED)
async def criar_pedido_ajuste(debito_id: int, payload: PedidoAjusteCreate, request: Request,
                              usuario: Usuario = Depends(require_any_permission(
                                  "pagamento_gerir", "pagamento_validar", "pagamento_autorizar")),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    """Pedido adicional sobre um débito já em ajuste — não transiciona o
    débito; a etapa vem da situação ATUAL dele, não do payload."""
    d = await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    etapa = ajustes.ETAPA_POR_SITUACAO.get(d.situacao_tramitacao)
    if etapa is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Débito não está em ajuste (está em '{d.situacao_tramitacao}').")
    codigo = CODIGO_POR_ETAPA[etapa]
    await _assert_permissao_dinamica(
        db, usuario, tenant_id, codigo,
        f"Sem permissão para abrir pedido de ajuste na etapa '{etapa}'.")
    pedido = await ajustes.criar_pedido(
        db, tenant_id=tenant_id, debito=d, usuario_id=usuario.id, etapa=etapa,
        motivo=payload.motivo, descricao=payload.descricao,
        transacao_responsavel=payload.transacao_responsavel, tipo=payload.tipo,
        prazo=payload.prazo, campos_relacionados=payload.campos_relacionados)
    await audit.log(
        db, tenant_id=tenant_id, id_usuario=usuario.id,
        acao="debito.ajuste_solicitado", entidade="debito", id_entidade=d.id,
        payload={"pedido_ajuste_id": pedido.id, "etapa": etapa,
                 "transacao_responsavel": payload.transacao_responsavel, "tipo": payload.tipo},
        request=request)
    await db.commit(); await db.refresh(pedido)
    return pedido


@debitos_router.post("/{debito_id}/pedidos-ajuste/{pedido_id}/responder",
                     response_model=PedidoAjusteOut)
async def responder_pedido_ajuste(debito_id: int, pedido_id: int, payload: PedidoAjusteResponderIn,
                                  request: Request,
                                  usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                  tenant_id: int = Depends(require_tenant_id),
                                  db: AsyncSession = Depends(get_db)):
    """Responde ao pedido — só quem tem a `transacao_responsavel` DO PEDIDO."""
    pedido = await ajustes.obter_pedido(db, tenant_id=tenant_id, debito_id=debito_id,
                                        pedido_id=pedido_id)
    await _assert_permissao_dinamica(
        db, usuario, tenant_id, pedido.transacao_responsavel,
        "Sem permissão para responder este pedido de ajuste.")
    pedido = await ajustes.responder_pedido(
        db, tenant_id=tenant_id, debito_id=debito_id, pedido_id=pedido_id,
        usuario_id=usuario.id, resposta=payload.resposta)
    await audit.log(
        db, tenant_id=tenant_id, id_usuario=usuario.id,
        acao="debito.ajuste_respondido", entidade="debito", id_entidade=debito_id,
        payload={"pedido_ajuste_id": pedido.id}, request=request)
    await db.commit(); await db.refresh(pedido)
    return pedido


@debitos_router.post("/{debito_id}/pedidos-ajuste/{pedido_id}/cancelar",
                     response_model=PedidoAjusteOut)
async def cancelar_pedido_ajuste(debito_id: int, pedido_id: int,
                                 usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                 tenant_id: int = Depends(require_tenant_id),
                                 db: AsyncSession = Depends(get_db)):
    """Cancela — só quem tem a transação da etapa SOLICITANTE do pedido."""
    pedido = await ajustes.obter_pedido(db, tenant_id=tenant_id, debito_id=debito_id,
                                        pedido_id=pedido_id)
    codigo = CODIGO_POR_ETAPA[pedido.etapa_solicitante]
    await _assert_permissao_dinamica(
        db, usuario, tenant_id, codigo,
        "Sem permissão para cancelar este pedido de ajuste.")
    pedido = await ajustes.cancelar_pedido(
        db, tenant_id=tenant_id, debito_id=debito_id, pedido_id=pedido_id,
        usuario_id=usuario.id)
    await db.commit(); await db.refresh(pedido)
    return pedido


@debitos_router.get("/{debito_id}/versoes", response_model=list[DebitoVersaoOut])
async def listar_versoes_debito(debito_id: int,
                                _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                tenant_id: int = Depends(require_tenant_id),
                                db: AsyncSession = Depends(get_db)):
    """Versões congeladas do débito antes de cada alteração material —
    prova que a versão anterior é recuperável (F2)."""
    await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return await svc.listar_versoes(db, tenant_id=tenant_id, debito_id=debito_id)


async def _anexos_debito_out(db, tenant_id: int, tenant_slug: str, vinculos) -> list[AnexoDebitoOut]:
    anexo_ids = {v.id_anexo for v in vinculos}
    anexos_map = {}
    if anexo_ids:
        rows = (await db.execute(select(Anexo).where(Anexo.id.in_(anexo_ids)))).scalars()
        anexos_map = {a.id: a for a in rows}
    out = []
    for v in vinculos:
        a = anexos_map.get(v.id_anexo)
        nome = a.descricao if a else None
        tipo = None
        tamanho = None
        if a and a.e_doc:
            if "." in a.e_doc:
                tipo = a.e_doc.rsplit(".", 1)[1]
            p = resolve_anexo_path(tenant_slug, a.e_doc)
            if p is not None:
                try:
                    tamanho = p.stat().st_size
                except OSError:
                    tamanho = None
        out.append(AnexoDebitoOut(
            id=v.id, id_anexo=v.id_anexo, nome=nome, tamanho=tamanho, tipo=tipo,
            versao_debito=v.versao_debito, id_pedido_ajuste=v.id_pedido_ajuste,
            id_usuario=v.id_usuario, criado_em=v.criado_em))
    return out


@debitos_router.post("/{debito_id}/anexos", response_model=AnexoDebitoOut,
                     status_code=status.HTTP_201_CREATED)
async def upload_anexo_debito(debito_id: int, request: Request,
                              file: UploadFile = File(...),
                              descricao: str | None = Form(None),
                              id_pedido_ajuste: int | None = Form(None),
                              usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                              tenant_id: int = Depends(require_tenant_id),
                              tenant_slug: str = Depends(require_tenant_slug),
                              db: AsyncSession = Depends(get_db)):
    """Anexa um documento ao débito, reaproveitando o storage de anexos de
    protocolo. `id_pedido_ajuste` opcional marca que o documento é a resposta
    a um pedido de ajuste específico (do mesmo débito)."""
    try:
        vinculo = await anexos_debito.anexar_ao_debito(
            db, tenant_id=tenant_id, tenant_slug=tenant_slug, debito_id=debito_id,
            usuario_id=usuario.id, file=file, descricao=descricao,
            id_pedido_ajuste=id_pedido_ajuste)
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await audit.log(
        db, tenant_id=tenant_id, id_usuario=usuario.id,
        acao="anexo_debito.incluido", entidade="anexo_debito", id_entidade=vinculo.id,
        payload={"debito_id": debito_id, "id_anexo": vinculo.id_anexo,
                 "id_pedido_ajuste": id_pedido_ajuste},
        request=request)
    await db.commit(); await db.refresh(vinculo)
    return (await _anexos_debito_out(db, tenant_id, tenant_slug, [vinculo]))[0]


@debitos_router.get("/{debito_id}/anexos", response_model=list[AnexoDebitoOut])
async def listar_anexos_debito_endpoint(debito_id: int,
                                        _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                        tenant_id: int = Depends(require_tenant_id),
                                        tenant_slug: str = Depends(require_tenant_slug),
                                        db: AsyncSession = Depends(get_db)):
    await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    vinculos = await anexos_debito.listar_anexos_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return await _anexos_debito_out(db, tenant_id, tenant_slug, vinculos)


@debitos_router.delete("/{debito_id}/anexos/{anexo_debito_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_anexo_debito_endpoint(debito_id: int, anexo_debito_id: int, request: Request,
                                        usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                                        tenant_id: int = Depends(require_tenant_id),
                                        db: AsyncSession = Depends(get_db)):
    await anexos_debito.remover_anexo_debito(
        db, tenant_id=tenant_id, debito_id=debito_id, anexo_debito_id=anexo_debito_id,
        usuario_id=usuario.id)
    await audit.log(
        db, tenant_id=tenant_id, id_usuario=usuario.id,
        acao="anexo_debito.removido", entidade="anexo_debito", id_entidade=anexo_debito_id,
        payload={"debito_id": debito_id}, request=request)
    await db.commit()


# Rota literal `anexos-debito` no `operacoes_router` — não colide com nenhuma
# paramétrica do mesmo router (o primeiro segmento é distinto de todos os
# outros: `ordens-pagamento`, `parcelas`, `fontes`, etc.).
@operacoes_router.get("/anexos-debito/{anexo_debito_id}/download")
async def download_anexo_debito(anexo_debito_id: int, inline: bool = Query(False),
                                _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                                tenant_id: int = Depends(require_tenant_id),
                                tenant_slug: str = Depends(require_tenant_slug),
                                db: AsyncSession = Depends(get_db)):
    path, anexo = await anexos_debito.get_anexo_debito_path_autorizado(
        db, tenant_id=tenant_id, tenant_slug=tenant_slug, anexo_debito_id=anexo_debito_id)
    download_name = (anexo.descricao or anexo.e_doc or f"anexo-{anexo.id}").strip()
    if anexo.e_doc and "." in anexo.e_doc and "." not in download_name:
        download_name += "." + anexo.e_doc.rsplit(".", 1)[1]
    safe_name = urllib.parse.quote(download_name)
    disposition = "inline" if inline else "attachment"
    media_type, _enc = mimetypes.guess_type(anexo.e_doc or "")
    return FileResponse(
        path=str(path), media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{safe_name}"})


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
async def autorizar_deprecated(debito_id: int,
                               _: Usuario = Depends(require_permission("pagamento_autorizar"))):
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


# C1.3 — export das ordens. ANTES de `/ordens-pagamento/{ordem_id}/pdf`:
# `exportar.csv` e `exportar.pdf` casariam em `{ordem_id}` se viessem depois, e
# a requisição morreria em 422 antes de chegar ao handler. Foi assim três vezes
# no transporte; `tests/test_guarda_ordem_rotas.py` cobre o caso.
@operacoes_router.get("/ordens-pagamento/exportar.csv")
async def exportar_ordens_csv(_: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    """Ordens de pagamento em CSV, com a exceção de saldo (RN-15) como coluna."""
    conteudo = await export.csv_ordens(db, tenant_id=tenant_id)
    return Response(
        content=conteudo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ordens-pagamento.csv"'},
    )


@operacoes_router.get("/ordens-pagamento/exportar.pdf")
async def exportar_ordens_pdf(_: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    """A mesma lista em PDF — o documento que o controle interno arquiva."""
    conteudo = await export.pdf_ordens(db, tenant_id=tenant_id)
    return Response(
        content=conteudo, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ordens-pagamento.pdf"'},
    )


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
    transacoes_usuario = (
        ajustes.TRANSACOES_PAGAMENTOS if perms.is_super_usuario
        else {p.codigo for p in perms.items} & ajustes.TRANSACOES_PAGAMENTOS
    )
    pares = await ajustes.pendencias_do_usuario(
        db, tenant_id=tenant_id, transacoes=transacoes_usuario)
    fila.pendencias_ajuste = [
        PendenciaAjusteOut(
            id_pedido=pedido.id, id_debito=pedido.id_debito, descricao_debito=descricao,
            motivo=pedido.motivo, prazo=pedido.prazo, criado_em=pedido.criado_em,
            etapa_solicitante=pedido.etapa_solicitante,
        )
        for pedido, descricao in pares
    ]
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
