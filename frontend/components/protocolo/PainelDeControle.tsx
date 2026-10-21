"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpFromLine,
  Bell,
  FilePlus2,
  FileSearch,
  LayoutDashboard,
  type LucideIcon,
  PenLine,
  RefreshCw,
  Settings2,
  Undo2,
  UserCheck,
  UserX,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, notificacoesApi, type PainelUnidade } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROTA_PROCESSOS, hrefDaCaixa } from "@/lib/caixas-processos";
import { useLotacaoAtiva } from "@/lib/lotacao-ativa";
import { cn } from "@/lib/utils";

/**
 * Painel de controle do protocolo, no formato que a prefeitura pediu na
 * reunião de 2026-10-20, tendo o Painel de Controle do SEI como referência:
 * quadros de números no alto, cada um levando à lista que conta, e embaixo
 * três tabelas curtas (prazos, aguardando retorno, assinaturas).
 *
 * Mora no módulo (`/m/protocolo/painel`), e não na tela inicial, por decisão
 * do produto: é o painel de quem opera processos, como no SEI é a porta do
 * sistema de processos. A `/home` leva quem opera processos até aqui.
 *
 * Os números vêm de `GET /processos/painel`, no mesmo recorte das caixas de
 * trabalho (unidade ATIVA, sigilo de quem consulta): o quadro diz 12 e a
 * lista abre com 12. Quem chega aqui sem a transação `processo` (digitando a
 * URL, ou caindo na raiz do módulo sem nenhum item de menu visível) vê só a
 * saudação e as notificações, em vez de quadros vazios.
 */

/** O painel fica aberto o dia todo na mesa do servidor; sem isto, os números
 * da manhã continuariam na tela à tarde, sem ninguém perceber. Dois minutos é
 * o bastante para "chegou processo" aparecer sem martelar o backend. */
const INTERVALO_ATUALIZACAO = 2 * 60_000;

interface Dados {
  painel: PainelUnidade | undefined;
  naoLidas: number | undefined;
}

type IdQuadro =
  | "analise"
  | "entrada"
  | "saida"
  | "recusados"
  | "atribuidos"
  | "sem_responsavel"
  | "assinar"
  | "notificacoes";

interface DefQuadro {
  id: IdQuadro;
  rotulo: string;
  href: string;
  /** Dica curta, visível sob o número. */
  dica: string;
  /** O que o número conta, por extenso: no `title` (mouse) e no
   * `aria-describedby` (leitor de tela). Escrito a partir do que
   * `painel_unidade`/`_predicado_caixa` contam no backend — uma explicação
   * que prometesse mais que a consulta faria o servidor desconfiar do número. */
  explicacao: string;
  icon: LucideIcon;
  intent?: "default" | "info" | "warning";
  /** Fica vermelho quando há algo: recusados, notificações. */
  alerta?: boolean;
  /** Só quem não opera processos ainda vê este quadro. */
  sempreDisponivel?: boolean;
  valor: (d: Dados) => number | undefined;
  /** Base da barra de proporção, como a barra fina do SEI. Só nos quadros
   * que são PARTE de "Na unidade": nos outros não há total honesto para
   * dividir, e uma barra com base inventada mentiria sobre a proporção. */
  base?: (d: Dados) => number | undefined;
}

