from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.choices import StatusPedido
from apps.core.middleware import get_current_ip
from apps.core.permissions import role_required

from . import services
from .exceptions import RegraDeNegocioError
from .forms import AnexoPedidoForm, ExecucaoPagamentoForm, JustificativaForm, PedidoPagamentoForm
from .models import PedidoPagamento


def _pode_visualizar(pedido, usuario):
    perfil = getattr(usuario, 'perfil', None)
    if perfil is None:
        return False
    if perfil.papel in ('CONTROLE_INTERNO', 'ADMIN', 'AUTORIZADOR', 'TESOURARIA'):
        return True
    if perfil.papel == 'SOLICITANTE':
        return pedido.solicitante_id == usuario.id
    if perfil.papel == 'SECRETARIO':
        return pedido.orgao_id == perfil.orgao_id
    return False


@login_required
def detalhe(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk)
    if not _pode_visualizar(pedido, request.user):
        raise PermissionDenied('Você não tem acesso a este pedido.')
    return render(request, 'pagamentos/detalhe.html', {'pedido': pedido})


# --- Solicitante (M2) -------------------------------------------------

@role_required('SOLICITANTE')
def solicitante_lista(request):
    pedidos = PedidoPagamento.objects.filter(solicitante=request.user).order_by('-criado_em')
    return render(request, 'pagamentos/solicitante_lista.html', {'pedidos': pedidos})


@role_required('SOLICITANTE')
def solicitante_criar(request):
    perfil = request.user.perfil
    if not perfil.orgao_id:
        messages.error(request, 'Seu usuário não possui órgão/secretaria vinculado. Contate o Administrador.')
        return redirect('pagamentos:solicitante_lista')

    if request.method == 'POST':
        form = PedidoPagamentoForm(request.POST)
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.solicitante = request.user
            pedido.orgao = perfil.orgao
            pedido.save()
            messages.success(request, f'Pedido {pedido.protocolo} criado. Anexe os documentos e envie para aprovação.')
            return redirect('pagamentos:detalhe', pk=pedido.pk)
    else:
        form = PedidoPagamentoForm()
    return render(request, 'pagamentos/solicitante_form.html', {'form': form, 'titulo': 'Novo Pedido de Pagamento'})


@role_required('SOLICITANTE')
def solicitante_editar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, solicitante=request.user)
    if not pedido.pode_editar:
        raise PermissionDenied('Pedido não pode mais ser editado (já enviado para aprovação).')
    if request.method == 'POST':
        form = PedidoPagamentoForm(request.POST, instance=pedido)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pedido atualizado.')
            return redirect('pagamentos:detalhe', pk=pedido.pk)
    else:
        form = PedidoPagamentoForm(instance=pedido)
    return render(request, 'pagamentos/solicitante_form.html', {'form': form, 'titulo': f'Editar {pedido.protocolo}'})


@role_required('SOLICITANTE')
def solicitante_anexar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, solicitante=request.user)
    if request.method == 'POST':
        form = AnexoPedidoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.pedido = pedido
            anexo.enviado_por = request.user
            anexo.save()
            messages.success(request, 'Anexo enviado.')
            return redirect('pagamentos:detalhe', pk=pedido.pk)
    else:
        form = AnexoPedidoForm()
    return render(request, 'pagamentos/anexo_form.html', {'form': form, 'pedido': pedido})


@role_required('SOLICITANTE')
def solicitante_enviar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, solicitante=request.user)
    if request.method == 'POST':
        try:
            services.enviar_para_aprovacao(pedido, request.user)
            messages.success(request, 'Pedido enviado para aprovação do Secretário.')
        except RegraDeNegocioError as exc:
            messages.error(request, str(exc))
    return redirect('pagamentos:detalhe', pk=pedido.pk)


@role_required('SOLICITANTE')
def solicitante_cancelar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, solicitante=request.user)
    if request.method == 'POST':
        try:
            services.cancelar(pedido, request.user)
            messages.success(request, 'Pedido cancelado.')
        except RegraDeNegocioError as exc:
            messages.error(request, str(exc))
    return redirect('pagamentos:solicitante_lista')


