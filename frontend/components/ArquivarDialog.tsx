"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/textarea";
import { api, type ProcessoDetail } from "@/lib/api";

/**
 * Arquivamento do processo (F4).
 *
 * Por que o diálogo avisa que é definitivo
 * ----------------------------------------
 * Não há desarquivar. Não por esquecimento: os seis leitores do dashboard
 * filtram por `id_arquivamento IS NOT NULL` **sem** olhar
 * `movimentacao.excluido`, então desfazer por soft-delete não desfaria nada nas
 * contagens. Enquanto essa decisão não for tomada no backend, arquivar é de
 * mão única — e a tela tem de dizer isso antes, não depois.
 *
 * O endereçamento físico fica recolhido
 * -------------------------------------
 * `estante`, `prateleira`, `caixa` e `pasta` são colunas da tabela legada e só
 * fazem sentido em processo de papel. Num processo virtual — o caso comum —
 * seriam quatro campos vazios competindo com o motivo, que é o obrigatório.
 * Ficam atrás de um `<details>`: presentes para quem precisa, silenciosos para
 * quem não.
 */
export function ArquivarDialog({
  open,
  onClose,
  processo,
}: {
  open: boolean;
  onClose: () => void;
  processo: ProcessoDetail;
}) {
  const qc = useQueryClient();
  const [motivo, setMotivo] = useState("");
  const [observacao, setObservacao] = useState("");
  const [local, setLocal] = useState("");
  const [estante, setEstante] = useState("");
  const [prateleira, setPrateleira] = useState("");
  const [caixa, setCaixa] = useState("");
  const [pasta, setPasta] = useState("");
  const [permanente, setPermanente] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const arquivarM = useMutation({
    mutationFn: () =>
      api.processos.arquivar(processo.id, {
        motivo: motivo.trim(),
        // Normaliza "" -> null: o backend aceita nulo e string vazia gravaria
        // uma prateleira chamada "".
        observacao: observacao.trim() || null,
        local: local.trim() || null,
        estante: estante.trim() || null,
        prateleira: prateleira.trim() || null,
        caixa: caixa.trim() || null,
        pasta: pasta.trim() || null,
        permanente,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      qc.invalidateQueries({ queryKey: ["processos"] });
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  // O mesmo piso do schema (`min_length=3`), para que o erro apareça antes da
  // viagem. O servidor continua sendo a autoridade — isto é conveniência.
  const motivoValido = motivo.trim().length >= 3;
  // Erro só depois de tentar arquivar: o botão não fica cinza sem explicação.
  const [tentou, setTentou] = useState(false);

  function fechar() {
    setTentou(false);
    setErr(null);
    onClose();
  }

  function arquivar() {
    setErr(null);
    setTentou(true);
    if (!motivoValido) {
      document.getElementById("arq-motivo")?.focus();
      return;
    }
    arquivarM.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={processo.numero_processo ? `Arquivar processo ${processo.numero_processo}` : "Arquivar processo"}
      description="Encerra o processo. Esta ação não pode ser desfeita pelo sistema."
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={arquivar} loading={arquivarM.isPending}>
            {arquivarM.isPending ? "Arquivando…" : "Arquivar processo"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FormField
          label="Motivo"
          required
          hint="Fica no histórico do processo."
          error={
            tentou && !motivoValido
              ? "Escreva o motivo do arquivamento, com pelo menos 3 letras."
              : undefined
          }
        >
          <Input
            id="arq-motivo"
            value={motivo}
            maxLength={255}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ex.: Pedido atendido"
          />
        </FormField>

        <FormField
          label="Observação"
          opcional
          hint="Aparece como despacho na linha do tempo."
        >
          <Textarea
            id="arq-obs"
            rows={3}
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            placeholder="Ex.: Serviço executado em 05/11; cidadão avisado por telefone."
          />
        </FormField>

        <label
          htmlFor="arq-permanente"
          className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast hover:bg-surface-2"
        >
          <Checkbox
            id="arq-permanente"
            checked={permanente}
            onChange={(e) => setPermanente(e.target.checked)}
            className="mt-0.5 h-4 w-4"
          />
          <span className="text-sm">
            <span className="block font-medium text-foreground">Guarda permanente</span>
            <span className="block text-xs text-foreground-muted">
              Guardado para sempre, sem prazo de eliminação.
            </span>
          </span>
        </label>

        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium text-foreground">
            Endereçamento físico
            <span className="ml-1.5 text-xs font-normal text-foreground-subtle">
              só para processo de papel
            </span>
          </summary>
          <p className="mt-1 text-xs text-foreground-muted">
            Onde o papel fica guardado. Em processo virtual, deixe em branco.
          </p>
          <div className="mt-3 space-y-3">
            <FormField label="Local">
              <Input
                id="arq-local"
                value={local}
                maxLength={255}
                onChange={(e) => setLocal(e.target.value)}
                placeholder="Ex.: Arquivo central"
              />
            </FormField>
            <GradeCampos>
              <FormField label="Estante">
                <Input id="arq-estante" value={estante} maxLength={255}
                  onChange={(e) => setEstante(e.target.value)} placeholder="Ex.: B" />
              </FormField>
              <FormField label="Prateleira">
                <Input id="arq-prateleira" value={prateleira} maxLength={255}
                  onChange={(e) => setPrateleira(e.target.value)} placeholder="Ex.: 3" />
              </FormField>
              <FormField label="Caixa">
                <Input id="arq-caixa" value={caixa} maxLength={255}
                  onChange={(e) => setCaixa(e.target.value)} placeholder="Ex.: 12" />
              </FormField>
              <FormField label="Pasta">
                <Input id="arq-pasta" value={pasta} maxLength={255}
                  onChange={(e) => setPasta(e.target.value)} placeholder="Ex.: 2026-A" />
              </FormField>
            </GradeCampos>
          </div>
        </details>

        {err && (
          <p
            role="alert"
            className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </p>
        )}
      </div>
    </Dialog>
  );
}
