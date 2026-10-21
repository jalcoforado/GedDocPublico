"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  type CaixaProcesso,
  type LoteRequest,
  type LoteResultado,
  type ProcessoListItem,
} from "@/lib/api";

type Acao = LoteRequest["acao"];

/**
 * Que ações em lote cada caixa oferece. Só o que faz sentido para TODO
 * processo daquela caixa: na Entrada tudo está chegando (receber); na mesa da
 * unidade (Análise, Recusados, Externos) tudo pode seguir, ganhar responsável
 * ou ser arquivado. Nas outras caixas não há ato comum, e a seleção nem
 * aparece.
 */
export const ACOES_POR_CAIXA: Partial<Record<CaixaProcesso, Acao[]>> = {
  entrada: ["receber"],
  analise: ["encaminhar", "atribuir_responsavel", "arquivar"],
  recusados: ["encaminhar", "atribuir_responsavel", "arquivar"],
  externos: ["encaminhar", "atribuir_responsavel", "arquivar"],
};

const ROTULO: Record<Acao, string> = {
  receber: "Receber",
  encaminhar: "Encaminhar…",
  atribuir_responsavel: "Atribuir a mim",
  arquivar: "Arquivar…",
};

interface Props {
  caixa: CaixaProcesso;
  /** Os processos selecionados, com o número para o relatório de falhas. */
  selecionados: ProcessoListItem[];
  idUsuario: number | undefined;
  onConcluido: () => void;
}

/**
 * Barra de ações sobre os processos selecionados numa caixa de trabalho
 * (pedido da reunião de 2026-10-20, item 2.2). O servidor aplica a ação a
 * cada processo pela mesma regra da ação individual e responde um a um; a
 * barra mostra quantos foram e por que cada um dos outros não foi.
 */