const QUADROS: DefQuadro[] = [
  {
    id: "analise",
    rotulo: "Na unidade",
    href: hrefDaCaixa("analise"),
    dica: "processos na mesa da sua unidade",
    explicacao:
      "Processos que estão com a sua unidade e não foram enviados a outra nem arquivados. Rascunhos não entram.",
    icon: FileSearch,
    valor: (d) => d.painel?.caixas.analise,
  },
  {
    id: "entrada",
    rotulo: "A receber",
    href: hrefDaCaixa("entrada"),
    dica: "enviados para a sua unidade",
    explicacao:
      "Processos que outra unidade enviou para a sua e que ninguém da sua unidade recebeu ainda.",
    icon: ArrowDownToLine,
    intent: "info",
    valor: (d) => d.painel?.caixas.entrada,
  },
  {
    id: "saida",
    rotulo: "Enviados",
    href: hrefDaCaixa("saida"),
    dica: "aguardando o destino receber",
    explicacao:
      "Processos que a sua unidade enviou e que a unidade de destino ainda não recebeu.",
    icon: ArrowUpFromLine,
    valor: (d) => d.painel?.caixas.saida,
  },
  {
    id: "recusados",
    rotulo: "Recusados",
    href: hrefDaCaixa("recusados"),
    dica: "devolvidos pelo destino",
    explicacao:
      "Processos cujo último envio, feito pela sua unidade, foi recusado pelo destino. Saem daqui quando forem reenviados ou arquivados.",
    icon: Undo2,
    alerta: true,
    valor: (d) => d.painel?.caixas.recusados,
  },
  {
    id: "atribuidos",
    rotulo: "Atribuídos a mim",
    href: `${ROTA_PROCESSOS}?caixa=analise&escopo=meus&ativos=0`,
    dica: "na unidade, com você como responsável",
    explicacao: "Dos processos contados em “Na unidade”, os que têm você como responsável.",
    icon: UserCheck,
    valor: (d) => d.painel?.atribuidos_a_mim,
    base: (d) => d.painel?.caixas.analise,
  },
  {
    id: "sem_responsavel",
    rotulo: "Sem responsável",
    href: hrefDaCaixa("analise"),
    dica: "na unidade, sem ninguém designado",
    explicacao: "Dos processos contados em “Na unidade”, os que não têm nenhum responsável designado.",
    icon: UserX,
    intent: "warning",
    valor: (d) => d.painel?.sem_responsavel,
    base: (d) => d.painel?.caixas.analise,
  },
  {
    id: "assinar",
    rotulo: "Para assinar",
    href: "/para-assinar",
    dica: "documentos aguardando sua assinatura",
    explicacao:
      "Processos com pelo menos um documento que você precisa assinar, numa solicitação de assinatura que não foi cancelada.",
    icon: PenLine,
    valor: (d) => d.painel?.caixas.aguardando_assinatura,
  },
  {
    id: "notificacoes",
    rotulo: "Notificações",
    href: "/perfil",
    dica: "não lidas",
    explicacao: "Notificações enviadas a você que ainda não foram marcadas como lidas.",
    icon: Bell,
    alerta: true,
    sempreDisponivel: true,
    valor: (d) => d.naoLidas,
  },
];

const IDS_PADRAO: IdQuadro[] = QUADROS.map((q) => q.id);
const POR_ID = new Map(QUADROS.map((q) => [q.id, q]));

/** O que o usuário escolheu no "Configurar". Guarda a ORDEM de todos e os
 * OCULTOS à parte, em vez de só a lista dos visíveis: assim um quadro que
 * nascer numa versão futura aparece para todo mundo, no fim, em vez de nascer
 * escondido para quem já tinha configurado. */
interface Preferencia {
  ordem: IdQuadro[];
  ocultos: IdQuadro[];
}

const PADRAO: Preferencia = { ordem: IDS_PADRAO, ocultos: [] };

const chavePreferencia = (idUsuario: number) => `aprimora:painel-quadros:${idUsuario}`;

/** Lê a preferência sem confiar nela: o armazenamento pode faltar (aba
 * anônima, site bloqueado), vir vazio ou trazer id de quadro que já não
 * existe. Qualquer coisa fora do esperado volta ao padrão, e a tela abre. */
function lerPreferencia(idUsuario: number | undefined): Preferencia {
  if (idUsuario == null) return PADRAO;
  try {
    const bruto = window.localStorage.getItem(chavePreferencia(idUsuario));
    if (!bruto) return PADRAO;
    const lido = JSON.parse(bruto) as Partial<Record<keyof Preferencia, unknown>>;
    const conhecidos = (v: unknown): IdQuadro[] =>
      Array.isArray(v) ? v.filter((id): id is IdQuadro => POR_ID.has(id as IdQuadro)) : [];
    const ordem = Array.from(new Set(conhecidos(lido.ordem)));
    for (const id of IDS_PADRAO) if (!ordem.includes(id)) ordem.push(id);
    return { ordem, ocultos: conhecidos(lido.ocultos) };
  } catch {
    return PADRAO;
  }
}

function gravarPreferencia(idUsuario: number | undefined, pref: Preferencia) {
  if (idUsuario == null) return;
  try {
    window.localStorage.setItem(chavePreferencia(idUsuario), JSON.stringify(pref));
  } catch {
    // Sem armazenamento a escolha vale só até recarregar — melhor que erro.
  }
}

