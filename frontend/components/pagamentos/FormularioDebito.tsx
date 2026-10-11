"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type CategoriaDebito, type DebitoDetalhe } from "@/lib/api";

/** Categorias da fila cronológica — espelha `CategoriaLit` (backend). */
export const CATEGORIAS_DEBITO: { value: CategoriaDebito; label: string }[] = [
  { value: "BENS", label: "Fornecimento de bens" },
  { value: "LOCACOES", label: "Locações" },
  { value: "SERVICOS", label: "Prestação de serviços" },
  { value: "OBRAS", label: "Obras" },
];

interface FormState {
  id_fornecedor: number | null;
  id_natureza: number | null;
  id_fonte_recursos: number | null;
  id_unidade: number | null;
  id_contrato: number | null;
  categoria: CategoriaDebito | "";
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

function formVazio(): FormState {
  return {
    id_fornecedor: null, id_natureza: null, id_fonte_recursos: null, id_unidade: null,
    id_contrato: null, categoria: "", valor_total: "", competencia: "", numero_ne: "",
    numero_nf: "", criticidade: "MEDIA", urgente: false, justificativa_urgencia: "",
    descricao: "", vencimento: "",
  };
}

function formDoDebito(d: DebitoDetalhe): FormState {
  return {
    id_fornecedor: d.id_fornecedor, id_natureza: d.id_natureza,
    id_fonte_recursos: d.id_fonte_recursos, id_unidade: d.id_unidade,
    id_contrato: d.id_contrato, categoria: d.categoria ?? "",
    valor_total: String(d.valor_total), competencia: d.competencia,
    numero_ne: d.numero_ne ?? "", numero_nf: d.numero_nf ?? "",
    criticidade: d.criticidade, urgente: d.urgente,
    justificativa_urgencia: d.justificativa_urgencia ?? "", descricao: d.descricao,
    vencimento: d.parcelas.length === 1 ? d.parcelas[0].vencimento : "",
  };
}

/**
 * Formulário da solicitação de pagamento — criação e edição.
 *
 * `debito` presente = edição. O backend só aceita editar em rascunho ou em
 * ajuste (409 fora disso); quem decide mostrar o caminho até aqui é o detalhe.
 *
 * Este formulário trabalha com UMA parcela. Débito que já tem várias (criado
 * por outra via) mantém as parcelas como estão: valor e vencimento ficam
 * travados, porque reenviar uma parcela só apagaria as outras.
 */
export function FormularioDebito({ debito }: { debito?: DebitoDetalhe }) {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();
  const editando = !!debito;
  const variasParcelas = !!debito && debito.parcelas.length > 1;

  const [form, setForm] = useState<FormState>(() => (debito ? formDoDebito(debito) : formVazio()));
  const [erros, setErros] = useState<Record<string, string>>({});

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

  function validar(f: FormState): Record<string, string> {
    const e: Record<string, string> = {};
    if (!f.id_fornecedor) e.id_fornecedor = "Fornecedor é obrigatório";
    if (!f.id_natureza) e.id_natureza = "Natureza é obrigatória";
    if (!f.id_fonte_recursos) e.id_fonte_recursos = "Fonte de recursos é obrigatória";
    if (!f.id_unidade) e.id_unidade = "Unidade solicitante é obrigatória";
    // Sem contrato, a categoria é o que posiciona o débito na fila
    // cronológica: sem ela a liquidação não pode ser confirmada.
    if (!f.id_contrato && !f.categoria) e.categoria = "Sem contrato, a categoria é obrigatória";
    if (!f.valor_total) e.valor_total = "Valor é obrigatório";
    if (!f.competencia) e.competencia = "Competência é obrigatória";
    if (!f.descricao.trim()) e.descricao = "Descrição é obrigatória";
    if (!variasParcelas && !f.vencimento) e.vencimento = "Vencimento é obrigatório";
    if (f.urgente && !f.justificativa_urgencia.trim())
      e.justificativa_urgencia = "Explique a urgência";
    return e;
  }

  const salvarM = useMutation({
    mutationFn: async (f: FormState) => {
      const e = validar(f);
      if (Object.keys(e).length > 0) {
        setErros(e);
        throw new Error("Preencha os campos obrigatórios");
      }
      const { vencimento, ...dados } = f;
      const corpo = {
        ...dados,
        id_contrato: dados.id_contrato || null,
        // Com contrato, a categoria vem dele; a do débito não é usada.
        categoria: dados.id_contrato ? null : dados.categoria || null,
        numero_ne: dados.numero_ne.trim() || null,
        numero_nf: dados.numero_nf.trim() || null,
        justificativa_urgencia: dados.urgente ? dados.justificativa_urgencia.trim() || null : null,
      };
      if (!debito) {
        return api.pagamentos.debitos.create({
          ...corpo,
          parcelas: [{ numero: 1, valor: Number(dados.valor_total), vencimento }],
        });
      }
      if (variasParcelas) {
        // Valor e parcelas ficam como estão.
        const { valor_total: _valor, ...semValor } = corpo;
        return api.pagamentos.debitos.update(debito.id, semValor);
      }
      return api.pagamentos.debitos.update(debito.id, {
        ...corpo,
        parcelas: [{ numero: 1, valor: Number(dados.valor_total), vencimento }],
      });
    },
    onSuccess: (salvo) => {
      toast.success(editando ? "Solicitação atualizada" : "Solicitação criada com sucesso");
      qc.invalidateQueries({ queryKey: ["pag-solicitacoes-fluxo"] });
      qc.invalidateQueries({ queryKey: ["pag-debito", salvo.id] });
      qc.invalidateQueries({ queryKey: ["pag-versoes", salvo.id] });
      router.push(`/m/pagamentos/solicitacoes/${salvo.id}`);
    },
    onError: (err: Error) => {
      toast.error(err.message || "Erro ao salvar a solicitação");
    },
  });

  function mudar<K extends keyof FormState>(campo: K, valor: FormState[K]) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
    if (erros[campo]) setErros((prev) => ({ ...prev, [campo]: "" }));
  }

