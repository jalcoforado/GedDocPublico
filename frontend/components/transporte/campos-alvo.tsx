"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { documentoParaExibir } from "@/components/transporte/rotulos";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { FormField } from "@/components/ui/form-field";
import { api } from "@/lib/api";

/**
 * Busca no servidor com debounce: as listas de cadastro crescem sem limite,
 * e carregar tudo esbarra no teto de `page_size` (o item some em silêncio).
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

export type TipoRegulado = "permissionario" | "empresa" | "veiculo";

const TEXTOS: Record<TipoRegulado, { placeholder: string; busca: string; vazio: string; rotulo: string }> = {
  permissionario: {
    placeholder: "Buscar por nome ou CPF…",
    busca: "Nome ou CPF…",
    vazio: "Nenhum permissionário encontrado.",
    rotulo: "Permissionário",
  },
  empresa: {
    placeholder: "Buscar por razão social ou CNPJ…",
    busca: "Razão social ou CNPJ…",
    vazio: "Nenhuma empresa encontrada.",
    rotulo: "Empresa",
  },
  veiculo: {
    placeholder: "Buscar por placa, marca ou modelo…",
    busca: "Placa, marca ou modelo…",
    vazio: "Nenhum veículo encontrado.",
    rotulo: "Veículo",
  },
};

/**
 * Combobox de permissionário, empresa ou veículo com busca no servidor.
 * Substitui o seletor feito à mão (caixa de busca + lista aberta embaixo +
 * "Limpar") que existia, igual, em ocorrência, linha e ponto.
 */
export function ComboRegulado({
  tipo,
  id,
  value,
  onChange,
  ativo,
}: {
  tipo: TipoRegulado;
  id?: string;
  value: number | null;
  onChange: (id: number | null) => void;
  /** Diálogo aberto — só então a busca vai ao servidor. */
  ativo: boolean;
}) {
  const [busca, setBusca] = useBuscaAplicada();
  const listaQ = useQuery({
    queryKey: [`tr-${tipo === "permissionario" ? "perms" : tipo === "empresa" ? "empresas" : "veiculos"}-busca`, busca, "opcoes"],
    queryFn: (): Promise<{ items: ComboboxOption[] }> => {
      const q = busca || undefined;
      if (tipo === "permissionario") {
        return api.permissionarios.list({ q }).then((r) => ({ items: r.items.map(opcaoPermissionario) }));
      }
      if (tipo === "empresa") {
        return api.empresas.list({ q }).then((r) => ({ items: r.items.map(opcaoEmpresa) }));
      }
      return api.veiculosRegulados.list({ q }).then((r) => ({ items: r.items.map(opcaoVeiculo) }));
    },
    enabled: ativo,
  });
  // O escolhido pode não estar no resultado da busca atual (ou ter vindo do
  // registro já gravado): o nome dele vem por id.
  const selQ = useQuery({
    queryKey: [
      tipo === "permissionario" ? "tr-perm-selecionado" : tipo === "empresa" ? "tr-empresa-selecionada" : "tr-veiculo-selecionado",
      value,
      "opcao",
    ],
    queryFn: (): Promise<ComboboxOption> => {
      const n = value as number;
      if (tipo === "permissionario") return api.permissionarios.get(n).then(opcaoPermissionario);
      if (tipo === "empresa") return api.empresas.get(n).then(opcaoEmpresa);
      return api.veiculosRegulados.get(n).then(opcaoVeiculo);
    },
    enabled: ativo && value !== null,
  });
  const t = TEXTOS[tipo];
  return (
    <Combobox
      id={id}
      options={listaQ.data?.items ?? []}
      value={value}
      selectedOption={value === null ? null : (selQ.data ?? { value, label: `${t.rotulo} nº ${value}` })}
      onChange={(v) => onChange(v == null ? null : Number(v))}
      onQueryChange={setBusca}
      loading={listaQ.isFetching}
      placeholder={t.placeholder}
      searchPlaceholder={t.busca}
      emptyText={t.vazio}
    />
  );
}

function opcaoPermissionario(p: { id: number; nome: string; cpf: string }): ComboboxOption {
  return { value: p.id, label: p.nome, hint: documentoParaExibir(p.cpf) };
}
function opcaoEmpresa(e: { id: number; razao_social: string; nome_fantasia: string | null; cnpj: string }): ComboboxOption {
  return { value: e.id, label: e.nome_fantasia ?? e.razao_social, hint: documentoParaExibir(e.cnpj) };
}
function opcaoVeiculo(v: { id: number; placa: string; marca: string; modelo: string }): ComboboxOption {
  return { value: v.id, label: v.placa, hint: `${v.marca} ${v.modelo}` };
}

/**
 * Grupo de campos com regra "ao menos um" (alvo da ocorrência: permissionário,
 * empresa ou veículo). A regra é do grupo, não de um campo: o erro aparece
 * sob o título, e o grupo (focável) recebe o foco quando o envio falha por ele.
 */
export function GrupoAoMenosUm({
  titulo,
  descricao,
  erro,
  children,
}: {
  titulo: string;
  descricao: string;
  erro?: string;
  children: React.ReactNode;
}) {
  const uid = useId();
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
          {titulo}
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
      {children}
    </div>
  );
}

/**
 * Os três alvos de uma ocorrência. Registrar e "Vincular alvo" tinham, cada
 * um, três caixas de busca com uma lista aberta embaixo — o mesmo seletor
 * escrito seis vezes, com lista ocupando o diálogo inteiro.
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
  return (
    <GrupoAoMenosUm titulo="Alvo da ocorrência" descricao={descricao} erro={erro}>
      <FormField label="Permissionário">
        <ComboRegulado tipo="permissionario" ativo={ativo} value={idPermissionario} onChange={onPermissionario} />
      </FormField>
      <FormField label="Empresa">
        <ComboRegulado tipo="empresa" ativo={ativo} value={idEmpresa} onChange={onEmpresa} />
      </FormField>
      <FormField label="Veículo">
        <ComboRegulado tipo="veiculo" ativo={ativo} value={idVeiculo} onChange={onVeiculo} />
      </FormField>
    </GrupoAoMenosUm>
  );
}
