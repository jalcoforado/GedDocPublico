"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  Banknote,
  Check,
  FileEdit,
  Gavel,
  Landmark,
  ListOrdered,
  type LucideIcon,
  Reply,
  ScrollText,
  SearchCheck,
  Send,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  X,
} from "lucide-react";
import Link from "next/link";

import {
  FasesDoFluxo,
  type FaseDoFluxo,
  type PassoDoFluxo,
} from "@/components/fluxo/MapaDeFluxo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/section-card";
import { api, type SituacaoTramitacao } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Passo extends PassoDoFluxo {
  /** Transação que dá a vez ao usuário neste passo. */
  transacao: string;
  /** Situações de tramitação que contam como "aqui agora". */
  situacoes?: SituacaoTramitacao[];
  /** Contagem que vem da fila pessoal, para os passos de execução. */
  fila?: "liberar" | "pagar";
}

/**
 * O processo inteiro, da solicitação à conciliação. É texto de orientação: a
 * regra mora no backend (`services/pagamentos_estados.py::TRANSICOES_TRAMITACAO`
 * e as guardas de autorização). As saídas de cada passo de decisão espelham
 * aquele grafo, e `__tests__/pagamentos-fluxo.test.tsx` confere as situações.
 */
export const FASES: FaseDoFluxo<Passo>[] = [
  {
    titulo: "Decisão",
    descricao:
      "A solicitação sobe por quatro mesas. Cada uma só recebe depois que a anterior concluiu.",
    passos: [
      {
        key: "solicitar",
        titulo: "Solicitar",
        responsavel: "Unidade setorial",
        descricao:
          "Cria a solicitação, informa fornecedor, valor e parcelas, anexa os documentos e envia.",
        icon: FileEdit,
        transacao: "pagamento_solicitar",
        situacoes: ["RASCUNHO", "AJUSTE_GESTOR", "AJUSTE_VALIDACAO", "AJUSTE_AUTORIDADE"],
        tela: { href: "/m/pagamentos/solicitacoes", label: "Abrir solicitações" },
        saidas: [
          { label: "Enviar", destino: "vai para o gestor", icon: Send, intent: "success" },
          { label: "Cancelar", destino: "encerra a solicitação", icon: Ban, intent: "neutral" },
        ],
      },
      {
        key: "gerir",
        titulo: "Analisar o mérito",
        responsavel: "Gestor da pasta",
        descricao: "Avalia se a despesa é conveniente e pertinente para a pasta.",
        icon: UserCheck,
        transacao: "pagamento_gerir",
        situacoes: ["AGUARDANDO_GESTOR"],
        tela: { href: "/m/pagamentos/solicitacoes/gestor", label: "Abrir fila do gestor" },
        saidas: [
          { label: "Autorizar", destino: "vai para a validação", icon: Check, intent: "success" },
          { label: "Pedir ajuste", destino: "volta para a unidade", icon: Reply, intent: "warning" },
          { label: "Rejeitar", destino: "encerra a solicitação", icon: X, intent: "danger" },
        ],
      },
      {
        key: "validar",
        titulo: "Validar",
        responsavel: "Validação financeira",
        descricao:
          "Confere a documentação fiscal e contábil, item a item do checklist. Não rejeita: valida ou devolve.",
        icon: SearchCheck,
        transacao: "pagamento_validar",
        situacoes: ["AGUARDANDO_VALIDACAO"],
        tela: { href: "/m/pagamentos/solicitacoes/validacao", label: "Abrir fila de validação" },
        saidas: [
          { label: "Validar", destino: "vai para a autoridade", icon: Check, intent: "success" },
          { label: "Pedir ajuste", destino: "volta para a unidade", icon: Reply, intent: "warning" },
        ],
      },
      {
        key: "autorizar",
        titulo: "Autorizar a despesa",
        responsavel: "Autoridade competente",
        descricao:
          "Escolhe a conta pagadora e autoriza. A autorização gera a ordem de pagamento.",
        icon: Gavel,
        transacao: "pagamento_autorizar",
        situacoes: ["AGUARDANDO_AUTORIDADE"],
        tela: { href: "/m/pagamentos/solicitacoes/autoridade", label: "Abrir fila da autoridade" },
        saidas: [
          { label: "Aprovar", destino: "gera a ordem de pagamento", icon: Check, intent: "success" },
          { label: "Pedir ajuste", destino: "volta para a unidade", icon: Reply, intent: "warning" },
          { label: "Não aprovar", destino: "encerra a solicitação", icon: X, intent: "danger" },
        ],
      },
    ],
  },
  {
    titulo: "Execução",
    descricao:
      "Com a despesa autorizada, o dinheiro sai em três atos. Aqui a unidade de trabalho é a parcela.",
    passos: [
      {
        key: "liberar",
        titulo: "Liberar o pagamento",
        responsavel: "Autoridade competente",
        descricao:
          "Libera as parcelas para a tesouraria, respeitando a ordem cronológica. Pode revogar enquanto não foi pago.",
        icon: ShieldCheck,
        transacao: "pagamento_autorizar",
        fila: "liberar",
        unidade: ["parcela", "parcelas"],
        tela: { href: "/m/pagamentos/autorizacao", label: "Abrir autorizações" },
        saidas: [
          { label: "Liberar", destino: "vai para a tesouraria", icon: Check, intent: "success" },
        ],
      },
      {
        key: "pagar",
        titulo: "Pagar",
        responsavel: "Tesouraria",
        descricao:
          "Paga a parcela avulsa ou monta um lote, envia ao banco e registra o retorno. Pode estornar.",
        icon: Banknote,
        transacao: "pagamento_pagar",
        fila: "pagar",
        unidade: ["parcela", "parcelas"],
        tela: { href: "/m/pagamentos/tesouraria", label: "Abrir tesouraria" },
        saidas: [
          { label: "Pagar", destino: "baixa a parcela e a conta", icon: Check, intent: "success" },
          { label: "Falha no banco", destino: "a parcela volta a liberada", icon: Reply, intent: "warning" },
        ],
      },
      {
        key: "conciliar",
        titulo: "Conciliar",
        responsavel: "Tesouraria",
        descricao:
          "Importa o extrato e casa cada lançamento do banco com o pagamento registrado.",
        icon: Landmark,
        transacao: "pagamento_pagar",
        tela: { href: "/m/pagamentos/conciliacao", label: "Abrir conciliação" },
        saidas: [
          { label: "Conciliar", destino: "fecha o ciclo do pagamento", icon: Check, intent: "success" },
        ],
      },
    ],
  },
];