/** "agora", "há 1 min", "há 2 h". Relativo, como no SEI: o servidor quer
 * saber se o número é fresco, não a hora exata. */
function haQuanto(desde: number, agora: number): string {
  const min = Math.floor((agora - desde) / 60_000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  return `há ${Math.floor(min / 60)} h`;
}

export function PainelDeControle() {
  const { user, perms, can } = useAuth();
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "—";
  const operaProcessos = can("processo");
  // A unidade cujo número aparece é a ATIVA (a do "alterar setor"): é por
  // ela que o `GET /processos/painel` conta. Vem do mesmo hook do cabeçalho
  // (`UnidadeAtiva`), para o nome daqui e o de lá não divergirem; trocar de
  // setor invalida as queries, e nome e números mudam juntos.
  const nomeUnidade = useLotacaoAtiva().ativa?.nome;

  const painelQ = useQuery({
    queryKey: ["protocolo-painel"],
    queryFn: () => api.processos.painel(),
    enabled: operaProcessos,
    staleTime: 60_000,
    refetchInterval: INTERVALO_ATUALIZACAO,
  });
  const notifQ = useQuery({
    queryKey: ["home-notif-unread"],
    queryFn: () => notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 1 }),
    staleTime: 30_000,
    refetchInterval: INTERVALO_ATUALIZACAO,
  });

  const painel = painelQ.data;
  const dados: Dados = { painel, naoLidas: notifQ.data?.nao_lidas };

  const [pref, setPref] = useState<Preferencia>(PADRAO);
  const [configurando, setConfigurando] = useState(false);
  // Lida no efeito, não no estado inicial: no SSR não há `window`, e ler lá
  // daria uma tela no servidor e outra no navegador.
  useEffect(() => {
    setPref(lerPreferencia(user?.id));
  }, [user?.id]);

  // Relógio do "Atualizado há": sem ele o texto congelaria em "agora".
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setAgora(Date.now()), 30_000);
    return () => window.clearInterval(t);
  }, []);
  // O rótulo existe para dizer se os NÚMEROS são frescos, então vale o mais
  // velho do que está na tela, nunca o mais novo: com o painel falhando e as
  // notificações em dia, o maior dos dois diria "agora" sobre quadros de
  // horas atrás, ao lado do aviso de erro. Com o painel em erro o rótulo some
  // — o aviso já diz o que há para dizer. Sem o painel (quem não opera
  // processos) só as notificações estão na tela, e elas mandam.
  const atualizadoEm = (() => {
    if (!operaProcessos) return notifQ.isError ? 0 : notifQ.dataUpdatedAt;
    if (painelQ.isError || painelQ.dataUpdatedAt === 0) return 0;
    return notifQ.dataUpdatedAt > 0
      ? Math.min(painelQ.dataUpdatedAt, notifQ.dataUpdatedAt)
      : painelQ.dataUpdatedAt;
  })();

  const carregando = painelQ.isFetching || notifQ.isFetching;
  function atualizar() {
    void painelQ.refetch();
    void notifQ.refetch();
  }

  const ocultos = new Set(pref.ocultos);
  const visiveis = pref.ordem
    .map((id) => POR_ID.get(id))
    .filter((q): q is DefQuadro => !!q && !ocultos.has(q.id))
    .filter((q) => operaProcessos || q.sempreDisponivel);

  // "Primeiro uso": nenhuma caixa DA UNIDADE tem processo. As de assinatura
  // ficam de fora porque são pessoais, não da unidade.
  const unidadeVazia =
    !!painel &&
    painel.caixas.analise +
      painel.caixas.entrada +
      painel.caixas.saida +
      painel.caixas.externos +
      painel.caixas.arquivados +
      painel.caixas.recusados ===
      0;

  return (
    <div className="space-y-6">
      {/* O cabeçalho das demais telas do módulo: a trilha do shell fica em
          cima, e o título da aba passa a ser "Painel de controle". */}
      <PageHeader
        title="Painel de controle"
        icon={LayoutDashboard}
        description={
          <>
            Olá, {primeiroNome}
            {perms?.is_super_usuario ? (
              <span className="ml-2 align-middle text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
                super usuário
              </span>
            ) : null}
            {operaProcessos
              ? nomeUnidade
                ? ` — números da unidade ${nomeUnidade}`
                : " — os números são da sua unidade."
              : null}
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {atualizadoEm > 0 && (
              <span className="text-xs text-foreground-subtle" data-testid="atualizado-ha">
                Atualizado {haQuanto(atualizadoEm, Math.max(agora, atualizadoEm))}
              </span>
            )}
            {operaProcessos && (
              <Button variant="secondary" size="sm" onClick={() => setConfigurando(true)}>
                <Settings2 className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Configurar
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={atualizar} disabled={carregando}>
              <RefreshCw
                className={cn("mr-1.5 h-4 w-4", carregando && "animate-spin")}
                aria-hidden="true"
              />
              Atualizar
            </Button>
          </div>
        }
      />

      {operaProcessos && painelQ.isError && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          Não foi possível carregar os números da unidade.{" "}
          <button type="button" className="underline" onClick={() => painelQ.refetch()}>
            Tentar de novo
          </button>
        </p>
      )}

      <section aria-label="Quadros de processos" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {visiveis.map((q) => (
          <Quadro key={q.id} def={q} dados={dados} />
        ))}
        {visiveis.length === 0 && (
          <p className="col-span-full text-sm text-foreground-muted">
            Nenhum quadro escolhido. Use &ldquo;Configurar&rdquo; para escolher o que aparece aqui.
          </p>
        )}
      </section>

      {operaProcessos && unidadeVazia && <PrimeiroUso podeAbrir={can("processo", "inserir")} />}

      {operaProcessos && painel && <Tabelas painel={painel} />}

      {configurando && (
        <ConfigurarQuadros
          atual={pref}
          onClose={() => setConfigurando(false)}
          onSalvar={(nova) => {
            setPref(nova);
            gravarPreferencia(user?.id, nova);
            setConfigurando(false);
          }}
        />
      )}
    </div>
  );
}

