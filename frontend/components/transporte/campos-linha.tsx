"use client";

import { CampoVinculoBusca, errosDoVinculo, idsDoVinculo, type ModoVinculo } from "@/components/transporte/campo-vinculo";
import { GrupoCampos } from "@/components/transporte/formulario";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { LinhaSituacao, TipoServico } from "@/lib/api";

/**
 * Campos da linha, iguais na lista ("Nova linha") e no detalhe ("Editar
 * linha"). Eram dois formulários copiados; um ganhava ajuste e o outro não.
 */
export interface CamposLinhaForm {
  nome: string;
  codigo: string;
  tipo_servico: TipoServico;
  origem: string;
  destino: string;
  situacao: LinhaSituacao;
  observacoes: string;
  id_empresa: number | null;
  id_permissionario: number | null;
}

export type CampoLinha = "nome" | "origem" | "destino" | "id_empresa" | "id_permissionario";

/** Erros da linha. Ao menos um operador — o backend devolve 422 sem nenhum. */
export function errosDaLinha(f: CamposLinhaForm, modo: ModoVinculo): Partial<Record<CampoLinha, string>> {
  return {
    nome: f.nome.trim() === "" ? "Informe o nome da linha." : undefined,
    origem: f.origem.trim() === "" ? "Informe a origem." : undefined,
    destino: f.destino.trim() === "" ? "Informe o destino." : undefined,
    ...errosDoVinculo(modo, String(f.id_permissionario ?? ""), String(f.id_empresa ?? "")),
  };
}

/** O lado do operador que a escolha "operada por" esconde vai como `null`. */
export function comOperador<F extends CamposLinhaForm>(f: F, modo: ModoVinculo): F {
  return { ...f, ...idsDoVinculo(modo, String(f.id_permissionario ?? ""), String(f.id_empresa ?? "")) };
}

export function CamposLinha<F extends CamposLinhaForm>({
  form,
  set,
  tipos,
  modoOperador,
  onModoOperador,
  ativo,
  erro,
  sair,
}: {
  form: F;
  set: <K extends keyof F>(k: K, v: F[K]) => void;
  tipos: { value: TipoServico; label: string }[];
  modoOperador: ModoVinculo;
  onModoOperador: (m: ModoVinculo) => void;
  ativo: boolean;
  erro: (c: CampoLinha) => string | undefined;
  sair: (c: CampoLinha) => () => void;
}) {
  return (
    <>
      <GrupoCampos titulo="Linha">
        <FormField label="Nome" required error={erro("nome")}>
          <Input
            id="nome"
            value={form.nome}
            onChange={(e) => set("nome", e.target.value as F["nome"])}
            onBlur={sair("nome")}
            placeholder="Ex.: Sede – Distrito Norte"
          />
        </FormField>
        <GradeCampos>
          <FormField label="Código" opcional hint="Como a linha é conhecida no município.">
            <Input
              id="codigo"
              value={form.codigo}
              onChange={(e) => set("codigo", e.target.value as F["codigo"])}
              placeholder="Ex.: L-04"
            />
          </FormField>
          <FormField label="Tipo de serviço" required>
            <Select
              id="tipo"
              value={form.tipo_servico}
              onChange={(e) => set("tipo_servico", e.target.value as F["tipo_servico"])}
            >
              {tipos.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </FormField>
        </GradeCampos>
        <GradeCampos>
          <FormField label="Origem" required error={erro("origem")}>
            <Input
              id="origem"
              value={form.origem}
              onChange={(e) => set("origem", e.target.value as F["origem"])}
              onBlur={sair("origem")}
              placeholder="Ex.: Terminal Rodoviário"
            />
          </FormField>
          <FormField label="Destino" required error={erro("destino")}>
            <Input
              id="destino"
              value={form.destino}
              onChange={(e) => set("destino", e.target.value as F["destino"])}
              onBlur={sair("destino")}
              placeholder="Ex.: Praça do Distrito Norte"
            />
          </FormField>
        </GradeCampos>
        <EscolhaSegmentada<LinhaSituacao>
          nome="linha-situacao"
          titulo="Situação"
          moldura={false}
          valor={form.situacao}
          onChange={(s) => set("situacao", s as F["situacao"])}
          opcoes={[
            { valor: "ativa", rotulo: "Ativa", descricao: "A linha está em operação." },
            { valor: "inativa", rotulo: "Inativa", descricao: "Fora de operação; a linha continua no cadastro." },
          ]}
        />
      </GrupoCampos>

      <GrupoCampos titulo="Operador">
        <CampoVinculoBusca
          nome="linha-operador"
          titulo="Operada por"
          modo={modoOperador}
          onModo={onModoOperador}
          descricoes={{
            empresa: "Uma empresa autorizada opera a linha.",
            permissionario: "Um permissionário opera a linha por conta própria.",
            ambos: "Empresa e permissionário operam a linha juntos.",
          }}
          idPermissionario={form.id_permissionario}
          idEmpresa={form.id_empresa}
          onPermissionario={(id) => set("id_permissionario", id as F["id_permissionario"])}
          onEmpresa={(id) => set("id_empresa", id as F["id_empresa"])}
          ativo={ativo}
          erroPermissionario={erro("id_permissionario")}
          erroEmpresa={erro("id_empresa")}
        />
      </GrupoCampos>

      <div className="border-t border-border pt-5">
        <FormField label="Observações" opcional>
          <Input
            id="obs"
            value={form.observacoes}
            onChange={(e) => set("observacoes", e.target.value as F["observacoes"])}
            placeholder="Ex.: não opera aos domingos"
          />
        </FormField>
      </div>
    </>
  );
}
