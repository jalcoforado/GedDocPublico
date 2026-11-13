"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  CheckCircle2,
  Clock,
  Cog,
  Download,
  Eraser,
  ListTodo,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { usePrompt } from "@/components/ui/confirm";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, jobResultadoUrl, type JobOut, type JobStatus } from "@/lib/api";
import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";

// dd/mm/aaaa hh:mm — o segundo não ajuda a ler a lista, só a alarga.
function fmtDateTime(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function statusBadge(status: JobStatus) {
  switch (status) {
    case "pendente":
      return (
        <Badge intent="neutral" icon={Clock}>
          Pendente
        </Badge>
      );
    case "em_andamento":
      return (
        <Badge intent="info" icon={Loader2}>
          Em andamento
        </Badge>
      );
    case "concluido":
      return (
        <Badge intent="success" icon={CheckCircle2}>
          Concluído
        </Badge>
      );
    case "falhou":
      return (
        <Badge intent="danger" icon={XCircle}>
          Falhou
        </Badge>
      );
  }
}

type Tab = "execucoes" | "agendados";

export default function JobsPage() {
  const [tab, setTab] = useState<Tab>("execucoes");

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Cog}
        title="Jobs em background"
        description="Operações demoradas que o sistema executa por trás — exportações, limpezas e tarefas agendadas."
      />

      <Tabs value={tab} onChange={(v) => setTab(v as Tab)}>
        <TabList
          aria-label="Tipos de jobs"
          tabs={[
            { value: "execucoes", label: "Execuções" },
            { value: "agendados", label: "Agendados" },
          ]}
        />
        <TabPanel value="execucoes">
          <ExecucoesTab />
        </TabPanel>
        <TabPanel value="agendados">
          <AgendadosTab />
        </TabPanel>
      </Tabs>
    </div>
  );
}

function ExecucoesTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const prompt = usePrompt();
  const [todos, setTodos] = useState(false);

  const q = useQuery({
    queryKey: ["jobs", todos],
    queryFn: () => api.jobs.list({ todos, limit: 100 }),
    refetchInterval: (query) => {
      const data = query.state.data as JobOut[] | undefined;
      if (!data) return false;
      const ativos = data.some(
        (j) => j.status === "pendente" || j.status === "em_andamento",
      );
      return ativos ? 2000 : false;
    },
  });

  const limpar = useMutation({
    mutationFn: (dias: number) => api.jobs.limparAntigos(dias),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      toast.success("Limpeza enfileirada — acompanhe o status na lista.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onLimpar() {
    const v = await prompt({
      title: "Limpar jobs antigos",
      message:
        "Apagar jobs com mais de quantos dias? Use 0 para apagar todos (exceto os em execução).",
      label: "Dias",
      defaultValue: "30",
      type: "number",
      inputMode: "numeric",
      confirmLabel: "Apagar",
      required: true,
    });
    if (v === null) return;
    const dias = Number(v);
    if (Number.isNaN(dias) || dias < 0) {
      toast.error("Valor inválido. Informe um número inteiro ≥ 0.");
      return;
    }
    limpar.mutate(dias);
  }

  return (
    <div className="space-y-4">
      <FilterBar>
        <FilterBar.Group>
          <label className="flex h-9 items-center gap-2 text-sm">
            <Checkbox checked={todos} onChange={(e) => setTodos(e.target.checked)} />
            Mostrar de todos os usuários
          </label>
        </FilterBar.Group>
        <FilterBar.Actions>
          <Button variant="secondary" size="sm" onClick={() => q.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Atualizar agora
          </Button>
          <Button variant="secondary" size="sm" onClick={onLimpar} disabled={limpar.isPending}>
            <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
            {limpar.isPending ? "Limpando..." : "Limpar antigos"}
          </Button>
        </FilterBar.Actions>
      </FilterBar>
      <p className="text-xs text-foreground-muted">
        Atualização automática a cada 2s enquanto houver jobs pendentes ou em andamento.
      </p>

      <Table>
        <THead>
          <TR>
            <TH>#</TH>
            <TH>Tipo</TH>
            <TH>Descrição</TH>
            <TH>Status</TH>
            <TH>Usuário</TH>
            <TH>Criado</TH>
            <TH>Concluído</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {q.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={8} />)}
          {!q.isLoading && (q.data?.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={8} className="p-0">
                <EmptyState
                  icon={ListTodo}
                  title="Nenhum job ainda"
                  description="Operações em background aparecem aqui quando enfileiradas."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {q.data?.map((j) => (
            <TR key={j.id}>
              <TD className="font-mono text-xs tabular-nums">{j.id}</TD>
              <TD className="font-mono text-xs">{j.tipo}</TD>
              <TD className="text-sm">{j.descricao ?? "—"}</TD>
              <TD>
                {statusBadge(j.status)}
                {j.erro && (
                  <div
                    className="mt-1 max-w-md truncate text-xs text-danger-soft-foreground"
                    title={j.erro}
                  >
                    {j.erro.split("\n")[0]}
                  </div>
                )}
              </TD>
              <TD className="text-sm">{j.nome_usuario ?? `#${j.id_usuario}`}</TD>
              <TD className="text-xs tabular-nums">{fmtDateTime(j.criado_em)}</TD>
              <TD className="text-xs tabular-nums">{fmtDateTime(j.concluido_em)}</TD>
              <TD className="text-right">
                {j.status === "concluido" && j.resultado_path && (
                  // Mesmo peso dos botões de linha das outras telas; <a> e não
                  // AcoesDaLinha porque o arquivo abre em outra aba.
                  <Button asChild variant="secondary" size="sm">
                    <a href={jobResultadoUrl(j.id)} target="_blank" rel="noreferrer">
                      <Download className="h-3.5 w-3.5" aria-hidden="true" />
                      Baixar
                    </a>
                  </Button>
                )}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function AgendadosTab() {
  const q = useQuery({
    queryKey: ["jobs-agenda"],
    queryFn: () => api.jobs.agenda(),
  });

  return (
    <div className="space-y-3">
      <p className="text-sm text-foreground-muted">
        Tarefas que o sistema dispara sozinho (Celery Beat), nos horários definidos.
      </p>
      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Tarefa</TH>
            <TH>Quando roda</TH>
            <TH>Argumentos</TH>
          </TR>
        </THead>
        <TBody>
          {q.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={4} />)}
          {!q.isLoading && (q.data?.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={4} className="p-0">
                <EmptyState
                  icon={CalendarClock}
                  title="Nenhuma tarefa agendada"
                  description="As tarefas periódicas configuradas no servidor aparecem aqui."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {q.data?.map((a) => (
            <TR key={a.nome}>
              <TD className="font-mono text-xs">{a.nome}</TD>
              <TD className="font-mono text-xs text-foreground-muted">{a.task}</TD>
              <TD className="font-mono text-xs">{a.schedule}</TD>
              <TD className="font-mono text-xs text-foreground-muted">
                {a.kwargs ? JSON.stringify(a.kwargs) : "—"}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
