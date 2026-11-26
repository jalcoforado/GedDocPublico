"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { fmtMoeda } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { api, type FormaPagamentoLote, type Parcela, type Retencao } from "@/lib/api";

/** "aaaa-mm-dd" de hoje no horário local (o toISOString() é UTC). */
function hojeLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export type AcaoParcela = "estornar" | "revogar";

const TEXTO_ACAO: Record<
  AcaoParcela,
  { titulo: string; confirmar: string; sucesso: string; impacto: (p: Parcela) => string }
> = {
  estornar: {
    titulo: "Estornar pagamento",
    confirmar: "Estornar pagamento",
    sucesso: "Pagamento estornado",
    impacto: (p) =>
      `A parcela ${p.numero} (${fmtMoeda(p.valor)}) volta para "a pagar" e o valor retorna ao ` +
      "saldo da conta pagadora, como uma entrada de estorno no extrato. O estorno fica " +
      "registrado no histórico da solicitação.",
  },
  revogar: {
    titulo: "Revogar liberação",
    confirmar: "Revogar liberação",
    sucesso: "Liberação revogada",
    impacto: (p) =>
      `A parcela ${p.numero} (${fmtMoeda(p.valor)}) sai da fila da tesouraria e volta para ` +
      '"a pagar". Para pagá-la será preciso liberá-la de novo.',
  },
};

/**
 * Estorno de parcela paga e revogação de liberação. Os dois endpoints
 * existiam sem tela: pagamento feito por engano ou liberação indevida só se
 * desfazia chamando a API à mão.
 */
export function AcaoParcelaDialog({
  alvo,
  onClose,
  onFeito,
}: {
  alvo: { acao: AcaoParcela; parcela: Parcela } | null;
  onClose: () => void;
  onFeito: () => void;
}) {
  const toast = useToast();
  const [justificativa, setJustificativa] = useState("");
  const v = useValidacaoCampos(
    { justificativa: !justificativa.trim() && "Explique o motivo — fica no histórico da solicitação." },
    { justificativa: "acao-parcela-justificativa" },
  );
  const { reiniciar } = v;
  useEffect(() => {
    setJustificativa("");
    reiniciar();
  }, [alvo, reiniciar]);

  const m = useMutation({
    mutationFn: () => {
      if (!alvo) throw new Error("Nenhuma parcela selecionada");
      return alvo.acao === "estornar"
        ? api.pagamentos.parcelas.estornar(alvo.parcela.id, justificativa.trim())
        : api.pagamentos.parcelas.revogarLiberacao(alvo.parcela.id, justificativa.trim());
    },
    onSuccess: () => {
      if (alvo) toast.success(TEXTO_ACAO[alvo.acao].sucesso);
      onFeito();
      onClose();
    },
    onError: (err: Error) => toast.error(err.message || "Não foi possível concluir a ação"),
  });

  const texto = alvo ? TEXTO_ACAO[alvo.acao] : null;

  return (
    <Dialog
      open={!!alvo}
      onClose={onClose}
      size="md"
      title={texto?.titulo ?? ""}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (v.conferir()) m.mutate();
            }}
            loading={m.isPending}
          >
            {texto?.confirmar}
          </Button>
        </>
      }
    >
      {alvo && texto && (
        <div className="space-y-4">
          <p className="text-sm text-foreground">{texto.impacto(alvo.parcela)}</p>
          <FormField
            label="Justificativa"
            required
            error={v.erro("justificativa")}
            hint="Até 255 caracteres."
          >
            <Textarea
              id="acao-parcela-justificativa"
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              onBlur={v.tocar("justificativa")}
              maxLength={255}
              placeholder={
                alvo.acao === "estornar"
                  ? "Ex.: Pagamento em duplicidade — o banco devolveu o valor."
                  : "Ex.: Nota fiscal cancelada pelo fornecedor."
              }
              className="min-h-24"
            />
          </FormField>
        </div>
      )}
    </Dialog>
  );
}

/**
 * Baixa de UMA parcela liberada, fora de lote — o pagamento avulso. O endpoint
 * existia sem tela: só se pagava montando lote, mesmo para um único boleto
 * pago no caixa.
 *
 * O backend recusa (409) a parcela que está num lote ativo ou que furaria a
 * ordem cronológica; a mensagem dele vira o aviso na tela.
 */
