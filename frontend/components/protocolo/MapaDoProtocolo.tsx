"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  Ban,
  Check,
  FilePlus2,
  FileSearch,
  type LucideIcon,
  PenLine,
  Reply,
  Send,
  ShieldAlert,
  Timer,
  Undo2,
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
import { api, type CaixaProcesso } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hrefDaCaixa } from "@/lib/caixas-processos";

interface Passo extends PassoDoFluxo {
  /** Caixa de trabalho cuja contagem é o "aqui agora" do passo. */
  caixa?: CaixaProcesso;
}

/**
 * O caminho de um processo, da abertura ao arquivamento. É texto de
 * orientação: a regra mora no backend (`services/acoes_processo.py`). As
 * quantidades são as das caixas de trabalho — as mesmas do menu lateral — e
 * `__tests__/protocolo-fluxo.test.tsx` confere que cada passo aponta para a
 * caixa que conta.
 */
export const FASES: FaseDoFluxo<Passo>[] = [
  {
    titulo: "Abertura",
    descricao: "O pedido entra no sistema e ganha número.",
    passos: [
      {
        key: "abrir",
        titulo: "Abrir o processo",
        responsavel: "Protocolo ou a unidade que recebe o pedido",
        descricao:
          "Registra o assunto e o interessado e anexa os documentos. Rascunho ainda não tem número nem aparece nas caixas: o número sai no primeiro encaminhamento.",
        icon: FilePlus2,
        tela: { href: "/m/protocolo/processos/novo", label: "Abrir processo" },
        saidas: [
          { label: "Abrir", destino: "o processo fica com a sua unidade", icon: Check, intent: "success" },
        ],
      },
    ],
  },
  {
    titulo: "Tramitação",
    descricao:
      "O processo anda de unidade em unidade. Estes três passos se repetem até alguém concluir.",
    passos: [
      {
        key: "encaminhar",
        titulo: "Encaminhar",
        responsavel: "Unidade que está com o processo",
        descricao:
          "Escolhe a unidade de destino, a prioridade e, se quiser, um prazo. O processo só muda de unidade quando o destino recebe.",
        icon: ArrowUpFromLine,
        caixa: "saida",
        tela: { href: hrefDaCaixa("saida"), label: "Abrir caixa de saída" },
        saidas: [
          { label: "Encaminhar", destino: "aguarda o destino receber", icon: Send, intent: "success" },
          { label: "Cancelar", destino: "volta para a sua Análise", icon: Ban, intent: "neutral" },
        ],
      },
      {
        key: "receber",
        titulo: "Receber ou recusar",
        responsavel: "Unidade de destino",
        descricao:
          "Confere se o processo é da unidade. Receber assume o processo; recusar devolve à origem, com o motivo.",
        icon: ArrowDownToLine,
        caixa: "entrada",
        tela: { href: hrefDaCaixa("entrada"), label: "Abrir caixa de entrada" },
        saidas: [
          { label: "Receber", destino: "entra na Análise da unidade", icon: Check, intent: "success" },
          { label: "Recusar", destino: "volta para quem enviou", icon: Undo2, intent: "warning" },
        ],
      },
      {
        key: "analisar",
        titulo: "Analisar",
        responsavel: "Unidade que recebeu",
        descricao:
          "Define o responsável, despacha, anexa documentos e pede assinatura quando precisa. Depois decide o destino.",
        icon: FileSearch,
        caixa: "analise",
        tela: { href: hrefDaCaixa("analise"), label: "Abrir análise" },
        saidas: [
          { label: "Encaminhar", destino: "segue para outra unidade", icon: Send, intent: "info" },
          { label: "Pedir assinatura", destino: "vai para quem assina", icon: PenLine, intent: "info" },
          { label: "Arquivar", destino: "encerra o processo", icon: Archive, intent: "success" },
        ],
      },
    ],
  },
  {
    titulo: "Conclusão",
    descricao: "Os documentos são assinados e o processo é encerrado.",
    passos: [
      {
        key: "assinar",
        titulo: "Assinar",
        responsavel: "A pessoa indicada",
        descricao:
          "Assina os documentos com a própria senha, ou recusa. A assinatura é da pessoa, não da unidade: aparece para ela onde o processo estiver.",
        icon: PenLine,
        caixa: "aguardando_assinatura",
        tela: { href: "/para-assinar", label: "Abrir para assinar" },
        unidade: ["processo espera sua assinatura", "processos esperam sua assinatura"],
        saidas: [
          { label: "Assinar", destino: "o documento fica assinado", icon: Check, intent: "success" },
          { label: "Recusar", destino: "quem pediu é avisado", icon: X, intent: "danger" },
        ],
      },
      {
        key: "arquivar",
        titulo: "Arquivar",
        responsavel: "Unidade que está com o processo",
        descricao:
          "Encerra o processo, com o motivo. É o que conta como concluído no prazo e nos relatórios.",
        icon: Archive,
        caixa: "arquivados",
        tela: { href: hrefDaCaixa("arquivados"), label: "Abrir arquivados" },
        unidade: ["processo arquivado", "processos arquivados"],
        saidas: [
          { label: "Arquivar", destino: "sai das caixas de trabalho", icon: Check, intent: "success" },
        ],
      },
    ],
  },
];