  const numero = (v: string) => (v ? Number(v) : null);
  const erro = (campo: string) =>
    erros[campo] ? (
      <p id={`erro-${campo}`} className="mt-1 text-xs text-danger">
        {erros[campo]}
      </p>
    ) : null;

  return (
    <div className="max-w-2xl space-y-6">
      {debito && debito.situacao_tramitacao !== "RASCUNHO" && (
        <p className="rounded-lg border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
          Esta solicitação está em ajuste. Alterar fornecedor, valor, fonte, natureza ou
          parcelas é uma alteração material: a versão atual fica guardada e as aprovações já
          dadas deixam de valer.
        </p>
      )}

      <div>
        <Label htmlFor="deb-fornecedor" required>Fornecedor</Label>
        <Select
          id="deb-fornecedor"
          value={form.id_fornecedor?.toString() ?? ""}
          onChange={(e) => mudar("id_fornecedor", numero(e.target.value))}
        >
          <option value="">Selecionar fornecedor...</option>
          {fornecedoresQ.data?.map((f) => (
            <option key={f.id} value={f.id}>{f.nome}</option>
          ))}
        </Select>
        {erro("id_fornecedor")}
      </div>

      <div>
        <Label htmlFor="deb-natureza" required>Natureza da despesa</Label>
        <Select
          id="deb-natureza"
          value={form.id_natureza?.toString() ?? ""}
          onChange={(e) => mudar("id_natureza", numero(e.target.value))}
        >
          <option value="">Selecionar natureza...</option>
          {naturezasQ.data?.map((n) => (
            <option key={n.id} value={n.id}>{n.descricao}</option>
          ))}
        </Select>
        {erro("id_natureza")}
      </div>

      <div>
        <Label htmlFor="deb-fonte" required>Fonte de recursos</Label>
        <Select
          id="deb-fonte"
          value={form.id_fonte_recursos?.toString() ?? ""}
          onChange={(e) => mudar("id_fonte_recursos", numero(e.target.value))}
        >
          <option value="">Selecionar fonte...</option>
          {fontesQ.data?.map((f) => (
            <option key={f.id} value={f.id}>{f.codigo} - {f.descricao}</option>
          ))}
        </Select>
        {erro("id_fonte_recursos")}
      </div>

      <div>
        <Label htmlFor="deb-contrato">Contrato</Label>
        <Select
          id="deb-contrato"
          value={form.id_contrato?.toString() ?? ""}
          onChange={(e) => mudar("id_contrato", numero(e.target.value))}
        >
          <option value="">Nenhum contrato</option>
          {contratosQ.data?.map((c) => (
            <option key={c.id} value={c.id}>{c.numero}</option>
          ))}
        </Select>
      </div>

      {form.id_contrato ? (
        <p className="text-sm text-foreground-muted">
          A categoria desta despesa é a do contrato escolhido.
        </p>
      ) : (
        <div>
          <Label htmlFor="deb-categoria" required>Categoria</Label>
          <Select
            id="deb-categoria"
            value={form.categoria}
            onChange={(e) => mudar("categoria", e.target.value as CategoriaDebito | "")}
          >
            <option value="">Selecionar categoria...</option>
            {CATEGORIAS_DEBITO.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </Select>
          <p className="mt-1 text-xs text-foreground-muted">
            Define em qual fila cronológica de pagamento a despesa entra.
          </p>
          {erro("categoria")}
        </div>
      )}

      <div>
        <Label htmlFor="deb-unidade" required>Unidade solicitante</Label>
        <Select
          id="deb-unidade"
          value={form.id_unidade?.toString() ?? ""}
          onChange={(e) => mudar("id_unidade", numero(e.target.value))}
        >
          <option value="">Selecionar unidade...</option>
          {unidadesQ.data?.items.map((u) => (
            <option key={u.id} value={u.id}>{u.unidade_trabalho}</option>
          ))}
        </Select>
        {erro("id_unidade")}
      </div>

      <div>
        <Label htmlFor="deb-valor" required>Valor total</Label>
        <Input
          id="deb-valor"
          type="number"
          step="0.01"
          value={form.valor_total}
          onChange={(e) => mudar("valor_total", e.target.value)}
          placeholder="0.00"
          disabled={variasParcelas}
        />
        {erro("valor_total")}
      </div>

      <div>
        <Label htmlFor="deb-competencia" required>Competência</Label>
        <Input
          id="deb-competencia"
          type="month"
          value={form.competencia}
          onChange={(e) => mudar("competencia", e.target.value)}
        />
        {erro("competencia")}
      </div>

      {variasParcelas ? (
        <p className="text-sm text-foreground-muted">
          Esta solicitação tem {debito?.parcelas.length} parcelas. O valor total e os vencimentos
          não são alterados por este formulário.
        </p>
      ) : (
        <div>
          <Label htmlFor="deb-vencimento" required>Vencimento da parcela</Label>
          <Input
            id="deb-vencimento"
            type="date"
            value={form.vencimento}
            onChange={(e) => mudar("vencimento", e.target.value)}
          />
          {erro("vencimento")}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="deb-ne">Nota de empenho (NE)</Label>
          <Input
            id="deb-ne"
            value={form.numero_ne}
            onChange={(e) => mudar("numero_ne", e.target.value)}
            placeholder="Número do empenho"
          />
          <p className="mt-1 text-xs text-foreground-muted">
            Exigida para a autorização do pagamento.
          </p>
        </div>
        <div>
          <Label htmlFor="deb-nf">Nota fiscal (NF)</Label>
          <Input
            id="deb-nf"
            value={form.numero_nf}
            onChange={(e) => mudar("numero_nf", e.target.value)}
            placeholder="Número da nota fiscal"
          />
        </div>
      </div>

      <div>
        <Label htmlFor="deb-criticidade">Criticidade</Label>
        <Select
          id="deb-criticidade"
          value={form.criticidade}
          onChange={(e) => mudar("criticidade", e.target.value)}
        >
          <option value="BAIXA">Baixa</option>
          <option value="MEDIA">Média</option>
          <option value="ALTA">Alta</option>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="urgente"
          checked={form.urgente}
          onChange={(e) => mudar("urgente", e.target.checked)}
        />
        <Label htmlFor="urgente">Marcar como urgente</Label>
      </div>

      {form.urgente && (
        <div>
          <Label htmlFor="deb-urgencia" required>Justificativa de urgência</Label>
          <Textarea
            id="deb-urgencia"
            value={form.justificativa_urgencia}
            onChange={(e) => mudar("justificativa_urgencia", e.target.value)}
            placeholder="Explique por que é urgente..."
            className="min-h-20"
          />
          {erro("justificativa_urgencia")}
        </div>
      )}

      <div>
        <Label htmlFor="deb-descricao" required>Descrição</Label>
        <Textarea
          id="deb-descricao"
          value={form.descricao}
          onChange={(e) => mudar("descricao", e.target.value)}
          placeholder="Descreva o débito..."
          className="min-h-20"
        />
        {erro("descricao")}
      </div>

      <div className="flex gap-3 pt-4">
        <Button variant="secondary" onClick={() => router.back()}>
          Cancelar
        </Button>
        <Button onClick={() => salvarM.mutate(form)} disabled={salvarM.isPending}>
          {salvarM.isPending
            ? "Salvando..."
            : editando
              ? "Salvar alterações"
              : "Criar Solicitação"}
        </Button>
      </div>
    </div>
  );
}