const ENCERRAMENTOS: { situacao: SituacaoTramitacao; label: string; quem: string }[] = [
  { situacao: "REJEITADA_GESTOR", label: "Rejeitada", quem: "pelo gestor da pasta" },
  { situacao: "INDEFERIDA_AUTORIDADE", label: "Indeferida", quem: "pela autoridade competente" },
  { situacao: "CANCELADA", label: "Cancelada", quem: "pela unidade, antes da autorização" },
];

const TRAVAS: { titulo: string; texto: string; icon: LucideIcon }[] = [
  {
    titulo: "Segregação de funções",
    texto: "Quem praticou um ato na solicitação não pratica o seguinte: quem solicita não aprova, quem autoriza não paga.",
    icon: UserCheck,
  },
  {
    titulo: "Checklist documental",
    texto: "A validação só conclui com todos os itens obrigatórios do checklist conferidos.",
    icon: SearchCheck,
  },
  {
    titulo: "Alçada",
    texto: "A autoridade só autoriza valores dentro da alçada cadastrada para ela.",
    icon: Gavel,
  },
  {
    titulo: "Ordem cronológica",
    texto: "Na liberação e no lote, a solicitação mais antiga da mesma fila (unidade, fonte, categoria e exercício) passa primeiro.",
    icon: ListOrdered,
  },
  {
    titulo: "Saldo da conta",
    texto: "Autorizar sem saldo disponível na conta pagadora exige exceção justificada, que fica registrada.",
    icon: Banknote,
  },
];

