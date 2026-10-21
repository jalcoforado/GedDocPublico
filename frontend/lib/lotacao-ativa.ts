"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useToast } from "@/components/ui/toast";
import type { LotacaoOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface LotacaoAtiva {
  /** Principal + secundárias, na ordem do backend (principal primeiro). */
  lotacoes: LotacaoOut[];
  /** Id da lotação ativa: a do token, caindo na principal. */
  ativaId: number | null;
  /** A lotação ativa resolvida, ou `null` quando o usuário não tem lotação. */
  ativa: LotacaoOut | null;
  /** Só há troca com 2+ lotações: com uma só não há o que escolher. */
  podeTrocar: boolean;
  trocando: boolean;
  selecionar: (id: number) => Promise<void>;
}

/**
 * E1 (benchmark SUiTE) — o "alterar setor": a regra da lotação ativa num
 * lugar só. O cabeçalho (`UnidadeAtiva`) e o menu da conta (`AvatarDropdown`)
 * consomem daqui; duas cópias divergiriam, e o sintoma seria um mostrar uma
 * unidade e o outro, outra.
 *
 * Trocar invalida TODAS as queries, e não só painel/caixas/processos: o
 * backend conta caixas e painel pela lotação ativa, e as permissões também
 * mudam com ela (vínculo de grupo por lotação, `load_permissions`). Listar
 * as chaves à mão deixaria de fora a próxima tela que depender da unidade —
 * e o sintoma seria número velho sem erro nenhum.
 */
export function useLotacaoAtiva(): LotacaoAtiva {
  const { user, trocarLotacao } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [trocando, setTrocando] = useState(false);

  // `?? []` porque telas/testes que montam `user` à mão nem sempre
  // preenchem o campo.
  const lotacoes = user?.lotacoes ?? [];
  // A unidade do token só vale se ainda for uma lotação do usuário; senão,
  // a principal. O `/auth/me` já devolve a unidade reconferida
  // (`resolver_unidade_ativa`), mas o `user` pode ser de antes de o admin
  // tirar a lotação — e uma ativa que não está na lista some do cabeçalho e
  // deixa a lista sem item marcado, enquanto os números já são da principal.
  const pedida = user?.unidade_contexto_id ?? user?.id_unidade_trabalho ?? null;
  const ativa =
    lotacoes.find((l) => l.id === pedida) ?? lotacoes.find((l) => l.principal) ?? null;
  const ativaId = ativa?.id ?? null;

  async function selecionar(id: number) {
    if (id === ativaId || trocando) return;
    setTrocando(true);
    try {
      await trocarLotacao(id);
      await qc.invalidateQueries();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível trocar de setor.");
    } finally {
      setTrocando(false);
    }
  }

  return {
    lotacoes,
    ativaId,
    ativa,
    podeTrocar: lotacoes.length > 1,
    trocando,
    selecionar,
  };
}
