"""Monta o texto do processo que vai no system prompt.

**Este arquivo é a fronteira de segurança da fatia.** Não há tool-calling: o
modelo só alcança o que sai daqui. Um campo acrescentado a esta função é um
campo exposto ao modelo — e, por consequência, ao usuário que perguntar.

Duas regras ao estender:

- **Só entra o que a tela do processo já mostra.** O usuário passou pelos três
  guards (permissão, contratação, sigilo) para abrir aquele processo; o
  assistente não pode ampliar o alcance dele, só reduzir o esforço de ler.
- **Nada de conteúdo de anexo.** Metadado (nome, páginas, se é público) sim;
  o conteúdo do arquivo é outra fatia e outro risco — ver a spec IA-1.
"""
from __future__ import annotations

from ...schemas.processo import ProcessoDetail

# Teto de movimentações no contexto. Processo antigo pode ter centenas, e a
# cauda raramente responde a pergunta ("onde está?", "o que houve por último?").
# Cortamos as MAIS ANTIGAS e dizemos ao modelo que cortamos — silenciar o corte
# faria o modelo afirmar "o processo começou em X" sobre uma abertura que ele
# não viu.
MAX_MOVIMENTACOES = 40

_STATUS_PRAZO = {
    "sem_prazo": "sem prazo definido",
    "dentro_do_prazo": "dentro do prazo",
    "vencendo": "vencendo",
    "atrasado": "atrasado",
    "concluido_no_prazo": "concluído no prazo",
    "concluido_atrasado": "concluído em atraso",
}


def _data(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _data_hora(d) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if d else "—"


def _bloco_identificacao(p: ProcessoDetail) -> list[str]:
    linhas = [
        "## Identificação",
        f"- Número: {p.numero_processo}",
    ]
    if p.nup:
        linhas.append(f"- NUP: {p.nup}")
    linhas += [
        f"- Aberto em: {_data_hora(p.data_hora_abertura)}",
        f"- Assunto: {p.assunto or '—'}",
        f"- Tipo: {p.tipo_processo or '—'}",
        f"- Situação: {'ativo' if p.ativo else 'encerrado'}",
        f"- Nível de sigilo: {p.nivel_sigilo}",
        f"- Unidade proprietária: {p.unidade_proprietaria or '—'}",
        f"- Local atual: {p.local_atual or '—'}",
        f"- Manifestante: {p.manifestante or '—'}",
    ]
    if p.canal_entrada:
        linhas.append(f"- Canal de entrada: {p.canal_entrada}")
    return linhas


def _bloco_prazo(p: ProcessoDetail) -> list[str]:
    """O prazo entra JÁ CALCULADO. O modelo não faz conta — ver regra 4."""
    pz = p.prazo
    linhas = ["", "## Prazo", f"- Situação: {_STATUS_PRAZO.get(pz.status, pz.status)}"]
    if pz.prazo_servico_dias_snapshot is not None:
        linhas.append(f"- Prazo do serviço: {pz.prazo_servico_dias_snapshot} dias")
    if pz.prazo_previsto_em:
        linhas.append(f"- Previsão: {_data(pz.prazo_previsto_em)}")
    if pz.dias_restantes is not None:
        linhas.append(f"- Dias restantes: {pz.dias_restantes}")
    if pz.dias_atraso is not None:
        linhas.append(f"- Dias de atraso: {pz.dias_atraso}")
    if pz.concluido_em:
        linhas.append(f"- Concluído em: {_data(pz.concluido_em)}")
    return linhas


def _bloco_sigilo(p: ProcessoDetail) -> list[str]:
    """Só aparece em processo com classificação legal (reservado ou acima).

    Não é vazamento: quem chegou aqui já passou por `assert_acesso_processo`,
    ou seja, a credencial dele alcança este nível.
    """
    if not p.sigilo_fundamento_legal and not p.sigilo_autoridade:
        return []
    linhas = ["", "## Classificação de sigilo (TCI)"]
    if p.sigilo_fundamento_legal:
        linhas.append(f"- Fundamento legal: {p.sigilo_fundamento_legal}")
    if p.sigilo_autoridade:
        linhas.append(f"- Autoridade classificadora: {p.sigilo_autoridade}")
    if p.sigilo_prazo_anos is not None:
        linhas.append(f"- Prazo: {p.sigilo_prazo_anos} anos")
    if p.sigilo_data_classificacao:
        linhas.append(f"- Classificado em: {_data(p.sigilo_data_classificacao)}")
    if p.sigilo_data_desclassificacao:
        linhas.append(f"- Desclassifica em: {_data(p.sigilo_data_desclassificacao)}")
    return linhas


def _bloco_movimentacoes(p: ProcessoDetail) -> list[str]:
    todas = p.movimentacoes or []
    linhas = ["", f"## Movimentações ({len(todas)} no total)"]
    if not todas:
        linhas.append("- Nenhuma movimentação registrada.")
        return linhas

    mostradas = todas
    if len(todas) > MAX_MOVIMENTACOES:
        mostradas = todas[-MAX_MOVIMENTACOES:]
        linhas.append(
            f"*(As {len(todas) - MAX_MOVIMENTACOES} mais antigas foram omitidas "
            "por limite de espaço. Não afirme nada sobre elas.)*"
        )

    for m in mostradas:
        linha = (
            f"- {_data_hora(m.data_hora_movimentacao)} — **{m.acao}** "
            f"em {m.unidade_responsavel or 'unidade não informada'}"
        )
        if m.usuario:
            linha += f", por {m.usuario}"
        linhas.append(linha)
        if m.despacho and m.despacho.despacho:
            linhas.append(f"  - Despacho: {m.despacho.despacho}")
        if m.encaminhamento:
            e = m.encaminhamento
            destino = f"  - Encaminhado para: {e.unidade_destino}"
            if e.data_prazo:
                destino += f" (prazo {_data(e.data_prazo)})"
            destino += "; recebido" if e.recebido else "; ainda não recebido"
            linhas.append(destino)
    return linhas


def _bloco_anexos(p: ProcessoDetail) -> list[str]:
    """METADADO apenas. O conteúdo do arquivo nunca entra — ver docstring."""
    anexos = p.anexos or []
    linhas = ["", f"## Anexos ({len(anexos)})"]
    if not anexos:
        linhas.append("- Nenhum anexo.")
        return linhas
    for a in anexos:
        desc = a.descricao or a.e_doc or f"anexo {a.id}"
        detalhe = f"- {desc}"
        if a.tipo_anexo:
            detalhe += f" ({a.tipo_anexo})"
        if a.qtd_paginas:
            detalhe += f", {a.qtd_paginas} páginas"
        linhas.append(detalhe)
    linhas.append(
        "*(Você vê apenas a lista de anexos, não o conteúdo dos arquivos. "
        "Não afirme nada sobre o que está escrito dentro deles.)*"
    )
    return linhas


def montar_contexto(p: ProcessoDetail) -> str:
    """Serializa o processo autorizado como Markdown para o system prompt."""
    linhas: list[str] = [f"# Processo {p.numero_processo}"]
    linhas += _bloco_identificacao(p)
    linhas += _bloco_prazo(p)
    linhas += _bloco_sigilo(p)

    if p.corpo:
        linhas += ["", "## Descrição (texto da abertura)", p.corpo]
    if p.observacao:
        linhas += ["", "## Observação", p.observacao]

    linhas += _bloco_movimentacoes(p)
    linhas += _bloco_anexos(p)
    return "\n".join(linhas)
