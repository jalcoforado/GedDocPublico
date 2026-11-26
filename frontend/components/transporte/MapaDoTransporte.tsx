"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  Ban,
  CalendarClock,
  Check,
  ClipboardCheck,
  FolderOpen,
  Gavel,
  IdCard,
  Megaphone,
  RefreshCw,
  ScrollText,
  Search,
  UserX,
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
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/**
 * De onde vem a quantidade de um passo.
 *
 * Os passos de alvará NÃO têm quantidade, de propósito. O único número
 * disponível é o do relatório (`alvaras/relatorio/kpis`), que classifica pela
 * data de validade e inclui alvará já renovado ou revogado: um alvará renovado
 * continua "vencido" para sempre. Mostrá-lo em "Renovar" diria que há trabalho
 * onde não há.
 */
export type Contagem =
  | "ciclos_abertos"
  | "ocorrencias_registradas"
  | "ocorrencias_em_apuracao";

interface Passo extends PassoDoFluxo {
  contagem?: Contagem;
}

const ALVARAS = { href: "/m/transporte/alvaras", label: "Abrir alvarás" };
const RECADASTRAMENTO = { href: "/m/transporte/recadastramento", label: "Abrir recadastramento" };
const OCORRENCIAS = { href: "/m/transporte/ocorrencias", label: "Abrir ocorrências" };
const EQUIPE = "Equipe de transporte";

/**
 * Os três caminhos do transporte regulado. São independentes entre si — um
 * alvará, um recadastramento e uma ocorrência não são etapas um do outro —,
 * por isso cada um tem a própria numeração.
 *
 * É texto de orientação. Os estados e as transições de cada caminho estão em
 * `services/transporte_workflow.py::SEMENTES`, que é o ponto de partida do
 * workflow de cada município; um município pode ter editado o seu.
 */
export const FLUXOS: FaseDoFluxo<Passo>[] = [
  {
    titulo: "Alvará",
    descricao: "Quem opera táxi, mototáxi ou transporte escolar precisa de alvará vigente.",
    passos: [
      {
        key: "cadastrar",
        titulo: "Cadastrar titular e veículos",
        responsavel: EQUIPE,
        descricao:
          "Registra o permissionário ou a empresa e os veículos que vão operar.",
        icon: IdCard,
        tela: { href: "/m/transporte/permissionarios", label: "Abrir permissionários" },
        saidas: [
          { label: "Cadastrar", destino: "fica pronto para o alvará", icon: Check, intent: "success" },
        ],
      },
      {
        key: "emitir",
        titulo: "Emitir o alvará",
        responsavel: EQUIPE,
        descricao:
          "Emite o alvará do titular, com a validade, vincula os veículos e anexa os documentos. O alvará nasce vigente.",
        icon: ScrollText,
        tela: ALVARAS,
        saidas: [
          { label: "Emitir", destino: "vale até a data de validade", icon: Check, intent: "success" },
        ],
      },
      {
        key: "renovar",
        titulo: "Renovar ou revogar",
        responsavel: EQUIPE,
        descricao:
          "Alvará vencido é renovado: nasce um novo, ligado ao anterior. Alvará vigente pode ser revogado, com motivo.",
        icon: RefreshCw,
        tela: ALVARAS,
        saidas: [
          { label: "Renovar", destino: "nasce um novo alvará vigente", icon: Check, intent: "success" },
          { label: "Revogar", destino: "encerra o alvará", icon: Ban, intent: "danger" },
        ],
      },
    ],
  },
  {
    titulo: "Recadastramento",
    descricao: "De tempos em tempos, todo regulado ativo é chamado a confirmar os seus dados.",
    passos: [
      {
        key: "ciclo",
        titulo: "Abrir o ciclo",
        responsavel: EQUIPE,
        descricao:
          "Define o período e como os prazos são escalonados. O ciclo começa como rascunho e é aberto quando está pronto.",
        icon: FolderOpen,
        contagem: "ciclos_abertos",
        unidade: ["ciclo aberto", "ciclos abertos"],
        tela: RECADASTRAMENTO,
        saidas: [
          { label: "Abrir", destino: "libera a convocação", icon: Check, intent: "success" },
        ],
      },
      {
        key: "convocar",
        titulo: "Convocar",
        responsavel: EQUIPE,
        descricao:
          "Gera a convocação de todo permissionário e empresa ativos. Pode ser repetido: alcança quem foi cadastrado depois, sem duplicar.",
        icon: Megaphone,
        tela: RECADASTRAMENTO,
        saidas: [
          { label: "Convocar", destino: "cada um recebe o seu prazo", icon: Check, intent: "success" },
        ],
      },
      {
        key: "atender",
        titulo: "Atender e conferir",
        responsavel: EQUIPE,
        descricao:
          "No atendimento, confere os documentos do checklist, item a item. A convocação passa a \"em análise\".",
        icon: ClipboardCheck,
        tela: RECADASTRAMENTO,
        saidas: [
          { label: "Iniciar análise", destino: "segue para a decisão", icon: Check, intent: "success" },
        ],
      },
      {
        key: "decidir-recadastramento",
        titulo: "Decidir",
        responsavel: EQUIPE,
        descricao:
          "Defere ou indefere, com parecer. Deferir exige o checklist completo; indeferir, não.",
        icon: Gavel,
        tela: RECADASTRAMENTO,
        saidas: [
          { label: "Deferir", destino: "recadastramento concluído", icon: Check, intent: "success" },
          { label: "Indeferir", destino: "encerra, com o parecer", icon: X, intent: "danger" },
        ],
      },
    ],
  },
  {
    titulo: "Ocorrência",
    descricao: "Irregularidades apontadas pela fiscalização ou denunciadas pelo cidadão.",
    passos: [
      {
        key: "registrar",
        titulo: "Registrar",
        responsavel: "Fiscalização ou cidadão",
        descricao:
          "Entra pela fiscalização ou por denúncia no portal do cidadão. A denúncia pode chegar sem o permissionário identificado.",
        icon: AlertOctagon,
        tela: OCORRENCIAS,
        saidas: [
          { label: "Registrar", destino: "aguarda a apuração", icon: Check, intent: "success" },
        ],
      },
      {
        key: "iniciar-apuracao",
        titulo: "Iniciar a apuração",
        responsavel: EQUIPE,
        descricao: "Assume a ocorrência registrada e começa a apurar.",
        icon: Search,
        contagem: "ocorrencias_registradas",
        unidade: ["ocorrência aguarda apuração", "ocorrências aguardam apuração"],
        tela: OCORRENCIAS,
        saidas: [
          { label: "Iniciar", destino: "fica em apuração", icon: Check, intent: "success" },
        ],
      },
      {
        key: "decidir-ocorrencia",
        titulo: "Apurar e decidir",
        responsavel: EQUIPE,
        descricao:
          "Anota os andamentos, vincula o permissionário, a empresa ou o veículo envolvido e decide.",
        icon: Gavel,
        contagem: "ocorrencias_em_apuracao",
        unidade: ["ocorrência em apuração", "ocorrências em apuração"],
        tela: OCORRENCIAS,
        saidas: [
          { label: "Procedente", destino: "encerra como procedente", icon: Check, intent: "warning" },
          { label: "Improcedente", destino: "encerra como improcedente", icon: X, intent: "neutral" },
          { label: "Arquivar", destino: "encerra sem julgar o mérito", icon: Ban, intent: "neutral" },
        ],
      },
    ],
  },
];

