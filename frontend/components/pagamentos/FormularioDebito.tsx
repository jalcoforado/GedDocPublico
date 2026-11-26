"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileText, Landmark, Receipt, Wallet } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { Alert } from "@/components/ui/alert";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Checkbox } from "@/components/ui/checkbox";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  LayoutFormulario,
  RoteiroFormulario,
  resumoDoQueFalta,
  type EtapaRoteiro,
} from "@/components/ui/roteiro-formulario";
import { SectionCard } from "@/components/ui/section-card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  CATEGORIA_CONTRATO_LABEL,
  type CategoriaDebito,
  type Contrato,
  type DebitoDetalhe,
  type Fornecedor,
  type NaturezaDespesa,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { aplicarMascara } from "@/lib/mascaras";

/** Categorias da fila cronológica — espelha `CategoriaLit` (backend). */
export const CATEGORIAS_DEBITO: { value: CategoriaDebito; label: string }[] = [
  { value: "BENS", label: "Fornecimento de bens" },
  { value: "LOCACOES", label: "Locações" },
  { value: "SERVICOS", label: "Prestação de serviços" },
  { value: "OBRAS", label: "Obras" },
];

// Rótulo curto no botão (quatro lado a lado não cabem com o nome longo); o
// nome completo vai na frase que aparece sob a escolha.
const OPCOES_CATEGORIA: OpcaoEscolha<CategoriaDebito>[] = [
  { valor: "BENS", rotulo: "Bens", descricao: "Fornecimento de bens — entra na fila cronológica de bens." },
  { valor: "LOCACOES", rotulo: "Locações", descricao: "Aluguel de imóvel, veículo ou equipamento — fila de locações." },
  { valor: "SERVICOS", rotulo: "Serviços", descricao: "Prestação de serviços — fila de serviços." },
  { valor: "OBRAS", rotulo: "Obras", descricao: "Obras e reformas — fila de obras." },
];

type Criticidade = "BAIXA" | "MEDIA" | "ALTA" | "URGENTE";

