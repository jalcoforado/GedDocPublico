"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, ShieldOff } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, assinaturaComprovanteUrl } from "@/lib/api";
import { statusValidacaoPublica } from "@/lib/assinatura";
import { useAuth } from "@/lib/auth";

const AVISO =
  "Este código permite validar publicamente a assinatura, mas a página pública " +
  "exibe apenas dados minimizados. Não compartilhe se o processo não puder ser " +
  "consultado publicamente.";

export function ValidacaoPublicaCard({
  aaId,
  defaultOpen = false,
}: {
  aaId: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const { can } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [revogarOpen, setRevogarOpen] = useState(false);
  const [motivo, setMotivo] = useState("");

  const evQ = useQuery({
    queryKey: ["validacao-publica", aaId],
    queryFn: () => api.assinaturas.evidencias(aaId),
    enabled: open,
  });

  const revogarM = useMutation({
    mutationFn: () =>
      api.assinaturas.revogarValidacaoPublica(aaId, motivo.trim() || undefined),
    onSuccess: () => {
      setRevogarOpen(false);
      setMotivo("");
      qc.invalidateQueries({ queryKey: ["validacao-publica", aaId] });
      toast.success("Validação pública revogada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function copiar(texto: string, rotulo: string) {
    try {
      await navigator.clipboard.writeText(texto);
      toast.success(`${rotulo} copiado`);
    } catch {
      toast.error("Não foi possível copiar.");
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="ml-2 text-xs text-primary hover:underline"
      >
        Validação pública
      </button>
    );
  }

  const ev = evQ.data;
  const st = statusValidacaoPublica(ev?.validacao_publica_status);
  const podeRevogar = ev?.validacao_publica_status === "ativa" && can("processo", "atualizar");

  return (
    <div className="mt-2 rounded-md border border-border bg-card p-3 text-xs">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-semibold text-foreground">Validação pública</span>
        {evQ.isLoading ? (
          <span className="text-muted-foreground">carregando…</span>
        ) : (
          <Badge intent={st.intent}>{st.label}</Badge>
        )}
      </div>

      {ev && st.exibeCodigo && ev.codigo_validacao && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Label className="text-muted-foreground">Código</Label>
            <code className="break-all rounded bg-muted px-1.5 py-0.5 font-mono">
              {ev.codigo_validacao}
            </code>
            <button
              type="button"
              aria-label="Copiar código"
              onClick={() => copiar(ev.codigo_validacao!, "Código")}
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              <Copy className="h-3 w-3" aria-hidden="true" /> copiar
            </button>
          </div>
          {ev.validacao_publica_url && (
            <div className="flex flex-wrap items-center gap-2">
              <Label className="text-muted-foreground">URL pública</Label>
              <a
                href={ev.validacao_publica_url}
                target="_blank"
                rel="noreferrer"
                className="break-all text-primary hover:underline"
              >
                {ev.validacao_publica_url}
              </a>
              <button
                type="button"
                aria-label="Copiar URL"
                onClick={() => copiar(ev.validacao_publica_url!, "URL")}
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <Copy className="h-3 w-3" aria-hidden="true" /> copiar
              </button>
            </div>
          )}
          <a
            href={assinaturaComprovanteUrl(aaId)}
            target="_blank"
            rel="noreferrer"
            className="inline-block text-primary hover:underline"
          >
            Ver comprovante (com QR Code)
          </a>
          <p className="text-muted-foreground">{AVISO}</p>
          {podeRevogar && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setRevogarOpen(true)}
            >
              <ShieldOff className="mr-1 h-4 w-4" aria-hidden="true" />
              Revogar validação pública
            </Button>
          )}
        </div>
      )}

      {ev && !st.exibeCodigo && (
        <p className="text-muted-foreground">
          A validação pública não está disponível para esta assinatura.
        </p>
      )}

      <Dialog
        open={revogarOpen}
        onClose={() => setRevogarOpen(false)}
        title="Revogar validação pública"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRevogarOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => revogarM.mutate()}
              disabled={revogarM.isPending}
            >
              {revogarM.isPending ? "Revogando…" : "Revogar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <p>
            Após revogada, a validação pública passará a retornar{" "}
            <strong>resposta neutra</strong>. Isto <strong>não</strong> apaga a
            assinatura, <strong>não</strong> apaga as evidências internas e{" "}
            <strong>não</strong> invalida o hash interno — apenas revoga o acesso
            público por código/token.
          </p>
          <div>
            <Label htmlFor="motivo-revogacao">Motivo (opcional)</Label>
            <Textarea
              id="motivo-revogacao"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={2}
              placeholder="Ex.: documento substituído por nova versão."
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
