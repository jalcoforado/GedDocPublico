"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

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
    AlvaraVeiculo[]
  >({
    queryKey: [`/transporte-regulado/alvaras/${alvaraId}/veiculos`],
    queryFn: () => api.alvaras.veiculos.list(alvaraId),
    enabled: open,
  });

  // Lista de todos os veículos para vincular
  const { data: todosVeiculos } = useQuery<VeiculoRegulado[]>({
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
    veiculosAlvara?.map((v) => v.id_veiculo) || [],
  );

  // Veículos disponíveis para vincular
  const veiculosDisponiveis = (todosVeiculos || []).filter(
    (v) => !veiculosVinculadosIds.has(v.id),
  );

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} title="Veículos do alvará">
      <div className="w-full max-w-2xl space-y-6 rounded-lg bg-white p-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-4">
          <h2 className="text-xl font-bold">Veículos do Alvará</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="h-6 w-6 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Form para vincular */}
        <div className="space-y-3 rounded-lg border bg-gray-50 p-4">
          <h3 className="font-semibold">Vincular Novo Veículo</h3>
          <div className="flex gap-2">
            <Select
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
          <h3 className="font-semibold">Veículos Vinculados</h3>
          {veiculosLoading ? (
            <div className="text-center text-gray-600">Carregando...</div>
          ) : !veiculosAlvara || veiculosAlvara.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="Nenhum veículo vinculado"
              description="Vincule um veículo para começar"
            />
          ) : (
            <div className="space-y-2">
              {veiculosAlvara.map((av) => {
                const veiculo = todosVeiculos?.find(
                  (v) => v.id === av.id_veiculo,
                );
                return (
                  <div
                    key={av.id}
                    className="flex items-center justify-between rounded border bg-white p-3"
                  >
                    <div>
                      <p className="font-medium">
                        {veiculo?.placa} — {veiculo?.marca} {veiculo?.modelo}
                      </p>
                      <p className="text-xs text-gray-600">
                        Vinculado em{" "}
                        {new Date(av.criado_em).toLocaleDateString("pt-BR")}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
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
                      className="text-red-600 hover:text-red-800"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t pt-4 flex justify-end">
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
          >
            Fechar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
