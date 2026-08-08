"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FilePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

interface FormState {
  id_fornecedor: number | null;
  id_natureza: number | null;
  id_fonte_recursos: number | null;
  id_unidade: number | null;
  id_contrato: number | null;
  valor_total: string;
  competencia: string;
  numero_ne: string;
  numero_nf: string;
  criticidade: string;
  urgente: boolean;
  justificativa_urgencia: string;
  descricao: string;
  vencimento: string;
}

function emptyForm(): FormState {
  return {
    id_fornecedor: null,
    id_natureza: null,
    id_fonte_recursos: null,
    id_unidade: null,
    id_contrato: null,
    valor_total: "",
    competencia: "",
    numero_ne: "",
    numero_nf: "",
    criticidade: "MEDIA",
    urgente: false,
    justificativa_urgencia: "",
    descricao: "",
    vencimento: "",
  };
}

export default function NovasolicitacaoPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();

  const [form, setForm] = useState<FormState>(emptyForm());
  const [erros, setErros] = useState<Record<string, string>>({});

  // Carregar dados necessários
  const fornecedoresQ = useQuery({
    queryKey: ["pag-fornecedores"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
  });

  const naturezasQ = useQuery({
    queryKey: ["pag-naturezas"],
    queryFn: () => api.pagamentos.cadastros.naturezas.list(),
  });

  const fontesQ = useQuery({
    queryKey: ["pag-fontes"],
    queryFn: () => api.pagamentos.cadastros.fontes.list(),
  });

  const contratosQ = useQuery({
    queryKey: ["pag-contratos"],
    queryFn: () => api.pagamentos.cadastros.contratos.list(),
  });

  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  // Criar débito
  const criarM = useMutation({
    mutationFn: async (payload: FormState) => {
      // Validação básica
      const newErros: Record<string, string> = {};
      if (!payload.id_fornecedor) newErros.id_fornecedor = "Fornecedor é obrigatório";
      if (!payload.id_natureza) newErros.id_natureza = "Natureza é obrigatória";
      if (!payload.id_fonte_recursos) newErros.id_fonte_recursos = "Fonte de recursos é obrigatória";
      if (!payload.id_unidade) newErros.id_unidade = "Unidade solicitante é obrigatória";
      if (!payload.valor_total) newErros.valor_total = "Valor é obrigatório";
      if (!payload.competencia) newErros.competencia = "Competência é obrigatória";
      if (!payload.descricao) newErros.descricao = "Descrição é obrigatória";
      if (!payload.vencimento) newErros.vencimento = "Vencimento é obrigatório";

      if (Object.keys(newErros).length > 0) {
        setErros(newErros);
        throw new Error("Preencha os campos obrigatórios");
      }

      const { vencimento, ...dados } = payload;
      return api.pagamentos.debitos.create({
        ...dados,
        id_contrato: dados.id_contrato || null,
        numero_ne: dados.numero_ne.trim() || null,
        numero_nf: dados.numero_nf.trim() || null,
        justificativa_urgencia: dados.urgente
          ? dados.justificativa_urgencia.trim() || null
          : null,
        parcelas: [{ numero: 1, valor: Number(dados.valor_total), vencimento }],
      });
    },
    onSuccess: (debito) => {
      toast.success("Solicitação criada com sucesso");
      qc.invalidateQueries({ queryKey: ["pag-solicitacoes-fluxo"] });
      router.push(`/m/pagamentos/solicitacoes/${debito.id}`);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao criar solicitação");
    },
  });

  const handleChange = (field: keyof FormState, value: any) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
    if (erros[field]) {
      setErros((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Nova Solicitação de Pagamento"
        description="Preencha os dados da solicitação. Você poderá editar enquanto estiver em rascunho."
        icon={FilePlus}
      />

      <div className="max-w-2xl space-y-6">
        {/* Fornecedor */}
        <div>
          <Label>Fornecedor *</Label>
          <Select
            value={form.id_fornecedor?.toString() ?? ""}
            onChange={(e) => handleChange("id_fornecedor", e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Selecionar fornecedor...</option>
            {fornecedoresQ.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.nome}
              </option>
            ))}
          </Select>
          {erros.id_fornecedor && (
            <p className="text-xs text-danger mt-1">{erros.id_fornecedor}</p>
          )}
        </div>

        {/* Natureza */}
        <div>
          <Label>Natureza da Despesa *</Label>
          <Select
            value={form.id_natureza?.toString() ?? ""}
            onChange={(e) => handleChange("id_natureza", e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Selecionar natureza...</option>
            {naturezasQ.data?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.descricao}
              </option>
            ))}
          </Select>
          {erros.id_natureza && (
            <p className="text-xs text-danger mt-1">{erros.id_natureza}</p>
          )}
        </div>

        {/* Fonte */}
        <div>
          <Label>Fonte de Recursos *</Label>
          <Select
            value={form.id_fonte_recursos?.toString() ?? ""}
            onChange={(e) => handleChange("id_fonte_recursos", e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Selecionar fonte...</option>
            {fontesQ.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.codigo} - {f.descricao}
              </option>
            ))}
          </Select>
          {erros.id_fonte_recursos && (
            <p className="text-xs text-danger mt-1">{erros.id_fonte_recursos}</p>
          )}
        </div>

        {/* Contrato (opcional) */}
        <div>
          <Label>Contrato</Label>
          <Select
            value={form.id_contrato?.toString() ?? ""}
            onChange={(e) => handleChange("id_contrato", e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Nenhum contrato</option>
            {contratosQ.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.numero}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label>Unidade solicitante *</Label>
          <Select
            value={form.id_unidade?.toString() ?? ""}
            onChange={(e) => handleChange("id_unidade", e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Selecionar unidade...</option>
            {unidadesQ.data?.items.map((u) => (
              <option key={u.id} value={u.id}>{u.unidade_trabalho}</option>
            ))}
          </Select>
          {erros.id_unidade && <p className="text-xs text-danger mt-1">{erros.id_unidade}</p>}
        </div>

        {/* Valor Total */}
        <div>
          <Label>Valor Total *</Label>
          <Input
            type="number"
            step="0.01"
            value={form.valor_total}
            onChange={(e) => handleChange("valor_total", e.target.value)}
            placeholder="0.00"
          />
          {erros.valor_total && (
            <p className="text-xs text-danger mt-1">{erros.valor_total}</p>
          )}
        </div>

        {/* Competência */}
        <div>
          <Label>Competência *</Label>
          <Input
            type="month"
            value={form.competencia}
            onChange={(e) => handleChange("competencia", e.target.value)}
          />
          {erros.competencia && (
            <p className="text-xs text-danger mt-1">{erros.competencia}</p>
          )}
        </div>

        <div>
          <Label>Vencimento da parcela *</Label>
          <Input
            type="date"
            value={form.vencimento}
            onChange={(e) => handleChange("vencimento", e.target.value)}
          />
          {erros.vencimento && <p className="text-xs text-danger mt-1">{erros.vencimento}</p>}
        </div>

        {/* NE e NF */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>NE</Label>
            <Input
              value={form.numero_ne}
              onChange={(e) => handleChange("numero_ne", e.target.value)}
              placeholder="Número da emissão"
            />
          </div>
          <div>
            <Label>NF</Label>
            <Input
              value={form.numero_nf}
              onChange={(e) => handleChange("numero_nf", e.target.value)}
              placeholder="Número da nota fiscal"
            />
          </div>
        </div>

        {/* Criticidade */}
        <div>
          <Label>Criticidade</Label>
          <Select
            value={form.criticidade}
            onChange={(e) => handleChange("criticidade", e.target.value)}
          >
            <option value="BAIXA">Baixa</option>
            <option value="MEDIA">Média</option>
            <option value="ALTA">Alta</option>
          </Select>
        </div>

        {/* Urgente */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="urgente"
            checked={form.urgente}
            onChange={(e) => handleChange("urgente", e.target.checked)}
          />
          <Label htmlFor="urgente">Marcar como urgente</Label>
        </div>

        {/* Justificativa de Urgência */}
        {form.urgente && (
          <div>
            <Label>Justificativa de Urgência *</Label>
            <Textarea
              value={form.justificativa_urgencia}
              onChange={(e) => handleChange("justificativa_urgencia", e.target.value)}
              placeholder="Explique por que é urgente..."
              className="min-h-20"
            />
          </div>
        )}

        {/* Descrição */}
        <div>
          <Label>Descrição *</Label>
          <Textarea
            value={form.descricao}
            onChange={(e) => handleChange("descricao", e.target.value)}
            placeholder="Descreva o débito..."
            className="min-h-20"
          />
          {erros.descricao && (
            <p className="text-xs text-danger mt-1">{erros.descricao}</p>
          )}
        </div>

        {/* Botões */}
        <div className="flex gap-3 pt-4">
          <Button variant="secondary" onClick={() => router.back()}>
            Cancelar
          </Button>
          <Button
            onClick={() => criarM.mutate(form)}
            disabled={criarM.isPending}
          >
            {criarM.isPending ? "Criando..." : "Criar Solicitação"}
          </Button>
        </div>
      </div>
    </div>
  );
}
