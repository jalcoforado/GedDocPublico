"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErroFormulario, ROTA_CONTRATOS, nullify } from "@/components/contratos/comum";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  CATEGORIA_CONTRATO_LABEL,
  api,
  type CategoriaContrato,
  type ContratoInput,
  type NaturezaDuracaoContrato,
} from "@/lib/api";

const CATEGORIAS = Object.entries(CATEGORIA_CONTRATO_LABEL) as [CategoriaContrato, string][];

interface Form {
  numero: string;
  id_fornecedor: string;
  id_unidade: string;
  objeto: string;
  valor_total: string;
  vigencia_inicio: string;
  vigencia_fim: string;
  data_celebracao: string;
  categoria: CategoriaContrato | "";
  tipo_objeto: string;
  natureza_duracao: NaturezaDuracaoContrato | "";
  reforma: boolean;
  processo_numero: string;
  processo_data_autuacao: string;
  pncp_id: string;
  pncp_publicado_em: string;
}

const VAZIO: Form = {
  numero: "",
  id_fornecedor: "",
  id_unidade: "",
  objeto: "",
  valor_total: "",
  vigencia_inicio: "",
  vigencia_fim: "",
  data_celebracao: "",
  categoria: "",
  tipo_objeto: "",
  natureza_duracao: "",
  reforma: false,
  processo_numero: "",
  processo_data_autuacao: "",
  pncp_id: "",
  pncp_publicado_em: "",
};

