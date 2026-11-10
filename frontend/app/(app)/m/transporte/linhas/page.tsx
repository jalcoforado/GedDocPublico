"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Pencil, Plus, Route, SearchX, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { modoDoVinculo, type ModoVinculo } from "@/components/transporte/campo-vinculo";
import { CamposLinha, comOperador, errosDaLinha, type CampoLinha } from "@/components/transporte/campos-linha";
import { useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type LinhaSituacao,
  type LinhaTransporte,
  type LinhaTransporteCreate,
  type TipoServico,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

// O formulário sugere só estes três — o banco não impõe (não há CHECK), mas
// não faz sentido oferecer táxi/mototáxi/motofrete/aplicativo para uma linha.
const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "outro", label: "Outro" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS.map((t) => [t.value, t.label]),
);

interface LinhaForm {
  nome: string;
  codigo: string;
  tipo_servico: TipoServico;
  origem: string;
  destino: string;
  situacao: LinhaSituacao;
  observacoes: string;
  id_empresa: number | null;
  id_permissionario: number | null;
}

const EMPTY: LinhaForm = {
  nome: "",
  codigo: "",
  tipo_servico: "transporte_distrital",
  origem: "",
  destino: "",
  situacao: "ativa",
  observacoes: "",
  id_empresa: null,
  id_permissionario: null,
};

