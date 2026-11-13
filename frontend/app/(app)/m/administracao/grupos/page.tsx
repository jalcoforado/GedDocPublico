"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Search, Shield, ShieldAlert } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Grupo, type GrupoTransacao, type Nivel, type Transacao } from "@/lib/api";
import { MENUS } from "@/lib/menus";
import type { NavItem } from "@/lib/menus";
import { nomeDoModulo } from "@/lib/modulos";
import { cn } from "@/lib/utils";

type FormState = Omit<Grupo, "id">;
type Acao = "inserir" | "atualizar" | "excluir";

const VAZIO: FormState = { grupo: "", id_nivel: 0, id_sistema: 0 };

const ACOES: { campo: Acao; rotulo: string }[] = [
  { campo: "inserir", rotulo: "Incluir" },
  { campo: "atualizar", rotulo: "Alterar" },
  { campo: "excluir", rotulo: "Excluir" },
];

/** A lista de áreas ganha uma busca a partir deste tamanho. */
const TRANSACOES_COM_BUSCA = 10;

/** Ordem dos módulos na matriz — a mesma do seletor de módulos. */
const ORDEM_MODULOS = ["protocolo", "pagamentos", "frota", "transporte", "administracao"];

/**
 * Transações que nenhum item de menu declara, mas que são claramente de um
 * módulo (Configurações usa a permissão `usuario` no menu, e a gravação
 * exige `configuracao`).
 */
const MODULO_EXTRA: Record<string, string> = {
  configuracao: "administracao",
  auditoria: "administracao",
};

const GERAL = "geral";

/**
 * Transação → módulo, lido dos próprios menus (`lib/menus`): cada item
 * declara a permissão que exige. Assim a matriz se agrupa como o sistema se
 * apresenta, sem uma segunda tabela para manter.
 */
function moduloPorTransacao(): Map<string, string> {
  const mapa = new Map<string, string>(Object.entries(MODULO_EXTRA));
  function visitar(itens: NavItem[], slug: string) {
    for (const it of itens) {
      for (const c of [it.perm, ...(it.anyOf ?? [])]) {
        if (c && !mapa.has(c)) mapa.set(c, slug);
      }
      if (it.children) visitar(it.children, slug);
    }
  }
  for (const slug of ORDEM_MODULOS) {
    const menu = MENUS[slug];
    if (menu) for (const g of menu.grupos) visitar(g.items, slug);
  }
  return mapa;
}

function nomeDoGrupoDeModulo(slug: string): string {
  return slug === GERAL ? "Geral" : nomeDoModulo(slug);
}

