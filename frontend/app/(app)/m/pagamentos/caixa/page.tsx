"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Plus, ReceiptText, Trash2, Wallet } from "lucide-react";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { BotaoExportarCsv, BotoesExportar } from "@/components/pagamentos/BotoesExportar";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm";
import {
  api,
  type ContaSaldoPainel,
  type OrigemMovimentacao,
  type TipoMovimentacao,
} from "@/lib/api";

/** Origem do lançamento por rótulo — o extrato mostrava o código ("APORTE"). */
const ORIGEM_LABEL: Record<OrigemMovimentacao, string> = {
  APORTE: "Aporte",
  RECEITA: "Receita",
  AJUSTE: "Ajuste",
  PAGAMENTO: "Pagamento",
  ESTORNO: "Estorno",
};

function hojeISO(): string {
  // Data LOCAL: o toISOString() é UTC, e depois das 21h (horário de Brasília)
  // o lançamento nascia com a data de amanhã.
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface FormState {
  id_conta: number | null;
  tipo: TipoMovimentacao;
  origem: OrigemMovimentacao;
  valor: string;
  data: string;
  descricao: string;
}

function emptyForm(idConta: number | null): FormState {
  return {
    id_conta: idConta,
    tipo: "ENTRADA",
    origem: "APORTE",
    valor: "",
    data: hojeISO(),
    descricao: "",
  };
}

interface BloqForm {
  valor: string;
  motivo: string;
  periodo_inicio: string;
  periodo_fim: string;
}

export default function CaixaPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [selecionada, setSelecionada] = useState<ContaSaldoPainel | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm(null));
  const [err, setErr] = useState<string | null>(null);
  const [bloqOpen, setBloqOpen] = useState(false);
  const [bloqForm, setBloqForm] = useState<BloqForm>({
    valor: "", motivo: "", periodo_inicio: hojeISO(), periodo_fim: "",
  });

  const painelQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });
  const contasQ = useQuery({
    queryKey: ["pag-contas-select"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const extratoQ = useQuery({
    queryKey: ["pag-caixa-extrato", selecionada?.id_conta],
    queryFn: () => api.pagamentos.caixa.extrato(selecionada!.id_conta),
    enabled: selecionada !== null,
  });

  function abrirLancar() {
    // Conta já escolhida no painel vem preenchida; sem escolha, só a conta
    // única entra sozinha (a primeira da lista era palpite).
    const contas = contasQ.data ?? [];
    setForm(emptyForm(selecionada?.id_conta ?? (contas.length === 1 ? contas[0].id : null)));
    vl.reiniciar();
    setErr(null);
    setOpen(true);
  }

  const lancarM = useMutation({
    mutationFn: () => {
      if (form.id_conta === null) throw new Error("Selecione uma conta.");
      return api.pagamentos.caixa.lancar({
        id_conta: form.id_conta,
        tipo: form.tipo,
        origem: form.origem,
        valor: Number(form.valor),
        data: form.data,
        descricao: form.descricao.trim() || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-caixa-painel"] });
      qc.invalidateQueries({ queryKey: ["pag-caixa-extrato"] });
      toast.success("Lançamento registrado.");
      setOpen(false);
    },
    onError: (e: Error) => {
      setErr(e.message);
      toast.error(e.message);
    },
  });

  const bloqueiosQ = useQuery({
    queryKey: ["pag-bloqueios", selecionada?.id_conta],
    queryFn: () => api.pagamentos.bloqueios.list({ conta_id: selecionada!.id_conta }),
    enabled: selecionada !== null,
  });

  function invalidarSaldos() {
    qc.invalidateQueries({ queryKey: ["pag-caixa-painel"] });
    qc.invalidateQueries({ queryKey: ["pag-bloqueios"] });
  }

  const criarBloqM = useMutation({
    mutationFn: () => {
      if (selecionada === null) throw new Error("Selecione uma conta.");
      return api.pagamentos.bloqueios.create({
        id_conta: selecionada.id_conta,
        valor: Number(bloqForm.valor),
        motivo: bloqForm.motivo.trim(),
        periodo_inicio: bloqForm.periodo_inicio,
        periodo_fim: bloqForm.periodo_fim || null,
      });
    },
    onSuccess: () => {
      invalidarSaldos();
      toast.success("Bloqueio registrado.");
      setBloqOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removerBloqM = useMutation({
    mutationFn: (bloqId: number) => api.pagamentos.bloqueios.remove(bloqId),
    onSuccess: () => {
      invalidarSaldos();
      toast.success("Bloqueio removido.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function removerBloqueio(bloqId: number) {
    const ok = await confirm({
      title: "Remover bloqueio",
      message: "Remover este bloqueio de saldo? O valor volta a ficar disponível.",
      confirmLabel: "Remover",
      intent: "danger",
    });
    if (ok) removerBloqM.mutate(bloqId);
  }

  const painel = painelQ.data ?? [];
  const extrato = extratoQ.data ?? [];
  const bloqueios = bloqueiosQ.data ?? [];
  const contaDoLancamento = painel.find((c) => c.id_conta === form.id_conta);

  const vl = useValidacaoCampos(
    {
      id_conta: form.id_conta === null && "Escolha a conta do lançamento.",
      valor: !(Number(form.valor) > 0) && "Informe um valor maior que zero, ex.: 1500,00.",
      data: !form.data && "Informe a data do lançamento.",
    },
    { id_conta: "cx-conta", valor: "cx-valor", data: "cx-data" },
  );
  const vb = useValidacaoCampos(
    {
      valor: !(Number(bloqForm.valor) > 0) && "Informe um valor maior que zero.",
      motivo: !bloqForm.motivo.trim() && "Diga por que o saldo fica bloqueado.",
      periodo_inicio: !bloqForm.periodo_inicio && "Informe desde quando o bloqueio vale.",
      periodo_fim:
        !!bloqForm.periodo_fim &&
        bloqForm.periodo_fim < bloqForm.periodo_inicio &&
        "O fim tem de ser depois do início.",
    },
    { valor: "bloq-valor", motivo: "bloq-motivo", periodo_inicio: "bloq-inicio", periodo_fim: "bloq-fim" },
  );

  function salvarLancamento() {
    if (vl.conferir()) lancarM.mutate();
  }
  function salvarBloqueio() {
    if (vb.conferir()) criarBloqM.mutate();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Wallet}
        title="Caixa"
        description="Saldo de cada conta, o extrato e os bloqueios; clique numa conta para ver o detalhe."
        actions={
          <>
            <BotoesExportar
              csvUrl={api.pagamentos.caixa.painelCsvUrl()}
              pdfUrl={api.pagamentos.caixa.painelPdfUrl()}
              rotulo="painel de caixa"
            />
            <Button onClick={abrirLancar}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Lançar entrada/saída
            </Button>
          </>
        }
      />

      <Table>
        <THead>
          <TR>
            <TH>Conta</TH>
            <TH>Banco</TH>
            <TH className="text-right">Saldo inicial</TH>
            <TH className="text-right">Entradas</TH>
            <TH className="text-right">Saídas</TH>
            <TH className="text-right">Reservado</TH>
            <TH className="text-right">Bloqueado</TH>
            <TH className="text-right">Disp. projetado</TH>
            <TH className="text-right">Saldo atual</TH>
            <TH></TH>
          </TR>
        </THead>
        <TBody>
          {painelQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={10} />)}
          {!painelQ.isLoading && painel.length === 0 && (
            <TR>
              <TD colSpan={10} className="p-0">
                <EmptyState
                  icon={Wallet}
                  title="Nenhuma conta bancária cadastrada"
                  description="O painel de caixa mostra o saldo das contas cadastradas em Contas bancárias."
                  className="rounded-none border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {painel.map((c) => (
            <TR
              key={c.id_conta}
              highlighted={selecionada?.id_conta === c.id_conta}
              onClickRow={() => setSelecionada(c)}
            >
              <TD>{c.nome}</TD>
              <TD>{c.banco}</TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.saldo_inicial)}</TD>
              <TD className="text-right tabular-nums text-success-soft-foreground">
                {fmtMoeda(c.total_entradas)}
              </TD>
              <TD className="text-right tabular-nums text-danger-soft-foreground">
                {fmtMoeda(c.total_saidas)}
              </TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.comprometido)}</TD>
              <TD className="text-right tabular-nums text-warning-soft-foreground">
                {fmtMoeda(c.bloqueado)}
              </TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.disponivel_projetado)}</TD>
              <TD className="text-right text-base font-semibold tabular-nums">
                {fmtMoeda(c.saldo_atual)}
              </TD>
              <TD>
                {c.abaixo_minimo && <Badge intent="danger">Abaixo do mínimo</Badge>}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Extrato{selecionada ? ` — ${selecionada.nome}` : ""}
          </h2>
          {/* Só quando há conta escolhida: o endpoint é por conta, e um botão
              que baixa o extrato "de nada" é pior que botão ausente. */}
          {selecionada !== null && (
            <BotaoExportarCsv
              csvUrl={api.pagamentos.caixa.extratoCsvUrl(selecionada.id_conta)}
              rotulo={`extrato da conta ${selecionada.nome}`}
            />
          )}
        </div>
        {selecionada === null ? (
          <EmptyState
            icon={ReceiptText}
            title="Escolha uma conta"
            description="Clique numa conta do painel acima para ver o extrato e os bloqueios dela."
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Data</TH>
                <TH>Tipo</TH>
                <TH>Origem</TH>
                <TH className="text-right">Valor</TH>
                <TH>Descrição</TH>
              </TR>
            </THead>
            <TBody>
              {extratoQ.isLoading &&
                Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={5} />)}
              {!extratoQ.isLoading && extrato.length === 0 && (
                <TR>
                  <TD colSpan={5} className="p-0">
                    <EmptyState
                      icon={ReceiptText}
                      title="Nenhuma movimentação nesta conta"
                      description="Entradas, saídas e pagamentos da conta aparecem aqui."
                      className="rounded-none border-0 bg-transparent"
                    />
                  </TD>
                </TR>
              )}
              {extrato.map((m) => (
                <TR key={m.id}>
                  <TD className="whitespace-nowrap tabular-nums">{fmtData(m.data)}</TD>
                  <TD>
                    <Badge intent={m.tipo === "ENTRADA" ? "success" : "danger"}>
                      {m.tipo === "ENTRADA" ? "Entrada" : "Saída"}
                    </Badge>
                  </TD>
                  <TD>{ORIGEM_LABEL[m.origem] ?? m.origem}</TD>
                  <TD
                    className={
                      "text-right tabular-nums " +
                      (m.tipo === "ENTRADA"
                        ? "text-success-soft-foreground"
                        : "text-danger-soft-foreground")
                    }
                  >
                    {m.tipo === "ENTRADA" ? "+" : "-"}
                    {fmtMoeda(m.valor)}
                  </TD>
                  <TD>{m.descricao ?? "—"}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>

      {selecionada !== null && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">
              Bloqueios — {selecionada.nome}
            </h2>
            <Button
              variant="secondary"
              onClick={() => {
                setBloqForm({ valor: "", motivo: "", periodo_inicio: hojeISO(), periodo_fim: "" });
                vb.reiniciar();
                setBloqOpen(true);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo bloqueio
            </Button>
          </div>
          <Table>
            <THead>
              <TR>
                <TH className="text-right">Valor</TH>
                <TH>Motivo</TH>
                <TH>Início</TH>
                <TH>Fim</TH>
                <TH>Situação</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {!bloqueiosQ.isLoading && bloqueios.length === 0 && (
                <TR>
                  <TD colSpan={6} className="p-0">
                    <EmptyState
                      icon={Lock}
                      title="Nenhum bloqueio nesta conta"
                      description="Bloqueie parte do saldo para reservá-lo a um fim específico."
                      className="rounded-none border-0 bg-transparent"
                    />
                  </TD>
                </TR>
              )}
              {bloqueios.map((b) => (
                <TR key={b.id}>
                  <TD className="text-right tabular-nums">{fmtMoeda(b.valor)}</TD>
                  <TD>{b.motivo}</TD>
                  <TD className="whitespace-nowrap tabular-nums">{fmtData(b.periodo_inicio)}</TD>
                  <TD className="whitespace-nowrap tabular-nums">{fmtData(b.periodo_fim)}</TD>
                  <TD>
                    <Badge intent={b.ativo ? "warning" : "neutral"}>
                      {b.ativo ? "Ativo" : "Inativo"}
                    </Badge>
                  </TD>
                  <TD className="text-right">
                    <AcoesDaLinha
                      acoes={[
                        {
                          label: "Remover",
                          icon: Trash2,
                          perigo: true,
                          onClick: () => removerBloqueio(b.id),
                          disabled: removerBloqM.isPending,
                          oculta: !b.ativo,
                        },
                      ]}
                    />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <Dialog
        open={bloqOpen}
        onClose={() => setBloqOpen(false)}
        title="Novo bloqueio de saldo"
        description={
          selecionada
            ? `Conta ${selecionada.nome}. O valor bloqueado sai do disponível enquanto o bloqueio valer.`
            : undefined
        }
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setBloqOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvarBloqueio} loading={criarBloqM.isPending}>
              Bloquear saldo
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField
            label="Valor"
            required
            error={vb.erro("valor")}
            hint={
              selecionada
                ? `Disponível hoje nesta conta: ${fmtMoeda(selecionada.disponivel)}.`
                : undefined
            }
          >
            <CampoComUnidade
              id="bloq-valor"
              prefixo="R$"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={bloqForm.valor}
              onChange={(e) => setBloqForm((f) => ({ ...f, valor: e.target.value }))}
              onBlur={vb.tocar("valor")}
              placeholder="0,00"
            />
          </FormField>
          <FormField
            label="Motivo"
            required
            error={vb.erro("motivo")}
            hint="Aparece na lista de bloqueios da conta."
          >
            <Input
              id="bloq-motivo"
              value={bloqForm.motivo}
              onChange={(e) => setBloqForm((f) => ({ ...f, motivo: e.target.value }))}
              onBlur={vb.tocar("motivo")}
              maxLength={255}
              placeholder="Ex.: Contrapartida do convênio 123/2026"
            />
          </FormField>
          <GradeCampos>
            <FormField label="Início da vigência" required error={vb.erro("periodo_inicio")} hint="Hoje, por padrão.">
              <Input
                id="bloq-inicio"
                type="date"
                value={bloqForm.periodo_inicio}
                onChange={(e) => setBloqForm((f) => ({ ...f, periodo_inicio: e.target.value }))}
                onBlur={vb.tocar("periodo_inicio")}
              />
            </FormField>
            <FormField
              label="Fim da vigência"
              opcional
              error={vb.erro("periodo_fim")}
              hint="Em branco, o bloqueio vale até ser removido."
            >
              <Input
                id="bloq-fim"
                type="date"
                value={bloqForm.periodo_fim}
                min={bloqForm.periodo_inicio || undefined}
                onChange={(e) => setBloqForm((f) => ({ ...f, periodo_fim: e.target.value }))}
                onBlur={vb.tocar("periodo_fim")}
              />
            </FormField>
          </GradeCampos>
        </div>
      </Dialog>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Lançar entrada ou saída"
        description="Movimentação manual no caixa. Pagamentos e estornos entram sozinhos pelo fluxo."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvarLancamento} loading={lancarM.isPending}>
              {form.tipo === "ENTRADA" ? "Lançar entrada" : "Lançar saída"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField
            label="Conta"
            required
            error={vl.erro("id_conta")}
            hint={
              contaDoLancamento
                ? `Saldo atual: ${fmtMoeda(contaDoLancamento.saldo_atual)}.`
                : undefined
            }
          >
            <Select
              id="cx-conta"
              value={form.id_conta ?? ""}
              onChange={(e) => {
                setForm({ ...form, id_conta: e.target.value === "" ? null : Number(e.target.value) });
                vl.tocar("id_conta")();
              }}
            >
              <option value="">Escolha a conta</option>
              {(contasQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome} ({c.banco})
                </option>
              ))}
            </Select>
          </FormField>
          <EscolhaSegmentada
            nome="cx-tipo"
            titulo="Tipo"
            valor={form.tipo}
            onChange={(t) => setForm({ ...form, tipo: t })}
            opcoes={[
              { valor: "ENTRADA", rotulo: "Entrada", descricao: "Soma ao saldo da conta." },
              { valor: "SAIDA", rotulo: "Saída", descricao: "Subtrai do saldo da conta." },
            ]}
            moldura={false}
          />
          <EscolhaSegmentada
            nome="cx-origem"
            titulo="Origem"
            valor={form.origem as "APORTE" | "RECEITA" | "AJUSTE"}
            onChange={(o) => setForm({ ...form, origem: o })}
            opcoes={[
              { valor: "APORTE", rotulo: "Aporte", descricao: "Dinheiro transferido para a conta." },
              { valor: "RECEITA", rotulo: "Receita", descricao: "Arrecadação que caiu na conta." },
              { valor: "AJUSTE", rotulo: "Ajuste", descricao: "Correção de saldo — explique na descrição." },
            ]}
            moldura={false}
          />
          <GradeCampos>
            <FormField
              label="Valor"
              required
              error={vl.erro("valor")}
              hint={
                contaDoLancamento && Number(form.valor) > 0
                  ? `Saldo depois: ${fmtMoeda(
                      Number(contaDoLancamento.saldo_atual) +
                        (form.tipo === "ENTRADA" ? 1 : -1) * Number(form.valor),
                    )}.`
                  : undefined
              }
            >
              <CampoComUnidade
                id="cx-valor"
                prefixo="R$"
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                value={form.valor}
                onChange={(e) => setForm({ ...form, valor: e.target.value })}
                onBlur={vl.tocar("valor")}
                placeholder="0,00"
              />
            </FormField>
            <FormField label="Data" required error={vl.erro("data")} hint="Hoje, por padrão.">
              <Input
                id="cx-data"
                type="date"
                value={form.data}
                onChange={(e) => setForm({ ...form, data: e.target.value })}
                onBlur={vl.tocar("data")}
              />
            </FormField>
          </GradeCampos>
          <FormField label="Descrição" opcional hint="Aparece no extrato da conta.">
            <Input
              id="cx-descricao"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              maxLength={255}
              placeholder="Ex.: Repasse do FPM — 1º decêndio"
            />
          </FormField>

          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
