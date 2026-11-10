"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Inbox, Pencil, Plus, Search, Trash2, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  aceitaLetras,
  aplicarMascara,
  documentoValido,
  emailValido,
  exemploDaMascara,
  type Mascara,
} from "@/lib/mascaras";
import { cn } from "@/lib/utils";

export type FieldType = "text" | "email" | "number" | "select" | "checkbox" | "textarea";

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface CrudField<T = any> {
  name: keyof T & string;
  /** Função quando o rótulo depende do formulário (ex.: CPF × CNPJ pelo tipo). */
  label: string | ((form: any) => string);
  type: FieldType;
  required?: boolean;
  options?: SelectOption[];
  placeholder?: string;
  colSpan?: 1 | 2;
  /**
   * Máscara de digitação (só `type: "text"`). Função quando depende do
   * formulário. O valor vai formatado ao servidor; vazio vai como `null`.
   */
  mascara?: Mascara | ((form: any) => Mascara);
  /** Checkbox: texto ao lado da caixa (o `label` fica como título acima). */
  textoAoLado?: string;
  /** Dica permanente sob o campo: formato, exemplo, para que serve. */
  dica?: string;
  /** Unidade grudada no campo (só `text`/`number`): "R$" antes, "km" depois. */
  prefixo?: string;
  sufixo?: string;
}

function resolver<V>(v: V | ((form: any) => V), form: any): V {
  return typeof v === "function" ? (v as (form: any) => V)(form) : v;
}

function vazio(v: unknown): boolean {
  return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
}

/**
 * Documento que veio do cadastro e não foi tocado não é reconferido: há
 * cadastro anterior à conferência do dígito verificador (a demonstração usa
 * CPF fictício), e exigir a correção travaria trocar o telefone. O backend
 * faz o mesmo (`routers/manifestantes.py::update_manifestante`).
 */
function docAlterado(m: Mascara, v: unknown, original: unknown): boolean {
  return original === undefined || aplicarMascara(m, v).valor !== aplicarMascara(m, original).valor;
}

/**
 * Erros por campo antes de enviar. `required` só valia no `<input>` nativo,
 * e o Salvar do rodapé fica fora do `<form>`: o navegador nunca conferia, e
 * campo obrigatório vazio chegava ao servidor. Na edição, `original` é o
 * registro como abriu no formulário.
 */
function validar(fields: CrudField[], form: any, original?: any): Record<string, string> {
  const erros: Record<string, string> = {};
  for (const f of fields) {
    if (f.type === "checkbox") continue;
    const v = form[f.name];
    if (vazio(v)) {
      if (f.required) erros[f.name] = "Campo obrigatório.";
      continue;
    }
    const m = f.mascara && resolver(f.mascara, form);
    if (m && !aplicarMascara(m, v).completo) {
      erros[f.name] = `Preencha no formato ${exemploDaMascara(m)}.`;
    } else if ((m === "cpf" || m === "cnpj") && docAlterado(m, v, original?.[f.name]) && !documentoValido(m, v)) {
      erros[f.name] = `${m.toUpperCase()} inválido: confira os dígitos.`;
    } else if (f.type === "email" && !emailValido(String(v))) {
      erros[f.name] = "E-mail inválido.";
    }
  }
  return erros;
}

function campoMascarado(m: Mascara, v: unknown): string | null {
  const { valor } = aplicarMascara(m, v);
  return valor === "" ? null : valor;
}

/**
 * Campo com máscara e guia no fundo: o texto digitado fica no `<input>`, e
 * uma camada por cima, que não recebe clique, repete o digitado invisível
 * seguido do resto do padrão em cinza. Mesma borda e padding do `Input`, para
 * a guia começar exatamente onde o texto termina.
 */