/** Minúsculas e sem acento: "saude" acha "Saúde". */
function semAcento(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Nível com valor 0 é super-usuário: passa por cima de toda permissão. */
function eSuperUsuario(nivel: Nivel | undefined): boolean {
  return nivel?.valor === 0;
}

export default function GruposPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Grupo | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(VAZIO);
  const [permsState, setPermsState] = useState<Record<number, GrupoTransacao>>({});
  // Grupo cujas permissões já foram copiadas para `permsState`. Antes a
  // condição era "permsState vazio" — e um grupo sem nenhuma permissão
  // regravava `{}` a cada render, sem parar.
  const [carregadoPara, setCarregadoPara] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tocados, setTocados] = useState<Set<keyof FormState>>(new Set());
  const [tentouCriar, setTentouCriar] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const gruposQ = useQuery({ queryKey: ["grupos"], queryFn: api.grupos.list });
  const niveisQ = useQuery({ queryKey: ["niveis"], queryFn: api.niveis });
  const sistemasQ = useQuery({ queryKey: ["sistemas"], queryFn: api.sistemas });
  const transacoesQ = useQuery({ queryKey: ["transacoes"], queryFn: api.transacoes });

  const groupPermsQ = useQuery({
    enabled: !!editing,
    queryKey: ["grupo-transacoes", editing?.id],
    queryFn: () => api.grupos.transacoes(editing!.id),
  });

  const createM = useMutation({
    mutationFn: (d: FormState) => api.grupos.create(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grupos"] });
      toast.success("Grupo criado.");
      fecharCriar();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const setPermsM = useMutation({
    mutationFn: (transacoes: GrupoTransacao[]) =>
      api.grupos.setTransacoes(editing!.id, transacoes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grupo-transacoes", editing?.id] });
      toast.success("Permissões atualizadas.");
      closePerms();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Copia as permissões do servidor para o estado editável, uma vez por grupo.
  if (editing && groupPermsQ.data && carregadoPara !== editing.id) {
    const initial: Record<number, GrupoTransacao> = {};
    for (const gt of groupPermsQ.data) initial[gt.id_transacao] = gt;
    setPermsState(initial);
    setCarregadoPara(editing.id);
  }

  // ----- Novo grupo -----------------------------------------------------------

  const erros: Partial<Record<keyof FormState, string>> = {};
  if (!form.grupo.trim()) erros.grupo = "Dê um nome ao grupo.";
  if (!form.id_nivel) erros.id_nivel = "Escolha o nível.";
  if (!form.id_sistema) erros.id_sistema = "Escolha o sistema.";
  const erroVisivel = (c: keyof FormState) =>
    tentouCriar || tocados.has(c) ? erros[c] : undefined;
  const tocar = (c: keyof FormState) => () =>
    setTocados((s) => (s.has(c) ? s : new Set(s).add(c)));

  function abrirCriar() {
    // Com um sistema só, não há o que escolher: já vem marcado.
    const sistemas = sistemasQ.data ?? [];
    setForm({ ...VAZIO, id_sistema: sistemas.length === 1 ? sistemas[0].id : 0 });
    setErr(null);
    setTocados(new Set());
    setTentouCriar(false);
    setCreating(true);
  }

  function fecharCriar() {
    setCreating(false);
    setForm(VAZIO);
  }

  function criar(e?: React.FormEvent) {
    e?.preventDefault();
    setErr(null);
    if (Object.keys(erros).length > 0) {
      flushSync(() => setTentouCriar(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
    createM.mutate({ ...form, grupo: form.grupo.trim() });
  }

  const nivelEscolhido = niveisQ.data?.find((n) => n.id === form.id_nivel);
  const sistemaUnico = (sistemasQ.data?.length ?? 0) === 1;

  // ----- Permissões -----------------------------------------------------------

  function openEdit(g: Grupo) {
    setPermsState({});
    setCarregadoPara(null);
    setEditing(g);
  }

  function togglePerm(transId: number, field: Acao, value: boolean) {
    setPermsState((s) => {
      const current = s[transId] ?? {
        id_transacao: transId,
        inserir: false,
        atualizar: false,
        excluir: false,
      };
      return { ...s, [transId]: { ...current, [field]: value } };
    });
  }

  function saveGroupPerms() {
    const list: GrupoTransacao[] = (transacoesQ.data ?? [])
      .map((t) => permsState[t.id])
      .filter((x): x is GrupoTransacao => !!x && (x.inserir || x.atualizar || x.excluir));
    setPermsM.mutate(list);
  }

  function closePerms() {
    setEditing(null);
    setPermsState({});
    setCarregadoPara(null);
  }

  const nivelDoEditado = niveisQ.data?.find((n) => n.id === editing?.id_nivel);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Shield}
        title="Grupos & Permissões"
        description="Perfis de acesso: o que cada grupo pode incluir, alterar e excluir em cada área do sistema."
        actions={
          <Button onClick={abrirCriar}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo grupo
          </Button>
        }
      />

      <Table>
        <THead>
          <TR>
            <TH>Grupo</TH>
            <TH>Nível</TH>
            <TH>Sistema</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {gruposQ.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={4} />)}
          {!gruposQ.isLoading && gruposQ.data?.length === 0 && (
            <TR>
              <TD colSpan={4} className="p-0">
                <EmptyState
                  icon={Shield}
                  title="Nenhum grupo cadastrado"
                  description="Use “Novo grupo” para criar o primeiro perfil de acesso."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {gruposQ.data?.map((g) => {
            const nivel = niveisQ.data?.find((n) => n.id === g.id_nivel);
            return (
              <TR key={g.id}>
                <TD className="font-medium">{g.grupo}</TD>
                <TD>
                  <span className="inline-flex items-center gap-2">
                    {nivel?.nivel ?? g.id_nivel}
                    {eSuperUsuario(nivel) && <Badge intent="warning">Super-usuário</Badge>}
                  </span>
                </TD>
                <TD>{sistemasQ.data?.find((s) => s.id === g.id_sistema)?.sistema ?? g.id_sistema}</TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[{ label: "Permissões", icon: KeyRound, onClick: () => openEdit(g) }]}
                  />
                </TD>
              </TR>
            );
          })}
        </TBody>
      </Table>

      <Dialog
        open={creating}
        onClose={fecharCriar}
        title="Novo grupo"
        description="Um perfil de acesso. Depois de criar, marque as permissões dele."
        footer={
          <>
            <Button variant="ghost" onClick={fecharCriar}>
              Cancelar
            </Button>
            <Button onClick={() => criar()} loading={createM.isPending}>
              {createM.isPending ? "Criando…" : "Criar grupo"}
            </Button>
          </>
        }
      >
        <form ref={formRef} onSubmit={criar} noValidate className="space-y-4">
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
          <FormField label="Nome do grupo" required error={erroVisivel("grupo")}>
            <Input
              value={form.grupo}
              onChange={(e) => setForm({ ...form, grupo: e.target.value })}
              onBlur={tocar("grupo")}
              placeholder="Ex.: Protocolo — atendimento"
              autoFocus
            />
          </FormField>
          <FormField
            label="Nível"
            required
            error={erroVisivel("id_nivel")}
            hint={
              eSuperUsuario(nivelEscolhido) ? (
                <span className="font-medium text-warning-soft-foreground">
                  Nível de super-usuário: quem estiver neste grupo passa por cima de todas as
                  permissões.
                </span>
              ) : undefined
            }
          >
            <Select
              value={form.id_nivel || ""}
              onChange={(e) => setForm({ ...form, id_nivel: Number(e.target.value) })}
              onBlur={tocar("id_nivel")}
            >
              <option value="">Escolha o nível…</option>
              {niveisQ.data?.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.nivel}
                  {eSuperUsuario(n) ? " (super-usuário)" : ""}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField
            label="Sistema"
            required
            error={erroVisivel("id_sistema")}
            hint={sistemaUnico ? "Só há um sistema cadastrado; já vem escolhido." : undefined}
          >
            <Select
              value={form.id_sistema || ""}
              onChange={(e) => setForm({ ...form, id_sistema: Number(e.target.value) })}
              onBlur={tocar("id_sistema")}
            >
              <option value="">Escolha o sistema…</option>
              {sistemasQ.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.sistema} {s.app ? `(${s.app})` : ""}
                </option>
              ))}
            </Select>
          </FormField>
        </form>
      </Dialog>

      <Dialog
        open={!!editing}
        onClose={closePerms}
        title="Permissões do grupo"
        description={
          editing
            ? `${editing.grupo} — marque o que o grupo pode fazer em cada área. Área sem nenhuma marcação fica sem acesso.`
            : undefined
        }
        size="xl"
        footer={
          <>
            <Button variant="ghost" onClick={closePerms}>
              Cancelar
            </Button>
            <Button onClick={saveGroupPerms} loading={setPermsM.isPending}>
              {setPermsM.isPending ? "Salvando…" : "Salvar permissões"}
            </Button>
          </>
        }
      >
        {eSuperUsuario(nivelDoEditado) && (
          <div className="mb-4 flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            Este grupo é de super-usuário: quem está nele já pode tudo, com ou sem as marcações
            abaixo.
          </div>
        )}
        {groupPermsQ.isError ? (
          <p role="alert" className="text-sm text-danger-soft-foreground">
            Não foi possível carregar as permissões deste grupo. Feche e tente de novo.
          </p>
        ) : groupPermsQ.isLoading || carregadoPara !== editing?.id ? (
          <p className="text-sm text-foreground-muted">Carregando permissões…</p>
        ) : (
          <MatrizPermissoes
            transacoes={transacoesQ.data ?? []}
            perms={permsState}
            onAlternar={togglePerm}
          />
        )}
      </Dialog>
    </div>
  );
}

/**
 * Matriz área × ação, agrupada por módulo. Cada célula é uma pílula que diz
 * a ação por extenso e muda de cor quando liberada — dá para varrer a
 * coluna e ver o que o grupo pode, sem decifrar caixinhas soltas.
 */
function MatrizPermissoes({
  transacoes,
  perms,
  onAlternar,
}: {
  transacoes: Transacao[];
  perms: Record<number, GrupoTransacao>;
  onAlternar: (id: number, acao: Acao, valor: boolean) => void;
}) {
  const [busca, setBusca] = useState("");
  const modulos = useMemo(() => moduloPorTransacao(), []);

  const termo = semAcento(busca.trim());
  const secoes = useMemo(() => {
    const porModulo = new Map<string, Transacao[]>();
    for (const t of transacoes) {
      if (termo && !semAcento(`${t.transacao} ${t.codigo}`).includes(termo)) continue;
      const slug = modulos.get(t.codigo) ?? GERAL;
      if (!porModulo.has(slug)) porModulo.set(slug, []);
      porModulo.get(slug)!.push(t);
    }
    const ordem = [...ORDEM_MODULOS, GERAL];
    return [...porModulo.entries()]
      .sort(([a], [b]) => ordem.indexOf(a) - ordem.indexOf(b))
      .map(([slug, lista]) => ({
        slug,
        lista: lista.sort((a, b) => a.transacao.localeCompare(b.transacao, "pt-BR")),
      }));
  }, [transacoes, termo, modulos]);

  const comAcesso = transacoes.filter((t) => {
    const p = perms[t.id];
    return p && (p.inserir || p.atualizar || p.excluir);
  }).length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {transacoes.length > TRANSACOES_COM_BUSCA ? (
          <div className="relative w-full max-w-xs">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle"
              aria-hidden="true"
            />
            <Input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Filtrar áreas…"
              aria-label="Filtrar áreas"
              className="pl-9"
            />
          </div>
        ) : (
          <span />
        )}
        <span className="text-xs text-foreground-muted" aria-live="polite">
          Acesso a {comAcesso} de {transacoes.length} áreas
        </span>
      </div>

      {secoes.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-3 py-6 text-center text-sm text-foreground-muted">
          Nenhuma área com esse nome.
        </p>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Área</TH>
              {ACOES.map((a) => (
                <TH key={a.campo} className="w-28 text-center">
                  {a.rotulo}
                </TH>
              ))}
            </TR>
          </THead>
          {secoes.map(({ slug, lista }) => (
            <TBody key={slug}>
              <TR className="bg-surface-2 hover:bg-surface-2">
                <TD colSpan={4} className="py-1.5 text-xs font-semibold uppercase tracking-wider text-foreground-muted">
                  {nomeDoGrupoDeModulo(slug)}
                </TD>
              </TR>
              {lista.map((t) => {
                const p = perms[t.id];
                return (
                  <TR key={t.id}>
                    <TD>
                      <div className="font-medium">{t.transacao}</div>
                      <div className="font-mono text-xs text-foreground-subtle">{t.codigo}</div>
                    </TD>
                    {ACOES.map(({ campo, rotulo }) => {
                      const ligado = p?.[campo] ?? false;
                      return (
                        <TD key={campo} className="text-center">
                          <label
                            className={cn(
                              "inline-flex min-w-[5.5rem] cursor-pointer items-center justify-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-fast",
                              "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                              ligado
                                ? "border-success/40 bg-success-soft text-success-soft-foreground"
                                : "border-border bg-card text-foreground-subtle hover:border-border-strong hover:text-foreground",
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={ligado}
                              onChange={(e) => onAlternar(t.id, campo, e.target.checked)}
                              aria-label={`${rotulo} em ${t.transacao}`}
                              className="h-3.5 w-3.5 accent-current"
                            />
                            {ligado ? "Sim" : "Não"}
                          </label>
                        </TD>
                      );
                    })}
                  </TR>
                );
              })}
            </TBody>
          ))}
        </Table>
      )}
    </div>
  );
}
