"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { fmtDataHora } from "@/components/pagamentos/format";
import { api, type ChecklistItemDebito } from "@/lib/api";

export const chaveChecklist = (id: number) => ["pag-checklist", id] as const;

/** Itens obrigatórios ainda não conferidos — o que trava a validação financeira. */
export function pendentesDoChecklist(itens: ChecklistItemDebito[] | undefined): ChecklistItemDebito[] {
  return (itens ?? []).filter((i) => i.obrigatorio && !i.marcado);
}

/**
 * Conferência documental do débito (RF-VAL-01/06).
 *
 * A validação financeira recusa o débito enquanto houver item obrigatório
 * pendente, e até esta seção existir não havia onde marcá-los: o débito criado
 * pela tela parava para sempre em "aguardando validação".
 *
 * `editavel` vem de quem monta a tela (permissão + etapa). É UX: quem decide se
 * a marcação vale é o backend.
 */
export function ChecklistDebito({ id, editavel }: { id: number; editavel: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();

  const q = useQuery({
    queryKey: chaveChecklist(id),
    queryFn: () => api.pagamentos.debitos.checklist(id),
  });

  const marcarM = useMutation({
    mutationFn: (v: { id_checklist_item: number; marcado: boolean }) =>
      api.pagamentos.debitos.marcarChecklist(id, v),
    // O POST devolve o checklist inteiro, já no estado novo.
    onSuccess: (itens) => qc.setQueryData(chaveChecklist(id), itens),
    onError: (err: Error) => toast.error(err.message || "Erro ao marcar o item"),
  });

  const itens = q.data ?? [];
  const pendentes = pendentesDoChecklist(itens);

  return (
    <SectionCard title="Conferência de documentos" icon={ListChecks}>
      {q.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : q.isError ? (
        <p className="text-sm text-foreground-subtle">
          Não foi possível carregar a conferência de documentos.
        </p>
      ) : itens.length === 0 ? (
        <p className="text-sm text-foreground-subtle">
          Nenhum item de conferência se aplica a esta solicitação.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-foreground-muted" role="status">
            {pendentes.length === 0
              ? "Todos os itens obrigatórios foram conferidos."
              : pendentes.length === 1
                ? "Falta 1 item obrigatório para a validação financeira."
                : `Faltam ${pendentes.length} itens obrigatórios para a validação financeira.`}
          </p>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {itens.map((item) => (
              <li key={item.id_checklist_item} className="flex items-start gap-3 px-3 py-2.5">
                <input
                  id={`checklist-${item.id_checklist_item}`}
                  type="checkbox"
                  checked={item.marcado}
                  disabled={!editavel || marcarM.isPending}
                  onChange={(e) =>
                    marcarM.mutate({
                      id_checklist_item: item.id_checklist_item,
                      marcado: e.target.checked,
                    })
                  }
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-border-strong accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
                />
                <div className="min-w-0 flex-1">
                  <label
                    htmlFor={`checklist-${item.id_checklist_item}`}
                    className="text-sm text-foreground"
                  >
                    {item.descricao}
                  </label>
                  {item.atualizado_em && (
                    <p className="text-xs text-foreground-muted">
                      {item.marcado ? "Conferido" : "Desmarcado"} em {fmtDataHora(item.atualizado_em)}
                      {item.observacao ? ` — ${item.observacao}` : ""}
                    </p>
                  )}
                </div>
                <Badge intent={item.obrigatorio ? "warning" : "neutral"}>
                  {item.obrigatorio ? "Obrigatório" : "Opcional"}
                </Badge>
              </li>
            ))}
          </ul>
          {!editavel && pendentes.length > 0 && (
            <p className="text-xs text-foreground-muted">
              A conferência é feita pela validação financeira, quando a solicitação chega a essa etapa.
            </p>
          )}
        </div>
      )}
    </SectionCard>
  );
}