function Quadro({ def, dados }: { def: DefQuadro; dados: Dados }) {
  const explicacaoId = useId();
  const valor = def.valor(dados);
  const base = def.base?.(dados);
  const temAlgo = (valor ?? 0) > 0;
  const intent = def.intent ?? "default";
  return (
    <div className="relative">
      <Link
        href={def.href}
        title={def.explicacao}
        aria-describedby={explicacaoId}
        className="block h-full rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <KpiCard
          label={def.rotulo}
          value={valor ?? "—"}
          hint={
            <>
              {def.dica}
              {valor != null && base != null && base > 0 && (
                <Proporcao parte={valor} total={base} />
              )}
            </>
          }
          icon={def.icon}
          intent={def.alerta && temAlgo ? "danger" : intent}
          className={cn("h-full", def.alerta && temAlgo && "border-l-4 border-l-danger")}
        />
      </Link>
      <span id={explicacaoId} className="sr-only">
        {def.explicacao}
      </span>
    </div>
  );
}

/** A barra fina sob o número, como a do SEI. O visual é decorativo; quem
 * usa leitor de tela ouve o "x de y" por extenso. */
function Proporcao({ parte, total }: { parte: number; total: number }) {
  const pct = Math.min(100, Math.max(0, (parte / total) * 100));
  return (
    <span className="mt-2 block" data-testid="proporcao">
      <span aria-hidden="true" className="block h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
      </span>
      <span className="sr-only">
        {parte} de {total} na unidade
      </span>
    </span>
  );
}

function PrimeiroUso({ podeAbrir }: { podeAbrir: boolean }) {
  return (
    <section
      aria-label="Primeiros passos"
      className="rounded-card border border-border bg-info-soft px-4 py-3 text-sm text-info-soft-foreground"
    >
      <p className="font-medium">Ainda não há nenhum processo na sua unidade.</p>
      <p className="mt-1">
        Os quadros acima se enchem conforme os processos chegam ou são abertos aqui.{" "}
        {podeAbrir
          ? "Comece abrindo o primeiro, ou veja antes o caminho que um processo percorre."
          : "Enquanto isso, veja o caminho que um processo percorre."}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {podeAbrir && (
          <Button asChild size="sm">
            <Link href="/m/protocolo/processos/novo">
              <FilePlus2 className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Abrir o primeiro processo
            </Link>
          </Button>
        )}
        <Button asChild size="sm" variant="secondary">
          <Link href="/m/protocolo/fluxo">
            <Workflow className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Ver o caminho do processo
          </Link>
        </Button>
      </div>
    </section>
  );
}

