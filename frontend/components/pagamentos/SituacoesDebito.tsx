"use client";

import type {
  SituacaoFila,
  SituacaoPagamento,
  SituacaoTramitacao,
} from "@/lib/api";
import {
  FILA_ROTULO,
  PAGAMENTO_ROTULO,
  TRAMITACAO_ROTULO,
} from "@/components/pagamentos/situacoes";

interface SituacoesDebitoProps {
  tramitacao: SituacaoTramitacao;
  fila: SituacaoFila;
  pagamento: SituacaoPagamento;
  posicaoFila?: number;
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

  const RotuloItem = ({ label, icone }: { label: string; icone: string }) => (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-600 dark:text-gray-400">{icone}</span>
      <span className="text-sm">{label}</span>
    </div>
  );

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900">
      <div>
        <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
          Tramitação
        </span>
        <RotuloItem
          label={rotuloTramitacao.label}
          icone={rotuloTramitacao.icone}
        />
      </div>

      <div>
        <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
          Ordem cronológica
        </span>
        <RotuloItem label={rotuloFila.label} icone={rotuloFila.icone} />
      </div>

      <div>
        <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
          Pagamento
        </span>
        <RotuloItem
          label={rotuloPagamento.label}
          icone={rotuloPagamento.icone}
        />
      </div>
    </div>
  );
}
