"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, Route } from "lucide-react";
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

  // Seletor de operador — empresa e permissionário. Busca NO SERVIDOR com
  // debounce, mesmo padrão do seletor de ocupante da P6
  // (pontos/[id]/page.tsx): filtrar no cliente sobre a primeira página
  // repete o bug "só enxerga os 50 primeiros".
  const [buscaEmpresa, setBuscaEmpresa] = useState("");
  const [buscaEmpresaAplicada, setBuscaEmpresaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaEmpresaAplicada(buscaEmpresa.trim()), 300);
    return () => clearTimeout(t);
  }, [buscaEmpresa]);

  const [buscaPerm, setBuscaPerm] = useState("");
  const [buscaPermAplicada, setBuscaPermAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaPermAplicada(buscaPerm.trim()), 300);
    return () => clearTimeout(t);
  }, [buscaPerm]);

  const empresasQ = useQuery({
    queryKey: ["tr-empresas-busca", buscaEmpresaAplicada],
    queryFn: () => api.empresas.list({ q: buscaEmpresaAplicada || undefined }),
    enabled: dialogOpen,
  });
  const permsQ = useQuery({
    queryKey: ["tr-perms-busca", buscaPermAplicada],
    queryFn: () => api.permissionarios.list({ q: buscaPermAplicada || undefined }),
    enabled: dialogOpen,
  });

  // Nome do operador já selecionado — busca dedicada por id, independente
  // do texto de busca atual (ao editar, o selecionado pode não estar entre
  // os resultados da busca corrente).
  const empresaSelecionadaQ = useQuery({
    queryKey: ["tr-empresa-selecionada", form.id_empresa],
    queryFn: () => api.empresas.get(form.id_empresa as number),
    enabled: form.id_empresa !== null,
  });
  const permSelecionadoQ = useQuery({
    queryKey: ["tr-perm-selecionado", form.id_permissionario],
    queryFn: () => api.permissionarios.get(form.id_permissionario as number),
    enabled: form.id_permissionario !== null,
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-linhas"] });
  }

  const salvarM = useMutation({
    mutationFn: () =>
      editing
        ? api.linhasTransporte.update(editing.id, paraPayload(form))
        : api.linhasTransporte.create(paraPayload(form)),
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
    setErr(null);
    setBuscaEmpresa("");
    setBuscaEmpresaAplicada("");
    setBuscaPerm("");
    setBuscaPermAplicada("");
    setDialogOpen(true);
  }

  function abrirEdicao(l: LinhaTransporte) {
    setEditing(l);
    setForm(paraForm(l));
    setErr(null);
    setBuscaEmpresa("");
    setBuscaEmpresaAplicada("");
    setBuscaPerm("");
    setBuscaPermAplicada("");
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

  function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    // Ao menos um operador — o backend devolve 422 se nenhum vier, mas
    // orientar antes do round-trip é melhor.
    if (form.id_empresa === null && form.id_permissionario === null) {
      setErr("Informe ao menos um operador: empresa ou permissionário.");
      return;
    }
    salvarM.mutate();
  }

  const empresaSelecionadaNome = empresaSelecionadaQ.data
    ? empresaSelecionadaQ.data.nome_fantasia ?? empresaSelecionadaQ.data.razao_social
    : form.id_empresa !== null
      ? `Empresa #${form.id_empresa}`
      : null;
  const permSelecionadoNome = permSelecionadoQ.data
    ? permSelecionadoQ.data.nome
    : form.id_permissionario !== null
      ? `Permissionário #${form.id_permissionario}`
      : null;

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

      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="Buscar por nome ou código..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <Select
          value={tipoFiltro}
          onChange={(e) => setTipoFiltro(e.target.value)}
          className="max-w-[200px]"
        >
          <option value="">Todos os tipos</option>
          {TIPOS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
        <Select
          value={situacaoFiltro}
          onChange={(e) => setSituacaoFiltro(e.target.value)}
          className="max-w-[160px]"
        >
          <option value="">Todas</option>
          <option value="ativa">Ativas</option>
          <option value="inativa">Inativas</option>
        </Select>
      </div>

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={buscaAplicada ? "Nenhuma linha encontrada" : "Nenhuma linha cadastrada"}
          // Com busca ativa, NÃO oferecer "cadastrar": convidaria a duplicar
          // uma linha que existe e a busca não achou.
          description={
            buscaAplicada
              ? "Nenhuma linha corresponde à busca. Revise o termo."
              : "Cadastre as linhas de transporte regulado do município."
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
                    className="hover:underline"
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
                <TD className="space-x-2 text-right">
                  {canEdit && (
                    <Button variant="ghost" size="sm" onClick={() => abrirEdicao(l)}>
                      Editar
                    </Button>
                  )}
                  {canDelete && (
                    <Button variant="ghost" size="sm" onClick={() => pedirExclusao(l)}>
                      Excluir
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? "Editar linha" : "Nova linha"}
      >
        <form className="space-y-3" onSubmit={submeter}>
          {err && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {err}
            </div>
          )}
          <div>
            <Label htmlFor="nome">Nome</Label>
            <Input
              id="nome"
              required
              value={form.nome}
              onChange={(e) => set("nome", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="codigo">Código</Label>
              <Input
                id="codigo"
                value={form.codigo}
                onChange={(e) => set("codigo", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tipo">Tipo de serviço</Label>
              <Select
                id="tipo"
                value={form.tipo_servico}
                onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}
              >
                {TIPOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="origem">Origem</Label>
              <Input
                id="origem"
                required
                value={form.origem}
                onChange={(e) => set("origem", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="destino">Destino</Label>
              <Input
                id="destino"
                required
                value={form.destino}
                onChange={(e) => set("destino", e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="situacao">Situação</Label>
            <Select
              id="situacao"
              value={form.situacao}
              onChange={(e) => set("situacao", e.target.value as LinhaSituacao)}
            >
              <option value="ativa">Ativa</option>
              <option value="inativa">Inativa</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="buscaEmpresa">Empresa operadora</Label>
              {form.id_empresa !== null ? (
                <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                  <span className="truncate">{empresaSelecionadaNome}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      set("id_empresa", null);
                      setBuscaEmpresa("");
                      setBuscaEmpresaAplicada("");
                    }}
                  >
                    Limpar
                  </Button>
                </div>
              ) : (
                <>
                  <Input
                    id="buscaEmpresa"
                    placeholder="Buscar por razão social/CNPJ..."
                    value={buscaEmpresa}
                    onChange={(e) => setBuscaEmpresa(e.target.value)}
                  />
                  <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">
                    {empresasQ.isLoading ? (
                      <div className="p-2 text-xs text-muted-foreground">Carregando...</div>
                    ) : (empresasQ.data?.items ?? []).length === 0 ? (
                      <div className="p-2 text-xs text-muted-foreground">
                        Nenhuma empresa encontrada.
                      </div>
                    ) : (
                      (empresasQ.data?.items ?? []).map((emp) => (
                        <button
                          key={emp.id}
                          type="button"
                          className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                          onClick={() => set("id_empresa", emp.id)}
                        >
                          {emp.nome_fantasia ?? emp.razao_social}
                          <span className="ml-2 text-xs text-muted-foreground">{emp.cnpj}</span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
            <div>
              <Label htmlFor="buscaPerm">Permissionário operador</Label>
              {form.id_permissionario !== null ? (
                <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                  <span className="truncate">{permSelecionadoNome}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      set("id_permissionario", null);
                      setBuscaPerm("");
                      setBuscaPermAplicada("");
                    }}
                  >
                    Limpar
                  </Button>
                </div>
              ) : (
                <>
                  <Input
                    id="buscaPerm"
                    placeholder="Buscar por nome/CPF..."
                    value={buscaPerm}
                    onChange={(e) => setBuscaPerm(e.target.value)}
                  />
                  <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">
                    {permsQ.isLoading ? (
                      <div className="p-2 text-xs text-muted-foreground">Carregando...</div>
                    ) : (permsQ.data?.items ?? []).length === 0 ? (
                      <div className="p-2 text-xs text-muted-foreground">
                        Nenhum permissionário encontrado.
                      </div>
                    ) : (
                      (permsQ.data?.items ?? []).map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                          onClick={() => set("id_permissionario", p.id)}
                        >
                          {p.nome}
                          <span className="ml-2 text-xs text-muted-foreground">{p.cpf}</span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Informe ao menos um operador: empresa, permissionário, ou os dois.
          </p>
          <div>
            <Label htmlFor="obs">Observações</Label>
            <Input
              id="obs"
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setDialogOpen(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={salvarM.isPending}>
              {salvarM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