/**
 * Mapa do processo de pagamento: o caminho inteiro, quem atua em cada passo,
 * o que cada decisão provoca e onde o trabalho está parado agora. O detalhe
 * de uma solicitação mostra onde ELA está (`EtapasFluxo`); este mostra o
 * processo, para quem opera entender o antes e o depois da sua mesa.
 */
export function MapaDoProcesso() {
  const { can } = useAuth();

  const contagemQ = useQuery({
    queryKey: ["pag-fluxo-contagem"],
    queryFn: () => api.pagamentos.debitos.contagemPorSituacao(),
  });
  const filaQ = useQuery({
    queryKey: ["pag-fluxo-minha-fila"],
    queryFn: () => api.pagamentos.minhaFila(),
  });

  const contagem = contagemQ.data;
  const quantidadeDe = (p: Passo): number | null => {
    if (p.situacoes) {
      if (!contagem) return null;
      return p.situacoes.reduce((soma, s) => soma + (contagem[s] ?? 0), 0);
    }
    // A fila pessoal devolve `null` no que o usuário não pode ver.
    if (p.fila) return filaQ.data?.[p.fila]?.length ?? null;
    return null;
  };

  return (
    <div className="space-y-6">
      {(contagemQ.isError || filaQ.isError) && (
        <p role="status" className="text-sm text-foreground-muted">
          Não foi possível carregar as quantidades agora. O mapa abaixo continua valendo.
        </p>
      )}

      <FasesDoFluxo
        fases={FASES}
        quantidadeDe={quantidadeDe}
        destaque={(p) => can(p.transacao)}
        podeAbrir={(p) => can(p.transacao)}
        unidadePadrao={["solicitação", "solicitações"]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Quando a solicitação volta" icon={Reply}>
          <p className="text-sm text-foreground-muted">
            Gestor, validação e autoridade podem pedir ajuste. A solicitação volta para a
            unidade, que corrige e reenvia. Ela retorna à mesa que pediu o ajuste, sem refazer
            as anteriores. Se a correção mudar um dado essencial da despesa, recomeça pelo gestor.
          </p>
        </SectionCard>

        <SectionCard title="Quando a solicitação encerra sem pagar" icon={X}>
          <ul className="space-y-2">
            {ENCERRAMENTOS.map((e) => (
              <li key={e.situacao} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-foreground">{e.label}</span>
                <span className="text-foreground-muted">{e.quem}</span>
                {contagem && (
                  <Badge intent="neutral">{contagem[e.situacao] ?? 0}</Badge>
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>

      <SectionCard title="O que impede um passo de avançar" icon={ShieldAlert}>
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {TRAVAS.map((t) => (
            <li key={t.titulo} className="flex gap-3">
              <t.icon className="mt-0.5 h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-foreground">{t.titulo}</p>
                <p className="text-sm text-foreground-muted">{t.texto}</p>
              </div>
            </li>
          ))}
        </ul>
      </SectionCard>

      <SectionCard title="Quem acompanha de fora" icon={ScrollText}>
        <p className="text-sm text-foreground-muted">
          O controle interno não decide nem paga: confere. Todo ato financeiro fica registrado
          com autor, data e origem, e as situações fora do padrão aparecem no relatório de exceções.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="secondary">
            <Link href="/m/pagamentos/fila">Ordem cronológica</Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link href="/m/pagamentos/excecoes">Exceções</Link>
          </Button>
          {can("pagamento_auditar") && (
            <Button asChild size="sm" variant="secondary">
              <Link href="/m/pagamentos/auditoria">Trilha de auditoria</Link>
            </Button>
          )}
        </div>
      </SectionCard>
    </div>
  );
}