# --- Secretário (M3) ---------------------------------------------------

@role_required('SECRETARIO')
def secretario_fila(request):
    perfil = request.user.perfil
    pedidos = PedidoPagamento.objects.filter(
        orgao=perfil.orgao, status=StatusPedido.PENDENTE, enviado_para_aprovacao=True,
    ).order_by('-criticidade', 'vencimento')
    return render(request, 'pagamentos/secretario_fila.html', {'pedidos': pedidos})


@role_required('SECRETARIO')
def secretario_aprovar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, orgao=request.user.perfil.orgao)
    if request.method == 'POST':
        try:
            services.aprovar_secretario(pedido, request.user)
            messages.success(request, 'Pedido aprovado e encaminhado ao Autorizador Final.')
        except RegraDeNegocioError as exc:
            messages.error(request, str(exc))
    return redirect('pagamentos:secretario_fila')


@role_required('SECRETARIO')
def secretario_devolver(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, orgao=request.user.perfil.orgao)
    return _acao_com_justificativa(
        request, pedido, services.devolver, 'pagamentos:secretario_fila', 'Pedido devolvido ao solicitante.'
    )


@role_required('SECRETARIO')
def secretario_rejeitar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk, orgao=request.user.perfil.orgao)
    return _acao_com_justificativa(
        request, pedido, services.rejeitar, 'pagamentos:secretario_fila', 'Pedido rejeitado.'
    )


def _acao_com_justificativa(request, pedido, acao, url_retorno, mensagem_sucesso):
    if request.method == 'POST':
        form = JustificativaForm(request.POST)
        if form.is_valid():
            try:
                acao(pedido, request.user, form.cleaned_data['justificativa'])
                messages.success(request, mensagem_sucesso)
                return redirect(url_retorno)
            except RegraDeNegocioError as exc:
                messages.error(request, str(exc))
    else:
        form = JustificativaForm()
    return render(request, 'pagamentos/justificativa_form.html', {'form': form, 'pedido': pedido})


# --- Autorizador Final (M4) --------------------------------------------

@role_required('AUTORIZADOR')
def autorizador_painel(request):
    pedidos = PedidoPagamento.objects.filter(status=StatusPedido.APROVADO_SECRETARIO)

    orgao_id = request.GET.get('orgao')
    natureza_id = request.GET.get('natureza')
    fonte_id = request.GET.get('fonte')
    apenas_urgentes = request.GET.get('urgentes') == '1'
    agrupar_por = request.GET.get('agrupar', 'natureza')

    if orgao_id:
        pedidos = pedidos.filter(orgao_id=orgao_id)
    if natureza_id:
        pedidos = pedidos.filter(natureza_id=natureza_id)
    if fonte_id:
        pedidos = pedidos.filter(conta_bancaria__fonte_recursos_id=fonte_id)
    if apenas_urgentes:
        pedidos = pedidos.filter(urgente=True)

    campo_grupo = 'orgao' if agrupar_por == 'orgao' else 'natureza'
    pedidos = pedidos.select_related('credor', 'natureza', 'orgao', 'conta_bancaria').order_by(
        f'{campo_grupo}__id', '-urgente', '-criticidade', 'vencimento'
    )

    contas_envolvidas = {}
    grupos = []
    grupo_atual_chave = object()
    for pedido in pedidos:
        chave = pedido.natureza_id if campo_grupo == 'natureza' else pedido.orgao_id
        rotulo = str(pedido.natureza) if campo_grupo == 'natureza' else str(pedido.orgao)
        if chave != grupo_atual_chave:
            grupos.append({'rotulo': rotulo, 'pedidos': [], 'subtotal': 0})
            grupo_atual_chave = chave
        grupos[-1]['pedidos'].append(pedido)
        grupos[-1]['subtotal'] += pedido.valor
        contas_envolvidas.setdefault(pedido.conta_bancaria_id, pedido.conta_bancaria)

    from apps.cadastros.models import FonteRecursos, NaturezaDespesa, OrgaoSecretaria

    contexto = {
        'grupos': grupos,
        'total_pedidos': sum(len(g['pedidos']) for g in grupos),
        'contas_envolvidas': contas_envolvidas.values(),
        'orgaos': OrgaoSecretaria.objects.filter(ativo=True),
        'naturezas': NaturezaDespesa.objects.filter(ativa=True),
        'fontes': FonteRecursos.objects.all(),
        'agrupar_por': agrupar_por,
        'filtros': request.GET,
    }
    return render(request, 'pagamentos/autorizador_painel.html', contexto)