export default function NovoContratoPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<Form>(VAZIO);
  const [err, setErr] = useState<string | null>(null);
  const [fornAberto, setFornAberto] = useState(false);
  const [forn, setForn] = useState({ tipo_pessoa: "JURIDICA", cnpj_cpf: "", nome: "" });
  const [fornErr, setFornErr] = useState<string | null>(null);

  const fornecedoresQ = useQuery({
    queryKey: ["contratos-fornecedores"],
    queryFn: () => api.contratos.fornecedores(),
  });
  const unidadesQ = useQuery({
    queryKey: ["contratos-unidades"],
    queryFn: () => api.unidades.list({ page: 1, page_size: 50 }),
  });
  const catalogosQ = useQuery({
    queryKey: ["contratos-catalogos"],
    queryFn: api.contratos.catalogos,
  });

  function set<K extends keyof Form>(campo: K, valor: Form[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
  }

  const criarM = useMutation({
    mutationFn: (payload: ContratoInput) => api.contratos.create(payload),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["contratos-lista"] });
      qc.invalidateQueries({ queryKey: ["contratos-painel"] });
      toast.success("Contrato criado em rascunho.");
      router.push(`${ROTA_CONTRATOS}/${c.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  // Fornecedor é cadastro do módulo de pagamentos. Quem contrata só
  // `contratos` não chega lá — então o mínimo (identificação, sem dado
  // bancário) se cadastra daqui.
  const criarFornM = useMutation({
    mutationFn: () =>
      api.contratos.criarFornecedor({
        tipo_pessoa: forn.tipo_pessoa,
        cnpj_cpf: forn.cnpj_cpf.trim(),
        nome: forn.nome.trim(),
      }),
    onSuccess: (novo) => {
      qc.invalidateQueries({ queryKey: ["contratos-fornecedores"] });
      set("id_fornecedor", String(novo.id));
      setFornAberto(false);
      setForn({ tipo_pessoa: "JURIDICA", cnpj_cpf: "", nome: "" });
      toast.success("Fornecedor cadastrado.");
    },
    onError: (e: Error) => setFornErr(e.message),
  });

  function salvarFornecedor() {
    setFornErr(null);
    if (!forn.nome.trim() || forn.cnpj_cpf.trim().length < 11) {
      setFornErr("Informe o nome e o CNPJ ou CPF.");
      return;
    }
    criarFornM.mutate();
  }

  function salvar() {
    setErr(null);
    const faltam: string[] = [];
    if (!form.numero.trim()) faltam.push("número");
    if (!form.id_fornecedor) faltam.push("contratado");
    if (!form.id_unidade) faltam.push("unidade");
    if (!form.objeto.trim()) faltam.push("objeto");
    if (!form.valor_total) faltam.push("valor");
    if (!form.vigencia_inicio) faltam.push("início da vigência");
    if (!form.vigencia_fim) faltam.push("fim da vigência");
    if (!form.categoria) faltam.push("categoria");
    if (faltam.length > 0) {
      setErr(`Preencha: ${faltam.join(", ")}.`);
      return;
    }
    criarM.mutate({
      numero: form.numero.trim(),
      id_fornecedor: Number(form.id_fornecedor),
      id_unidade: Number(form.id_unidade),
      objeto: form.objeto.trim(),
      valor_total: form.valor_total,
      vigencia_inicio: form.vigencia_inicio,
      vigencia_fim: form.vigencia_fim,
      categoria: form.categoria as CategoriaContrato,
      data_celebracao: nullify(form.data_celebracao),
      tipo_objeto: nullify(form.tipo_objeto),
      natureza_duracao: form.natureza_duracao === "" ? null : form.natureza_duracao,
      reforma: form.reforma,
      processo_numero: nullify(form.processo_numero),
      processo_data_autuacao: nullify(form.processo_data_autuacao),
      pncp_id: nullify(form.pncp_id),
      pncp_publicado_em: nullify(form.pncp_publicado_em),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Novo contrato"
        description="O contrato nasce em rascunho. Valor e vigência só congelam na assinatura."
        breadcrumbs={[
          { label: "Contratos e Convênios", href: "/m/contratos" },
          { label: "Contratos", href: ROTA_CONTRATOS },
          { label: "Novo" },
        ]}
      />

      <ErroFormulario mensagem={err} />

      {fornecedoresQ.data && fornecedoresQ.data.length === 0 && (
        <Alert intent="warning" title="Nenhum fornecedor cadastrado">
          O contrato precisa de um contratado. Use "Novo fornecedor", ao lado do campo
          Contratado.
        </Alert>
      )}

      <div className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
        <h2 className="text-sm font-semibold text-foreground">Identificação</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="numero" required>
              Número
            </Label>
            <Input
              id="numero"
              value={form.numero}
              maxLength={50}
              onChange={(e) => set("numero", e.target.value)}
              placeholder="012/2026"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Para assinar, até 15 caracteres — é o tamanho do campo no SIM do TCE-CE.
            </p>
          </div>
          <div>
            <Label htmlFor="fornecedor" required>
              Contratado
            </Label>
            <Select
              id="fornecedor"
              value={form.id_fornecedor}
              onChange={(e) => set("id_fornecedor", e.target.value)}
            >
              <option value="">Selecione</option>
              {fornecedoresQ.data?.map((f) => (
                <option key={f.id} value={String(f.id)}>
                  {f.nome}
                </option>
              ))}
            </Select>
            <button
              type="button"
              className="mt-1 text-xs text-primary hover:underline"
              onClick={() => {
                setFornErr(null);
                setFornAberto(true);
              }}
            >
              + Novo fornecedor
            </button>
          </div>
          <div>
            <Label htmlFor="unidade" required>
              Unidade contratante
            </Label>
            <Select
              id="unidade"
              value={form.id_unidade}
              onChange={(e) => set("id_unidade", e.target.value)}
            >
              <option value="">Selecione</option>
              {unidadesQ.data?.items.map((u) => (
                <option key={u.id} value={String(u.id)}>
                  {u.sigla ? `${u.sigla} — ${u.unidade_trabalho}` : u.unidade_trabalho}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div>
          <Label htmlFor="objeto" required>
            Objeto
          </Label>
          <Textarea
            id="objeto"
            rows={3}
            maxLength={3000}
            value={form.objeto}
            onChange={(e) => set("objeto", e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
        <h2 className="text-sm font-semibold text-foreground">Valor e vigência</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <Label htmlFor="valor" required>
              Valor (R$)
            </Label>
            <Input
              id="valor"
              type="number"
              min="0"
              step="0.01"
              value={form.valor_total}
              onChange={(e) => set("valor_total", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="celebracao">Data de celebração</Label>
            <Input
              id="celebracao"
              type="date"
              value={form.data_celebracao}
              onChange={(e) => set("data_celebracao", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="inicio" required>
              Início da vigência
            </Label>
            <Input
              id="inicio"
              type="date"
              value={form.vigencia_inicio}
              onChange={(e) => set("vigencia_inicio", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="fim" required>
              Fim da vigência
            </Label>
            <Input
              id="fim"
              type="date"
              value={form.vigencia_fim}
              onChange={(e) => set("vigencia_fim", e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
        <h2 className="text-sm font-semibold text-foreground">Classificação</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="categoria" required>
              Categoria (fila de pagamentos)
            </Label>
            <Select
              id="categoria"
              value={form.categoria}
              onChange={(e) => set("categoria", e.target.value as CategoriaContrato | "")}
            >
              <option value="">Selecione</option>
              {CATEGORIAS.map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="tipo_objeto">Tipo de objeto (SIM)</Label>
            <Select
              id="tipo_objeto"
              value={form.tipo_objeto}
              onChange={(e) => set("tipo_objeto", e.target.value)}
            >
              <option value="">Selecione</option>
              {catalogosQ.data?.tipos_objeto.map((t) => (
                <option key={t.codigo} value={t.codigo}>
                  {t.rotulo}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="natureza">Natureza da duração</Label>
            <Select
              id="natureza"
              value={form.natureza_duracao}
              onChange={(e) =>
                set("natureza_duracao", e.target.value as NaturezaDuracaoContrato | "")
              }
            >
              <option value="">Selecione</option>
              <option value="CONTINUO">Contínuo (serviço ou fornecimento)</option>
              <option value="ESCOPO">Escopo (obra ou entrega definida)</option>
            </Select>
          </div>
        </div>
        <label className="flex items-start gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="mt-1"
            checked={form.reforma}
            onChange={(e) => set("reforma", e.target.checked)}
          />
          <span>
            Reforma de edifício ou de equipamento
            <span className="block text-xs text-muted-foreground">
              Eleva o limite de acréscimo de 25% para 50% (art. 125 da Lei 14.133).
            </span>
          </span>
        </label>
        <p className="text-xs text-muted-foreground">
          Tipo de objeto, natureza e data de celebração podem ficar para depois, mas são exigidos
          na assinatura.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
        <h2 className="text-sm font-semibold text-foreground">Processo e publicação</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <Label htmlFor="proc_num">Nº do processo de contratação</Label>
            <Input
              id="proc_num"
              maxLength={15}
              value={form.processo_numero}
              onChange={(e) => set("processo_numero", e.target.value)}
              placeholder="2026.07.01.01CC"
            />
          </div>
          <div>
            <Label htmlFor="proc_data">Autuação do processo</Label>
            <Input
              id="proc_data"
              type="date"
              value={form.processo_data_autuacao}
              onChange={(e) => set("processo_data_autuacao", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="pncp_id">Id do contrato no PNCP</Label>
            <Input
              id="pncp_id"
              maxLength={25}
              value={form.pncp_id}
              onChange={(e) => set("pncp_id", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="pncp_data">Publicado no PNCP em</Label>
            <Input
              id="pncp_data"
              type="date"
              value={form.pncp_publicado_em}
              onChange={(e) => set("pncp_publicado_em", e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => router.push(ROTA_CONTRATOS)}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={criarM.isPending}>
          Salvar rascunho
        </Button>
      </div>

      <Dialog
        open={fornAberto}
        onClose={() => setFornAberto(false)}
        title="Novo fornecedor"
        description="Só a identificação. Dados bancários ficam no módulo de pagamentos."
        footer={
          <>
            <Button variant="secondary" onClick={() => setFornAberto(false)}>
              Cancelar
            </Button>
            <Button onClick={salvarFornecedor} loading={criarFornM.isPending}>
              Cadastrar
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <ErroFormulario mensagem={fornErr} />
          <div>
            <Label htmlFor="forn_tipo" required>
              Tipo
            </Label>
            <Select
              id="forn_tipo"
              value={forn.tipo_pessoa}
              onChange={(e) => setForn((f) => ({ ...f, tipo_pessoa: e.target.value }))}
            >
              <option value="JURIDICA">Pessoa jurídica</option>
              <option value="FISICA">Pessoa física</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="forn_doc" required>
              CNPJ ou CPF
            </Label>
            <Input
              id="forn_doc"
              maxLength={18}
              value={forn.cnpj_cpf}
              onChange={(e) => setForn((f) => ({ ...f, cnpj_cpf: e.target.value }))}
            />
          </div>
          <div>
            <Label htmlFor="forn_nome" required>
              Nome ou razão social
            </Label>
            <Input
              id="forn_nome"
              maxLength={200}
              value={forn.nome}
              onChange={(e) => setForn((f) => ({ ...f, nome: e.target.value }))}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