/**
 * Mapa do transporte regulado: os três caminhos do módulo e o que há em cada
 * passo agora. Não há "sua etapa": o módulo tem uma transação só
 * (`transporte_regulado`).
 */
export function MapaDoTransporte() {
  const { can } = useAuth();
  const opera = can("transporte_regulado");

  const alvarasQ = useQuery({
    queryKey: ["transporte-fluxo-alvaras"],
    queryFn: () => api.alvaras.relatorio.kpis(),
    enabled: opera,
  });
  // `page_size: 1`: só o `total` interessa, não as linhas.
  const ciclosQ = useQuery({
    queryKey: ["transporte-fluxo-ciclos"],
    queryFn: () => api.recadastramento.ciclos.list({ situacao: "aberto", page_size: 1 }),
    enabled: opera,
  });
  const registradasQ = useQuery({
    queryKey: ["transporte-fluxo-ocorrencias", "registrada"],
    queryFn: () => api.ocorrenciasTransporte.list({ situacao: "registrada", page_size: 1 }),
    enabled: opera,
  });
  const apuracaoQ = useQuery({
    queryKey: ["transporte-fluxo-ocorrencias", "em_apuracao"],
    queryFn: () => api.ocorrenciasTransporte.list({ situacao: "em_apuracao", page_size: 1 }),
    enabled: opera,
  });

  const quantidades: Record<Contagem, number | null> = {
    ciclos_abertos: ciclosQ.data?.total ?? null,
    ocorrencias_registradas: registradasQ.data?.total ?? null,
    ocorrencias_em_apuracao: apuracaoQ.data?.total ?? null,
  };
  const algumaFalhou = [alvarasQ, ciclosQ, registradasQ, apuracaoQ].some((q) => q.isError);
  const aVencer = alvarasQ.data?.a_renovar_30d;

  return (
    <div className="space-y-6">
      {algumaFalhou && (
        <p role="status" className="text-sm text-foreground-muted">
          Não foi possível carregar todas as quantidades agora. O mapa abaixo continua valendo.
        </p>
      )}

      <FasesDoFluxo
        fases={FLUXOS}
        quantidadeDe={(p) => (p.contagem ? quantidades[p.contagem] : null)}
        destaque={() => false}
        podeAbrir={() => opera}
        unidadePadrao={["item", "itens"]}
        rotuloDaSecao="Fluxo"
        numerarPorSecao
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Alvarás perto de vencer" icon={CalendarClock}>
          <p className="text-sm text-foreground-muted">
            A renovação só é aceita depois do vencimento. O relatório mostra, pela data de
            validade, quem vence nos próximos 30 dias, para avisar o titular antes.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/m/transporte/relatorio">Abrir relatório de alvarás</Link>
            </Button>
            {aVencer !== undefined && (
              <Badge intent={aVencer > 0 ? "warning" : "neutral"}>
                {aVencer === 1 ? "1 vence em 30 dias" : `${aVencer} vencem em 30 dias`}
              </Badge>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Quem não recadastra" icon={UserX}>
          <p className="text-sm text-foreground-muted">
            Com o prazo vencido, a convocação pode ser suspensa, com parecer. A suspensão não
            cassa nem altera o cadastro, mas bloqueia a renovação do alvará do titular. Se o
            recurso for aceito, a convocação é reativada e volta para onde estava.
          </p>
          <div className="mt-3">
            <Button asChild size="sm" variant="secondary">
              <Link href={RECADASTRAMENTO.href}>Abrir recadastramento</Link>
            </Button>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
