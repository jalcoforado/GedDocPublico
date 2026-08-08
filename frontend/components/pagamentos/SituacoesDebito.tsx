"use client";

import type { LucideIcon } from "lucide-react";

import type {
  SituacaoFila,
  SituacaoPagamento,
  SituacaoTramitacao,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  FILA_ROTULO,
  PAGAMENTO_ROTULO,
  TRAMITACAO_ROTULO,
} from "@/components/pagamentos/situacoes";

interface SituacoesDebitoProps {
  tramitacao: SituacaoTramitacao;
  fila: SituacaoFila;
  pagamento: SituacaoPagamento;
}

function Dimensao({
  titulo,
  label,
  intent,
  icon,
}: {
  titulo: string;
  label: string;
  intent: "neutral" | "warning" | "info" | "success" | "danger";
  icon: LucideIcon;
}) {
  return (
    <div className="space-y-1.5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-foreground-muted">
        {titulo}
      </span>
      <div>
        <Badge intent={intent} icon={icon}>
          {label}
        </Badge>
      </div>
    </div>
  );
}

/**
 * Exibe as três dimensões independentes de situação do débito:
 * tramitação (decisão), fila (ordem cronológica) e pagamento (execução).
 */
export function SituacoesDebito({
  tramitacao,
  fila,
  pagamento,
}: SituacoesDebitoProps) {
  const rotuloTramitacao = TRAMITACAO_ROTULO[tramitacao];
  const rotuloFila = FILA_ROTULO[fila];
  const rotuloPagamento = PAGAMENTO_ROTULO[pagamento];

  return (
    <div className="grid grid-cols-1 gap-4 rounded-card border border-border bg-surface-2 p-4 sm:grid-cols-3">
      <Dimensao
        titulo="Tramitação"
        label={rotuloTramitacao.label}
        intent={rotuloTramitacao.intent}
        icon={rotuloTramitacao.icon}
      />
      <Dimensao
        titulo="Ordem cronológica"
        label={rotuloFila.label}
        intent={rotuloFila.intent}
        icon={rotuloFila.icon}
      />
      <Dimensao
        titulo="Pagamento"
        label={rotuloPagamento.label}
        intent={rotuloPagamento.intent}
        icon={rotuloPagamento.icon}
      />
    </div>
  );
}