export function AcoesEmLote({ caixa, selecionados, idUsuario, onConcluido }: Props) {
  const qc = useQueryClient();
  const acoes = ACOES_POR_CAIXA[caixa] ?? [];
  const [dialogo, setDialogo] = useState<null | "encaminhar" | "arquivar">(null);
  const [resultado, setResultado] = useState<LoteResultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Os números ficam guardados no momento do pedido: ao concluir, a seleção
  // zera, e o relatório de falhas ainda precisa dizer QUAL processo falhou.
  const [numeroDe, setNumeroDe] = useState<Map<number, string>>(new Map());

  const m = useMutation({
    mutationFn: (pedido: LoteRequest) => api.processos.lote(pedido),
    onSuccess: (r) => {
      setResultado(r);
      setDialogo(null);
      // Mudou caixa, contador, painel e responsável: tudo que lista processos.
      void qc.invalidateQueries();
      onConcluido();
    },
    onError: (e: Error) => setErro(e.message),
  });

  if (acoes.length === 0) return null;
  const ids = selecionados.map((p) => p.id);
  const n = ids.length;

  function executar(acao: Acao, extra: Partial<LoteRequest> = {}) {
    setErro(null);
    setResultado(null);
    setNumeroDe(new Map(selecionados.map((p) => [p.id, p.nup ?? p.numero_processo ?? `#${p.id}`])));
    m.mutate({ acao, ids, ...extra });
  }

  function clicar(acao: Acao) {
    if (acao === "encaminhar" || acao === "arquivar") {
      setErro(null);
      setDialogo(acao);
    } else if (acao === "atribuir_responsavel") {
      executar(acao, { responsavel: { id_usuario: idUsuario ?? null } });
    } else {
      executar(acao);
    }
  }

  return (
    <div className="space-y-2">
      <div
        role="toolbar"
        aria-label="Ações em lote"
        className="flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface-2 px-3 py-2"
      >
        <span className="mr-2 text-sm font-medium text-foreground" aria-live="polite">
          {n === 0 ? "Nenhum processo selecionado" : n === 1 ? "1 selecionado" : `${n} selecionados`}
        </span>
        {acoes.map((acao) => (
          <Button
            key={acao}
            size="sm"
            variant={acao === acoes[0] ? "primary" : "secondary"}
            disabled={n === 0 || m.isPending || (acao === "atribuir_responsavel" && !idUsuario)}
            onClick={() => clicar(acao)}
          >
            {ROTULO[acao]}
          </Button>
        ))}
        {m.isPending && <span className="text-xs text-foreground-muted">Processando…</span>}
      </div>

      {erro && !dialogo && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          {erro}
        </p>
      )}

      {resultado && (
        <div
          role="status"
          className="rounded-md border border-border bg-surface-1 px-3 py-2 text-sm"
        >
          <p className="font-medium text-foreground">
            {resultado.concluidos === 1 ? "1 processo concluído" : `${resultado.concluidos} processos concluídos`}
            {resultado.falhas > 0 &&
              (resultado.falhas === 1 ? ", 1 não pôde ser feito:" : `, ${resultado.falhas} não puderam ser feitos:`)}
          </p>
          {resultado.falhas > 0 && (
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-foreground-muted">
              {resultado.itens
                .filter((i) => !i.ok)
                .map((i) => (
                  <li key={i.id}>
                    <span className="font-mono text-xs text-foreground">{numeroDe.get(i.id) ?? `#${i.id}`}</span>
                    {" — "}
                    {i.erro}
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}

      <EncaminharEmLote
        open={dialogo === "encaminhar"}
        n={n}
        enviando={m.isPending}
        erro={erro}
        onClose={() => setDialogo(null)}
        onConfirmar={(encaminhar) => executar("encaminhar", { encaminhar })}
      />
      <ArquivarEmLote
        open={dialogo === "arquivar"}
        n={n}
        enviando={m.isPending}
        erro={erro}
        onClose={() => setDialogo(null)}
        onConfirmar={(arquivar) => executar("arquivar", { arquivar })}
      />
    </div>
  );
}

function ErroDoDialogo({ erro }: { erro: string | null }) {
  if (!erro) return null;
  return (
    <p role="alert" className="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
      {erro}
    </p>
  );
}

function EncaminharEmLote({
  open,
  n,
  enviando,
  erro,
  onClose,
  onConfirmar,
}: {
  open: boolean;
  n: number;
  enviando: boolean;
  erro: string | null;
  onClose: () => void;
  onConfirmar: (e: NonNullable<LoteRequest["encaminhar"]>) => void;
}) {
  const [destino, setDestino] = useState("");
  const [prioridade, setPrioridade] = useState("");
  const [prazo, setPrazo] = useState("");
  const [despacho, setDespacho] = useState("");
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
    enabled: open,
  });
  const prioridadesQ = useQuery({
    queryKey: ["prioridades"],
    queryFn: () => api.prioridades(),
    enabled: open,
  });
  const valido = destino !== "" && prioridade !== "";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={n === 1 ? "Encaminhar 1 processo" : `Encaminhar ${n} processos`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Voltar
          </Button>
          <Button
            disabled={!valido || enviando}
            onClick={() =>
              onConfirmar({
                id_unidade_destino: Number(destino),
                id_prioridade: Number(prioridade),
                data_prazo: prazo || null,
                despacho: despacho.trim() || null,
              })
            }
          >
            {enviando ? "Encaminhando..." : "Confirmar encaminhamento"}
          </Button>
        </>
      }
    >
      <p className="text-sm text-foreground-muted">
        Todos vão para o mesmo destino, com a mesma prioridade, prazo e despacho. Processo com
        fluxo obrigatório que não aceite esse destino fica de fora e aparece no resultado.
      </p>
      <div className="mt-3 space-y-3">
        <div>
          <Label htmlFor="lote-destino">Unidade de destino</Label>
          <Select id="lote-destino" value={destino} onChange={(e) => setDestino(e.target.value)}>
            <option value="">Selecione…</option>
            {(unidadesQ.data?.items ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.unidade_trabalho}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="lote-prioridade">Prioridade</Label>
          <Select id="lote-prioridade" value={prioridade} onChange={(e) => setPrioridade(e.target.value)}>
            <option value="">Selecione…</option>
            {(prioridadesQ.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.prioridade}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="lote-prazo">Prazo (opcional)</Label>
          <Input id="lote-prazo" type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="lote-despacho">Despacho (opcional)</Label>
          <Textarea id="lote-despacho" rows={3} value={despacho} onChange={(e) => setDespacho(e.target.value)} />
        </div>
      </div>
      <ErroDoDialogo erro={erro} />
    </Dialog>
  );
}

function ArquivarEmLote({
  open,
  n,
  enviando,
  erro,
  onClose,
  onConfirmar,
}: {
  open: boolean;
  n: number;
  enviando: boolean;
  erro: string | null;
  onClose: () => void;
  onConfirmar: (a: NonNullable<LoteRequest["arquivar"]>) => void;
}) {
  const [motivo, setMotivo] = useState("");
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={n === 1 ? "Arquivar 1 processo" : `Arquivar ${n} processos`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Voltar
          </Button>
          <Button
            disabled={motivo.trim().length < 3 || enviando}
            onClick={() => onConfirmar({ motivo: motivo.trim() })}
          >
            {enviando ? "Arquivando..." : "Confirmar arquivamento"}
          </Button>
        </>
      }
    >
      <p className="text-sm text-foreground-muted">
        Arquivar encerra os processos. O mesmo motivo fica registrado em todos.
      </p>
      <div className="mt-3">
        <Label htmlFor="lote-motivo">Motivo do arquivamento</Label>
        <Textarea id="lote-motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <ErroDoDialogo erro={erro} />
    </Dialog>
  );
}
