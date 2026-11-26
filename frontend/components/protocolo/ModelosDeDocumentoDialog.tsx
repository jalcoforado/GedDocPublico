"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Sem acento e em minúsculas: "oficio" acha "Ofício". */
function normalizar(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/**
 * "Modelos de documentos" do editor (SI-67) — a lista da imagem 2 do Suite:
 * busca por nome e um clique escolhe. Quem chama decide o que fazer com a
 * escolha (avisar que o texto será substituído e aplicar).
 *
 * `null` é o "Documento em branco".
 */
export function ModelosDeDocumentoDialog({
  open,
  onClose,
  onEscolher,
  modeloAtualId,
}: {
  open: boolean;
  onClose: () => void;
  onEscolher: (modelo: { id: number | null; nome: string }) => void;
  /** O modelo de onde o texto veio, marcado na lista. */
  modeloAtualId?: number | null;
}) {
  const [busca, setBusca] = useState("");
  useEffect(() => {
    if (open) setBusca("");
  }, [open]);

  const modelosQ = useQuery({
    queryKey: ["templates-documento", "ativos"],
    queryFn: () => api.templatesDocumento.list({ apenas_ativos: true }),
    enabled: open,
  });

  const filtrados = useMemo(() => {
    const termo = normalizar(busca.trim());
    const lista = modelosQ.data ?? [];
    const achados = termo
      ? lista.filter((m) => normalizar(`${m.nome} ${m.descricao ?? ""}`).includes(termo))
      : lista;
    // O padrão da prefeitura primeiro, depois por nome.
    return [...achados].sort(
      (a, b) => Number(b.padrao) - Number(a.padrao) || a.nome.localeCompare(b.nome, "pt-BR"),
    );
  }, [modelosQ.data, busca]);

  const linha =
    "flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors duration-fast " +
    "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Modelos de documentos"
      description="Escolha um modelo para o documento. Os dados do processo já entram preenchidos."
      size="lg"
      footer={
        <Button variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
      }
    >
      <div className="space-y-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            aria-hidden="true"
          />
          <Input
            aria-label="Buscar modelo"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Digite para buscar um modelo"
            className="pl-9"
          />
        </div>

        <ul aria-label="Modelos" className="divide-y divide-border rounded-md border border-border">
          {!busca.trim() && (
            <li>
              <button
                type="button"
                className={cn(linha, modeloAtualId === null && "bg-brand/5")}
                onClick={() => onEscolher({ id: null, nome: "Documento em branco" })}
              >
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
                <span className="text-sm font-medium text-foreground">Documento em branco</span>
              </button>
            </li>
          )}
          {modelosQ.isLoading && (
            <li className="px-3 py-3 text-sm text-foreground-muted">Carregando modelos…</li>
          )}
          {modelosQ.isError && (
            <li role="alert" className="px-3 py-3 text-sm text-danger-soft-foreground">
              Não foi possível carregar os modelos.
            </li>
          )}
          {filtrados.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                className={cn(linha, modeloAtualId === m.id && "bg-brand/5")}
                onClick={() => onEscolher({ id: m.id, nome: m.nome })}
              >
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                    {m.nome}
                    {m.padrao && <Badge intent="info">Padrão</Badge>}
                    {modeloAtualId === m.id && <Badge intent="neutral">Em uso</Badge>}
                  </span>
                  {m.descricao && (
                    <span className="mt-0.5 block text-xs text-foreground-muted">{m.descricao}</span>
                  )}
                </span>
              </button>
            </li>
          ))}
          {modelosQ.isSuccess && filtrados.length === 0 && (
            <li className="px-3 py-3 text-sm text-foreground-muted">
              {busca.trim() ? `Nenhum modelo com "${busca.trim()}".` : "Nenhum modelo cadastrado."}
            </li>
          )}
        </ul>
      </div>
    </Dialog>
  );
}