const CUIDADOS: { titulo: string; texto: string; icon: LucideIcon }[] = [
  {
    titulo: "Prazo",
    texto:
      "Vale o prazo do encaminhamento, quando quem enviou marcou um, ou o do serviço, contado da abertura. Na caixa, amarelo é prazo vencendo e vermelho é prazo vencido.",
    icon: Timer,
  },
  {
    titulo: "Sigilo",
    texto:
      "Processo com sigilo só aparece para quem tem credencial no nível dele. Para os demais é como se não existisse.",
    icon: ShieldAlert,
  },
  {
    titulo: "Responsável",
    texto:
      "Dentro da unidade, o processo pode ter um responsável. Sem ele, a caixa mostra \"Sem responsável\".",
    icon: UserCheck,
  },
  {
    titulo: "Um encaminhamento por vez",
    texto:
      "Enquanto o destino não recebe ou recusa, e a origem não cancela, o processo não pode ser encaminhado de novo.",
    icon: Send,
  },
];

/**
 * Mapa do protocolo: o caminho do processo e onde o trabalho da SUA unidade
 * está agora. Não há "sua etapa" como em pagamentos — no protocolo todo
 * operador faz todos os passos; o que muda é a caixa em que o processo está.
 */
export function MapaDoProtocolo() {
  const { can } = useAuth();
  const opera = can("processo");

  const caixasQ = useQuery({
    queryKey: ["protocolo-fluxo-caixas"],
    queryFn: () => api.processos.caixas(),
    enabled: opera,
  });
  const caixas = caixasQ.data;

  return (
    <div className="space-y-6">
      {caixasQ.isError && (
        <p role="status" className="text-sm text-foreground-muted">
          Não foi possível carregar as quantidades agora. O mapa abaixo continua valendo.
        </p>
      )}
      {caixas && (
        <p className="text-sm text-foreground-muted">
          As quantidades são as da sua unidade, as mesmas das caixas do menu.
        </p>
      )}

      <FasesDoFluxo
        fases={FASES}
        quantidadeDe={(p) => (p.caixa && caixas ? caixas[p.caixa] : null)}
        destaque={() => false}
        podeAbrir={() => opera}
        unidadePadrao={["processo", "processos"]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Quando o destino recusa" icon={Reply}>
          <p className="text-sm text-foreground-muted">
            O processo não chega a sair da unidade de origem. Ele volta para a mesa de quem
            enviou, com o motivo na linha do tempo, e quem enviou é avisado. A origem decide:
            corrige e reenvia, manda para outra unidade ou arquiva.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href={hrefDaCaixa("recusados")}>Abrir recusados</Link>
            </Button>
            {caixas && (
              <Badge intent={caixas.recusados > 0 ? "warning" : "neutral"}>
                {caixas.recusados === 1 ? "1 recusado" : `${caixas.recusados} recusados`}
              </Badge>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Quem acompanha o andamento" icon={FileSearch}>
          <p className="text-sm text-foreground-muted">
            O interessado acompanha pelo portal do cidadão. Internamente, a linha do tempo de
            cada processo mostra por onde ele passou e quanto tempo ficou em cada unidade.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/m/protocolo/relatorios">Relatórios</Link>
            </Button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="O que vale saber antes de tramitar" icon={ShieldAlert}>
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {CUIDADOS.map((c) => (
            <li key={c.titulo} className="flex gap-3">
              <c.icon className="mt-0.5 h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-foreground">{c.titulo}</p>
                <p className="text-sm text-foreground-muted">{c.texto}</p>
              </div>
            </li>
          ))}
        </ul>
      </SectionCard>
    </div>
  );
}
