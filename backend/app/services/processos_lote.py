"""Ações em lote sobre processos selecionados na lista (pedido da reunião de
2026-10-20, item 2.2).

Cada processo passa pela MESMA função da ação individual (`acoes_processo`) e
pelo MESMO guard de sigilo da rota individual (`assert_acesso_processo`): o
lote não é um caminho com regra própria, é a ação de um processo repetida. Se
uma regra nova entrar em `receber`, ela vale no lote sem tocar aqui.

**Cada processo é independente.** Não é tudo-ou-nada: receber 20 processos e
falhar no 7º (o destino era outra unidade) não deve desfazer os outros 19 —
quem selecionou quer saber quais foram e quais não. Os serviços já comitam
por conta própria; uma falha faz `rollback` só do processo que falhou, e o
resultado diz, um a um, o que aconteceu.

**Processo fora do sigilo de quem pede vira "não encontrado"**, como na rota
individual: dizer "sem permissão" confirmaria que ele existe.
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Usuario
from ..schemas.processo import ItemDoLote, LoteRequest, LoteResultado
from . import acoes_processo as acoes
from .sigilo import SigiloAcessoError, assert_acesso_processo


async def _aplicar(
    db: AsyncSession, processo_id: int, pedido: LoteRequest, *,
    tenant_id: int, usuario: Usuario, is_super_usuario: bool,
) -> None:
    comum = {"tenant_id": tenant_id, "usuario_id": usuario.id}  # `usuario` = o retrato abaixo
    if pedido.acao == "receber":
        await acoes.receber(db, processo_id, is_super_usuario=is_super_usuario, **comum)
    elif pedido.acao == "encaminhar":
        await acoes.encaminhar(
            db, processo_id, pedido.encaminhar, is_super_usuario=is_super_usuario, **comum)
    elif pedido.acao == "atribuir_responsavel":
        await acoes.atribuir_responsavel(
            db, processo_id, id_usuario=pedido.responsavel.id_usuario, **comum)
    elif pedido.acao == "arquivar":
        await acoes.arquivar(
            db, processo_id, pedido.arquivar, is_super_usuario=is_super_usuario, **comum)
    else:  # pragma: no cover — o Literal do schema não deixa chegar aqui
        raise acoes.AcaoError(f"Ação desconhecida: {pedido.acao}")


async def executar_lote(
    db: AsyncSession, pedido: LoteRequest, *,
    tenant_id: int, usuario: Usuario, is_super_usuario: bool,
) -> LoteResultado:
    itens: list[ItemDoLote] = []
    # Retrato do usuário tirado UMA vez: o `rollback` de um processo que
    # falha expira os objetos da sessão, e ler `usuario.id` depois dele
    # dispararia uma carga síncrona no meio do laço assíncrono.
    usuario = SimpleNamespace(
        id=usuario.id, nivel_acesso_sigilo=getattr(usuario, "nivel_acesso_sigilo", None))
    for processo_id in pedido.ids:
        try:
            await assert_acesso_processo(
                db, tenant_id=tenant_id, processo_id=processo_id, usuario=usuario)
            await _aplicar(
                db, processo_id, pedido, tenant_id=tenant_id, usuario=usuario,
                is_super_usuario=is_super_usuario)
            # Arquivar e atribuir não comitam (a rota individual conta com o
            # commit do fim do request); aqui cada processo fecha o seu.
            await db.commit()
            itens.append(ItemDoLote(id=processo_id, ok=True))
        except SigiloAcessoError:
            await db.rollback()
            itens.append(ItemDoLote(id=processo_id, ok=False, erro="Processo não encontrado"))
        except acoes.AcaoError as e:
            await db.rollback()
            itens.append(ItemDoLote(id=processo_id, ok=False, erro=str(e)))
    ok = sum(1 for i in itens if i.ok)
    return LoteResultado(itens=itens, concluidos=ok, falhas=len(itens) - ok)