/** "Configurar", como o botão do Painel de Controle do SEI: quais quadros
 * aparecem e em que ordem. Edita um rascunho; só "Salvar" muda a tela, para
 * que mexer e desistir não deixe nada pela metade. */
function ConfigurarQuadros({
  atual,
  onClose,
  onSalvar,
}: {
  atual: Preferencia;
  onClose: () => void;
  onSalvar: (p: Preferencia) => void;
}) {
  const [rascunho, setRascunho] = useState<Preferencia>(atual);
  const ocultos = new Set(rascunho.ocultos);
  // Foco pelo teclado ao reordenar. Sem isto ele se perdia de dois jeitos: o
  // React reposiciona o `<li>` movido (e nó do DOM que muda de lugar perde o
  // foco), e a seta que chega ao topo ou ao fim vira `disabled` com o foco
  // dentro — que cai no body, e o próximo Tab recomeça do início do diálogo.
  const botoes = useRef(new Map<string, HTMLButtonElement | null>());
  const [focoPendente, setFocoPendente] = useState<string | null>(null);
  const [anuncio, setAnuncio] = useState("");

  useEffect(() => {
    if (!focoPendente) return;
    botoes.current.get(focoPendente)?.focus();
    setFocoPendente(null);
  }, [focoPendente]);

  function mover(i: number, delta: -1 | 1) {
    const ordem = [...rascunho.ordem];
    const j = i + delta;
    if (j < 0 || j >= ordem.length) return;
    [ordem[i], ordem[j]] = [ordem[j], ordem[i]];
    setRascunho({ ...rascunho, ordem });
    const id = ordem[j];
    // Chegou à ponta: a mesma seta fica inativa, então o foco vai para a
    // oposta do MESMO quadro, que é o que o usuário estava mexendo.
    const naPonta = delta === -1 ? j === 0 : j === ordem.length - 1;
    const direcao = naPonta ? (delta === -1 ? "descer" : "subir") : delta === -1 ? "subir" : "descer";
    setFocoPendente(`${id}:${direcao}`);
    setAnuncio(`${POR_ID.get(id)?.rotulo ?? ""} na posição ${j + 1} de ${ordem.length}`);
  }

  function alternar(id: IdQuadro, visivel: boolean) {
    const novos = rascunho.ocultos.filter((o) => o !== id);
    setRascunho({ ...rascunho, ocultos: visivel ? novos : [...novos, id] });
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title="Configurar quadros"
      description="Escolha quais quadros aparecem no painel e em que ordem."
      footer={
        <>
          <Button variant="ghost" size="sm" className="mr-auto" onClick={() => setRascunho(PADRAO)}>
            Restaurar padrão
          </Button>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancelar
          </Button>
          <Button size="sm" onClick={() => onSalvar(rascunho)}>
            Salvar
          </Button>
        </>
      }
    >
      <ul className="divide-y divide-border" aria-label="Quadros do painel">
        {rascunho.ordem.map((id, i) => {
          const q = POR_ID.get(id);
          if (!q) return null;
          const inputId = `quadro-${id}`;
          return (
            <li key={id} className="flex items-center gap-3 py-2">
              <Checkbox
                id={inputId}
                checked={!ocultos.has(id)}
                onChange={(e) => alternar(id, e.target.checked)}
              />
              <label htmlFor={inputId} className="flex-1 text-sm text-foreground">
                {q.rotulo}
              </label>
              <Button
                variant="ghost"
                size="sm"
                ref={(el) => {
                  botoes.current.set(`${id}:subir`, el);
                }}
                aria-label={`Subir ${q.rotulo}`}
                disabled={i === 0}
                onClick={() => mover(i, -1)}
              >
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                ref={(el) => {
                  botoes.current.set(`${id}:descer`, el);
                }}
                aria-label={`Descer ${q.rotulo}`}
                disabled={i === rascunho.ordem.length - 1}
                onClick={() => mover(i, 1)}
              >
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </Button>
            </li>
          );
        })}
      </ul>
      {/* Quem usa leitor de tela não vê a lista mudar: ouve a nova posição. */}
      <p aria-live="polite" className="sr-only" data-testid="anuncio-posicao">
        {anuncio}
      </p>
    </Dialog>
  );
}

