"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type AlvaraVeiculo,
  type Paginated,
  type VeiculoRegulado,
} from "@/lib/api";

interface AlvaraVeiculosModalProps {
  alvaraId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AlvaraVeiculosModal({
  alvaraId,
  open,
  onOpenChange,
}: AlvaraVeiculosModalProps) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [selectedVeiculo, setSelectedVeiculo] = useState<number | null>(null);

  // Veículos do alvará
  const { data: veiculosAlvara, isLoading: veiculosLoading } = useQuery<
    Paginated<AlvaraVeiculo>
  >({
    queryKey: [`/transporte-regulado/alvaras/${alvaraId}/veiculos`],
    queryFn: () => api.alvaras.veiculos.list(alvaraId),
    enabled: open,
  });

  // Lista de todos os veículos para vincular
  const { data: todosVeiculos } = useQuery<Paginated<VeiculoRegulado>>({
    queryKey: ["/transporte-regulado/veiculos"],
    queryFn: () => api.veiculosRegulados.list(),
    enabled: open,
  });

  // Vincular veículo
  const vincularMutation = useMutation({
    mutationFn: async () => {
      if (!selectedVeiculo) throw new Error("Selecione um veículo");
      await api.alvaras.veiculos.add(alvaraId, { id_veiculo: selectedVeiculo });
    },
    onSuccess: () => {
      toast({ message: "Veículo vinculado com sucesso!", intent: "success" });
      queryClient.invalidateQueries({
        queryKey: [`/transporte-regulado/alvaras/${alvaraId}/veiculos`],
      });
      setSelectedVeiculo(null);
    },
    onError: (err: any) => {
      const msg = err.message || "Erro ao vincular veículo";
      toast({ message: msg, intent: "error" });
    },
  });

  // Desvincular veículo
  const desvinculateMutation = useMutation({
    mutationFn: async (veiculoId: number) => {
      await api.alvaras.veiculos.remove(alvaraId, veiculoId);
    },
    onSuccess: () => {
      toast({ message: "Veículo desvinculado com sucesso!", intent: "success" });
      queryClient.invalidateQueries({
        queryKey: [`/transporte-regulado/alvaras/${alvaraId}/veiculos`],
      });
    },
    onError: (err: any) => {
      toast({ message: "Erro ao desvincular veículo", intent: "error" });
    },
  });

  // Veículos já vinculados
  const veiculosVinculadosIds = new Set(
    veiculosAlvara?.items.map((v) => v.id_veiculo) || [],
  );

  // Veículos disponíveis para vincular
  const veiculosDisponiveis = (todosVeiculos?.items || []).filter(
    (v) => !veiculosVinculadosIds.has(v.id),
  );

  return (
    // O Dialog já desenha título, botão de fechar e rodapé. O conteúdo
    // repetia os três (com fundo branco fixo, que sumia no tema escuro).
    <Dialog
      open={open}
      onClose={() => onOpenChange(false)}
      title="Veículos do alvará"
      size="lg"
      footer={
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Fechar
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Form para vincular */}
        <div className="space-y-3 rounded-lg border border-border bg-surface-2/50 p-4">
          <h3 className="font-semibold text-foreground">Vincular veículo</h3>
          <div className="flex gap-2">
            <Select
              aria-label="Veículo a vincular"
              value={selectedVeiculo?.toString() || ""}
              onChange={(e) =>
                setSelectedVeiculo(e.target.value ? parseInt(e.target.value) : null)
              }
              disabled={veiculosDisponiveis.length === 0}
            >
              <option value="">
                {veiculosDisponiveis.length === 0
                  ? "Todos os veículos já estão vinculados"
                  : "Selecione um veículo..."}
              </option>
              {veiculosDisponiveis.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.placa} — {v.marca} {v.modelo}
                </option>
              ))}
            </Select>
            <Button
              onClick={() => vincularMutation.mutate()}
              disabled={
                !selectedVeiculo || vincularMutation.isPending
              }
              className="whitespace-nowrap"
            >
              <Plus className="mr-2 h-4 w-4" />
              Vincular
            </Button>
          </div>
        </div>

        {/* Lista de veículos vinculados */}
        <div className="space-y-3">
          <h3 className="font-semibold text-foreground">Veículos vinculados</h3>
          {veiculosLoading ? (
            <Carregando className="text-center text-foreground-muted" />
          ) : !veiculosAlvara || veiculosAlvara.items.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="Nenhum veículo vinculado"
              description="Escolha um veículo acima para vinculá-lo a este alvará."
            />
          ) : (
            <div className="space-y-2">
              {veiculosAlvara.items.map((av) => {
                const veiculo = todosVeiculos?.items.find(
                  (v) => v.id === av.id_veiculo,
                );
                return (
                  <div
                    key={av.id}
                    className="flex items-center justify-between rounded border border-border bg-surface-1 p-3"
                  >
                    <div>
                      <p className="font-medium text-foreground">
                        {veiculo?.placa} — {veiculo?.marca} {veiculo?.modelo}
                      </p>
                      <p className="text-xs text-foreground-muted">
                        Vinculado em {fmtData(av.criado_em)}
                      </p>
                    </div>
                    <Button
                      variant="danger-outline"
                      size="sm"
                      aria-label="Desvincular veículo"
                      onClick={async () => {
                        if (
                          await confirm({
                            title: "Desvincular veículo",
                            message: "Desvincular este veículo do alvará?",
                            intent: "danger",
                          })
                        ) {
                          desvinculateMutation.mutate(av.id_veiculo);
                        }
                      }}
                      disabled={desvinculateMutation.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      Desvincular
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
}
