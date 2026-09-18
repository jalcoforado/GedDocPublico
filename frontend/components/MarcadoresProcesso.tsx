"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Tag } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover } from "@/components/ui/popover";
import { useToast } from "@/components/ui/toast";
import { api, type ProcessoDetail } from "@/lib/api";

/**
 * F5 — badges de marcador no processo + edição do conjunto (substitui tudo
 * de uma vez, espelhando `DefinirMarcadoresRequest` do backend: mais simples
 * no cliente do que marcar/desmarcar um a um).
 */
export function MarcadoresProcesso({
  processo,
  podeEditar,
}: {
  processo: ProcessoDetail;
  podeEditar: boolean;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);

  const catalogoQ = useQuery({
    queryKey: ["marcadores-catalogo"],
    queryFn: () => api.marcadores.list(),
    enabled: open,
  });

  const [selecao, setSelecao] = useState<number[] | null>(null);
  const idsAtuais = selecao ?? processo.marcadores.map((m) => m.id);

  const m = useMutation({
    mutationFn: (ids: number[]) => api.processos.definirMarcadores(processo.id, ids),
    onSuccess: (atualizado) => {
      qc.setQueryData(["processo", processo.id], atualizado);
      qc.invalidateQueries({ queryKey: ["processos"] });
      setOpen(false);
      setSelecao(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function toggle(id: number) {
    const atual = new Set(idsAtuais);
    if (atual.has(id)) atual.delete(id);
    else atual.add(id);
    setSelecao(Array.from(atual));
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {processo.marcadores.map((mk) => (
        <Badge
          key={mk.id}
          style={{ backgroundColor: `${mk.cor}22`, color: mk.cor }}
        >
          {mk.nome}
        </Badge>
      ))}
      {podeEditar && (
        <>
          <button
            ref={anchorRef}
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Editar marcadores"
            title="Editar marcadores"
            className="inline-flex h-6 w-6 items-center justify-center rounded-full text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Tag className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <Popover open={open} anchorRef={anchorRef} onClose={() => setOpen(false)}>
            <div className="w-64 space-y-2 p-3">
              <p className="text-xs font-semibold text-foreground-muted">Marcadores</p>
              {catalogoQ.isLoading && (
                <p className="text-xs text-foreground-muted">Carregando…</p>
              )}
              {catalogoQ.data?.length === 0 && (
                <p className="text-xs text-foreground-muted">
                  Nenhum marcador cadastrado no tenant.
                </p>
              )}
              <div className="max-h-56 space-y-1 overflow-y-auto">
                {catalogoQ.data?.map((mk) => (
                  <label
                    key={mk.id}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-muted"
                  >
                    <Checkbox
                      checked={idsAtuais.includes(mk.id)}
                      onChange={() => toggle(mk.id)}
                    />
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: mk.cor }}
                      aria-hidden="true"
                    />
                    {mk.nome}
                  </label>
                ))}
              </div>
              <div className="flex justify-end gap-1.5 pt-1">
                <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  size="sm"
                  loading={m.isPending}
                  onClick={() => m.mutate(idsAtuais)}
                >
                  Salvar
                </Button>
              </div>
            </div>
          </Popover>
        </>
      )}
    </div>
  );
}
