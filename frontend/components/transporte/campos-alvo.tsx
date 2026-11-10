"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { documentoParaExibir } from "@/components/transporte/rotulos";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { FormField } from "@/components/ui/form-field";
import { api } from "@/lib/api";

/**
 * Busca no servidor com debounce: as listas de alvo crescem sem limite, e
 * carregar tudo esbarra no teto de `page_size` (o alvo some em silêncio).
 */
function useBuscaAplicada(): [string, (q: string) => void] {
  const [busca, setBusca] = useState("");
  const [aplicada, setAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);
  return [aplicada, setBusca];
}

/**
 * Os três alvos de uma ocorrência (permissionário, empresa, veículo), cada um
 * num `Combobox` com busca no servidor. Registrar e "Vincular alvo" tinham,
 * cada um, três caixas de busca com uma lista aberta embaixo e um "Limpar"
 * — o mesmo seletor escrito seis vezes, com lista ocupando o diálogo inteiro.
 *
 * A regra "ao menos um alvo" é do grupo, não de um campo: o erro aparece sob
 * o grupo, que recebe o foco quando o envio falha por ele.
 */
export function CamposAlvo({
  ativo,
  idPermissionario,
  idEmpresa,
  idVeiculo,
  onPermissionario,
  onEmpresa,
  onVeiculo,
  erro,
  descricao = "Informe ao menos um: permissionário, empresa ou veículo.",
}: {
  /** Diálogo aberto — só então as buscas vão ao servidor. */
  ativo: boolean;
  idPermissionario: number | null;
  idEmpresa: number | null;
  idVeiculo: number | null;
  onPermissionario: (id: number | null) => void;
  onEmpresa: (id: number | null) => void;
  onVeiculo: (id: number | null) => void;
  erro?: string;
  descricao?: string;
}) {
  const uid = useId();
  const [buscaPerm, setBuscaPerm] = useBuscaAplicada();
  const [buscaEmpresa, setBuscaEmpresa] = useBuscaAplicada();
  const [buscaVeiculo, setBuscaVeiculo] = useBuscaAplicada();

  const permsQ = useQuery({
    queryKey: ["tr-perms-busca", buscaPerm],
    queryFn: () => api.permissionarios.list({ q: buscaPerm || undefined }),
    enabled: ativo,
  });
  const empresasQ = useQuery({
    queryKey: ["tr-empresas-busca", buscaEmpresa],
    queryFn: () => api.empresas.list({ q: buscaEmpresa || undefined }),
    enabled: ativo,
  });
  const veiculosQ = useQuery({
    queryKey: ["tr-veiculos-busca", buscaVeiculo],
    queryFn: () => api.veiculosRegulados.list({ q: buscaVeiculo || undefined }),
    enabled: ativo,
  });
  // O escolhido pode não estar no resultado da busca atual (ou ter vindo do
  // registro já gravado): o nome dele vem por id.
  const permSelQ = useQuery({
    queryKey: ["tr-perm-selecionado", idPermissionario],
    queryFn: () => api.permissionarios.get(idPermissionario as number),
    enabled: ativo && idPermissionario !== null,
  });
  const empresaSelQ = useQuery({
    queryKey: ["tr-empresa-selecionada", idEmpresa],
    queryFn: () => api.empresas.get(idEmpresa as number),
    enabled: ativo && idEmpresa !== null,
  });
  const veiculoSelQ = useQuery({
    queryKey: ["tr-veiculo-selecionado", idVeiculo],
    queryFn: () => api.veiculosRegulados.get(idVeiculo as number),
    enabled: ativo && idVeiculo !== null,
  });

  const optPerm = (p: { id: number; nome: string; cpf: string }): ComboboxOption => ({
    value: p.id,
    label: p.nome,
    hint: documentoParaExibir(p.cpf),
  });
  const optEmpresa = (e: { id: number; razao_social: string; nome_fantasia: string | null; cnpj: string }): ComboboxOption => ({
    value: e.id,
    label: e.nome_fantasia ?? e.razao_social,
    hint: documentoParaExibir(e.cnpj),
  });
  const optVeiculo = (v: { id: number; placa: string; marca: string; modelo: string }): ComboboxOption => ({
    value: v.id,
    label: v.placa,
    hint: `${v.marca} ${v.modelo}`,
  });
  const selecionado = <T,>(id: number | null, dado: T | undefined, op: (d: T) => ComboboxOption, rotulo: string) =>
    id === null ? null : dado ? op(dado) : { value: id, label: `${rotulo} nº ${id}` };

  const erroId = `${uid}-erro`;
  const descId = `${uid}-desc`;

  return (
    <div
      role="group"
      aria-labelledby={`${uid}-titulo`}
      aria-describedby={erro ? erroId : descId}
      aria-invalid={erro ? true : undefined}
      tabIndex={-1}
      className="space-y-4 rounded-lg focus-visible:outline-none"
    >
      <div>
        <p id={`${uid}-titulo`} className="text-sm font-medium text-foreground">
          Alvo da ocorrência
        </p>
        {erro ? (
          <p id={erroId} className="mt-0.5 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground">
            <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {erro}
          </p>
        ) : (
          <p id={descId} className="mt-0.5 text-xs text-foreground-muted">
            {descricao}
          </p>
        )}
      </div>
      <FormField label="Permissionário">
        <Combobox
          id={`${uid}-perm`}
          options={(permsQ.data?.items ?? []).map(optPerm)}
          value={idPermissionario}
          selectedOption={selecionado(idPermissionario, permSelQ.data, optPerm, "Permissionário")}
          onChange={(v) => onPermissionario(v == null ? null : Number(v))}
          onQueryChange={setBuscaPerm}
          loading={permsQ.isFetching}
          placeholder="Buscar por nome ou CPF…"
          searchPlaceholder="Nome ou CPF…"
          emptyText="Nenhum permissionário encontrado."
        />
      </FormField>
      <FormField label="Empresa">
        <Combobox
          id={`${uid}-empresa`}
          options={(empresasQ.data?.items ?? []).map(optEmpresa)}
          value={idEmpresa}
          selectedOption={selecionado(idEmpresa, empresaSelQ.data, optEmpresa, "Empresa")}
          onChange={(v) => onEmpresa(v == null ? null : Number(v))}
          onQueryChange={setBuscaEmpresa}
          loading={empresasQ.isFetching}
          placeholder="Buscar por razão social ou CNPJ…"
          searchPlaceholder="Razão social ou CNPJ…"
          emptyText="Nenhuma empresa encontrada."
        />
      </FormField>
      <FormField label="Veículo">
        <Combobox
          id={`${uid}-veiculo`}
          options={(veiculosQ.data?.items ?? []).map(optVeiculo)}
          value={idVeiculo}
          selectedOption={selecionado(idVeiculo, veiculoSelQ.data, optVeiculo, "Veículo")}
          onChange={(v) => onVeiculo(v == null ? null : Number(v))}
          onQueryChange={setBuscaVeiculo}
          loading={veiculosQ.isFetching}
          placeholder="Buscar por placa, marca ou modelo…"
          searchPlaceholder="Placa, marca ou modelo…"
          emptyText="Nenhum veículo encontrado."
        />
      </FormField>
    </div>
  );
}
