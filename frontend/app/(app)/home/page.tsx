"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Bell,
  FileSearch,
  type LucideIcon,
  PenLine,
  RefreshCw,
  Undo2,
  UserCheck,
  UserX,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/ui/kpi-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, notificacoesApi, type PainelUnidade } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROTA_PROCESSOS, hrefDaCaixa } from "@/lib/caixas-processos";
import { cn } from "@/lib/utils";

/**
 * Painel de controle — a tela inicial no formato que a prefeitura pediu na
 * reunião de 2026-10-20, tendo o Painel de Controle do SEI como referência:
 * quadros de números no alto, cada um levando à lista que conta, e embaixo
 * três tabelas curtas (prazos, aguardando retorno, assinaturas).
 *
 * Os números vêm de `GET /processos/painel`, no mesmo recorte das caixas de
 * trabalho (unidade de lotação principal, sigilo de quem consulta): o quadro
 * diz 12 e a lista abre com 12. Quem não opera processos (sem a transação
 * `processo`, ou sem o módulo contratado) vê só a saudação e as
 * notificações.
 */
export default function HomePage() {
  const { user, perms, can } = useAuth();
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "—";
  const operaProcessos = can("processo");

  const painelQ = useQuery({
    queryKey: ["home-painel"],
    queryFn: () => api.processos.painel(),
    enabled: operaProcessos,
    staleTime: 60_000,
  });
  const notifQ = useQuery({
    queryKey: ["home-notif-unread"],
    queryFn: () => notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 1 }),
    staleTime: 30_000,
  });

  const painel = painelQ.data;
  const naoLidas = notifQ.data?.nao_lidas;

  function atualizar() {
    void painelQ.refetch();
    void notifQ.refetch();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border-strong pb-3">
        <div>
          <h1 className="font-display text-2xl font-semibold text-titulo-destaque">
            Painel de controle
          </h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Olá, {primeiroNome}
            {perms?.is_super_usuario ? (
              <span className="ml-2 align-middle text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
                super usuário
              </span>
            ) : null}
            {operaProcessos ? " — os números são da sua unidade." : null}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={atualizar}
          disabled={painelQ.isFetching || notifQ.isFetching}
        >
          <RefreshCw
            className={cn("mr-1.5 h-4 w-4", (painelQ.isFetching || notifQ.isFetching) && "animate-spin")}
            aria-hidden="true"
          />
          Atualizar
        </Button>
      </div>

      {operaProcessos && painelQ.isError && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          Não foi possível carregar os números da unidade.{" "}
          <button type="button" className="underline" onClick={() => painelQ.refetch()}>
            Tentar de novo
          </button>
        </p>
      )}

      <section aria-label="Quadros de processos" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {operaProcessos && (
          <>
            <Quadro
              href={hrefDaCaixa("analise")}
              rotulo="Na unidade"
              valor={painel?.caixas.analise}
              dica="processos na mesa da sua unidade"
              icon={FileSearch}
            />
            <Quadro
              href={hrefDaCaixa("entrada")}
              rotulo="A receber"
              valor={painel?.caixas.entrada}
              dica="enviados para a sua unidade"
              icon={ArrowDownToLine}
              intent="info"
            />
            <Quadro
              href={hrefDaCaixa("saida")}
              rotulo="Enviados"
              valor={painel?.caixas.saida}
              dica="aguardando o destino receber"
              icon={ArrowUpFromLine}
            />
            <Quadro
              href={hrefDaCaixa("recusados")}
              rotulo="Recusados"
              valor={painel?.caixas.recusados}
              dica="devolvidos pelo destino"
              icon={Undo2}
              alerta
            />
            <Quadro
              href={`${ROTA_PROCESSOS}?caixa=analise&escopo=meus&ativos=0`}
              rotulo="Atribuídos a mim"
              valor={painel?.atribuidos_a_mim}
              dica="na unidade, com você como responsável"
              icon={UserCheck}
            />
            <Quadro
              href={hrefDaCaixa("analise")}
              rotulo="Sem responsável"
              valor={painel?.sem_responsavel}
              dica="na unidade, sem ninguém designado"
              icon={UserX}
              intent="warning"
            />
            <Quadro
              href="/para-assinar"
              rotulo="Para assinar"
              valor={painel?.caixas.aguardando_assinatura}
              dica="documentos aguardando sua assinatura"
              icon={PenLine}
            />
          </>
        )}
        <Quadro
          href="/perfil"
          rotulo="Notificações"
          valor={naoLidas}
          dica="não lidas"
          icon={Bell}
          alerta
        />
      </section>

      {operaProcessos && painel && <Tabelas painel={painel} />}
    </div>
  );
}

function Quadro({
  href,
  rotulo,
  valor,
  dica,
  icon,
  intent = "default",
  alerta = false,
}: {
  href: string;
  rotulo: string;
  valor: number | undefined;
  dica: string;
  icon: LucideIcon;
  intent?: "default" | "info" | "warning";
  /** Fica vermelho quando há algo: recusados, notificações. */
  alerta?: boolean;
}) {
  const temAlgo = (valor ?? 0) > 0;
  return (
    <Link
      href={href}
      className="rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <KpiCard
        label={rotulo}
        value={valor ?? "—"}
        hint={dica}
        icon={icon}
        intent={alerta && temAlgo ? "danger" : intent}
        className={cn("h-full", alerta && temAlgo && "border-l-4 border-l-danger")}
      />
    </Link>
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
          <Link href={href} className="text-primary underline-offset-2 hover:underline">
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
