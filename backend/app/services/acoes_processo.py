"""Ações de tramitação: encaminhar, receber, cancelar encaminhamento.

Espelha o fluxo de aprimora/app/models/Processo.php:
- Encaminhar (flag ENCAMINHAMENTO): cria movimentação + encaminhamento + despacho opcional.
  id_local_atual NÃO muda no encaminhamento — o processo continua "fisicamente"
  na unidade de origem até o destinatário confirmar o recebimento.
- Receber (flag RECEBIMENTO): marca o encaminhamento pendente como recebido,
  cria nova movimentação, e SÓ ENTÃO atualiza id_local_atual.
- Cancelar (sem flag dedicada — usa registro lógico): só permite cancelar
  encaminhamento ainda não recebido. Mantém histórico (não deleta).

Fase 13a: recebe `tenant_id` e propaga em todas as escritas e filtra leituras.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Acao,
    Arquivamento,
    Despacho,
    Encaminhamento,
    Movimentacao,
    Processo,
    StatusArquivamento,
    Tenant,
    Usuario,
    UsuarioUnidadeTrabalho,
)
from ..schemas.processo import (
    ArquivarRequest,
    CancelarEncaminhamentoRequest,
    EncaminharRequest,
)


class AcaoError(Exception):
    pass


class WorkflowStrictBlock(AcaoError):
    """Ação bloqueada pelo workflow strict. 400 com instrução de override."""

    pass


async def _get_acao(db: AsyncSession, flag: str) -> Acao:
    """Acao é catálogo global — sem tenant_id."""
    acao = (
        await db.execute(
            select(Acao).where(
                Acao.flag == flag,
                Acao.excluido.is_(False),
                Acao.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if acao is None:
        raise AcaoError(f"Ação '{flag}' não cadastrada em protocolos.acao")
    return acao


async def _get_processo(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise AcaoError(f"Processo {processo_id} não encontrado")
    if not p.ativo:
        raise AcaoError("Processo inativo — não permite movimentação")
    return p


async def encaminhar(
    db: AsyncSession,
    processo_id: int,
    payload: EncaminharRequest,
    *,
    tenant_id: int,
    usuario_id: int,
    is_super_usuario: bool = False,
) -> Encaminhamento:
    processo = await _get_processo(db, processo_id, tenant_id)

    # E3 (benchmark SUiTE) — primeira tramitação de um rascunho emite o
    # número (+ NUP, se opt-in) e marca situacao='protocolado'. Workflow só
    # é instanciado aqui, não na criação (ver abertura_processo.py) — pra
    # fins de BPM o processo "nasce" agora, não quando era rascunho.
    era_rascunho = processo.situacao == "rascunho"
    if era_rascunho:
        from .audit import log as audit_log
        from .numeracao_processo import emitir_numero

        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            raise AcaoError("Tenant não encontrado")

        await emitir_numero(
            db, processo, tenant=tenant, usuario_id=usuario_id, now=datetime.now()
        )
        processo.situacao = "protocolado"

        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="processo.numerado_na_tramitacao",
            entidade="processo",
            id_entidade=processo.id,
            payload={"numero_processo": processo.numero_processo},
        )

    # Workflow strict: valida se o encaminhamento respeita o fluxo.
    from .workflow_integration import validar_acao_strict

    ok, motivo = await validar_acao_strict(
        db,
        processo,
        acao="encaminhar",
        id_unidade_destino=payload.id_unidade_destino,
    )
    if not ok:
        if not (is_super_usuario and payload.override_motivo):
            raise WorkflowStrictBlock(
                motivo
                or "Workflow strict bloqueou a ação. Super-usuário pode usar 'override_motivo'."
            )
        # Override registrado — audit do override
        from .audit import log as audit_log

        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="processo.encaminhar.override_strict",
            entidade="processo",
            id_entidade=processo_id,
            payload={
                "id_unidade_destino": payload.id_unidade_destino,
                "motivo": payload.override_motivo,
                "bloqueio_original": motivo,
            },
        )

    # Bloqueia se há encaminhamento pendente (não recebido e não cancelado).
    pendente = (
        await db.execute(
            select(Encaminhamento).where(
                Encaminhamento.id_processo == processo_id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.excluido.is_(False),
                Encaminhamento.recebido.is_(False),
                Encaminhamento.cancelado.is_(False),
            )
        )
    ).scalar_one_or_none()
    if pendente:
        raise AcaoError(
            "Já existe encaminhamento pendente. Cancele-o ou aguarde o recebimento."
        )

    acao = await _get_acao(db, "ENCAMINHAMENTO")
    now = datetime.now()
    unidade_origem = processo.id_local_atual or processo.id_unidade_proprietaria

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_unidade_responsavel=unidade_origem,
        id_acao=acao.id,
        id_usuario=usuario_id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    encaminhamento = Encaminhamento(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_unidade_origem=unidade_origem,
        id_unidade_destino=payload.id_unidade_destino,
        id_prioridade=payload.id_prioridade,
        quantidade_folhas=payload.quantidade_folhas,
        data_prazo=payload.data_prazo,
        externo=False,
        recebido=False,
        cancelado=False,
        id_usuario=usuario_id,
        id_movimentacao=movimentacao.id,
        ativo=True,
        excluido=False,
    )
    db.add(encaminhamento)

    if payload.despacho:
        db.add(
            Despacho(
                tenant_id=tenant_id,
                id_processo=processo_id,
                despacho=payload.despacho,
                id_usuario=usuario_id,
                id_movimentacao=movimentacao.id,
                ativo=True,
                excluido=False,
            )
        )

    movimentacao.id_encaminhamento = None  # ligação inversa é via encaminhamento.id_movimentacao
    processo.id_ultima_movimentacao = movimentacao.id

    await db.commit()
    await db.refresh(encaminhamento)

    if era_rascunho:
        # Processo acabou de ganhar número — instancia workflow agora
        # (mesma chamada que abertura_processo.py faz pra processo
        # não-rascunho), não dispara "encaminhamento" contra instance que
        # acabou de nascer no estado inicial.
        from .workflow_integration import auto_iniciar_workflow_se_aplicavel

        await auto_iniciar_workflow_se_aplicavel(db, processo, usuario_id)
    else:
        # (Fase 20b) Dispara evento de workflow, se houver instance ativa
        from .workflow_integration import disparar_evento

        await disparar_evento(db, processo, "encaminhamento", usuario_id)

    return encaminhamento


async def receber(
    db: AsyncSession,
    processo_id: int,
    *,
    tenant_id: int,
    usuario_id: int,
    is_super_usuario: bool = False,
    override_motivo: str | None = None,
) -> Encaminhamento:
    processo = await _get_processo(db, processo_id, tenant_id)

    # Workflow strict (receber é menos restritivo — só audita se há override)
    from .workflow_integration import validar_acao_strict

    ok, motivo = await validar_acao_strict(db, processo, acao="receber")
    if not ok and not (is_super_usuario and override_motivo):
        raise WorkflowStrictBlock(
            motivo or "Workflow strict bloqueou o recebimento."
        )

    enc = (
        await db.execute(
            select(Encaminhamento)
            .where(
                Encaminhamento.id_processo == processo_id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.excluido.is_(False),
                Encaminhamento.recebido.is_(False),
                Encaminhamento.cancelado.is_(False),
            )
            .order_by(Encaminhamento.id.desc())
        )
    ).scalar_one_or_none()
    if enc is None:
        raise AcaoError("Nenhum encaminhamento pendente para este processo")

    acao = await _get_acao(db, "RECEBIMENTO")
    now = datetime.now()

    enc.recebido = True
    enc.data_hora_recebimento = now

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_unidade_responsavel=enc.id_unidade_destino,
        id_acao=acao.id,
        id_usuario=usuario_id,
        id_encaminhamento=enc.id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    # Só aqui o processo "muda de lugar".
    processo.id_local_atual = enc.id_unidade_destino
    processo.id_ultima_movimentacao = movimentacao.id

    # Audit (Fase 24)
    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.recebido",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_encaminhamento": enc.id,
            "id_unidade_destino": enc.id_unidade_destino,
        },
    )

    await db.commit()
    await db.refresh(enc)

    # (Fase 20b) Dispara evento de workflow
    from .workflow_integration import disparar_evento

    await disparar_evento(db, processo, "recebimento", usuario_id)

    return enc


async def cancelar_encaminhamento(
    db: AsyncSession,
    encaminhamento_id: int,
    payload: CancelarEncaminhamentoRequest,
    *,
    tenant_id: int,
    usuario_id: int,
) -> Encaminhamento:
    enc = (
        await db.execute(
            select(Encaminhamento).where(
                Encaminhamento.id == encaminhamento_id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if enc is None:
        raise AcaoError(f"Encaminhamento {encaminhamento_id} não encontrado")
    if enc.recebido:
        raise AcaoError("Não pode cancelar encaminhamento já recebido")
    if enc.cancelado:
        raise AcaoError("Encaminhamento já estava cancelado")

    enc.cancelado = True
    # Mantém id_local_atual onde estava (origem) — encaminhamento não chegou a mudar.

    if payload.despacho:
        db.add(
            Despacho(
                tenant_id=tenant_id,
                id_processo=enc.id_processo,
                despacho=f"[Cancelamento de encaminhamento] {payload.despacho}",
                id_usuario=usuario_id,
                id_movimentacao=enc.id_movimentacao,
                ativo=True,
                excluido=False,
            )
        )

    await db.commit()
    await db.refresh(enc)
    return enc


async def _lotado_em(
    db: AsyncSession,
    *,
    id_usuario: int,
    id_unidade: int,
    tenant_id: int,
) -> bool:
    """O usuário está lotado nesta unidade, por qualquer das DUAS formas?

    Lotação neste sistema tem duas representações simultâneas e ambas valem:

    - `utils.usuario.id_unidade_trabalho` — a principal, uma só;
    - `utils.usuario_unidade_trabalho` — as demais, N:N, editáveis pela tela de
      usuário (`PUT /usuarios/{id}/unidades`).

    Conferir só a principal foi a primeira versão desta função, e estava errada:
    rejeitaria designar alguém que está legitimamente no setor pela lotação
    secundária — o caso do servidor que atua em dois lugares, que é justamente
    por que a tabela N:N existe.
    """
    alvo = (
        await db.execute(
            select(Usuario.id_unidade_trabalho).where(
                Usuario.id == id_usuario, Usuario.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if alvo == id_unidade:
        return True
    extra = (
        await db.execute(
            select(UsuarioUnidadeTrabalho.id).where(
                UsuarioUnidadeTrabalho.id_usuario == id_usuario,
                UsuarioUnidadeTrabalho.id_unidade_trabalho == id_unidade,
                UsuarioUnidadeTrabalho.tenant_id == tenant_id,
                UsuarioUnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    return extra is not None


async def atribuir_responsavel(
    db: AsyncSession,
    processo_id: int,
    *,
    tenant_id: int,
    id_usuario: int | None,
    usuario_id: int,
) -> Processo:
    """Designa (ou desdesigna) quem responde pelo processo. Fatia F2.

    `id_usuario=None` devolve o processo ao estado **pendente de designação**,
    que é um estado legítimo e não a ausência de um: é o que faz um processo
    aparecer como "sem dono" na fila da unidade, em vez de sumir do radar por
    estar atribuído a alguém que ninguém lembra.

    A regra do mesmo setor
    ----------------------
    O designado tem de estar lotado na unidade onde o processo ESTÁ
    (`id_local_atual`). Sem isso, "atribuir" viraria um jeito de empurrar
    trabalho para fora da própria unidade sem tramitar — o processo continuaria
    na minha mesa, com o nome de outro na coluna, e a permanência (F1) contaria
    o tempo para a unidade errada.

    A regra vale para todos, inclusive super-usuário: quem precisa designar
    alguém de outro setor tem o caminho normal, que é encaminhar o processo
    para lá. Abrir exceção por papel criaria política de acesso paralela.

    Processo sem `id_local_atual` (legado, ou aberto antes do primeiro
    encaminhamento) não tem setor contra o que conferir, e aí a regra não se
    aplica — barrar seria impedir designação em processo recém-aberto, que é
    exatamente quando ela é mais útil.

    Não cria movimentação. Designar não é tramitar: o processo não muda de
    lugar e a linha do tempo de tramitação continuaria dizendo a verdade sem
    isto. O registro vai para `audit_log`, que é onde moram os atos que não são
    movimentação.
    """
    processo = await _get_processo(db, processo_id, tenant_id)

    anterior = processo.id_usuario_responsavel
    if anterior == id_usuario:
        # Idempotente: reatribuir a mesma pessoa não gera entrada de auditoria
        # nem toca a linha. Sem isto, um duplo clique vira duas entradas.
        return processo

    if id_usuario is not None:
        alvo = (
            await db.execute(
                select(Usuario).where(
                    Usuario.id == id_usuario,
                    Usuario.tenant_id == tenant_id,
                    Usuario.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        # Same-tenant explícito: a FK do Postgres aponta para `utils.usuario` e
        # NÃO filtra por tenant. Sem esta checagem daria para atribuir um
        # processo a um usuário de outra prefeitura informando o id dele.
        if alvo is None:
            raise AcaoError("Usuário não encontrado neste tenant")
        if processo.id_local_atual is not None and not await _lotado_em(
            db,
            id_usuario=alvo.id,
            id_unidade=processo.id_local_atual,
            tenant_id=tenant_id,
        ):
            raise AcaoError(
                "O responsável precisa estar lotado na unidade onde o processo "
                "está. Para designar alguém de outro setor, encaminhe o "
                "processo para lá."
            )

    processo.id_usuario_responsavel = id_usuario

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.responsavel_atribuido"
        if id_usuario is not None
        else "processo.responsavel_removido",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_usuario_responsavel_anterior": anterior,
            "id_usuario_responsavel": id_usuario,
        },
    )

    await db.commit()
    await db.refresh(processo)
    return processo


async def arquivar(
    db: AsyncSession,
    processo_id: int,
    payload: ArquivarRequest,
    *,
    tenant_id: int,
    usuario_id: int,
    is_super_usuario: bool = False,
) -> Arquivamento:
    """Encerra o processo por arquivamento. Fatia F4.

    Por que isto faltava, e o que destrava
    --------------------------------------
    O lado da LEITURA já estava inteiro e em produção; o da escrita nunca
    existiu. Seis lugares de `services/dashboard.py` contam arquivados,
    `services/cidadao_processos.py` diz "concluído" ao cidadão e
    `services/processos.py` deriva `data_conclusao` — todos por
    `Movimentacao.id_arquivamento IS NOT NULL`, que nenhum caminho preenchia.

    Consequência medida em 2026-09-16: 0 linhas em `protocolos.arquivamento`, o
    KPI "arquivados" zerado **por construção**, o "tempo médio de conclusão"
    sempre nulo, e os status `concluido_no_prazo`/`concluido_atrasado` de
    `PrazoInfo` inalcançáveis. A F1 (permanência) só consegue fechar um
    processo — `em_curso=false` — depois disto existir.

    O formato gravado aqui é exatamente o que aqueles seis leitores esperam:
    uma `Movimentacao` com `id_acao=ARQUIVAMENTO` e `id_arquivamento` apontando
    para a linha nova. Nada nos leitores muda.

    O que NÃO faz
    -------------
    **Não mexe em `processo.ativo`.** Nada no app escreve esse campo (as 3
    linhas `false` no banco vêm de seed/legado), e o filtro `apenas_ativos` da
    lista o consulta. Acoplá-lo ao arquivamento mudaria em silêncio o que as
    listas existentes mostram, apoiado numa suposição sobre o que `ativo`
    significa. É pergunta de negócio, não detalhe de implementação.

    **Não desarquiva.** Não é esquecimento: os leitores filtram por
    `id_arquivamento IS NOT NULL` **sem** olhar `Movimentacao.excluido`, então
    "desarquivar" por soft-delete não desfaria nada nas contagens. Fazer
    direito exige decidir antes se aqueles seis lugares passam a filtrar
    `excluido` — mudança de comportamento em métrica existente, que não cabe
    nesta fatia.
    """
    processo = await _get_processo(db, processo_id, tenant_id)

    ja_arquivado = (
        await db.execute(
            select(Movimentacao.id).where(
                Movimentacao.id_processo == processo_id,
                Movimentacao.tenant_id == tenant_id,
                Movimentacao.id_arquivamento.is_not(None),
                Movimentacao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ja_arquivado is not None:
        # Não é idempotente de propósito: arquivar duas vezes criaria dois
        # eventos de conclusão, e o "tempo médio de conclusão" do dashboard
        # passaria a contar o mesmo processo duas vezes com datas diferentes.
        raise AcaoError("Processo já está arquivado")

    from .workflow_integration import validar_acao_strict

    ok, bloqueio = await validar_acao_strict(db, processo, acao="arquivar")
    if not ok and not (is_super_usuario and payload.override_motivo):
        raise WorkflowStrictBlock(
            bloqueio or "Workflow strict bloqueou o arquivamento."
        )

    acao = await _get_acao(db, "ARQUIVAMENTO")
    status_id = (
        await db.execute(
            select(StatusArquivamento.id).where(
                StatusArquivamento.ativo.is_(True),
                StatusArquivamento.excluido.is_(False),
            ).order_by(StatusArquivamento.id).limit(1)
        )
    ).scalar_one_or_none()
    if status_id is None:
        # Catálogo global garantido pelo `seed_bootstrap`. Mensagem explícita
        # porque a alternativa é um `IntegrityError` cru de FK, que não diz o
        # que fazer.
        raise AcaoError(
            "Catálogo `protocolos.status_arquivamento` vazio — rode "
            "`python -m app.cli.seed_bootstrap`"
        )

    now = datetime.now()

    arquivamento = Arquivamento(
        tenant_id=tenant_id,
        id_status_arquivamento=status_id,
        motivo=payload.motivo,
        local=payload.local,
        estante=payload.estante,
        prateleira=payload.prateleira,
        caixa=payload.caixa,
        pasta=payload.pasta,
        permanente=payload.permanente,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
    )
    db.add(arquivamento)
    await db.flush()

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_unidade_responsavel=processo.id_local_atual
        or processo.id_unidade_proprietaria,
        id_acao=acao.id,
        id_usuario=usuario_id,
        id_arquivamento=arquivamento.id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    arquivamento.movimentacao_id = movimentacao.id
    processo.id_ultima_movimentacao = movimentacao.id

    if payload.observacao:
        db.add(
            Despacho(
                tenant_id=tenant_id,
                id_processo=processo_id,
                despacho=payload.observacao,
                id_usuario=usuario_id,
                id_movimentacao=movimentacao.id,
                ativo=True,
                excluido=False,
            )
        )

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.arquivado",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_arquivamento": arquivamento.id,
            "motivo": payload.motivo,
            "permanente": payload.permanente,
            "override_motivo": payload.override_motivo,
        },
    )

    await db.commit()
    await db.refresh(arquivamento)
    return arquivamento
