"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { notificacoesApi, type Notificacao } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtRel(s: string) {
  const d = new Date(s);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "agora";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export function NotificacoesBell() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  const q = useQuery({
    queryKey: ["notificacoes", "me"],
    queryFn: () => notificacoesApi.listarMinhas({ limit: 30 }),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const marcarLida = useMutation({
    mutationFn: (id: number) => notificacoesApi.marcarLida(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificacoes", "me"] }),
  });

  const marcarTodas = useMutation({
    mutationFn: () => notificacoesApi.marcarTodasLidas(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificacoes", "me"] }),
  });

  // Fecha ao clicar fora
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const count = q.data?.nao_lidas ?? 0;

  function handleItemClick(n: Notificacao) {
    if (!n.lido_em) marcarLida.mutate(n.id);
    if (n.link_url) setOpen(false);
  }

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notificações"
        aria-haspopup="true"
        aria-expanded={open}
        className="relative inline-flex h-11 w-11 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {count > 0 && (
          <span
            aria-label={`${count} não lidas`}
            className="absolute right-1.5 top-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-none text-danger-foreground"
          >
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notificações"
          className="absolute right-0 top-full z-50 mt-2 w-[360px] overflow-hidden rounded-md border border-border bg-card shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-sm font-semibold">Notificações</span>
            {count > 0 && (
              <button
                type="button"
                onClick={() => marcarTodas.mutate()}
                disabled={marcarTodas.isPending}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-50"
              >
                <CheckCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Marcar todas como lidas
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {q.isLoading && (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                Carregando…
              </div>
            )}
            {!q.isLoading && (q.data?.items.length ?? 0) === 0 && (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                Nenhuma notificação por enquanto.
              </div>
            )}
            {q.data?.items.map((n) => {
              const naoLida = !n.lido_em;
              const inner = (
                <div
                  className={cn(
                    "border-b border-border px-3 py-2.5 text-sm transition-colors hover:bg-muted/60",
                    naoLida && "bg-primary/5",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {naoLida && (
                          <span
                            aria-hidden="true"
                            className="inline-block h-2 w-2 shrink-0 rounded-full bg-primary"
                          />
                        )}
                        <span className="font-medium leading-tight">{n.titulo}</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {n.mensagem}
                      </p>
                    </div>
                    <span className="shrink-0 text-[10px] text-muted-foreground">
                      {fmtRel(n.criado_em)}
                    </span>
                  </div>
                  {n.prioridade === "alta" && (
                    <span className="mt-1 inline-block rounded bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-danger-soft-foreground">
                      Alta
                    </span>
                  )}
                </div>
              );
              return n.link_url ? (
                <Link
                  key={n.id}
                  href={n.link_url}
                  onClick={() => handleItemClick(n)}
                  className="block"
                >
                  {inner}
                </Link>
              ) : (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className="block w-full text-left"
                >
                  {inner}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
