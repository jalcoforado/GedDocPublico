"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  FileUp,
  Landmark,
  Link2,
  ListChecks,
  Undo2,
  X,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { BotaoExportarCsv } from "@/components/pagamentos/BotoesExportar";
import { fmtData, fmtDataHora, fmtMoeda } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField } from "@/components/ui/form-field";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type ExtratoBancario,
  type ImportarExtratoResultado,
  type LancamentoExtrato,
  type Movimentacao,
} from "@/lib/api";

const CHAVES_INVALIDAR = [
  ["pag-conc-extratos"],
  ["pag-conc-lancamentos"],
  ["pag-conc-sugestoes"],
  ["pag-caixa-painel"],
  ["pag-debitos"],
] as const;

/** Cabeçalho aceito pelo importador do backend (`_parse_csv`). */
const MODELO_CSV = "data;historico;documento;favorecido;valor;tipo";

type FormatoExtrato = "CSV" | "OFX" | "CNAB240";

const ACCEPT_POR_FORMATO: Record<FormatoExtrato, string> = {
  CSV: ".csv,text/csv,text/plain",
  OFX: ".ofx,text/plain,text/xml,application/xml",
  CNAB240: ".txt,.rem,.ret,text/plain",
};

interface FormImport {
  id_conta: number | null;
  formato: FormatoExtrato;
  nome_arquivo: string;
  conteudo: string;
}

function formVazio(): FormImport {
  return { id_conta: null, formato: "CSV", nome_arquivo: "", conteudo: "" };
}

