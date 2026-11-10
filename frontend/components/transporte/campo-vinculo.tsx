"use client";

import { Building2, User, Users } from "lucide-react";

import { documentoParaExibir } from "@/components/transporte/rotulos";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField } from "@/components/ui/form-field";
import type { Empresa, Permissionario } from "@/lib/api";

/**
 * "Em nome de quem" — veículo e alvará pertencem a um permissionário, a uma
 * empresa ou aos dois (empresa com o permissionário que opera). Eram dois
 * `<select>` lado a lado com "— Nenhum —" e uma frase solta dizendo "informe
 * ao menos um": a regra só aparecia depois do erro do servidor. Agora a
 * escolha vem primeiro e só o campo que ela pede aparece.
 */
export type ModoVinculo = "permissionario" | "empresa" | "ambos";

export function modoDoVinculo(idPermissionario: string, idEmpresa: string): ModoVinculo {
  if (idPermissionario && idEmpresa) return "ambos";
  return idEmpresa ? "empresa" : "permissionario";
}

/** O que vai ao servidor: o lado que a escolha esconde vai como `null`. */
export function idsDoVinculo(
  modo: ModoVinculo,
  idPermissionario: string,
  idEmpresa: string,
): { id_permissionario: number | null; id_empresa: number | null } {
  return {
    id_permissionario: modo !== "empresa" && idPermissionario ? Number(idPermissionario) : null,
    id_empresa: modo !== "permissionario" && idEmpresa ? Number(idEmpresa) : null,
  };
}

export function errosDoVinculo(
  modo: ModoVinculo,
  idPermissionario: string,
  idEmpresa: string,
): { id_permissionario?: string; id_empresa?: string } {
  return {
    id_permissionario:
      modo !== "empresa" && !idPermissionario ? "Escolha o permissionário na lista." : undefined,
    id_empresa: modo !== "permissionario" && !idEmpresa ? "Escolha a empresa na lista." : undefined,
  };
}

/**
 * Nome sem acento ou documento só pelos dígitos: "12345" acha o CPF
 * "123.456.789-09", que o filtro padrão (texto puro) não acharia.
 */
function buscaNomeOuDocumento(o: ComboboxOption, q: string): boolean {
  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  if (norm(o.label).includes(norm(q))) return true;
  const dq = q.replace(/\D/g, "");
  return dq !== "" && (o.hint ?? "").replace(/\D/g, "").includes(dq);
}

export function CampoVinculo({
  nome,
  titulo = "Em nome de",
  modo,
  onModo,
  descricoes,
  idPermissionario,
  idEmpresa,
  onPermissionario,
  onEmpresa,
  permissionarios,
  empresas,
  carregando,
  erroPermissionario,
  erroEmpresa,
}: {
  /** `name` dos rádios — único na tela. */
  nome: string;
  titulo?: string;
  modo: ModoVinculo;
  onModo: (m: ModoVinculo) => void;
  /** Consequência de cada escolha, dita sob o grupo. */
  descricoes: Record<ModoVinculo, string>;
  idPermissionario: string;
  idEmpresa: string;
  onPermissionario: (id: string) => void;
  onEmpresa: (id: string) => void;
  permissionarios: Permissionario[];
  empresas: Empresa[];
  carregando?: boolean;
  erroPermissionario?: string;
  erroEmpresa?: string;
}) {
  return (
    <div className="space-y-4">
      <EscolhaSegmentada<ModoVinculo>
        nome={nome}
        titulo={titulo}
        valor={modo}
        onChange={onModo}
        opcoes={[
          { valor: "permissionario", rotulo: "Permissionário", icon: User, descricao: descricoes.permissionario },
          { valor: "empresa", rotulo: "Empresa", icon: Building2, descricao: descricoes.empresa },
          { valor: "ambos", rotulo: "Os dois", icon: Users, descricao: descricoes.ambos },
        ]}
      />
      {modo !== "empresa" && (
        <FormField label="Permissionário" required error={erroPermissionario} hint="Busque pelo nome ou CPF.">
          <Combobox
            id={`${nome}-permissionario`}
            options={permissionarios.map((p) => ({
              value: p.id,
              label: p.nome,
              hint: documentoParaExibir(p.cpf),
            }))}
            value={idPermissionario ? Number(idPermissionario) : null}
            onChange={(v) => onPermissionario(v == null ? "" : String(v))}
            placeholder="Escolha o permissionário…"
            searchPlaceholder="Nome ou CPF…"
            emptyText="Nenhum permissionário com esse nome ou CPF."
            loading={carregando}
            filter={buscaNomeOuDocumento}
          />
        </FormField>
      )}
      {modo !== "permissionario" && (
        <FormField label="Empresa" required error={erroEmpresa} hint="Busque pela razão social ou CNPJ.">
          <Combobox
            id={`${nome}-empresa`}
            options={empresas.map((e) => ({
              value: e.id,
              label: e.razao_social,
              hint: documentoParaExibir(e.cnpj),
            }))}
            value={idEmpresa ? Number(idEmpresa) : null}
            onChange={(v) => onEmpresa(v == null ? "" : String(v))}
            placeholder="Escolha a empresa…"
            searchPlaceholder="Razão social ou CNPJ…"
            emptyText="Nenhuma empresa com esse nome ou CNPJ."
            loading={carregando}
            filter={buscaNomeOuDocumento}
          />
        </FormField>
      )}
    </div>
  );
}
