"""Despacho sem encaminhar (SI-62, RF-03 do documento de requisitos v1.0).

Registra uma manifestação no processo SEM mandá-lo para outra unidade:
"Analisei, aguardando parecer jurídico", e o processo continua onde está.

Ciclo de vida:

1. **Rascunho** — uma minuta com `finalidade='despacho'`, escrita no editor
   do sistema (`services/minutas.py`). Só o autor a vê, nem na lista nem por
   id (`minutas.eh_rascunho_de_despacho_alheio`), e ela não aparece na linha
   do tempo: ainda não é ato.
2. **Concluir** (`concluir_despacho`) — o autor confirma com a senha, e numa
   transação só:
   - a movimentação DESPACHO entra na linha do tempo, na unidade onde o
     processo está, SEM mudar o local (`id_local_atual` não é tocado);
   - a minuta vira PDF anexado ao processo, ligado a essa movimentação;
   - o autor assina o PDF (mesma assinatura por senha do restante do
     sistema: hash do arquivo e código de validação pública);
   - os anexos enviados junto entram ligados à mesma movimentação.
   Senha errada não grava nada. Dois cliques: o segundo recebe 409.
3. **Concluído não se edita.** Correção é um novo despacho.

Quem pode concluir: o autor do rascunho, lotado na unidade onde o processo
está (super-usuário passa, como em receber). Não se despacha processo em
rascunho, arquivado (o caminho é desarquivar, RF-01) ou em trânsito (enquanto
o destino não recebe, não fica claro quem responde por ele).

O PDF e os anexos do despacho nascem NÃO públicos: o cidadão vê no portal que
houve um despacho, sem o texto nem o documento (decisão a confirmar na revisão
do SI-62).
"""
from __future__ import annotations

import html
import re
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Despacho, Minuta, Movimentacao, Processo, Usuario
from . import anexos as anexos_svc
from . import assinaturas as assinaturas_svc
from . import minutas as minutas_svc
from .acoes_processo import (
    AcaoError,
    _encaminhamento_pendente,
    _esta_arquivado,
    _get_acao,
    _lotado_em,
)
from .audit import log as audit_log


def texto_do_despacho(corpo_html: str) -> str:
    """Texto corrido do HTML do editor, para a linha do tempo (que mostra
    texto, não HTML). O documento fiel é o PDF assinado."""
    t = re.sub(r"(?i)<br\s*/?>", "\n", corpo_html or "")
    t = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|blockquote)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace("\xa0", " ")
    t = "\n".join(linha.rstrip() for linha in t.splitlines())
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _erro(codigo: int, detalhe: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=detalhe)


