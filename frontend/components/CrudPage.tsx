"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";

export type FieldType = "text" | "number" | "select" | "checkbox" | "textarea";

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface CrudField<T = any> {
  name: keyof T & string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: SelectOption[];
  placeholder?: string;
  colSpan?: 1 | 2;
}

export interface CrudColumn<T> {
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

interface CrudPageProps<T extends { id: number }> {
  title: string;
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
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    onSearchChange?.(q);
  }, [q, onSearchChange]);

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
  }

  function openNew() {
    setEditing(null);
    setForm(emptyForm);
    setErr(null);
    setOpen(true);
  }

  function openEdit(row: T) {
    setEditing(row);
    setForm(rowToForm ? rowToForm(row) : { ...row });
    setErr(null);
    setOpen(true);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (editing) updateM.mutate({ id: editing.id, data: form });
    else createM.mutate(form);
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-aprimora">{title}</h1>
        <Button onClick={openNew}>Novo</Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {searchable && (
          <Input
            placeholder="Buscar..."
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="max-w-sm"
          />
        )}
        {toolbar}
      </div>

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
                  description="Clique em Novo para criar o primeiro."
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
                <div className="inline-flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => openEdit(row)}
                  >
                    Editar
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={async () => {
                      const ok = await confirm({
                        title: "Excluir registro",
                        message:
                          "Esta ação não pode ser desfeita. Deseja realmente excluir este registro?",
                        confirmLabel: "Excluir",
                        intent: "danger",
                      });
                      if (ok) deleteM.mutate(row.id);
                    }}
                  >
                    Excluir
                  </Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {meta && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {meta.total} registros — página {page}
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
        title={editing ? "Editar" : "Novo"}
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
        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          {fields.map((f) => (
            <div
              key={f.name}
              className={f.colSpan === 2 ? "col-span-2" : "col-span-1"}
            >
              <Label htmlFor={f.name} required={f.required && f.type !== "checkbox"}>
                {f.label}
              </Label>
              {f.type === "select" ? (
                <Select
                  id={f.name}
                  value={form[f.name] ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      [f.name]: e.target.value === "" ? null : isNaN(Number(e.target.value)) ? e.target.value : Number(e.target.value),
                    })
                  }
                  required={f.required}
                >
                  <option value="">—</option>
                  {f.options?.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              ) : f.type === "checkbox" ? (
                <div className="flex h-10 items-center">
                  <input
                    id={f.name}
                    type="checkbox"
                    checked={!!form[f.name]}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                </div>
              ) : f.type === "textarea" ? (
                <Textarea
                  id={f.name}
                  value={form[f.name] ?? ""}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  placeholder={f.placeholder}
                  rows={3}
                />
              ) : (
                <Input
                  id={f.name}
                  type={f.type}
                  value={form[f.name] ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      [f.name]:
                        f.type === "number"
                          ? e.target.value === ""
                            ? null
                            : Number(e.target.value)
                          : e.target.value,
                    })
                  }
                  required={f.required}
                  placeholder={f.placeholder}
                />
              )}
            </div>
          ))}
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