const OPCOES_CRITICIDADE: OpcaoEscolha<Criticidade>[] = [
  { valor: "BAIXA", rotulo: "Baixa" },
  { valor: "MEDIA", rotulo: "Média" },
  { valor: "ALTA", rotulo: "Alta" },
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

type Campo = keyof FormState;

/** "aaaa-mm" do mês corrente — a competência mais comum de uma despesa nova. */
function mesAtual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formVazio(): FormState {
  return {
    id_fornecedor: null, id_natureza: null, id_fonte_recursos: null, id_unidade: null,
    id_contrato: null, categoria: "", valor_total: "", competencia: mesAtual(), numero_ne: "",
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

/** Id do controle de cada campo: âncora do roteiro e alvo do foco no erro. */
const ID: Partial<Record<Campo, string>> = {
  id_fornecedor: "deb-fornecedor",
  id_contrato: "deb-contrato",
  descricao: "deb-descricao",
  id_natureza: "deb-natureza",
  categoria: "deb-categoria",
  justificativa_urgencia: "deb-urgencia",
  id_unidade: "deb-unidade",
  id_fonte_recursos: "deb-fonte",
  valor_total: "deb-valor",
  competencia: "deb-competencia",
  vencimento: "deb-vencimento",
};

/** Ordem da tela — o foco vai ao primeiro erro de cima para baixo. */
const ORDEM: Campo[] = [
  "id_fornecedor", "descricao", "id_natureza", "categoria", "justificativa_urgencia",
  "id_unidade", "id_fonte_recursos", "valor_total", "competencia", "vencimento",
];

/** Nome curto de cada obrigatório no roteiro e no "Falta: …" da barra. */
const ROTULO: Partial<Record<Campo, string>> = {
  id_fornecedor: "Fornecedor",
  descricao: "Descrição",
  id_natureza: "Natureza",
  categoria: "Categoria",
  justificativa_urgencia: "Justificativa da urgência",
  id_unidade: "Unidade solicitante",
  id_fonte_recursos: "Fonte de recursos",
  valor_total: "Valor total",
  competencia: "Competência",
  vencimento: "Vencimento",
};

function focarCampo(campo: Campo) {
  if (campo === "categoria") {
    // Grupo de rádios: o foco vai à primeira opção.
    document.querySelector<HTMLInputElement>(`input[name="${ID.categoria}"]`)?.focus();
    return;
  }
  const id = ID[campo];
  if (id) document.getElementById(id)?.focus();
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
 *
 * As etapas seguem a ordem em que quem pede pensa: quem recebe → o que é →
 * de onde sai o dinheiro → quanto e quando → documentos. O corpo enviado à
 * API é o mesmo de antes; só a tela mudou.
 */
export function FormularioDebito({ debito }: { debito?: DebitoDetalhe }) {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();
  const { user } = useAuth();
  const editando = !!debito;
  const variasParcelas = !!debito && debito.parcelas.length > 1;

  const [form, setForm] = useState<FormState>(() => (debito ? formDoDebito(debito) : formVazio()));
  // Erro aparece só depois da tentativa: ao sair do campo (tocados) ou ao
  // enviar (tentou). Nunca ao abrir a tela.
  const [tocados, setTocados] = useState<Set<Campo>>(() => new Set());
  const [tentou, setTentou] = useState(false);
  // Criticidade escolhida à mão não é mais sobrescrita pela da natureza.
  const criticidadeManual = useRef(editando);

  const fornecedoresQ = useQuery({
    queryKey: ["pag-fornecedores"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
    // O atalho "Cadastrar fornecedor" abre outra aba: ao voltar, o novo já
    // aparece na lista sem recarregar a página (e sem perder o preenchido).
    refetchOnWindowFocus: true,
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

  // Unidade solicitante sugerida: a do usuário — só em solicitação nova, e só
  // se ela estiver na lista (senão o campo pareceria vazio com um valor dentro).
  const unidadeDoUsuario = user?.id_unidade_trabalho ?? null;
  const sugeriuUnidade = useRef(false);
  useEffect(() => {
    if (editando || sugeriuUnidade.current || !unidadesQ.data || unidadeDoUsuario == null) return;
    sugeriuUnidade.current = true;
    if (!unidadesQ.data.items.some((u) => u.id === unidadeDoUsuario)) return;
    setForm((prev) => (prev.id_unidade == null ? { ...prev, id_unidade: unidadeDoUsuario } : prev));
  }, [editando, unidadesQ.data, unidadeDoUsuario]);

  const fornecedor: Fornecedor | undefined = fornecedoresQ.data?.find((f) => f.id === form.id_fornecedor);
  const contrato: Contrato | undefined = contratosQ.data?.find((c) => c.id === form.id_contrato);
  const natureza: NaturezaDespesa | undefined = naturezasQ.data?.find((n) => n.id === form.id_natureza);

  function validar(f: FormState): Partial<Record<Campo, string>> {
    const e: Partial<Record<Campo, string>> = {};
    if (!f.id_fornecedor) e.id_fornecedor = "Escolha quem vai receber o pagamento.";
    if (!f.descricao.trim()) e.descricao = "Descreva em uma linha o que está sendo pago.";
    if (!f.id_natureza) e.id_natureza = "Escolha a natureza da despesa.";
    // Sem contrato, a categoria é o que posiciona o débito na fila
    // cronológica: sem ela a liquidação não pode ser confirmada.
    if (!f.id_contrato && !f.categoria)
      e.categoria = "Sem contrato, escolha a categoria: é ela que põe a despesa na fila de pagamento.";
    if (f.urgente && !f.justificativa_urgencia.trim())
      e.justificativa_urgencia = "Explique por que é urgente — quem aprova vai ler isto.";
    if (!f.id_unidade) e.id_unidade = "Escolha a unidade que está pedindo o pagamento.";
    if (!f.id_fonte_recursos) e.id_fonte_recursos = "Escolha a fonte de recursos que paga esta despesa.";
    if (!variasParcelas) {
      if (!f.valor_total) e.valor_total = "Informe o valor, ex.: 1250,00.";
      else if (!(Number(f.valor_total) > 0)) e.valor_total = "O valor tem de ser maior que zero.";
    }
    if (!f.competencia) e.competencia = "Informe o mês a que a despesa se refere.";
    if (!variasParcelas && !f.vencimento) e.vencimento = "Informe a data de vencimento.";
    return e;
  }

  const errosAtuais = validar(form);
  const erroDe = (campo: Campo) =>
    tentou || tocados.has(campo) ? errosAtuais[campo] : undefined;
  const tocar = (campo: Campo) => () =>
    setTocados((prev) => (prev.has(campo) ? prev : new Set(prev).add(campo)));

  // Trava contra clique duplo: o `isPending` só desabilita o botão depois que
  // o React redesenha, e dois cliques rápidos criavam duas solicitações.
  const enviando = useRef(false);

  const salvarM = useMutation({
    mutationFn: async (f: FormState) => {
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
      enviando.current = false;
      toast.error(err.message || "Erro ao salvar a solicitação");
    },
  });

  function enviar() {
    setTentou(true);
    const primeiro = ORDEM.find((c) => errosAtuais[c]);
    if (primeiro) {
      focarCampo(primeiro);
      return;
    }
    if (enviando.current) return;
    enviando.current = true;
    salvarM.mutate(form);
  }

  function mudar<K extends Campo>(campo: K, valor: FormState[K]) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
  }

  function escolherNatureza(id: number | null) {
    const n = naturezasQ.data?.find((x) => x.id === id);
    setForm((prev) => {
      const prox = { ...prev, id_natureza: id };
      // A natureza traz uma criticidade padrão; vale até a pessoa escolher outra.
      if (n && !criticidadeManual.current && ["BAIXA", "MEDIA", "ALTA"].includes(n.criticidade_padrao)) {
        prox.criticidade = n.criticidade_padrao;
      }
      return prox;
    });
  }

  function escolherContrato(id: number | null) {
    const c = contratosQ.data?.find((x) => x.id === id);
    setForm((prev) => ({
      ...prev,
      id_contrato: id,
      // Contrato escolhido antes do fornecedor já diz quem recebe.
      id_fornecedor: prev.id_fornecedor ?? c?.id_fornecedor ?? null,
    }));
  }

  // ---------- Opções das listas ----------
  const nomeFornecedor = useMemo(
    () => new Map((fornecedoresQ.data ?? []).map((f) => [f.id, f.nome])),
    [fornecedoresQ.data],
  );

  const opcoesFornecedor = useMemo<ComboboxOption[]>(
    () =>
      (fornecedoresQ.data ?? []).map((f) => ({
        value: f.id,
        label: f.nome,
        hint: f.cnpj_cpf
          ? aplicarMascara(f.tipo_pessoa === "FISICA" ? "cpf" : "cnpj", f.cnpj_cpf).valor
          : undefined,
      })),
    [fornecedoresQ.data],
  );

  // Contratos do fornecedor escolhido primeiro. Os dos outros continuam na
  // lista (o backend não exige que batam), marcados para chamar atenção.
  const opcoesContrato = useMemo<ComboboxOption[]>(() => {
    const lista = [...(contratosQ.data ?? [])];
    if (form.id_fornecedor) {
      lista.sort(
        (a, b) =>
          Number(b.id_fornecedor === form.id_fornecedor) - Number(a.id_fornecedor === form.id_fornecedor),
      );
    }
    return lista.map((c) => {
      const outro = form.id_fornecedor && c.id_fornecedor !== form.id_fornecedor;
      const partes = [
        outro ? `de ${nomeFornecedor.get(c.id_fornecedor) ?? "outro fornecedor"}` : null,
        c.objeto || null,
      ].filter(Boolean);
      return { value: c.id, label: c.numero, hint: partes.join(" · ") || undefined };
    });
  }, [contratosQ.data, form.id_fornecedor, nomeFornecedor]);

  const opcoesNatureza = useMemo<ComboboxOption[]>(
    () =>
      (naturezasQ.data ?? []).map((n) => ({ value: n.id, label: n.descricao, hint: n.codigo || undefined })),
    [naturezasQ.data],
  );

  const opcoesFonte = useMemo<ComboboxOption[]>(
    () =>
      (fontesQ.data ?? []).map((f) => ({
        value: f.id,
        label: `${f.codigo} - ${f.descricao}`,
        hint:
          f.situacao === "SUSPENSA" ? "Suspensa" : f.situacao === "ENCERRADA" ? "Encerrada" : undefined,
      })),
    [fontesQ.data],
  );

  const opcoesUnidade = useMemo<ComboboxOption[]>(
    () =>
      (unidadesQ.data?.items ?? []).map((u) => ({
        value: u.id,
        label: u.unidade_trabalho,
        hint: u.sigla || undefined,
      })),
    [unidadesQ.data],
  );

  // ---------- Roteiro (o que falta, por etapa) ----------
  const falta = (campos: Campo[]) =>
    campos
      .filter((c) => errosAtuais[c])
      .map((c) => ({ rotulo: ROTULO[c] ?? c, campoId: ID[c] ?? c }));

  const etapas: EtapaRoteiro[] = [
    { id: "deb-sec-recebe", titulo: "Quem recebe", faltando: falta(["id_fornecedor"]) },
    {
      id: "deb-sec-despesa",
      titulo: "O que é a despesa",
      faltando: falta(["descricao", "id_natureza", "categoria", "justificativa_urgencia"]),
    },
    {
      id: "deb-sec-origem",
      titulo: "De onde sai o dinheiro",
      faltando: falta(["id_unidade", "id_fonte_recursos"]),
    },
    {
      id: "deb-sec-valor",
      titulo: variasParcelas ? "Valor e parcelas" : "Valor e vencimento",
      faltando: falta(["valor_total", "competencia", "vencimento"]),
    },
    { id: "deb-sec-documentos", titulo: "Documentos", faltando: [], opcional: true },
  ];
  const pendentes = ORDEM.filter((c) => errosAtuais[c]);

  // ---------- Avisos de contexto ----------
  const docFornecedor = fornecedor?.cnpj_cpf
    ? aplicarMascara(fornecedor.tipo_pessoa === "FISICA" ? "cpf" : "cnpj", fornecedor.cnpj_cpf).valor
    : null;
  const avisoFornecedor = fornecedor
    ? [
        fornecedor.situacao_cadastral !== "REGULAR"
          ? `Cadastro ${fornecedor.situacao_cadastral === "PENDENTE" ? "pendente" : "irregular"}${
              fornecedor.motivo_pendencia ? `: ${fornecedor.motivo_pendencia}` : ""
            }.`
          : null,
        fornecedor.tem_dados_bancarios ? null : "Sem dados bancários cadastrados.",
      ].filter(Boolean).join(" ")
    : "";

  const contratoDeOutro = !!contrato && !!form.id_fornecedor && contrato.id_fornecedor !== form.id_fornecedor;
  const contratoVencido = !!contrato && contrato.vigencia_fim < hojeIso();
  const vencimentoPassado = !!form.vencimento && form.vencimento < hojeIso();
  const valorNumero = Number(form.valor_total);

  return (
    <LayoutFormulario roteiro={<RoteiroFormulario etapas={etapas} />}>
      {debito && debito.situacao_tramitacao !== "RASCUNHO" && (
        <Alert intent="warning" title="Esta solicitação voltou para ajuste">
          Mudar quem recebe, o valor, a fonte, a unidade, a descrição ou as notas é uma
          alteração material: a versão atual fica guardada e as aprovações já dadas deixam de
          valer. Natureza, competência e criticidade podem mudar sem isso.
        </Alert>
      )}

      {tentou && pendentes.length > 1 && (
        <Alert intent="danger" title={`Faltam ${pendentes.length} campos para continuar`}>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {pendentes.map((c) => (
              <li key={c}>
                <button
                  type="button"
                  onClick={() => focarCampo(c)}
                  className="underline underline-offset-2 hover:no-underline"
                >
                  {ROTULO[c]}
                </button>
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {/* === 1. Quem recebe === */}
      <SectionCard
        id="deb-sec-recebe"
        step={1}
        icon={Building2}
        title="Quem recebe"
        description="O fornecedor que vai receber e, se houver, o contrato da despesa."
      >
        <FormField
          label="Fornecedor"
          required
          error={erroDe("id_fornecedor")}
          hint={
            fornecedor
              ? [docFornecedor, avisoFornecedor].filter(Boolean).join(" · ") || "Cadastro regular."
              : "Busque pelo nome ou pelo CPF/CNPJ."
          }
        >
          <Combobox
            id="deb-fornecedor"
            options={opcoesFornecedor}
            value={form.id_fornecedor}
            onChange={(v) => {
              mudar("id_fornecedor", typeof v === "number" ? v : null);
              tocar("id_fornecedor")();
            }}
            placeholder="Buscar fornecedor…"
            searchPlaceholder="Nome, CPF ou CNPJ…"
            emptyText="Nenhum fornecedor com esse nome."
            loading={fornecedoresQ.isLoading}
            footer={
              <a
                href="/m/pagamentos/cadastros/fornecedores"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <span aria-hidden="true">+</span> Cadastrar fornecedor (abre em outra aba)
              </a>
            }
          />
        </FormField>

        <FormField
          label="Contrato"
          opcional
          hint={
            contrato
              ? [
                  contratoDeOutro
                    ? `Atenção: este contrato é de ${nomeFornecedor.get(contrato.id_fornecedor) ?? "outro fornecedor"}.`
                    : null,
                  contratoVencido ? `Vigência encerrada em ${fmtData(contrato.vigencia_fim)}.` : null,
                  contrato.categoria
                    ? `Categoria do contrato: ${CATEGORIA_CONTRATO_LABEL[contrato.categoria]}.`
                    : null,
                ].filter(Boolean).join(" ")
              : form.id_fornecedor
                ? "Os contratos deste fornecedor aparecem primeiro. Sem contrato, você escolhe a categoria abaixo."
                : "Sem contrato, você escolhe a categoria da despesa na próxima etapa."
          }
        >
          <Combobox
            id="deb-contrato"
            options={opcoesContrato}
            value={form.id_contrato}
            onChange={(v) => escolherContrato(typeof v === "number" ? v : null)}
            placeholder="Nenhum contrato"
            searchPlaceholder="Número ou objeto…"
            emptyText="Nenhum contrato encontrado."
            loading={contratosQ.isLoading}
          />
        </FormField>
      </SectionCard>

      {/* === 2. O que é a despesa === */}
      <SectionCard
        id="deb-sec-despesa"
        step={2}
        icon={FileText}
        title="O que é a despesa"
        description="O que está sendo pago, como é classificado e com que prioridade."
      >
        <FormField
          label="Descrição"
          required
          error={erroDe("descricao")}
          hint={`Aparece nas filas e no extrato do pagamento. ${form.descricao.length}/255 caracteres.`}
        >
          <Textarea
            id="deb-descricao"
            value={form.descricao}
            onChange={(e) => mudar("descricao", e.target.value)}
            onBlur={tocar("descricao")}
            maxLength={255}
            rows={2}
            placeholder="Ex.: Material de limpeza para as escolas — outubro"
            className="min-h-16"
          />
        </FormField>

        <FormField
          label="Natureza da despesa"
          required
          error={erroDe("id_natureza")}
          hint={natureza?.codigo ? `Código ${natureza.codigo}.` : "Busque pela descrição ou pelo código."}
        >
          <Combobox
            id="deb-natureza"
            options={opcoesNatureza}
            value={form.id_natureza}
            onChange={(v) => {
              escolherNatureza(typeof v === "number" ? v : null);
              tocar("id_natureza")();
            }}
            placeholder="Buscar natureza…"
            searchPlaceholder="Descrição ou código…"
            emptyText="Nenhuma natureza encontrada."
            loading={naturezasQ.isLoading}
          />
        </FormField>

        {form.id_contrato ? (
          <p className="rounded-md bg-surface-2 px-3 py-2 text-sm text-foreground-muted">
            A categoria desta despesa é a do contrato escolhido.
          </p>
        ) : (
          <div id={ID.categoria} className="scroll-mt-24 space-y-1">
            <EscolhaSegmentada
              nome={ID.categoria as string}
              titulo="Categoria"
              valor={form.categoria as CategoriaDebito}
              opcoes={OPCOES_CATEGORIA}
              onChange={(v) => {
                mudar("categoria", v);
                tocar("categoria")();
              }}
              moldura={false}
            />
            {erroDe("categoria") ? (
              <p className="text-xs font-medium text-danger-soft-foreground" role="alert">
                {erroDe("categoria")}
              </p>
            ) : (
              !form.categoria && (
                <p className="text-xs text-foreground-muted">
                  Define em qual fila cronológica de pagamento a despesa entra.
                </p>
              )
            )}
          </div>
        )}

        <EscolhaSegmentada
          nome="deb-criticidade"
          titulo="Criticidade"
          valor={form.criticidade as Criticidade}
          opcoes={
            // Débito antigo pode estar como "Urgente" (criado por outra via):
            // a opção aparece só nesse caso, para o valor não sumir da tela.
            form.criticidade === "URGENTE"
              ? [...OPCOES_CRITICIDADE, { valor: "URGENTE", rotulo: "Urgente" }]
              : OPCOES_CRITICIDADE
          }
          onChange={(v) => {
            criticidadeManual.current = true;
            mudar("criticidade", v);
          }}
          moldura={false}
        />
        {!criticidadeManual.current && natureza && (
          <p className="-mt-2 text-xs text-foreground-muted">
            Sugerida pela natureza escolhida. Pode mudar.
          </p>
        )}

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Checkbox
              id="deb-urgente"
              checked={form.urgente}
              onChange={(e) => mudar("urgente", e.target.checked)}
              aria-describedby="deb-urgente-hint"
            />
            <Label htmlFor="deb-urgente" className="mb-0">
              Pagamento urgente
            </Label>
          </div>
          <p id="deb-urgente-hint" className="pl-7 text-xs text-foreground-muted">
            Passa à frente nas filas e pede uma justificativa.
          </p>
        </div>

        {form.urgente && (
          <FormField
            label="Justificativa da urgência"
            required
            error={erroDe("justificativa_urgencia")}
            hint="Quem aprova vai ler isto. Até 255 caracteres."
          >
            <Textarea
              id="deb-urgencia"
              value={form.justificativa_urgencia}
              onChange={(e) => mudar("justificativa_urgencia", e.target.value)}
              onBlur={tocar("justificativa_urgencia")}
              maxLength={255}
              rows={2}
              placeholder="Ex.: Fornecedor suspende a entrega se não receber até sexta."
              className="min-h-16"
            />
          </FormField>
        )}
      </SectionCard>

      {/* === 3. De onde sai o dinheiro === */}
      <SectionCard
        id="deb-sec-origem"
        step={3}
        icon={Landmark}
        title="De onde sai o dinheiro"
        description="A unidade que pede o pagamento e a fonte de recursos que o cobre."
      >
        <FormField
          label="Unidade solicitante"
          required
          error={erroDe("id_unidade")}
          hint={
            !editando && unidadeDoUsuario != null && form.id_unidade === unidadeDoUsuario
              ? "Preenchida com a sua unidade. Troque se o pedido for de outra."
              : "Busque pelo nome ou pela sigla."
          }
        >
          <Combobox
            id="deb-unidade"
            options={opcoesUnidade}
            value={form.id_unidade}
            onChange={(v) => {
              mudar("id_unidade", typeof v === "number" ? v : null);
              tocar("id_unidade")();
            }}
            placeholder="Buscar unidade…"
            searchPlaceholder="Nome ou sigla…"
            emptyText="Nenhuma unidade encontrada."
            loading={unidadesQ.isLoading}
          />
        </FormField>

        <FormField
          label="Fonte de recursos"
          required
          error={erroDe("id_fonte_recursos")}
          hint="A fonte do empenho. É ela que define de quais contas o pagamento pode sair."
        >
          <Combobox
            id="deb-fonte"
            options={opcoesFonte}
            value={form.id_fonte_recursos}
            onChange={(v) => {
              mudar("id_fonte_recursos", typeof v === "number" ? v : null);
              tocar("id_fonte_recursos")();
            }}
            placeholder="Buscar fonte…"
            searchPlaceholder="Código ou descrição…"
            emptyText="Nenhuma fonte encontrada."
            loading={fontesQ.isLoading}
          />
        </FormField>
      </SectionCard>

      {/* === 4. Valor e vencimento === */}
      <SectionCard
        id="deb-sec-valor"
        step={4}
        icon={Wallet}
        title={variasParcelas ? "Valor e parcelas" : "Valor e vencimento"}
        description={
          variasParcelas
            ? "O valor e as parcelas desta solicitação não mudam por aqui."
            : "Quanto se paga, a que mês a despesa pertence e quando vence."
        }
      >
        {/* "R$" grudado no campo e placeholder com vírgula: o "0.00" de antes
            parecia valor já preenchido, e em notação americana. */}
        <FormField
          label="Valor total"
          required={!variasParcelas}
          error={erroDe("valor_total")}
          hint={
            variasParcelas
              ? `Dividido em ${debito?.parcelas.length} parcelas — veja abaixo.`
              : form.valor_total && valorNumero > 0
                ? `${fmtMoeda(valorNumero)} em uma parcela.`
                : "Pago em uma parcela, no vencimento abaixo."
          }
        >
          <CampoComUnidade
            id="deb-valor"
            prefixo="R$"
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            value={form.valor_total}
            onChange={(e) => mudar("valor_total", e.target.value)}
            onBlur={tocar("valor_total")}
            placeholder="0,00"
            disabled={variasParcelas}
          />
        </FormField>

        <GradeCampos>
          <FormField
            label="Competência"
            required
            error={erroDe("competencia")}
            hint={editando ? "Mês a que a despesa se refere." : "Mês a que a despesa se refere. Começa no mês atual."}
          >
            <Input
              id="deb-competencia"
              type="month"
              value={form.competencia}
              onChange={(e) => mudar("competencia", e.target.value)}
              onBlur={tocar("competencia")}
            />
          </FormField>

          {!variasParcelas && (
            <FormField
              label="Vencimento"
              required
              error={erroDe("vencimento")}
              hint={vencimentoPassado ? "Esta data já passou — confira." : "Data limite para pagar sem atraso."}
            >
              <Input
                id="deb-vencimento"
                type="date"
                value={form.vencimento}
                onChange={(e) => mudar("vencimento", e.target.value)}
                onBlur={tocar("vencimento")}
              />
            </FormField>
          )}
        </GradeCampos>

        {variasParcelas && debito && (
          <ul className="divide-y divide-border rounded-md border border-border text-sm">
            {debito.parcelas.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2">
                <span className="text-foreground-muted">Parcela {p.numero}</span>
                <span className="tabular-nums text-foreground">{fmtMoeda(p.valor)}</span>
                <span className="tabular-nums text-foreground-muted">vence {fmtData(p.vencimento)}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* === 5. Documentos === */}
      <SectionCard
        id="deb-sec-documentos"
        step={5}
        icon={Receipt}
        title="Documentos"
        description="Números do empenho e da nota fiscal. Dá para informar depois, editando a solicitação."
      >
        <GradeCampos>
          <FormField
            label="Nota de empenho (NE)"
            opcional
            hint="Exigida para a autorização do pagamento."
          >
            <Input
              id="deb-ne"
              value={form.numero_ne}
              onChange={(e) => mudar("numero_ne", e.target.value)}
              maxLength={30}
              placeholder="Ex.: 2026NE000123"
            />
          </FormField>
          <FormField label="Nota fiscal (NF)" opcional hint="Número da nota emitida pelo fornecedor.">
            <Input
              id="deb-nf"
              value={form.numero_nf}
              onChange={(e) => mudar("numero_nf", e.target.value)}
              maxLength={40}
              placeholder="Ex.: 4587"
            />
          </FormField>
        </GradeCampos>
      </SectionCard>

      <BarraAcoesFormulario
        status={
          resumoDoQueFalta(etapas) ??
          (editando ? "Tudo pronto. As alterações valem ao salvar." : "Tudo pronto para criar a solicitação.")
        }
      >
        <Button type="button" variant="ghost" onClick={() => router.back()}>
          Cancelar
        </Button>
        <Button type="button" onClick={enviar} loading={salvarM.isPending}>
          {editando ? "Salvar alterações" : "Criar solicitação"}
        </Button>
      </BarraAcoesFormulario>
    </LayoutFormulario>
  );
}