async def _ler_arquivos(arquivos: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Mesmas regras do upload manual (`anexos.upload_anexo`): nome,
    extensão permitida e tamanho máximo. Lidos ANTES de qualquer gravação."""
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    lidos: list[tuple[str, bytes]] = []
    for f in arquivos:
        if not f.filename:
            raise _erro(status.HTTP_400_BAD_REQUEST, "Arquivo sem nome")
        ext = anexos_svc._ext_of(f.filename)
        if ext not in anexos_svc.ALLOWED_EXTS:
            raise _erro(status.HTTP_400_BAD_REQUEST, f"Extensão '.{ext}' não permitida")
        conteudo = await f.read(max_bytes + 1)
        if len(conteudo) > max_bytes:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Arquivo {f.filename} excede {settings.max_upload_size_mb} MB",
            )
        lidos.append((f.filename, conteudo))
    return lidos


async def _exigir_que_possa_despachar(
    db: AsyncSession, processo: Processo, *, tenant_id: int, usuario: Usuario
) -> None:
    if processo.situacao == "rascunho":
        raise _erro(status.HTTP_409_CONFLICT,
                    "Processo em rascunho não recebe despacho. Abra o processo antes.")
    # Mesmas regras do resto da tramitação (`acoes_processo`): arquivado é ter
    # arquivamento EM VIGOR — desarquivado (SI-60) volta a receber despacho.
    if await _esta_arquivado(db, processo.id, tenant_id):
        raise _erro(status.HTTP_409_CONFLICT,
                    "Processo arquivado não recebe despacho.")
    if await _encaminhamento_pendente(db, processo.id, tenant_id) is not None:
        raise _erro(status.HTTP_409_CONFLICT,
                    "Processo em trânsito não recebe despacho. Aguarde o recebimento "
                    "ou cancele o encaminhamento.")

    if processo.id_local_atual is None:
        raise _erro(status.HTTP_409_CONFLICT,
                    "Processo sem unidade atual registrada — não dá para saber onde o "
                    "despacho é feito.")

    from .permissoes import load_permissions

    perms = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    if perms.is_super_usuario:
        return
    if not await _lotado_em(
        db, id_usuario=usuario.id, id_unidade=processo.id_local_atual, tenant_id=tenant_id
    ):
        raise _erro(status.HTTP_403_FORBIDDEN,
                    "Só quem é lotado na unidade onde o processo está pode despachar nele.")


async def concluir_despacho(
    db: AsyncSession,
    *,
    tenant_id: int,
    tenant_slug: str,
    minuta_id: int,
    usuario: Usuario,
    senha: str,
    arquivos: list[UploadFile],
    ip: str | None = None,
    user_agent: str | None = None,
) -> Despacho:
    """Ver o docstring do módulo. A rota já passou por
    `minutas.obter_minuta_autorizada` (prefeitura, sigilo e autoria)."""
    m = (
        await db.execute(
            select(Minuta).where(
                Minuta.id == minuta_id,
                Minuta.tenant_id == tenant_id,
                Minuta.excluido.is_(False),
            ).with_for_update()  # dois cliques: o segundo espera e cai no 409
        )
    ).scalar_one_or_none()
    if m is None or m.id_usuario_criacao != usuario.id:
        raise _erro(status.HTTP_404_NOT_FOUND, "Minuta não encontrada")
    if m.finalidade != "despacho":
        raise _erro(status.HTTP_409_CONFLICT, "Esta minuta não é um despacho.")
    if m.status != "rascunho":
        raise _erro(status.HTTP_409_CONFLICT, "Este despacho já foi concluído.")
    texto = texto_do_despacho(m.corpo_html or "")
    if not texto:
        raise _erro(status.HTTP_400_BAD_REQUEST,
                    "O despacho está vazio — escreva o texto antes de concluir.")

    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == m.id_processo,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one()
    await _exigir_que_possa_despachar(db, processo, tenant_id=tenant_id, usuario=usuario)
    lidos = await _ler_arquivos(arquivos)

    # Senha por último entre as checagens e antes de qualquer gravação: errada,
    # nada do despacho é gravado (só a tentativa, auditada).
    await assinaturas_svc.conferir_senha_para_assinar(
        db,
        tenant_id=tenant_id,
        usuario_id=usuario.id,
        senha=senha,
        chave_throttle=-m.id,
        entidade="minuta",
        id_entidade=m.id,
        id_processo=processo.id,
    )

    try:
        acao = await _get_acao(db, "DESPACHO")
    except AcaoError:
        raise _erro(status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Ação 'DESPACHO' não cadastrada — execute o seed_bootstrap.")

    agora = datetime.now()
    despacho = Despacho(
        tenant_id=tenant_id,
        id_processo=processo.id,
        despacho=texto,
        id_usuario=usuario.id,
        ativo=True,
        excluido=False,
    )
    db.add(despacho)
    await db.flush()
    mov = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo.id,
        # Fica onde está: a unidade da movimentação é a atual, e
        # `id_local_atual` não muda.
        id_unidade_responsavel=processo.id_local_atual,
        id_acao=acao.id,
        id_despacho=despacho.id,
        id_usuario=usuario.id,
        data_hora_movimentacao=agora,
        ativo=True,
        excluido=False,
    )
    db.add(mov)
    await db.flush()
    despacho.id_movimentacao = mov.id
    # Os anexos (o PDF e os enviados junto) se ligam à última movimentação.
    processo.id_ultima_movimentacao = mov.id

    anexo = await minutas_svc.virar_anexo_sem_commit(
        db, m, tenant_id=tenant_id, tenant_slug=tenant_slug,
        usuario_id=usuario.id, publico=False,
    )
    despacho.id_anexo = anexo.id
    for nome, conteudo in lidos:
        await anexos_svc._criar_anexo_from_bytes(
            db,
            processo.id,
            content=conteudo,
            filename=nome,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            descricao=nome,
            id_tipo_anexo=None,
            publico=False,
            usuario_id=usuario.id,
            commit=False,
            # Filhos do PDF do despacho: o vínculo pela movimentação não serve,
            # porque anexo enviado depois cairia nela também (migration 0142).
            id_anexo_principal=anexo.id,
        )

    await assinaturas_svc.autoassinar_sem_commit(
        db,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        processo_id=processo.id,
        anexo_id=anexo.id,
        usuario_id=usuario.id,
        id_unidade=processo.id_local_atual,
        ip=ip,
        user_agent=user_agent,
    )
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="despacho.concluido",
        entidade="despacho",
        id_entidade=despacho.id,
        payload={
            "id_processo": processo.id,
            "id_movimentacao": mov.id,
            "id_minuta": m.id,
            "id_anexo": anexo.id,
            "anexos_extras": len(lidos),
        },
    )
    await db.commit()
    await db.refresh(despacho)
    return despacho