@role_required('AUTORIZADOR')
def autorizador_autorizar(request):
    if request.method != 'POST':
        return redirect('pagamentos:autorizador_painel')
    ids = request.POST.getlist('pedidos')
    if not ids:
        messages.error(request, 'Selecione ao menos um pedido para autorizar.')
        return redirect('pagamentos:autorizador_painel')

    pedidos = list(PedidoPagamento.objects.filter(pk__in=ids))
    try:
        ordem = services.autorizar_lote(pedidos, request.user, ip_origem=get_current_ip())
        messages.success(
            request,
            f'{len(pedidos)} pedido(s) autorizado(s) — Ordem de Pagamento {ordem.numero} '
            f'(R$ {ordem.valor_total}).',
        )
        return redirect('pagamentos:ordem_detalhe', pk=ordem.pk)
    except RegraDeNegocioError as exc:
        messages.error(request, str(exc))
        return redirect('pagamentos:autorizador_painel')


@role_required('AUTORIZADOR', 'TESOURARIA', 'CONTROLE_INTERNO')
def ordem_detalhe(request, pk):
    from .models import OrdemPagamento

    ordem = get_object_or_404(OrdemPagamento, pk=pk)
    return render(request, 'pagamentos/ordem_detalhe.html', {'ordem': ordem})


@role_required('AUTORIZADOR', 'TESOURARIA', 'CONTROLE_INTERNO')
def ordem_pdf(request, pk):
    """RF33 — emissão da Ordem de Pagamento como documento formal em PDF."""
    from apps.relatorios.exports import response_pdf

    from .models import OrdemPagamento

    ordem = get_object_or_404(OrdemPagamento, pk=pk)
    return response_pdf('pagamentos/ordem_pdf.html', {'ordem': ordem}, f'{ordem.numero}.pdf')


# --- Tesouraria (M5) -----------------------------------------------------

@role_required('TESOURARIA')
def tesouraria_fila(request):
    pedidos = PedidoPagamento.objects.filter(status=StatusPedido.AUTORIZADO).select_related(
        'credor', 'conta_bancaria'
    ).order_by('-urgente', '-criticidade', 'vencimento')
    return render(request, 'pagamentos/tesouraria_fila.html', {'pedidos': pedidos})


@role_required('TESOURARIA')
def tesouraria_executar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk)
    if request.method == 'POST':
        form = ExecucaoPagamentoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                services.executar_pagamento(
                    pedido, request.user,
                    forma_pagamento=form.cleaned_data['forma_pagamento'],
                    data_pagamento=form.cleaned_data['data_pagamento'],
                    comprovante=form.cleaned_data.get('comprovante'),
                )
                messages.success(request, f'Pagamento de {pedido.protocolo} registrado como Pago.')
                return redirect('pagamentos:tesouraria_fila')
            except RegraDeNegocioError as exc:
                messages.error(request, str(exc))
    else:
        form = ExecucaoPagamentoForm()
    return render(request, 'pagamentos/execucao_form.html', {'form': form, 'pedido': pedido})


@role_required('TESOURARIA')
def tesouraria_estornar(request, pk):
    pedido = get_object_or_404(PedidoPagamento, pk=pk)
    return _acao_com_justificativa(
        request, pedido, services.estornar_pagamento, 'pagamentos:tesouraria_fila', 'Pagamento estornado.'
    )
