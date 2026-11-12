"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardList,
  Inbox,
  Pencil,
  Plus,
  RefreshCw,
  SearchX,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import {
  dataBR,
  diasEntre,
  duracaoLegivel,
  GrupoCampos,
  somarDias,
  useValidacao,
} from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR, TRLink } from "@/components/ui/table";
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

const DESCRICAO_SITUACAO: Record<CicloSituacao, string> = {
  rascunho: "Em preparação.",
  aberto: "Em andamento.",
  encerrado: "Não gera convocações nem aceita ajuste de prazo.",
};

const FAIXAS = 10;

/**
 * Prazo de cada final de documento (0 a 9), na forma `dd/mm` (ou
 * `dd/mm/aaaa` quando a janela atravessa o ano). Espelha
 * `prazo_do_regulado` do backend: o prazo é o FIM da faixa. `null` quando
 * não há o que mostrar (sem escalonamento ou janela incompleta).
 */
function faixasDoCiclo(f: CicloForm): string[] | null {
  if (f.criterio_escalonamento !== "final_documento") return null;
  if (!f.data_inicio || !f.data_fim || f.data_fim < f.data_inicio) return null;
  const total = diasEntre(f.data_inicio, f.data_fim);
  if (total === null) return null;
  const mesmoAno = f.data_inicio.slice(0, 4) === f.data_fim.slice(0, 4);
  return Array.from({ length: FAIXAS }, (_, faixa) => {
    const dias = Math.floor(((faixa + 1) * total) / FAIXAS);
    const prazo = dataBR(somarDias(f.data_inicio, dias));
    return mesmoAno ? prazo.slice(0, 5) : prazo;
  });
}

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
    val.reiniciar();
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
    val.reiniciar();
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  // Mesmas regras do backend (`RecadastramentoCicloCreate`), no campo.
  const val = useValidacao<"nome" | "data_inicio" | "data_fim">({
    nome: form.nome.trim() === "" ? "Informe o nome do ciclo." : undefined,
    data_inicio: form.data_inicio === "" ? "Informe o início da janela." : undefined,
    data_fim:
      form.data_fim === ""
        ? "Informe o fim da janela."
        : form.data_inicio && form.data_fim < form.data_inicio
          ? "O fim não pode ser antes do início. Confira o ano."
          : undefined,
  });

  // A consequência do escalonamento, antes de gerar: o prazo de cada final
  // de documento. Mesma conta de `prazo_do_regulado` no backend.
  const faixas = faixasDoCiclo(form);

  function submit() {
    setErr(null);
    if (!val.conferir()) return;
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
  const filtrando = buscando || situacaoFiltro !== "";

  function limparFiltros() {
    setSituacaoFiltro("");
    setBusca("");
  }

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
          <>
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
          </>
        }
      />

      <FilterBar ariaLabel="Filtros dos ciclos">
        <FilterBar.Group label="Situação" className="w-full sm:w-44">
          <Select
            id="f_sit"
            aria-label="Situação"
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
        </FilterBar.Group>
        <FilterBar.Group label="Busca por nome" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca por nome"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Recadastramento 2026..."
          />
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {listaQ.isLoading ? (
        <Carregando className="text-center text-muted-foreground py-8" />
      ) : ciclos.length === 0 ? (
        // Dois estados distintos: "não existe ciclo" convida a criar; "a busca
        // não achou" NÃO — o município pode ter vários, e o botão convidaria a
        // duplicar um que já existe.
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhum ciclo encontrado" : "Nenhum ciclo de recadastramento"}
          description={
            buscando
              ? `Nada corresponde a "${buscaAplicada}". A busca cobre todos os ciclos do município, não só os desta página.`
              : filtrando
                ? "Nenhum ciclo nesta situação."
                : "Crie o primeiro ciclo para convocar os regulados ativos."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
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
              <TRLink key={c.id} href={`/m/transporte/recadastramento/${c.id}`}>
                <TD className="font-medium">
                  <Link
                    href={`/m/transporte/recadastramento/${c.id}`}
                    className="text-primary hover:underline"
                  >
                    {c.nome}
                  </Link>
                </TD>
                <TD className="whitespace-nowrap text-sm tabular-nums">
                  {fmtData(c.data_inicio)} a {fmtData(c.data_fim)}
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
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Convocados",
                        icon: Users,
                        href: `/m/transporte/recadastramento/${c.id}`,
                      },
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(c), oculta: !canEdit },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        oculta: !canDelete,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir ciclo",
                            message: `Excluir o ciclo "${c.nome}"? As convocações permanecem registradas.`,
                          });
                          if (ok) deleteM.mutate(c.id);
                        },
                      },
                    ]}
                  />
                </TD>
              </TRLink>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar ciclo — ${editing.nome}` : "Novo ciclo de recadastramento"}
        description={
          editing ? undefined : "O ciclo nasce como rascunho. As convocações se geram depois, na tela do ciclo."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Criar ciclo"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <FormField label="Nome" required error={val.erro("nome")}>
            <Input
              id="c_nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              onBlur={val.sair("nome")}
              placeholder="Ex.: Recadastramento 2026"
            />
          </FormField>

          <GrupoCampos titulo="Janela" descricao="O período em que os regulados devem se recadastrar.">
            <GradeCampos>
              <FormField label="Início" required error={val.erro("data_inicio")}>
                <Input
                  id="c_ini"
                  type="date"
                  value={form.data_inicio}
                  onChange={(e) => setForm({ ...form, data_inicio: e.target.value })}
                  onBlur={val.sair("data_inicio")}
                />
              </FormField>
              <FormField
                label="Fim"
                required
                error={val.erro("data_fim")}
                hint={
                  form.data_inicio && form.data_fim && form.data_fim >= form.data_inicio
                    ? `Janela de ${duracaoLegivel(form.data_inicio, form.data_fim)}.`
                    : "Último dia para se recadastrar."
                }
              >
                <Input
                  id="c_fim"
                  type="date"
                  value={form.data_fim}
                  onChange={(e) => setForm({ ...form, data_fim: e.target.value })}
                  onBlur={val.sair("data_fim")}
                />
              </FormField>
            </GradeCampos>

            <EscolhaSegmentada<CriterioEscalonamento>
              nome="c_crit"
              titulo="Prazo de cada regulado"
              valor={form.criterio_escalonamento}
              onChange={(c) => setForm({ ...form, criterio_escalonamento: c })}
              opcoes={[
                {
                  valor: "final_documento",
                  rotulo: "Pelo final do CPF/CNPJ",
                  descricao:
                    "A janela é dividida em dez faixas; o último dígito do documento escolhe a faixa, e o prazo é o fim dela.",
                },
                {
                  valor: "sem_escalonamento",
                  rotulo: "Todos no fim",
                  descricao: "Todos têm até o último dia da janela.",
                },
              ]}
            />
            {faixas && (
              <div className="rounded-lg border border-border bg-surface-1 p-3">
                <p className="mb-2 text-xs font-medium text-foreground">Prazo por final do documento</p>
                <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-5">
                  {faixas.map((prazo, final) => (
                    <li key={final} className="flex items-baseline justify-between gap-2 tabular-nums">
                      <span className="text-foreground-muted">Final {final}</span>
                      <span className="text-foreground">{prazo}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {editing && (
              <p className="text-xs text-foreground-muted">
                Mudar a janela depois de gerar <strong>não</strong> remarca quem já foi convocado — o prazo
                comunicado permanece.
              </p>
            )}
          </GrupoCampos>

          {editing && (
            <GrupoCampos titulo="Situação">
              <EscolhaSegmentada<CicloSituacao>
                nome="c_sit"
                titulo="Situação do ciclo"
                moldura={false}
                valor={form.situacao}
                onChange={(s) => setForm({ ...form, situacao: s })}
                opcoes={SITUACOES.map((s) => ({
                  valor: s.value,
                  rotulo: s.label,
                  descricao: DESCRICAO_SITUACAO[s.value],
                }))}
              />
            </GrupoCampos>
          )}

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Textarea
                id="c_obs"
                value={form.observacoes}
                onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
                placeholder="Ex.: decreto municipal nº 123/2026"
                rows={3}
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