function Tabela({
  titulo,
  colunas,
  children,
}: {
  titulo: string;
  colunas: [string, string];
  children: React.ReactNode;
}) {
  return (
    <section aria-label={titulo} className="space-y-2">
      <h2 className="font-display text-base font-semibold text-foreground">{titulo}</h2>
      <div className="overflow-x-auto rounded-card border border-border bg-surface-1 shadow-card">
        <Table>
          <THead>
            <TR>
              <TH>{colunas[0]}</TH>
              <TH className="w-32 text-right">{colunas[1]}</TH>
            </TR>
          </THead>
          <TBody>{children}</TBody>
        </Table>
      </div>
    </section>
  );
}

function Linha({
  rotulo,
  valor,
  href,
  tom,
}: {
  rotulo: string;
  valor: number;
  href: string;
  tom?: "danger" | "warning";
}) {
  return (
    <TR>
      <TD>
        <span
          className={cn(
            valor > 0 && tom === "danger" && "font-medium text-danger-soft-foreground",
            valor > 0 && tom === "warning" && "font-medium text-warning-soft-foreground",
          )}
        >
          {rotulo}
        </span>
      </TD>
      <TD className="text-right tabular-nums">
        {valor > 0 ? (
          // Cor neutra, sublinhada: a cor de link do tema (laranja em
          // Itaitinga) fazia "No prazo: 3" parecer alarme. Vermelho e amarelo
          // ficam só para vencido e vencendo.
          <Link
            href={href}
            className={cn(
              "font-medium underline underline-offset-2 hover:no-underline",
              tom === "danger" && "text-danger-soft-foreground",
              tom === "warning" && "text-warning-soft-foreground",
              !tom && "text-foreground",
            )}
          >
            {valor}
          </Link>
        ) : (
          <span className="text-foreground-muted">0</span>
        )}
      </TD>
    </TR>
  );
}

function Tabelas({ painel }: { painel: PainelUnidade }) {
  const { prazos, aguardando_retorno: retorno, caixas } = painel;
  const comPrazo = prazos.vencidos + prazos.vencendo + prazos.no_prazo;
  // A caixa Análise abre pelo que espera há mais tempo, e o destaque de cada
  // linha é o prazo: é lá que vencidos e vencendo aparecem marcados.
  const analise = hrefDaCaixa("analise");

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Tabela titulo="Controle de prazos" colunas={["Situação", "Processos"]}>
        {comPrazo === 0 ? (
          <TR>
            <TD colSpan={2} className="text-sm text-foreground-muted">
              Nenhum processo com prazo na unidade.
            </TD>
          </TR>
        ) : (
          <>
            <Linha rotulo="Prazo vencido" valor={prazos.vencidos} href={analise} tom="danger" />
            <Linha rotulo="Vencendo" valor={prazos.vencendo} href={analise} tom="warning" />
            <Linha rotulo="No prazo" valor={prazos.no_prazo} href={analise} />
          </>
        )}
        <Linha rotulo="Sem prazo definido" valor={prazos.sem_prazo} href={analise} />
      </Tabela>

      <Tabela titulo="Aguardando retorno de outras unidades" colunas={["Situação", "Processos"]}>
        <Linha
          rotulo="Prazo vencido"
          valor={retorno.atrasados}
          href={hrefDaCaixa("saida")}
          tom="danger"
        />
        <Linha rotulo="Total enviado" valor={retorno.total} href={hrefDaCaixa("saida")} />
      </Tabela>

      <Tabela titulo="Assinaturas" colunas={["Situação", "Processos"]}>
        <Linha
          rotulo="Aguardando a sua assinatura"
          valor={caixas.aguardando_assinatura}
          href="/para-assinar"
          tom="warning"
        />
        <Linha
          rotulo="Enviados por você, ainda não assinados"
          valor={caixas.enviado_para_assinatura}
          href={hrefDaCaixa("enviado_para_assinatura")}
        />
      </Tabela>
    </div>
  );
}
