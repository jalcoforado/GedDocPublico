"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSpreadsheet, Plus } from "lucide-react";
import { useState } from "react";

import { fmtData, fmtDataHora } from "@/components/pagamentos/format";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { ApiError, api } from "@/lib/api";

/** `yyyy-mm-dd` de hoje, no fuso local — valor inicial do campo data-limite. */
function hojeIso(): string {
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

export default function ExportContabilPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const [gerarOpen, setGerarOpen] = useState(false);
  const [ate, setAte] = useState(hojeIso());

  const lotesQ = useQuery({
    queryKey: ["pag-contabil-lotes"],
    queryFn: () => api.pagamentos.contabil.listarLotes(),
  });

  const lotes = lotesQ.data ?? [];

  const gerar = useMutation({
    mutationFn: () => api.pagamentos.contabil.gerarLote(ate),
    onSuccess: (lote) => {
      qc.invalidateQueries({ queryKey: ["pag-contabil-lotes"] });
      setGerarOpen(false);
      toast.success(`Lote ${lote.numero} gerado — ${lote.qtd_eventos} evento(s).`);
    },
    onError: (e: unknown) => {
      // 409 é esperado (nada pendente até a data escolhida) — o `detail` do
      // backend já é a mensagem amigável; não deve virar "Erro 409" genérico.
      if (e instanceof ApiError && e.status === 409) {
        toast.error(e.message);
        return;
      }
      toast.error(e instanceof Error ? e.message : "Falha ao gerar o lote.");
    },
  });

  function abrirGerar() {
    setAte(hojeIso());
    setGerarOpen(true);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileSpreadsheet}
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Export contábil" },
        ]}
        title="Export contábil"
        description="Lotes imutáveis de eventos neutros (empenho, liquidação, pagamento, estorno, cancelamento) para o sistema contábil externo. Cada lote captura só o que ainda não entrou em outro lote."
        actions={
          <Button onClick={abrirGerar}>
            <Plus className="mr-2 h-4 w-4" />
            Gerar lote
          </Button>
        }
      />

      <SectionCard title="Lotes gerados">
        {lotesQ.isLoading ? (
          <p className="text-sm text-muted">Carregando…</p>
        ) : lotes.length === 0 ? (
          <EmptyState
            icon={FileSpreadsheet}
            title="Nenhum lote gerado ainda"
            description="Gere o primeiro lote para exportar os eventos pendentes até uma data-limite."
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Lote</TH>
                <TH>Período</TH>
                <TH className="text-right">Eventos</TH>
                <TH>Gerado em</TH>
                <TH>Gerado por</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {lotes.map((l) => (
                <TR key={l.id}>
                  <TD className="font-medium">Lote {l.numero}</TD>
                  <TD>
                    {fmtData(l.periodo_inicio)} — {fmtData(l.periodo_fim)}
                  </TD>
                  <TD className="text-right tabular-nums">{l.qtd_eventos}</TD>
                  <TD>{fmtDataHora(l.gerado_em)}</TD>
                  <TD>{l.id_usuario ? `Usuário #${l.id_usuario}` : "—"}</TD>
                  <TD className="text-right">
                    <Button asChild variant="secondary" size="sm">
                      <a
                        href={api.pagamentos.contabil.arquivoUrl(l.id)}
                        download
                        aria-label={`Baixar CSV do lote ${l.numero}`}
                      >
                        <Download className="mr-2 h-4 w-4" aria-hidden />
                        CSV
                      </a>
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </SectionCard>

      <Dialog
        open={gerarOpen}
        onClose={() => setGerarOpen(false)}
        title="Gerar lote de export contábil"
        footer={
          <>
            <Button variant="ghost" onClick={() => setGerarOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => gerar.mutate()} disabled={gerar.isPending || !ate}>
              Gerar
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <Label htmlFor="contabil-ate">Data-limite</Label>
            <Input
              id="contabil-ate"
              type="date"
              value={ate}
              onChange={(e) => setAte(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted">
              O lote captura os eventos pendentes ocorridos até esta data (inclusive).
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