function InputMascarado({
  mascara,
  value,
  onChange,
  ...props
}: {
  mascara: Mascara;
  value: unknown;
  onChange: (valor: string) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const { valor, guia } = aplicarMascara(mascara, value);
  return (
    <div className="relative">
      <Input
        {...props}
        type="text"
        // CNPJ alfanumérico precisa do teclado com letras no celular.
        inputMode={aceitaLetras(mascara) ? "text" : "numeric"}
        autoCapitalize={aceitaLetras(mascara) ? "characters" : undefined}
        autoComplete="off"
        value={valor}
        onChange={(e) => onChange(aplicarMascara(mascara, e.target.value).valor)}
      />
      <span
        aria-hidden="true"
        data-testid={`guia-${props.id}`}
        className="pointer-events-none absolute inset-0 flex items-center whitespace-pre rounded-input border border-transparent px-3 text-base"
      >
        <span className="invisible">{valor}</span>
        <span className="text-muted-foreground/70">{guia}</span>
      </span>
    </div>
  );
}

export interface CrudColumn<T> {
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

interface CrudPageProps<T extends { id: number }> {
  title: string;
  /** Uma frase sobre o que é o cadastro — o PageHeader de toda tela tem. */
  description?: React.ReactNode;
  /** Ícone do cadastro (o mesmo do menu/hub, para a tela ser reconhecível). */
  icon?: LucideIcon;
  /**
   * Rótulo do botão de criar, com o nome da coisa e o gênero certo
   * ("Nova cidade", "Novo fornecedor"). Também titula o diálogo. Padrão: "Novo".
   */
  novoLabel?: string;
  queryKey: any[];
  /**
   * Função que retorna `{items, total, page, page_size}` ou `T[]` direto.
   * Recebe a página atual; respostas paginadas devem repassá-la à API
   * (`page`), senão a navegação renderiza sempre a primeira página.
   */
  fetchList: (params: {
    page: number;
  }) => Promise<{ items: T[]; total?: number; page?: number; page_size?: number } | T[]>;
  createFn: (data: any) => Promise<T>;
  updateFn: (id: number, data: any) => Promise<T>;
  deleteFn: (id: number) => Promise<void>;
  columns: CrudColumn<T>[];
  fields: CrudField<T>[];
  emptyForm: any;
  permCode?: string;
  searchable?: boolean;
  onSearchChange?: (q: string) => void;
  toolbar?: React.ReactNode;
  /** Recebe a row e devolve form pré-preenchido para edição. */
  rowToForm?: (row: T) => any;
  /** Tamanho do modal. */
  dialogSize?: "sm" | "md" | "lg";
}

export function CrudPage<T extends { id: number }>({
  title,
  description,
  icon,
  novoLabel = "Novo",
  queryKey,
  fetchList,
  createFn,
  updateFn,
  deleteFn,
  columns,
  fields,
  emptyForm,
  permCode,
  searchable,
  onSearchChange,
  toolbar,
  rowToForm,
  dialogSize = "md",
}: CrudPageProps<T>) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [form, setForm] = useState<any>(emptyForm);
  const [err, setErr] = useState<string | null>(null);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  // Termo efetivado após o debounce: o input responde a cada tecla via `q`,
  // mas quem dispara busca (onSearchChange → queryKey do caller) e reset de
  // página é só o valor estabilizado — teclas rápidas não geram fetch por tecla.
  const [qDebounced, setQDebounced] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    onSearchChange?.(qDebounced);
  }, [qDebounced, onSearchChange]);

  // Novo termo efetivado (inclusive busca limpa) recomeça da página 1; no
  // mount é no-op porque a página já é 1.
  useEffect(() => {
    setPage(1);
  }, [qDebounced]);

  // A página entra na queryKey para que páginas diferentes não colidam no
  // cache; as mutations seguem invalidando por prefixo (`queryKey` do caller),
  // o que alcança todas as páginas da família.
  const listQ = useQuery({
    queryKey: [...queryKey, { page }],
    queryFn: () => fetchList({ page }),
  });

  const createM = useMutation({
    mutationFn: (data: any) => createFn(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      toast.success("Registro criado.");
      close();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => updateFn(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      toast.success("Alterações salvas.");
      close();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => deleteFn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      toast.success("Registro excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function close() {
    setOpen(false);
    setEditing(null);
    setForm(emptyForm);
    setErr(null);
    setErros({});
  }

  function openNew() {
    setEditing(null);
    setForm(emptyForm);
    setErr(null);
    setErros({});
    setOpen(true);
  }

  function openEdit(row: T) {
    setEditing(row);
    setForm(rowToForm ? rowToForm(row) : { ...row });
    setErr(null);
    setErros({});
    setOpen(true);
  }

  function mudar(nome: string, valor: unknown) {
    setForm((f: any) => ({ ...f, [nome]: valor }));
    if (erros[nome]) setErros(({ [nome]: _, ...resto }) => resto);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const original = editing ? (rowToForm ? rowToForm(editing) : editing) : undefined;
    const encontrados = validar(fields, form, original);
    setErros(encontrados);
    if (Object.keys(encontrados).length > 0) {
      document.getElementById(Object.keys(encontrados)[0])?.focus();
      return;
    }
    const data = { ...form };
    for (const f of fields) {
      const m = f.mascara && resolver(f.mascara, form);
      if (m) data[f.name] = campoMascarado(m, form[f.name]);
    }
    if (editing) updateM.mutate({ id: editing.id, data });
    else createM.mutate(data);
  }

  const rows: T[] = Array.isArray(listQ.data)
    ? listQ.data
    : (listQ.data as { items: T[] } | undefined)?.items ?? [];

  // Metadata real da resposta paginada; array simples (contrato legítimo de
  // alguns call-sites) fica sem controles de paginação.
  const meta =
    listQ.data && !Array.isArray(listQ.data)
      ? typeof listQ.data.total === "number" &&
        typeof listQ.data.page_size === "number" &&
        listQ.data.page_size > 0
        ? { total: listQ.data.total, page_size: listQ.data.page_size }
        : null
      : null;
  const lastPage = meta ? Math.max(1, Math.ceil(meta.total / meta.page_size)) : 1;

  // Página órfã (ex.: exclusão do último item da última página): volta para a
  // última página válida em vez de exibir um vazio falso.
  useEffect(() => {
    if (meta && page > lastPage) setPage(lastPage);
  }, [meta, page, lastPage]);

  return (
    <div className="space-y-4">
      <PageHeader
        title={title}
        description={description}
        icon={icon}
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            {novoLabel}
          </Button>
        }
      />

      {(searchable || toolbar) && (
        <div className="flex flex-wrap items-center gap-2">
          {searchable && (
            <div className="relative w-full max-w-sm">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle"
                aria-hidden="true"
              />
              <Input
                placeholder={`Buscar em ${title.toLowerCase()}…`}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="pl-9"
              />
            </div>
          )}
          {toolbar}
        </div>
      )}

      <Table>
        <THead>
          <TR>
            {columns.map((c) => (
              <TH key={c.header} className={c.className}>
                {c.header}
              </TH>
            ))}
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading &&
            Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} cols={columns.length + 1} />
            ))}
          {!listQ.isLoading && rows.length === 0 && (
            <TR>
              <TD colSpan={columns.length + 1} className="p-0">
                <EmptyState
                  icon={Inbox}
                  title={`Nenhum registro em ${title.toLowerCase()}`}
                  description={`Use “${novoLabel}” para cadastrar o primeiro.`}
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {rows.map((row) => (
            <TR key={row.id}>
              {columns.map((c) => (
                <TD key={c.header} className={c.className}>
                  {c.render(row)}
                </TD>
              ))}
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, onClick: () => openEdit(row) },
                    {
                      label: "Excluir",
                      icon: Trash2,
                      perigo: true,
                      onClick: async () => {
                        const ok = await confirm({
                          title: "Excluir registro",
                          message:
                            "Esta ação não pode ser desfeita. Deseja realmente excluir este registro?",
                          confirmLabel: "Excluir",
                          intent: "danger",
                        });
                        if (ok) deleteM.mutate(row.id);
                      },
                    },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {/* Lista vazia já diz isso no EmptyState; "0 registros — página 1"
          com Anterior/Próxima desabilitados embaixo era ruído. */}
      {meta && meta.total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {meta.total} {meta.total === 1 ? "registro" : "registros"}
            {` — página ${page} de ${lastPage}`}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= lastPage}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog
        open={open}
        onClose={close}
        // "Nova cidade" → "Editar cidade": o diálogo diz o que se edita.
        title={
          editing
            ? novoLabel === "Novo"
              ? "Editar"
              : `Editar ${novoLabel.replace(/^Nov[oa]\s+/i, "")}`
            : novoLabel
        }
        size={dialogSize}
        footer={
          <>
            <Button variant="secondary" onClick={close}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={createM.isPending || updateM.isPending}>
              {createM.isPending || updateM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <form onSubmit={submit} noValidate className="grid grid-cols-2 gap-x-4 gap-y-4">
          {/* Resumo dos erros no topo: num diálogo que rola, o primeiro campo
              inválido recebe o foco, mas quem errou três precisa saber que
              são três. Cada item leva ao campo. */}
          {Object.keys(erros).length > 1 && (
            <div
              role="alert"
              className="col-span-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              <p className="font-medium">Revise {Object.keys(erros).length} campos antes de salvar:</p>
              <ul className="mt-1 list-inside list-disc">
                {fields
                  .filter((f) => erros[f.name])
                  .map((f) => (
                    <li key={f.name}>
                      <button
                        type="button"
                        onClick={() => document.getElementById(f.name)?.focus()}
                        className="underline underline-offset-2 hover:no-underline"
                      >
                        {resolver(f.label, form)}
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          )}
          {fields.map((f) => {
            const erro = erros[f.name];
            const mascara = f.mascara && f.type === "text" ? resolver(f.mascara, form) : undefined;
            const aria = {
              "aria-invalid": erro ? true : undefined,
              "aria-describedby":
                [erro ? `${f.name}-erro` : null, f.dica ? `${f.name}-dica` : null].filter(Boolean).join(" ") ||
                undefined,
            };
            const comUnidade = (f.prefixo || f.sufixo) && (f.type === "text" || f.type === "number") && !mascara;
            return (
            <div
              key={f.name}
              className={f.colSpan === 2 ? "col-span-2" : "col-span-2 sm:col-span-1"}
            >
              <Label htmlFor={f.name} required={f.required && f.type !== "checkbox"}>
                {resolver(f.label, form)}
              </Label>
              {f.type === "select" ? (
                <Select
                  id={f.name}
                  value={form[f.name] ?? ""}
                  onChange={(e) =>
                    mudar(
                      f.name,
                      e.target.value === "" ? null : isNaN(Number(e.target.value)) ? e.target.value : Number(e.target.value),
                    )
                  }
                  required={f.required}
                  {...aria}
                >
                  <option value="">—</option>
                  {f.options?.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              ) : f.type === "checkbox" ? (
                <div className="flex h-[var(--density-row-h)] items-center gap-2">
                  <input
                    id={f.name}
                    type="checkbox"
                    checked={!!form[f.name]}
                    onChange={(e) => mudar(f.name, e.target.checked)}
                    className="h-4 w-4 rounded border-border-strong accent-[hsl(var(--brand))]"
                  />
                  {f.textoAoLado && (
                    <label htmlFor={f.name} className="text-sm text-foreground">
                      {f.textoAoLado}
                    </label>
                  )}
                </div>
              ) : f.type === "textarea" ? (
                <Textarea
                  id={f.name}
                  value={form[f.name] ?? ""}
                  onChange={(e) => mudar(f.name, e.target.value)}
                  placeholder={f.placeholder}
                  rows={3}
                  {...aria}
                />
              ) : mascara ? (
                <InputMascarado
                  id={f.name}
                  mascara={mascara}
                  value={form[f.name]}
                  onChange={(v) => mudar(f.name, v)}
                  required={f.required}
                  {...aria}
                />
              ) : comUnidade ? (
                <CampoComUnidade
                  id={f.name}
                  type={f.type}
                  inputMode={f.type === "number" ? "decimal" : undefined}
                  prefixo={f.prefixo}
                  sufixo={f.sufixo}
                  value={form[f.name] ?? ""}
                  onChange={(e) =>
                    mudar(
                      f.name,
                      f.type === "number"
                        ? e.target.value === ""
                          ? null
                          : Number(e.target.value)
                        : e.target.value,
                    )
                  }
                  required={f.required}
                  placeholder={f.placeholder}
                  {...aria}
                />
              ) : (
                <Input
                  id={f.name}
                  type={f.type}
                  value={form[f.name] ?? ""}
                  onChange={(e) =>
                    mudar(
                      f.name,
                      f.type === "number"
                        ? e.target.value === ""
                          ? null
                          : Number(e.target.value)
                        : e.target.value,
                    )
                  }
                  required={f.required}
                  placeholder={f.placeholder}
                  {...aria}
                />
              )}
              {f.dica && (
                <p id={`${f.name}-dica`} className={cn("mt-1 text-xs text-foreground-muted", erro && "sr-only")}>
                  {f.dica}
                </p>
              )}
              {erro && (
                <p id={`${f.name}-erro`} className="mt-1 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground">
                  <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {erro}
                </p>
              )}
            </div>
            );
          })}
          {err && (
            <div
              role="alert"
              className="col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </form>
      </Dialog>
    </div>
  );
}
