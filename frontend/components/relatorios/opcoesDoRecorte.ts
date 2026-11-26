"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { ComboboxOption } from "@/components/ui/combobox";
import { api, organogramaApi } from "@/lib/api";
import { useAssuntosAll } from "@/lib/assuntos";

/**
 * As opções do recorte comum dos relatórios — unidades, tipos, assuntos (do
 * tipo escolhido) e serviços. Uma fonte só para a barra de filtros das telas
 * de relatório e para o montador (SI-35), que não podem oferecer listas
 * diferentes para o mesmo filtro.
 */
export function useOpcoesDoRecorte(idTipoProcesso?: number | null) {
  const organogramaQ = useQuery({ queryKey: ["organograma"], queryFn: () => organogramaApi.tree() });
  const tiposQ = useQuery({ queryKey: ["tipos-processo"], queryFn: () => api.tiposProcesso.list() });
  const assuntosQ = useAssuntosAll();
  // Rota dos relatórios, não `/servicos`: aquela exige administrar o catálogo.
  const servicosQ = useQuery({ queryKey: ["relatorios-servicos"], queryFn: () => api.relatorios.servicos() });

  const unidades = useMemo<ComboboxOption[]>(
    () =>
      (organogramaQ.data ?? [])
        .map((u) => ({ value: u.id, label: u.unidade_trabalho, hint: u.sigla ?? undefined }))
        .sort((a, b) => a.label.localeCompare(b.label, "pt-BR")),
    [organogramaQ.data],
  );
  const tipos = useMemo<ComboboxOption[]>(
    () => (tiposQ.data ?? []).map((t) => ({ value: t.id, label: t.tipo_processo })),
    [tiposQ.data],
  );
  const assuntos = useMemo<ComboboxOption[]>(
    () =>
      (assuntosQ.data ?? [])
        .filter((a) => !idTipoProcesso || a.id_tipo_processo === idTipoProcesso)
        .map((a) => ({ value: a.id, label: a.assunto })),
    [assuntosQ.data, idTipoProcesso],
  );
  const servicos = useMemo<ComboboxOption[]>(
    () =>
      (servicosQ.data ?? []).map((s) => ({
        value: s.id,
        label: s.nome,
        hint: s.ativo ? undefined : "inativo",
      })),
    [servicosQ.data],
  );

  /** O assunto continua valendo com o tipo novo? (assunto de outro tipo sai) */
  function assuntoCombina(idAssunto: number | null | undefined, idTipo: number | undefined): boolean {
    if (!idTipo || !idAssunto) return true;
    return assuntosQ.data?.find((a) => a.id === idAssunto)?.id_tipo_processo === idTipo;
  }

  return {
    unidades,
    tipos,
    assuntos,
    servicos,
    assuntoCombina,
    carregando: {
      unidades: organogramaQ.isLoading,
      tipos: tiposQ.isLoading,
      assuntos: assuntosQ.isLoading,
      servicos: servicosQ.isLoading,
    },
  };
}