export default function ConciliacaoPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [contaFiltro, setContaFiltro] = useState<number | null>(null);
  const [extratoSel, setExtratoSel] = useState<ExtratoBancario | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [form, setForm] = useState<FormImport>(formVazio());
  const [erroImport, setErroImport] = useState<string | null>(null);
  const [relatoImport, setRelatoImport] = useState<ImportarExtratoResultado | null>(null);
  const [manual, setManual] = useState<LancamentoExtrato | null>(null);
  const [movEscolhida, setMovEscolhida] = useState<number | null>(null);
  const [aDesfazer, setADesfazer] = useState<LancamentoExtrato | null>(null);
  const [motivoDesfazer, setMotivoDesfazer] = useState("");
  const arquivoRef = useRef<HTMLInputElement>(null);

  const contasQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });

  const extratosQ = useQuery({
    queryKey: ["pag-conc-extratos", contaFiltro],
    queryFn: () => api.pagamentos.conciliacao.extratos(contaFiltro ?? undefined),
  });

  const lancamentosQ = useQuery({
    queryKey: ["pag-conc-lancamentos", extratoSel?.id],
    queryFn: () => api.pagamentos.conciliacao.lancamentos(extratoSel!.id),
    enabled: !!extratoSel,
  });

  const sugestoesQ = useQuery({
    queryKey: ["pag-conc-sugestoes", extratoSel?.id],
    queryFn: () => api.pagamentos.conciliacao.sugestoes(extratoSel!.id),
    enabled: !!extratoSel,
  });

  // Movimentações da conta do extrato — base da conciliação manual. O backend
  // recusa as já conciliadas (RN-14); aqui só filtramos pelo que pode casar:
  // saídas de pagamento.
  const movimentacoesQ = useQuery({
    queryKey: ["pag-caixa-extrato", extratoSel?.id_conta],
    queryFn: () => api.pagamentos.caixa.extrato(extratoSel!.id_conta),
    enabled: !!extratoSel,
  });

  const contas = contasQ.data ?? [];
  const vImport = useValidacaoCampos(
    {
      id_conta: form.id_conta === null && "Escolha a conta do extrato.",
      conteudo:
        !form.conteudo.trim() &&
        (form.formato === "CSV"
          ? "Escolha o arquivo ou cole o conteúdo do extrato."
          : "Escolha o arquivo do extrato."),
      nome_arquivo: !form.nome_arquivo.trim() && "Dê um nome ao extrato, ex.: extrato-julho.csv.",
    },
    {
      id_conta: "imp-conta",
      conteudo: form.formato === "CSV" ? "imp-conteudo" : "imp-arquivo",
      nome_arquivo: "imp-nome",
    },
  );
  const vDesfazer = useValidacaoCampos(
    { motivo: !motivoDesfazer.trim() && "Explique por que desfazer — fica registrado." },
    { motivo: "motivo-desfazer" },
  );
  const vManual = useValidacaoCampos(
    { mov: movEscolhida === null && "Escolha o pagamento que corresponde a este lançamento." },
    { mov: "mov-alvo" },
  );
  const extratos = extratosQ.data ?? [];
  const lancamentos = lancamentosQ.data ?? [];
  const sugestoes = sugestoesQ.data ?? [];

  const nomeConta = (id: number) =>
    contas.find((c) => c.id_conta === id)?.nome ?? `Conta ${id}`;

  const exatas = useMemo(
    () => sugestoes.filter((s) => s.tipo_correspondencia === "EXATA").length,
    [sugestoes],
  );

  const pendentes = useMemo(
    () => lancamentos.filter((l) => !l.conciliado).length,
    [lancamentos],
  );

  const movsPagamento = useMemo(
    () =>
      (movimentacoesQ.data ?? []).filter(
        (m: Movimentacao) => m.tipo === "SAIDA" && m.origem === "PAGAMENTO",
      ),
    [movimentacoesQ.data],
  );

  function invalidar() {
    for (const k of CHAVES_INVALIDAR) qc.invalidateQueries({ queryKey: [...k] });
  }

  const importar = useMutation({
    mutationFn: () =>
      api.pagamentos.conciliacao.importar({
        id_conta: form.id_conta!,
        nome_arquivo: form.nome_arquivo.trim(),
        formato: form.formato,
        conteudo: form.conteudo,
      }),
    onSuccess: (res) => {
      setErroImport(null);
      setRelatoImport(res);
      invalidar();
      toast.success(`Extrato importado — ${res.importados} lançamento(s).`);
    },
    onError: (e: unknown) =>
      setErroImport(e instanceof Error ? e.message : "Falha ao importar o extrato."),
  });

  const baixaAuto = useMutation({
    mutationFn: () => api.pagamentos.conciliacao.baixaAutomatica(extratoSel!.id),
    onSuccess: (r) => {
      invalidar();
      toast.success(
        r.baixas === 0
          ? "Nenhuma correspondência exata para baixar."
          : `${r.baixas} baixa(s) conciliada(s).`,
      );
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Falha na baixa automática."),
  });

  const conciliar = useMutation({
    mutationFn: (v: { id_lancamento: number; id_movimentacao: number }) =>
      api.pagamentos.conciliacao.conciliar(v),
    onSuccess: () => {
      setManual(null);
      setMovEscolhida(null);
      invalidar();
      toast.success("Lançamento conciliado.");
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Falha ao conciliar."),
  });

  const desfazer = useMutation({
    mutationFn: () =>
      api.pagamentos.conciliacao.desfazer(aDesfazer!.id, motivoDesfazer.trim()),
    onSuccess: () => {
      setADesfazer(null);
      setMotivoDesfazer("");
      invalidar();
      toast.success("Conciliação desfeita — o lançamento voltou a pendente.");
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Falha ao desfazer a conciliação."),
  });

  function lerArquivo(f: File) {
    const leitor = new FileReader();
    leitor.onload = () => {
      const texto = typeof leitor.result === "string" ? leitor.result : "";
      setForm((s) => ({ ...s, conteudo: texto, nome_arquivo: s.nome_arquivo || f.name }));
    };
    leitor.onerror = () => setErroImport("Não foi possível ler o arquivo selecionado.");
    leitor.readAsText(f);
  }

  function fecharDialogoImport() {
    setImportOpen(false);
    setForm(formVazio());
    setErroImport(null);
    setRelatoImport(null);
  }

  function verExtratoImportado() {
    if (relatoImport) setExtratoSel(relatoImport.extrato);
    fecharDialogoImport();
  }

  async function confirmarBaixaAuto() {
    const ok = await confirm({
      title: "Baixa automática",
      message:
        `Conciliar de uma vez as ${exatas} correspondência(s) EXATA(S) deste extrato? ` +
        "Correspondências prováveis não são tocadas — essas continuam exigindo conferência.",
      confirmLabel: "Conciliar exatas",
    });
    if (ok) baixaAuto.mutate();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Landmark}
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }, { label: "Conciliação" }]}
        title="Conciliação bancária"
        description="Importe o extrato da conta e case cada lançamento com o pagamento; o débito com tudo casado fica conciliado sozinho."
        actions={
          <Button
            onClick={() => {
              setForm(formVazio());
              setErroImport(null);
              setRelatoImport(null);
              vImport.reiniciar();
              setImportOpen(true);
            }}
          >
            <FileUp className="mr-2 h-4 w-4" />
            Importar extrato
          </Button>
        }
      />

      <FilterBar>
        <FilterBar.Group className="min-w-64">
          <Label htmlFor="filtro-conta">Conta</Label>
          <Select
            id="filtro-conta"
            value={contaFiltro ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              setContaFiltro(v === "" ? null : Number(v));
              setExtratoSel(null);
            }}
          >
            <option value="">Todas</option>
            {contas.map((c) => (
              <option key={c.id_conta} value={c.id_conta}>
                {c.nome}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        {contaFiltro !== null && (
          <FilterBar.Actions>
            <Button
              variant="ghost"
              onClick={() => {
                setContaFiltro(null);
                setExtratoSel(null);
              }}
            >
              <X className="h-4 w-4" aria-hidden="true" />
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      <SectionCard title="Extratos importados">

        {extratosQ.isLoading ? (
          <Carregando className="text-sm text-foreground-muted" />
        ) : extratos.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title="Nenhum extrato importado"
            description="Importe um CSV do banco para começar a conciliar os pagamentos desta conta."
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Arquivo</TH>
                <TH>Conta</TH>
                <TH>Período</TH>
                <TH className="text-right">Lançamentos</TH>
                <TH>Importado em</TH>
              </TR>
            </THead>
            <TBody>
              {extratos.map((e) => (
                <TR
                  key={e.id}
                  onClick={() => setExtratoSel(e)}
                  className={
                    extratoSel?.id === e.id
                      ? "cursor-pointer bg-surface-2"
                      : "cursor-pointer hover:bg-surface-2"
                  }
                >
                  <TD className="font-medium">{e.nome_arquivo}</TD>
                  <TD>{nomeConta(e.id_conta)}</TD>
                  <TD>
                    {fmtData(e.periodo_inicio)} — {fmtData(e.periodo_fim)}
                  </TD>
                  <TD className="text-right tabular-nums">{e.qtd_lancamentos}</TD>
                  <TD>{fmtDataHora(e.importado_em)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </SectionCard>

      {extratoSel && (
        <>
          <SectionCard
            title="Sugestões de baixa"
            description="Exata: mesmo valor e mesma data. Provável: mesmo valor, até 3 dias de diferença — confira antes de conciliar."
          >
            {exatas > 0 && (
              <div className="mb-4 flex justify-end">
                <Button
                  variant="secondary"
                  onClick={confirmarBaixaAuto}
                  disabled={baixaAuto.isPending}
                >
                  <CheckCheck className="mr-2 h-4 w-4" />
                  Baixar {exatas} exata{exatas > 1 ? "s" : ""}
                </Button>
              </div>
            )}
            {sugestoesQ.isLoading ? (
              <Carregando className="text-sm text-foreground-muted" />
            ) : sugestoes.length === 0 ? (
              <EmptyState
                icon={ListChecks}
                title="Nenhuma correspondência encontrada"
                description={
                  pendentes === 0
                    ? "Todos os lançamentos deste extrato já estão conciliados."
                    : "Os lançamentos pendentes não casaram com nenhum pagamento em aberto desta conta. Use a conciliação manual abaixo."
                }
              />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Lançamento do extrato</TH>
                    <TH className="text-right">Valor</TH>
                    <TH>Pagamento correspondente</TH>
                    <TH>Correspondência</TH>
                    <TH className="text-right">Ações</TH>
                  </TR>
                </THead>
                <TBody>
                  {sugestoes.map((s) => (
                    <TR key={s.id_lancamento}>
                      <TD>
                        <div className="font-medium">{s.lancamento_historico}</div>
                        <div className="text-xs text-foreground-muted">{fmtData(s.lancamento_data)}</div>
                      </TD>
                      <TD className="text-right tabular-nums">{fmtMoeda(s.lancamento_valor)}</TD>
                      <TD>
                        <div>{s.nome_fornecedor ?? "—"}</div>
                        <div className="text-xs text-foreground-muted">
                          {fmtData(s.movimentacao_data)}
                          {s.id_debito ? ` · débito #${s.id_debito}` : ""}
                        </div>
                      </TD>
                      <TD>
                        <Badge intent={s.tipo_correspondencia === "EXATA" ? "success" : "warning"}>
                          {s.tipo_correspondencia === "EXATA" ? "Exata" : "Provável"}
                        </Badge>
                      </TD>
                      <TD className="text-right">
                        <AcoesDaLinha
                          acoes={[
                            {
                              label: "Conciliar",
                              icon: Link2,
                              disabled: conciliar.isPending,
                              onClick: () =>
                                conciliar.mutate({
                                  id_lancamento: s.id_lancamento,
                                  id_movimentacao: s.id_movimentacao,
                                }),
                            },
                          ]}
                        />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </SectionCard>

          <SectionCard
            title="Lançamentos do extrato"
            description={`${pendentes} pendente(s) de ${lancamentos.length}.`}
          >
            {/* Export (C1.3). Dentro do card, e não no header dele, porque
                `SectionCard` não tem slot de ação — mexer no componente
                compartilhado por causa de um botão teria raio de alcance
                maior que o da fatia. */}
            {extratoSel && (
              <div className="flex justify-end">
                <BotaoExportarCsv
                  csvUrl={api.pagamentos.conciliacao.lancamentosCsvUrl(extratoSel.id)}
                  rotulo="lançamentos do extrato"
                />
              </div>
            )}
            {lancamentosQ.isLoading ? (
              <Carregando className="text-sm text-foreground-muted" />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Data</TH>
                    <TH>Histórico</TH>
                    <TH>Documento</TH>
                    <TH>Favorecido</TH>
                    <TH className="text-right">Valor</TH>
                    <TH>Tipo</TH>
                    <TH>Situação</TH>
                    <TH className="text-right">Ações</TH>
                  </TR>
                </THead>
                <TBody>
                  {lancamentos.map((l) => (
                    <TR key={l.id}>
                      <TD>{fmtData(l.data)}</TD>
                      <TD className="font-medium">{l.historico}</TD>
                      <TD>{l.documento ?? "—"}</TD>
                      <TD>{l.favorecido ?? "—"}</TD>
                      <TD className="text-right tabular-nums">{fmtMoeda(l.valor)}</TD>
                      <TD>{l.tipo === "DEBITO" ? "Débito" : "Crédito"}</TD>
                      <TD>
                        <Badge intent={l.conciliado ? "success" : "neutral"}>
                          {l.conciliado ? "Conciliado" : "Pendente"}
                        </Badge>
                      </TD>
                      <TD className="text-right">
                        <AcoesDaLinha
                          acoes={[
                            {
                              label: "Conciliar manualmente",
                              icon: Link2,
                              oculta: l.conciliado || l.tipo !== "DEBITO",
                              onClick: () => {
                                setManual(l);
                                setMovEscolhida(null);
                                vManual.reiniciar();
                              },
                            },
                            {
                              label: "Desfazer",
                              icon: Undo2,
                              perigo: true,
                              ariaLabel: `Desfazer conciliação de ${l.historico}`,
                              oculta: !l.conciliado,
                              onClick: () => {
                                setADesfazer(l);
                                setMotivoDesfazer("");
                                vDesfazer.reiniciar();
                              },
                            },
                          ]}
                        />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </SectionCard>
        </>
      )}

      <Dialog
        open={importOpen}
        onClose={fecharDialogoImport}
        title={relatoImport ? "Extrato importado" : "Importar extrato bancário"}
        footer={
          relatoImport ? (
            <Button onClick={verExtratoImportado}>
              <Link2 className="mr-2 h-4 w-4" />
              Ver extrato
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={fecharDialogoImport}>
                Cancelar
              </Button>
              <Button
                onClick={() => {
                  if (vImport.conferir()) importar.mutate();
                }}
                loading={importar.isPending}
              >
                Importar
              </Button>
            </>
          )
        }
      >
        {relatoImport ? (
          <div className="space-y-4" data-testid="relato-importacao">
            <div className="flex items-start gap-3 rounded-card border border-success/30 bg-success-soft p-3 text-sm text-success-soft-foreground">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                {relatoImport.total_no_arquivo} linha(s) no arquivo — {relatoImport.importados}{" "}
                importado(s).
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-card border border-border bg-surface-1 p-3">
                <dt className="text-xs text-foreground-muted">Ignorados por ID externo</dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {relatoImport.ignorados_por_id_externo} ignorado(s)
                </dd>
              </div>
              <div className="rounded-card border border-border bg-surface-1 p-3">
                <dt className="text-xs text-foreground-muted">Possíveis duplicatas</dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {relatoImport.possiveis_duplicatas} possível duplicata(s)
                </dd>
              </div>
            </dl>

            {relatoImport.possiveis_duplicatas > 0 && (
              <div className="flex items-start gap-2 rounded-card border border-warning/30 bg-warning-soft p-3 text-xs text-warning-soft-foreground">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p>
                  Possível duplicata: já existe lançamento com a mesma data, valor e tipo
                  nesta conta. Elas <strong>não foram puladas</strong> — dois pagamentos
                  iguais no mesmo dia podem ser legítimos. Confira antes de conciliar.
                </p>
              </div>
            )}

            {relatoImport.ignorados_por_id_externo > 0 && (
              <p className="text-xs text-foreground-muted">
                Linhas ignoradas por ID externo já tinham o mesmo identificador do banco
                (FITID/documento) importado antes nesta conta — não foram duplicadas.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <FormField label="Conta" required error={vImport.erro("id_conta")}>
              <Select
                id="imp-conta"
                value={form.id_conta ?? ""}
                onChange={(e) => {
                  setForm((s) => ({
                    ...s,
                    id_conta: e.target.value === "" ? null : Number(e.target.value),
                  }));
                  vImport.tocar("id_conta")();
                }}
              >
                <option value="">Escolha a conta</option>
                {contas.map((c) => (
                  <option key={c.id_conta} value={c.id_conta}>
                    {c.nome}
                  </option>
                ))}
              </Select>
            </FormField>

            {/* Três formatos, todos à vista: o banco diz qual exporta. Trocar
                o formato limpa o arquivo já lido (o de antes não serve). */}
            <EscolhaSegmentada
              nome="imp-formato"
              titulo="Formato do arquivo"
              valor={form.formato}
              onChange={(formato) => {
                setForm((s) => ({ ...s, formato, conteudo: "", nome_arquivo: "" }));
                if (arquivoRef.current) arquivoRef.current.value = "";
              }}
              opcoes={[
                {
                  valor: "CSV",
                  rotulo: "CSV",
                  descricao: "Planilha exportada pelo banco, ou colada no campo abaixo.",
                },
                { valor: "OFX", rotulo: "OFX", descricao: "Extrato OFX (versão 1.x SGML ou 2.x XML)." },
                {
                  valor: "CNAB240",
                  rotulo: "CNAB240",
                  descricao: "Retorno CNAB240 (layout FEBRABAN, registros de 240 posições).",
                },
              ]}
              moldura={false}
            />

            <FormField
              label="Arquivo"
              required={form.formato !== "CSV"}
              error={form.formato !== "CSV" ? vImport.erro("conteudo") : undefined}
              hint={
                form.formato === "CSV" ? (
                  <>
                    Colunas: <code>{MODELO_CSV}</code>. Separador <code>;</code> ou{" "}
                    <code>,</code>; cabeçalho opcional; tipo <code>CREDITO</code> ou{" "}
                    <code>DEBITO</code>.
                  </>
                ) : undefined
              }
            >
              <Input
                id="imp-arquivo"
                ref={arquivoRef}
                type="file"
                accept={ACCEPT_POR_FORMATO[form.formato]}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) lerArquivo(f);
                }}
              />
            </FormField>

            <FormField
              label="Nome do extrato"
              required
              error={vImport.erro("nome_arquivo")}
              hint="Vem do arquivo escolhido. É como o extrato aparece na lista."
            >
              <Input
                id="imp-nome"
                value={form.nome_arquivo}
                onChange={(e) => setForm((s) => ({ ...s, nome_arquivo: e.target.value }))}
                onBlur={vImport.tocar("nome_arquivo")}
                placeholder="Ex.: extrato-julho.csv"
              />
            </FormField>

            {form.formato === "CSV" && (
              <FormField
                label="Conteúdo"
                opcional
                error={vImport.erro("conteudo")}
                hint="Também pode colar o conteúdo aqui em vez de escolher um arquivo."
              >
                <Textarea
                  id="imp-conteudo"
                  rows={8}
                  className="font-mono text-xs"
                  value={form.conteudo}
                  onChange={(e) => setForm((s) => ({ ...s, conteudo: e.target.value }))}
                  placeholder={`${MODELO_CSV}\n01/07/2026;PAGAMENTO FORNECEDOR;DOC123;ACME LTDA;1234,56;DEBITO`}
                />
              </FormField>
            )}

            <p className="text-xs text-foreground-muted">
              Reimportar o mesmo arquivo na mesma conta é recusado — a checagem é por hash
              do conteúdo.
            </p>

            {erroImport && (
              <p className="text-sm text-danger-soft-foreground" role="alert">
                {erroImport}
              </p>
            )}
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!aDesfazer}
        onClose={() => setADesfazer(null)}
        size="md"
        title="Desfazer conciliação"
        footer={
          <>
            <Button variant="ghost" onClick={() => setADesfazer(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (vDesfazer.conferir()) desfazer.mutate();
              }}
              loading={desfazer.isPending}
            >
              Desfazer conciliação
            </Button>
          </>
        }
      >
        {aDesfazer && (
          <div className="space-y-4">
            <p className="text-sm text-foreground">
              O lançamento &ldquo;{aDesfazer.historico}&rdquo; ({fmtMoeda(aDesfazer.valor)}) volta a
              pendente e pode ser conciliado de novo. Se a solicitação de pagamento ligada a ele
              estava como conciliada, ela volta a &ldquo;paga&rdquo;.
            </p>
            <FormField
              label="Justificativa"
              required
              error={vDesfazer.erro("motivo")}
              hint="Fica registrada no histórico da conciliação. Até 255 caracteres."
            >
              <Textarea
                id="motivo-desfazer"
                value={motivoDesfazer}
                onChange={(e) => setMotivoDesfazer(e.target.value)}
                onBlur={vDesfazer.tocar("motivo")}
                maxLength={255}
                placeholder="Ex.: Casado com o pagamento errado — o certo é o de 12/07."
                className="min-h-24"
              />
            </FormField>
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!manual}
        onClose={() => setManual(null)}
        title="Conciliação manual"
        footer={
          <>
            <Button variant="ghost" onClick={() => setManual(null)}>
              Cancelar
            </Button>
            <Button
              loading={conciliar.isPending}
              onClick={() => {
                if (manual && vManual.conferir())
                  conciliar.mutate({
                    id_lancamento: manual.id,
                    id_movimentacao: movEscolhida!,
                  });
              }}
            >
              Conciliar
            </Button>
          </>
        }
      >
        {manual && (
          <div className="space-y-4">
            <div className="rounded-card border border-border bg-surface-1 p-3 text-sm">
              <div className="font-medium">{manual.historico}</div>
              <div className="text-foreground-muted">
                {fmtData(manual.data)} · {fmtMoeda(manual.valor)}
                {manual.favorecido ? ` · ${manual.favorecido}` : ""}
              </div>
            </div>

            <FormField
              label="Pagamento a vincular"
              required
              error={vManual.erro("mov")}
              hint="Só saídas de pagamento desta conta. As já conciliadas são recusadas pelo servidor."
            >
              <Select
                id="mov-alvo"
                value={movEscolhida ?? ""}
                onChange={(e) =>
                  setMovEscolhida(e.target.value === "" ? null : Number(e.target.value))
                }
              >
                <option value="">Escolha o pagamento</option>
                {movsPagamento.map((m) => (
                  <option key={m.id} value={m.id}>
                    {fmtData(m.data)} — {fmtMoeda(m.valor)}
                    {m.descricao ? ` — ${m.descricao}` : ""}
                  </option>
                ))}
              </Select>
            </FormField>

          </div>
        )}
      </Dialog>
    </div>
  );
}
