"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

const PLANOS = ["basico", "profissional", "enterprise"];

export function TenantEditForm({ tenantId }: { tenantId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["admin-tenant", tenantId], queryFn: () => api.admin.tenants.detalhe(tenantId) });
  const [form, setForm] = useState({ nome: "", cnpj: "", plano: "basico", cor_primaria: "", limite_usuarios: "", limite_armazenamento_mb: "" });

  useEffect(() => {
    if (q.data) {
      setForm({
        nome: q.data.nome ?? "",
        cnpj: q.data.cnpj ?? "",
        plano: q.data.plano ?? "basico",
        cor_primaria: q.data.cor_primaria ?? "",
        limite_usuarios: q.data.limite_usuarios?.toString() ?? "",
        limite_armazenamento_mb: q.data.limite_armazenamento_mb?.toString() ?? "",
      });
    }
  }, [q.data]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api.admin.tenants.editar(tenantId, {
        nome: form.nome.trim(),
        cnpj: form.cnpj.trim() || null,
        plano: form.plano,
        cor_primaria: form.cor_primaria.trim() || null,
        limite_usuarios: form.limite_usuarios ? Number(form.limite_usuarios) : null,
        limite_armazenamento_mb: form.limite_armazenamento_mb ? Number(form.limite_armazenamento_mb) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenant", tenantId] });
      qc.invalidateQueries({ queryKey: ["admin-tenants"] });
      toast.success("Tenant atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) return <p className="text-sm text-muted-foreground" role="status">Carregando…</p>;
  if (!q.data) return <p className="text-sm text-muted-foreground">Tenant não encontrado.</p>;

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); m.mutate(); }}
      className="max-w-2xl space-y-4"
    >
      <h1 className="text-xl font-bold text-foreground">Editar prefeitura</h1>

      <div>
        <Label>Slug (subdomínio — imutável)</Label>
        {/* Slug NÃO é editável: identifica o subdomínio / URLs públicas. */}
        <Input value={q.data.slug} readOnly disabled className="font-mono" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div><Label>Nome</Label><Input value={form.nome} onChange={set("nome")} /></div>
        <div><Label>CNPJ</Label><Input value={form.cnpj} onChange={set("cnpj")} /></div>
        <div>
          <Label>Plano</Label>
          <select value={form.plano} onChange={set("plano")} className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm">
            {PLANOS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div><Label>Cor primária</Label><Input value={form.cor_primaria} onChange={set("cor_primaria")} placeholder="#0055aa" /></div>
        <div><Label>Limite de usuários</Label><Input value={form.limite_usuarios} onChange={set("limite_usuarios")} type="number" /></div>
        <div><Label>Limite de armazenamento (MB)</Label><Input value={form.limite_armazenamento_mb} onChange={set("limite_armazenamento_mb")} type="number" /></div>
      </div>

      <p className="text-xs text-muted-foreground">
        Módulos do plano: {q.data.modulos.join(", ") || "—"}
      </p>

      <Button type="submit" disabled={m.isPending}>{m.isPending ? "Salvando…" : "Salvar"}</Button>
    </form>
  );
}
