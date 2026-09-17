"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Arquivar processo"
      description="Encerra o processo. Esta ação não pode ser desfeita pelo sistema."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              setErr(null);
              arquivarM.mutate();
            }}
            disabled={!motivoValido || arquivarM.isPending}
          >
            {arquivarM.isPending ? "Arquivando..." : "Arquivar"}
          </Button>
        </>
      }
    >
      <p className="text-sm">
        Arquivar o processo{" "}
        <b className="font-mono">{processo.numero_processo}</b>?
      </p>

      <div className="mt-4 space-y-4">
        <div>
          <Label htmlFor="arq-motivo">
            Motivo <span className="text-danger">*</span>
          </Label>
          <Input
            id="arq-motivo"
            value={motivo}
            maxLength={255}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Por que este processo está sendo encerrado?"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Fica no histórico do processo. Mínimo de 3 caracteres.
          </p>
        </div>

        <div>
          <Label htmlFor="arq-obs">Observação</Label>
          <Textarea
            id="arq-obs"
            rows={3}
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            placeholder="Texto livre — aparece como despacho na linha do tempo."
          />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="arq-permanente"
            checked={permanente}
            onChange={(e) => setPermanente(e.target.checked)}
          />
          <Label htmlFor="arq-permanente" className="!mb-0">
            Guarda permanente
          </Label>
        </div>

        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            Endereçamento físico
          </summary>
          <p className="mt-1 text-xs text-muted-foreground">
            Só para processo de papel. Deixe em branco em processo virtual.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="arq-local">Local</Label>
              <Input id="arq-local" value={local} maxLength={255}
                onChange={(e) => setLocal(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="arq-estante">Estante</Label>
              <Input id="arq-estante" value={estante} maxLength={255}
                onChange={(e) => setEstante(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="arq-prateleira">Prateleira</Label>
              <Input id="arq-prateleira" value={prateleira} maxLength={255}
                onChange={(e) => setPrateleira(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="arq-caixa">Caixa</Label>
              <Input id="arq-caixa" value={caixa} maxLength={255}
                onChange={(e) => setCaixa(e.target.value)} />
            </div>
            <div className="col-span-2">
              <Label htmlFor="arq-pasta">Pasta</Label>
              <Input id="arq-pasta" value={pasta} maxLength={255}
                onChange={(e) => setPasta(e.target.value)} />
            </div>
          </div>
        </details>
      </div>

      {err && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {err}
        </p>
      )}
    </Dialog>
  );
}
