"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { api, type AdminTenantModulo } from "@/lib/api";

/**
 * Aba "Módulos" do admin de tenant (F2 Task 7). Contrata/descontrata os
 * módulos de UM tenant.
 *
 * Duas regras de backend que a UI tem que respeitar (services/modulos.py):
 *  - o PUT reconcilia: manda a lista COMPLETA do estado final, não o delta —
 *    por isso "salvar" recalcula os slugs marcados a partir do catálogo
 *    inteiro, na ordem do catálogo, e não de um histórico de cliques;
 *  - descontratar é soft-delete (`excluido = true`, nunca some a linha) —
 *    é por isso que um módulo inativo pode ser descontratado mesmo não
 *    podendo ser (re)contratado: o vínculo "morto" continua existindo.
 */
export function TenantModulosTab({ tenantId }: { tenantId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const q = useQuery({
    queryKey: ["admin-tenant-modulos", tenantId],
    queryFn: () => api.adminTenantModulos(tenantId),
  });

  // Estado local de edição: slugs marcados. Inicializa a partir do que veio
  // contratado do servidor e só é resetado quando o servidor manda dado novo.
  const [selecionados, setSelecionados] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (q.data) {
      setSelecionados(new Set(q.data.filter((m) => m.contratado).map((m) => m.slug)));
    }
  }, [q.data]);

  function alternar(modulo: AdminTenantModulo) {
    setSelecionados((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(modulo.slug)) {
        proximo.delete(modulo.slug); // descontratar: sempre permitido, mesmo inativo
      } else {
        // Contratar módulo inativo é recusado (services/modulos.py::contratar).
        // Hoje inalcançável — o `disabled` do Checkbox já bloqueia o clique —
        // mas se essa condição um dia sair, `return atual` (mesma referência)
        // faria o React pular o re-render: o checkbox nativo ficaria marcado
        // visualmente sem o estado ter mudado, mentindo pro usuário. Um Set
        // novo, mesmo com o mesmo conteúdo, garante o re-render correto.
        if (!modulo.ativo) return new Set(atual);
        proximo.add(modulo.slug);
      }
      return proximo;
    });
  }

  const salvar = useMutation({
    mutationFn: (slugs: string[]) => api.adminTenantContratarModulos(tenantId, slugs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenant-modulos", tenantId] });
      toast.success("Contratação de módulos atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function handleSalvar() {
    const catalogo = q.data ?? [];
    // Ordem do catálogo, não ordem de clique — o PUT reconcilia com a lista
    // inteira, e a ordem aqui não importa pro backend, mas importa pra não
    // depender de iteração de Set (que segue ordem de inserção).
    const slugs = catalogo.filter((m) => selecionados.has(m.slug)).map((m) => m.slug);
    const contratadosNoServidor = new Set(catalogo.filter((m) => m.contratado).map((m) => m.slug));
    const descontratando = catalogo
      .filter((m) => contratadosNoServidor.has(m.slug) && !selecionados.has(m.slug))
      .map((m) => m.nome);

    if (descontratando.length > 0) {
      const ok = await confirm({
        title: "Descontratar módulo",
        message: (
          <>
            <p>
              Ao salvar, este tenant perde o acesso a <strong>{descontratando.join(", ")}</strong>{" "}
              agora — escrita e leitura. Os usuários dele passam a receber erro de
              permissão (403) em qualquer tela desses módulos.
            </p>
            <p className="mt-2">
              Nenhum dado é apagado: a contratação pode ser refeita depois e o que
              foi produzido enquanto o módulo estava ativo permanece.
            </p>
          </>
        ),
        confirmLabel: "Descontratar e salvar",
        intent: "danger",
      });
      if (!ok) return;
    }

    salvar.mutate(slugs);
  }

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground" role="status">Carregando…</p>;
  }
  if (q.isError) {
    return (
      <p className="text-sm text-danger" role="alert">
        Não foi possível carregar os módulos deste tenant.
        {q.error instanceof Error ? ` (${q.error.message})` : ""}
      </p>
    );
  }
  if (!q.data || q.data.length === 0) {
    return <p className="text-sm text-muted-foreground">Nenhum módulo contratável no catálogo.</p>;
  }

  return (
    <div className="max-w-2xl space-y-4">
      <p className="text-sm text-muted-foreground">
        Descontratar não apaga dados — apenas suspende o acesso do tenant ao módulo.
        Os dados permanecem e a contratação pode ser refeita a qualquer momento.
      </p>

      <ul className="divide-y divide-border rounded-md border border-border">
        {q.data.map((m) => {
          const marcado = selecionados.has(m.slug);
          const inputId = `modulo-${m.slug}`;
          return (
            <li key={m.slug} className="flex items-center justify-between gap-3 p-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  id={inputId}
                  checked={marcado}
                  disabled={!m.ativo && !marcado}
                  onChange={() => alternar(m)}
                />
                <Label htmlFor={inputId} className="cursor-pointer text-sm font-medium text-foreground">
                  {m.nome}
                </Label>
              </div>
              {!m.ativo && (
                <span className="text-xs text-muted-foreground">
                  Módulo inativo na plataforma{marcado ? " — pode descontratar, não pode recontratar" : ""}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <Button type="button" onClick={handleSalvar} disabled={salvar.isPending}>
        {salvar.isPending ? "Salvando…" : "Salvar"}
      </Button>
    </div>
  );
}