export function PagarParcelaDialog({
  parcela,
  onClose,
  onFeito,
}: {
  parcela: Parcela | null;
  onClose: () => void;
  onFeito: () => void;
}) {
  const toast = useToast();
  const [forma, setForma] = useState<FormaPagamentoLote>("PIX");
  const [data, setData] = useState("");
  useEffect(() => {
    setForma("PIX");
    setData("");
  }, [parcela]);

  const m = useMutation({
    mutationFn: () => {
      if (!parcela) throw new Error("Nenhuma parcela selecionada");
      return api.pagamentos.parcelas.pagar(parcela.id, {
        forma_pagamento: forma,
        data_pagamento: data || null,
      });
    },
    onSuccess: () => {
      toast.success("Pagamento registrado");
      onFeito();
      onClose();
    },
    onError: (err: Error) => toast.error(err.message || "Não foi possível registrar o pagamento"),
  });

  return (
    <Dialog
      open={!!parcela}
      onClose={onClose}
      size="sm"
      title="Registrar pagamento"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => m.mutate()} loading={m.isPending}>
            Registrar pagamento
          </Button>
        </>
      }
    >
      {parcela && (
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            A parcela {parcela.numero} ({fmtMoeda(parcela.valor)}) passa a constar como paga e o
            valor sai do saldo da conta pagadora. Use para pagamento feito fora de lote.
          </p>
          <FormField label="Forma de pagamento" required>
            <Select value={forma} onChange={(e) => setForma(e.target.value as FormaPagamentoLote)}>
              <option value="PIX">PIX</option>
              <option value="TED">TED</option>
              <option value="BOLETO">Boleto</option>
              <option value="DINHEIRO">Dinheiro</option>
              <option value="OUTRO">Outro</option>
            </Select>
          </FormField>
          <FormField label="Data do pagamento" opcional hint="Em branco, vale a data de hoje.">
            <Input type="date" value={data} onChange={(e) => setData(e.target.value)} />
          </FormField>
        </div>
      )}
    </Dialog>
  );
}

/**
 * Registro do recolhimento de uma retenção (guia paga ao fisco). A tela só
 * criava e excluía retenções: elas ficavam "pendentes" para sempre.
 */
export function RecolherRetencaoDialog({
  retencao,
  onClose,
  onFeito,
}: {
  retencao: Retencao | null;
  onClose: () => void;
  onFeito: () => void;
}) {
  const toast = useToast();
  const [data, setData] = useState("");
  const [documento, setDocumento] = useState("");
  const v = useValidacaoCampos(
    {
      data: !data && "Informe a data em que a guia foi paga.",
      documento: !documento.trim() && "Informe o número da guia paga.",
    },
    { data: "recolher-data", documento: "recolher-documento" },
  );
  const { reiniciar } = v;
  useEffect(() => {
    // A guia costuma ser registrada no dia em que é paga.
    setData(hojeLocal());
    setDocumento("");
    reiniciar();
  }, [retencao, reiniciar]);

  const m = useMutation({
    mutationFn: () => {
      if (!retencao) throw new Error("Nenhuma retenção selecionada");
      return api.pagamentos.retencoes.recolher(retencao.id, {
        data_recolhimento: data,
        documento_recolhimento: documento.trim(),
      });
    },
    onSuccess: () => {
      toast.success("Recolhimento registrado");
      onFeito();
      onClose();
    },
    onError: (err: Error) => toast.error(err.message || "Erro ao registrar o recolhimento"),
  });

  return (
    <Dialog
      open={!!retencao}
      onClose={onClose}
      size="sm"
      title="Registrar recolhimento"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              if (v.conferir()) m.mutate();
            }}
            loading={m.isPending}
          >
            Registrar recolhimento
          </Button>
        </>
      }
    >
      {retencao && (
        <div className="space-y-4">
          <p className="text-sm text-foreground-muted">
            Retenção de {retencao.tipo}, no valor de {fmtMoeda(retencao.valor)}. Depois de
            registrada como recolhida, ela não pode mais ser removida por esta tela.
          </p>
          <FormField label="Data do recolhimento" required error={v.erro("data")} hint="Hoje, por padrão.">
            <Input
              id="recolher-data"
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
              onBlur={v.tocar("data")}
            />
          </FormField>
          <FormField
            label="Documento de arrecadação"
            required
            error={v.erro("documento")}
            hint="Número da guia paga (DARF, GPS, DAM…)."
          >
            <Input
              id="recolher-documento"
              value={documento}
              onChange={(e) => setDocumento(e.target.value)}
              onBlur={v.tocar("documento")}
              maxLength={50}
              placeholder="Ex.: DARF 0561 — 10/2026"
            />
          </FormField>
        </div>
      )}
    </Dialog>
  );
}
