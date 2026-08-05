"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Inbox, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type CicloSituacao,
  type CriterioEscalonamento,
  type RecadastramentoCiclo,
  type RecadastramentoCicloInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const CRITERIOS: { value: CriterioEscalonamento; label: string }[] = [
  { value: "final_documento", label: "Final do CPF/CNPJ (dez faixas)" },
  { value: "sem_escalonamento", label: "Sem escalonamento (todos no fim)" },
];
const CRITERIO_LABEL: Record<string, string> = Object.fromEntries(
  CRITERIOS.map((c) => [c.value, c.label]),
);

const SITUACOES: { value: CicloSituacao; label: string }[] = [
  { value: "rascunho", label: "Rascunho" },
  { value: "aberto", label: "Aberto" },
  { value: "encerrado", label: "Encerrado" },
];
const SITUACAO_INTENT: Record<string, "neutral" | "success" | "info"> = {
  rascunho: "neutral",
  aberto: "success",
  encerrado: "info",
};

interface CicloForm {
  nome: string;
  data_inicio: string;
  data_fim: string;
  criterio_escalonamento: CriterioEscalonamento;
  situacao: CicloSituacao;
  observacoes: string;
}

const EMPTY: CicloForm = {
  nome: "",
  data_inicio: "",
  data_fim: "",
  criterio_escalonamento: "final_documento",
  situacao: "rascunho",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function RecadastramentoPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<RecadastramentoCiclo | null>(null);
  const [form, setForm] = useState<CicloForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  // O termo vai para o SERVIDOR, então sem debounce seria uma consulta por
  // tecla digitada.
  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const listaQ = useQuery({
    queryKey: ["tr-recad-ciclos", situacaoFiltro, buscaAplicada],
    queryFn: () =>
      api.recadastramento.ciclos.list({
        situacao: situacaoFiltro || undefined,
        // Busca no servidor: filtrar `items` aqui faria a tela dizer que um
        // ciclo não existe só porque ficou fora da página corrente.
        q: buscaAplicada || undefined,
      }),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tr-recad-ciclos"] });
  };

  const saveM = useMutation({
    mutationFn: (data: RecadastramentoCicloInput & { situacao?: CicloSituacao }) =>
      editing
        ? api.recadastramento.ciclos.update(editing.id, data)
        : api.recadastramento.ciclos.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Ciclo atualizado." : "Ciclo criado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => api.recadastramento.ciclos.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Ciclo excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(c: RecadastramentoCiclo) {
    setEditing(c);
    setForm({
      nome: c.nome,
      data_inicio: c.data_inicio,
      data_fim: c.data_fim,
      criterio_escalonamento: c.criterio_escalonamento as CriterioEscalonamento,
      situacao: c.situacao as CicloSituacao,
      observacoes: c.observacoes ?? "",
    });
    setErr(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function submit() {
    setErr(null);
    if (form.nome.trim() === "") {
      setErr("Nome do ciclo é obrigatório.");
      return;
    }
    if (!form.data_inicio || !form.data_fim) {
      setErr("Informe o início e o fim da janela.");
      return;
    }
    if (form.data_inicio > form.data_fim) {
      setErr("Data de início não pode ser posterior à data de fim.");
      return;
    }
    const payload = {
      nome: form.nome.trim(),
      data_inicio: form.data_inicio,
      data_fim: form.data_fim,
      criterio_escalonamento: form.criterio_escalonamento,
      observacoes: nullify(form.observacoes),
      // A situação só vai na EDIÇÃO: ciclo nasce em rascunho por decisão do
      // serviço, e mandá-la na criação seria o cliente ditando estado.
      ...(editing ? { situacao: form.situacao } : {}),
    };
    saveM.mutate(payload);
  }

  const ciclos = listaQ.data?.items ?? [];
  const buscando = buscaAplicada.length > 0;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={RefreshCw}
        title="Recadastramento"
        description="Campanhas de recadastramento: quem tem de comparecer e até quando."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Recadastramento" },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" asChild>
              <Link href="/m/transporte/recadastramento/itens">
                <ClipboardList className="mr-1 h-4 w-4" />
                Itens exigidos
              </Link>
            </Button>
            {canCreate && (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Novo ciclo
              </Button>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_sit">Situação</Label>
          <Select
            id="f_sit"
            value={situacaoFiltro}
            onChange={(e) => setSituacaoFiltro(e.target.value)}
          >
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="f_q">Busca por nome</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Recadastramento 2026..."
          />
        </div>
      </div>

      {listaQ.isLoading ? (
        <div className="text-center text-muted-foreground py-8">Carregando...</div>
      ) : ciclos.length === 0 ? (
        // Dois estados distintos: "não existe ciclo" convida a criar; "a busca
        // não achou" NÃO — o município pode ter vários, e o botão convidaria a
        // duplicar um que já existe.
        <EmptyState
          icon={Inbox}
          title={buscando ? "Nenhum ciclo encontrado" : "Nenhum ciclo de recadastramento"}
          description={
            buscando
              ? `Nada corresponde a "${buscaAplicada}". A busca cobre todos os ciclos do município, não só os desta página.`
              : "Crie o primeiro ciclo para convocar os regulados ativos."
          }
          action={
            !buscando && canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Criar ciclo
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nome</TH>
              <TH>Janela</TH>
              <TH>Escalonamento</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {ciclos.map((c) => (
              <TR key={c.id}>
                <TD className="font-medium">
                  <Link
                    href={`/m/transporte/recadastramento/${c.id}`}
                    className="text-primary hover:underline"
                  >
                    {c.nome}
                  </Link>
                </TD>
                <TD className="text-sm">
                  {c.data_inicio} — {c.data_fim}
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {CRITERIO_LABEL[c.criterio_escalonamento] ?? c.criterio_escalonamento}
                </TD>
                <TD>
                  <Badge intent={SITUACAO_INTENT[c.situacao] ?? "neutral"}>
                    {SITUACOES.find((s) => s.value === c.situacao)?.label ?? c.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    <Button variant="secondary" size="sm" asChild>
                      <Link href={`/m/transporte/recadastramento/${c.id}`}>Convocados</Link>
                    </Button>
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(c)}>
                        Editar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir ciclo",
                            message: `Excluir o ciclo "${c.nome}"? As convocações permanecem registradas.`,
                          });
                          if (ok) deleteM.mutate(c.id);
                        }}
                      >
                        Excluir
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar ciclo" : "Novo ciclo de recadastramento"}
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {err && <div className="text-sm text-danger">{err}</div>}
          <div>
            <Label htmlFor="c_nome">Nome</Label>
            <Input
              id="c_nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              placeholder="Recadastramento 2026"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="c_ini">Início</Label>
              <Input
                id="c_ini"
                type="date"
                value={form.data_inicio}
                onChange={(e) => setForm({ ...form, data_inicio: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="c_fim">Fim</Label>
              <Input
                id="c_fim"
                type="date"
                value={form.data_fim}
                onChange={(e) => setForm({ ...form, data_fim: e.target.value })}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="c_crit">Escalonamento</Label>
            <Select
              id="c_crit"
              value={form.criterio_escalonamento}
              onChange={(e) =>
                setForm({
                  ...form,
                  criterio_escalonamento: e.target.value as CriterioEscalonamento,
                })
              }
            >
              {CRITERIOS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              Mudar a janela depois de gerar <strong>não</strong> remarca quem já foi
              convocado — o prazo comunicado permanece.
            </p>
          </div>
          {editing && (
            <div>
              <Label htmlFor="c_sit">Situação</Label>
              <Select
                id="c_sit"
                value={form.situacao}
                onChange={(e) =>
                  setForm({ ...form, situacao: e.target.value as CicloSituacao })
                }
              >
                {SITUACOES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-muted-foreground">
                Ciclo encerrado não gera convocações nem aceita ajuste de prazo.
              </p>
            </div>
          )}
          <div>
            <Label htmlFor="c_obs">Observações</Label>
            <Textarea
              id="c_obs"
              value={form.observacoes}
              onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
              rows={3}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
