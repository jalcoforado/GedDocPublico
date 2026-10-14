"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  Car,
  Check,
  ClipboardList,
  Gauge,
  IdCard,
  LogIn,
  LogOut,
  type LucideIcon,
  ShieldAlert,
  ThumbsUp,
  Wrench,
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
import { api, type SolicitacaoVeiculo } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Passo extends PassoDoFluxo {
  /** Quais solicitações estão paradas neste passo. Ausente = não se conta. */
  estaAqui?: (s: SolicitacaoVeiculo) => boolean;
}

const TELA = { href: "/m/frota/solicitacoes", label: "Abrir solicitações" };

/**
 * O caminho de uma solicitação de veículo, do pedido ao retorno. É texto de
 * orientação: a regra mora no backend (`services/frota.py`). Os predicados
 * `estaAqui` repartem as solicitações em andamento, e
 * `__tests__/frota-fluxo.test.tsx` confere que nenhuma cai em dois passos.
 */
export const FASES: FaseDoFluxo<Passo>[] = [
  {
    titulo: "Pedido",
    descricao: "A unidade pede o veículo e a gestão da frota decide.",
    passos: [
      {
        key: "solicitar",
        titulo: "Solicitar",
        responsavel: "Quem precisa do veículo",
        descricao:
          "Informa o destino, a finalidade, o período e se precisa de motorista.",
        icon: ClipboardList,
        tela: TELA,
        saidas: [
          { label: "Solicitar", destino: "aguarda a aprovação", icon: Check, intent: "success" },
        ],
      },
      {
        key: "aprovar",
        titulo: "Aprovar",
        responsavel: "Gestão da frota",
        descricao: "Avalia se o pedido procede. Rejeição encerra a solicitação.",
        icon: ThumbsUp,
        estaAqui: (s) => s.status === "solicitada",
        tela: TELA,
        saidas: [
          { label: "Aprovar", destino: "segue para a designação", icon: Check, intent: "success" },
          { label: "Rejeitar", destino: "encerra a solicitação", icon: X, intent: "danger" },
        ],
      },
    ],
  },
  {
    titulo: "Viagem",
    descricao: "Com o pedido aprovado, o veículo é reservado, sai e volta.",
    passos: [
      {
        key: "designar",
        titulo: "Designar veículo e motorista",
        responsavel: "Gestão da frota",
        descricao:
          "Escolhe um veículo disponível e, se o pedido exigir, um motorista ativo. Pode trocar enquanto o veículo não saiu.",
        icon: Car,
        estaAqui: (s) => s.status === "aprovada" && s.id_veiculo_designado === null,
        tela: TELA,
        saidas: [
          { label: "Designar", destino: "fica pronta para a saída", icon: Check, intent: "success" },
        ],
      },
      {
        key: "saida",
        titulo: "Registrar a saída",
        responsavel: "Gestão da frota",
        descricao:
          "Anota a quilometragem de saída. A partir daqui o veículo consta em uso e não pode ser designado a outro pedido.",
        icon: LogOut,
        estaAqui: (s) => s.status === "aprovada" && s.id_veiculo_designado !== null,
        tela: TELA,
        saidas: [
          { label: "Registrar saída", destino: "o veículo fica em uso", icon: Check, intent: "success" },
        ],
      },
      {
        key: "retorno",
        titulo: "Registrar o retorno",
        responsavel: "Gestão da frota",
        descricao:
          "Anota a quilometragem de chegada. O veículo volta a ficar disponível, com a quilometragem atualizada.",
        icon: LogIn,
        estaAqui: (s) => s.status === "em_uso",
        unidade: ["veículo na rua", "veículos na rua"],
        tela: TELA,
        saidas: [
          { label: "Registrar retorno", destino: "conclui a solicitação", icon: Check, intent: "success" },
        ],
      },
    ],
  },
];

const TRAVAS: { titulo: string; texto: string; icon: LucideIcon }[] = [
  {
    titulo: "Veículo disponível",
    texto:
      "Só veículo com situação \"disponível\" pode ser designado e sair. Em uso ou em manutenção, não.",
    icon: Car,
  },
  {
    titulo: "Motorista",
    texto:
      "Pedido que exige motorista não sai sem um designado, e só motorista ativo pode ser designado.",
    icon: IdCard,
  },
  {
    titulo: "Quilometragem",
    texto:
      "A quilometragem de saída não pode ser menor que a atual do veículo, nem a de retorno menor que a de saída.",
    icon: Gauge,
  },
  {
    titulo: "Cancelamento",
    texto:
      "A solicitação pode ser cancelada enquanto o veículo não saiu. Depois da saída, o caminho é registrar o retorno.",
    icon: Ban,
  },
];

const CUIDADOS = [
  { href: "/m/frota/manutencoes", label: "Manutenções" },
  { href: "/m/frota/abastecimentos", label: "Abastecimentos" },
  { href: "/m/frota/vistorias", label: "Vistorias" },
  { href: "/m/frota/ocorrencias", label: "Ocorrências" },
];

/**
 * Mapa da frota: o caminho de uma solicitação de veículo e onde elas estão
 * paradas agora. Não há "sua etapa": o módulo tem uma transação só (`frota`),
 * então quem a tem faz todos os passos.
 */
export function MapaDaFrota() {
  const { can } = useAuth();
  const opera = can("frota");

  const q = useQuery({
    queryKey: ["frota-fluxo-solicitacoes"],
    queryFn: () => api.solicitacoes.listAll(),
    enabled: opera,
  });
  const solicitacoes = q.data;
  const encerradas = (status: SolicitacaoVeiculo["status"]) =>
    solicitacoes?.filter((s) => s.status === status).length ?? 0;

  return (
    <div className="space-y-6">
      {q.isError && (
        <p role="status" className="text-sm text-foreground-muted">
          Não foi possível carregar as quantidades agora. O mapa abaixo continua valendo.
        </p>
      )}

      <FasesDoFluxo
        fases={FASES}
        quantidadeDe={(p) =>
          p.estaAqui && solicitacoes ? solicitacoes.filter(p.estaAqui).length : null
        }
        destaque={() => false}
        podeAbrir={() => opera}
        unidadePadrao={["solicitação", "solicitações"]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Como uma solicitação termina" icon={Check}>
          <ul className="space-y-2 text-sm">
            {(
              [
                ["concluida", "Concluída", "o veículo saiu e voltou"],
                ["rejeitada", "Rejeitada", "pela gestão da frota, antes de aprovar"],
                ["cancelada", "Cancelada", "antes de o veículo sair"],
              ] as const
            ).map(([status, label, quando]) => (
              <li key={status} className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">{label}</span>
                <span className="text-foreground-muted">{quando}</span>
                {solicitacoes && <Badge intent="neutral">{encerradas(status)}</Badge>}
              </li>
            ))}
          </ul>
        </SectionCard>

        <SectionCard title="Cuidando do veículo" icon={Wrench}>
          <p className="text-sm text-foreground-muted">
            Fora das viagens, cada veículo tem o seu histórico. Veículo com situação
            &quot;manutenção&quot; não pode ser designado; concluir a manutenção o devolve a disponível.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {CUIDADOS.map((c) => (
              <Button key={c.href} asChild size="sm" variant="secondary">
                <Link href={c.href}>{c.label}</Link>
              </Button>
            ))}
          </div>
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
    </div>
  );
}