/** `""` vira `null` — o backend distingue "não informado" de string vazia. */
function limpo(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function paraPayload(f: LinhaForm): LinhaTransporteCreate {
  return {
    nome: f.nome.trim(),
    codigo: limpo(f.codigo),
    tipo_servico: f.tipo_servico,
    origem: f.origem.trim(),
    destino: f.destino.trim(),
    situacao: f.situacao,
    observacoes: limpo(f.observacoes),
    id_empresa: f.id_empresa,
    id_permissionario: f.id_permissionario,
  };
}

function paraForm(l: LinhaTransporte): LinhaForm {
  return {
    nome: l.nome,
    codigo: l.codigo ?? "",
    tipo_servico: l.tipo_servico,
    origem: l.origem,
    destino: l.destino,
    situacao: l.situacao,
    observacoes: l.observacoes ?? "",
    id_empresa: l.id_empresa,
    id_permissionario: l.id_permissionario,
  };
}

export default function LinhasPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [busca, setBusca] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<LinhaTransporte | null>(null);
  const [form, setForm] = useState<LinhaForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [modoOperador, setModoOperador] = useState<ModoVinculo>("empresa");

  // Busca NO SERVIDOR, com debounce. Filtrar no cliente sobre a página
  // truncada faz a tela afirmar que uma linha não existe.
  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const q = useQuery({
    queryKey: ["tr-linhas", buscaAplicada, tipoFiltro, situacaoFiltro],
    queryFn: () =>
      api.linhasTransporte.list({
        q: buscaAplicada || undefined,
        tipo_servico: tipoFiltro || undefined,
        situacao: situacaoFiltro || undefined,
      }),
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-linhas"] });
  }

  const salvarM = useMutation({
    mutationFn: () =>
      editing
        ? api.linhasTransporte.update(editing.id, paraPayload(comOperador(form, modoOperador)))
        : api.linhasTransporte.create(paraPayload(comOperador(form, modoOperador))),
    onSuccess: () => {
      toast.success(editing ? "Linha atualizada." : "Linha criada.");
      setDialogOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const excluirM = useMutation({
    mutationFn: (id: number) => api.linhasTransporte.remove(id),
    onSuccess: () => {
      toast.success("Linha excluída.");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function abrirNovo() {
    setEditing(null);
    setForm(EMPTY);
    setModoOperador("empresa");
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }

  function abrirEdicao(l: LinhaTransporte) {
    setEditing(l);
    setForm(paraForm(l));
    setModoOperador(modoDoVinculo(String(l.id_permissionario ?? ""), String(l.id_empresa ?? "")));
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }

  async function pedirExclusao(l: LinhaTransporte) {
    const ok = await confirm({
      title: `Excluir "${l.nome}"?`,
      message: "A linha sai das listagens, junto com seu itinerário e horários.",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) excluirM.mutate(l.id);
  }

  const itens = q.data?.items ?? [];

  function set<K extends keyof LinhaForm>(k: K, v: LinhaForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  // Ao menos um operador — o backend devolve 422 se nenhum vier; a escolha
  // "operada por" diz qual campo falta antes do round-trip.
  const val = useValidacao<CampoLinha>(errosDaLinha(form, modoOperador));

  function submeter() {
    setErr(null);
    if (!val.conferir()) return;
    salvarM.mutate();
  }

  const filtrando = buscaAplicada !== "" || tipoFiltro !== "" || situacaoFiltro !== "";

  function limparFiltros() {
    setBusca("");
    setTipoFiltro("");
    setSituacaoFiltro("");
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Route}
        title="Linhas e Itinerários"
        description="Linhas de transporte regulado, com trajeto, paradas e grade de horários."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Linhas" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={abrirNovo}>
              <Plus className="mr-1 h-4 w-4" />
              Nova linha
            </Button>
          ) : undefined
        }
      />

      <FilterBar ariaLabel="Filtros das linhas">
        <FilterBar.Group label="Busca" className="w-full sm:w-72">
          <Input
            aria-label="Buscar por nome ou código"
            placeholder="Buscar por nome ou código..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </FilterBar.Group>
        <FilterBar.Group label="Tipo de serviço" className="w-full sm:w-56">
          <Select
            aria-label="Tipo de serviço"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value)}
          >
            <option value="">Todos os tipos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Situação" className="w-full sm:w-40">
          <Select
            aria-label="Situação"
            value={situacaoFiltro}
            onChange={(e) => setSituacaoFiltro(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="ativa">Ativas</option>
            <option value="inativa">Inativas</option>
          </Select>
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {q.isLoading ? (
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : itens.length === 0 ? (
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhuma linha encontrada" : "Nenhuma linha cadastrada"}
          // Com busca ativa, NÃO oferecer "cadastrar": convidaria a duplicar
          // uma linha que existe e a busca não achou.
          description={
            filtrando
              ? "Nenhuma linha corresponde à busca ou aos filtros. Revise o termo."
              : "Cadastre as linhas de transporte regulado do município."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar linha
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Linha</TH>
              <TH>Trajeto</TH>
              <TH>Tipo</TH>
              <TH>Operador</TH>
              <TH>Horários/semana</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((l) => (
              <TR key={l.id}>
                <TD className="font-medium">
                  <Link
                    href={`/m/transporte/linhas/${l.id}`}
                    className="text-primary hover:underline"
                  >
                    {l.nome}
                  </Link>
                  {l.codigo && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {l.codigo}
                    </span>
                  )}
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {l.origem} → {l.destino}
                </TD>
                <TD className="text-sm">
                  {TIPO_LABEL[l.tipo_servico] ?? l.tipo_servico}
                </TD>
                <TD className="text-sm">{l.operador_nome ?? "—"}</TD>
                <TD className="text-sm">{l.total_horarios}</TD>
                <TD>
                  <Badge intent={l.situacao === "ativa" ? "success" : "neutral"}>
                    {l.situacao === "ativa" ? "Ativa" : "Inativa"}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Editar",
                        icon: Pencil,
                        onClick: () => abrirEdicao(l),
                        oculta: !canEdit,
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        onClick: () => pedirExclusao(l),
                        oculta: !canDelete,
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? `Editar linha — ${editing.nome}` : "Nova linha"}
        description={
          editing ? undefined : "O trajeto e quem opera. Paradas e horários se cadastram depois, na tela da linha."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeter} loading={salvarM.isPending}>
              {editing ? "Salvar alterações" : "Criar linha"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <CamposLinha
            form={form}
            set={set}
            tipos={TIPOS}
            modoOperador={modoOperador}
            onModoOperador={setModoOperador}
            ativo={dialogOpen}
            erro={val.erro}
            sair={val.sair}
          />

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
