"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { api, type AdminTenantCreated } from "@/lib/api";

const PLANOS = ["basico", "profissional", "enterprise"];

export function TenantsAdmin() {
  const qc = useQueryClient();
  const toast = useToast();
  const [openCriar, setOpenCriar] = useState(false);

  const listQ = useQuery({ queryKey: ["admin-tenants"], queryFn: () => api.admin.tenants.list() });

  const toggleM = useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) =>
      ativo ? api.admin.tenants.desativar(id) : api.admin.tenants.ativar(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenants"] });
      toast.success("Status atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">Tenants (prefeituras)</h1>
        <Button onClick={() => setOpenCriar(true)}>Nova prefeitura</Button>
      </div>

      {listQ.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Nome</th>
              <th className="px-3 py-2">Plano</th>
              <th className="px-3 py-2">Limite usuários</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Ações</th>
            </tr>
          </thead>
          <tbody>
            {(listQ.data ?? []).map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono">{t.slug}</td>
                <td className="px-3 py-2">{t.nome}</td>
                <td className="px-3 py-2">{t.plano}</td>
                <td className="px-3 py-2">{t.limite_usuarios ?? "—"}</td>
                <td className="px-3 py-2">
                  <Badge intent={t.ativo ? "success" : "danger"}>{t.ativo ? "Ativo" : "Inativo"}</Badge>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-3">
                    <Link href={`/admin/tenants/${t.id}`} className="text-primary hover:underline">
                      Editar
                    </Link>
                    <button
                      type="button"
                      onClick={() => toggleM.mutate({ id: t.id, ativo: t.ativo })}
                      disabled={toggleM.isPending}
                      className={t.ativo ? "text-danger hover:underline" : "text-success hover:underline"}
                    >
                      {t.ativo ? "Desativar" : "Ativar"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {listQ.data && listQ.data.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhuma prefeitura cadastrada.</p>
      )}

      <CriarTenantDialog
        open={openCriar}
        onClose={() => setOpenCriar(false)}
        onCreated={() => qc.invalidateQueries({ queryKey: ["admin-tenants"] })}
      />
    </div>
  );
}

function CriarTenantDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    slug: "", nome: "", admin_email: "", admin_nome: "", admin_cpf: "", plano: "basico", cnpj: "", limite_usuarios: "",
  });
  const [criado, setCriado] = useState<AdminTenantCreated | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api.admin.tenants.criar({
        slug: form.slug.trim(),
        nome: form.nome.trim(),
        admin_email: form.admin_email.trim(),
        admin_nome: form.admin_nome.trim(),
        admin_cpf: form.admin_cpf.trim(),
        plano: form.plano,
        cnpj: form.cnpj.trim() || null,
        limite_usuarios: form.limite_usuarios ? Number(form.limite_usuarios) : null,
      }),
    onSuccess: (res) => {
      setCriado(res);
      onCreated();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function fechar() {
    setCriado(null);
    setForm({ slug: "", nome: "", admin_email: "", admin_nome: "", admin_cpf: "", plano: "basico", cnpj: "", limite_usuarios: "" });
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={criado ? "Prefeitura criada" : "Nova prefeitura"}
      size="lg"
      footer={
        criado ? (
          <Button onClick={fechar}>Fechar</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={fechar}>Cancelar</Button>
            <Button onClick={() => m.mutate()} disabled={m.isPending}>
              {m.isPending ? "Criando…" : "Criar"}
            </Button>
          </>
        )
      }
    >
      {criado ? (
        <div className="space-y-3 text-sm">
          <p className="text-foreground">
            Prefeitura <b>{criado.tenant.nome}</b> (<span className="font-mono">{criado.tenant.slug}</span>) criada.
          </p>
          <div className="rounded-md border border-border bg-muted p-3">
            <Label className="text-muted-foreground">Senha temporária do admin ({criado.admin_email})</Label>
            <code className="mt-1 block break-all font-mono text-base text-foreground">{criado.senha_temporaria}</code>
          </div>
          <p className="text-xs text-warning-soft-foreground">{criado.aviso}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Campo label="Slug (subdomínio, imutável)"><Input value={form.slug} onChange={set("slug")} placeholder="ex.: fortaleza" /></Campo>
          <Campo label="Nome"><Input value={form.nome} onChange={set("nome")} /></Campo>
          <Campo label="E-mail do admin"><Input value={form.admin_email} onChange={set("admin_email")} type="email" /></Campo>
          <Campo label="Nome do admin"><Input value={form.admin_nome} onChange={set("admin_nome")} /></Campo>
          <Campo label="CPF do admin"><Input value={form.admin_cpf} onChange={set("admin_cpf")} /></Campo>
          <Campo label="Plano">
            <select value={form.plano} onChange={set("plano")} className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm">
              {PLANOS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Campo>
          <Campo label="CNPJ (opcional)"><Input value={form.cnpj} onChange={set("cnpj")} /></Campo>
          <Campo label="Limite de usuários (opcional)"><Input value={form.limite_usuarios} onChange={set("limite_usuarios")} type="number" /></Campo>
        </div>
      )}
    </Dialog>
  );
}

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
