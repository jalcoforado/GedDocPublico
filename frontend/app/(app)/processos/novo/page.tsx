"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type ProcessoCreateInput } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type FormState = {
  id_tipo_processo: number | "";
  id_assunto: number | "";
  id_manifestante: number | "";
  id_unidade_proprietaria: number | "";
  observacao: string;
  corpo: string;
  numero_origem: string;
  publico: boolean;
  externo: boolean;
};

export default function NovoProcessoPage() {
  const router = useRouter();
  const toast = useToast();
  const { user } = useAuth();

  const [form, setForm] = useState<FormState>({
    id_tipo_processo: "",
    id_assunto: "",
    id_manifestante: "",
    id_unidade_proprietaria: user?.id_unidade_trabalho ?? "",
    observacao: "",
    corpo: "",
    numero_origem: "",
    publico: true,
    externo: false,
  });
  const [err, setErr] = useState<string | null>(null);

  const tiposProcessoQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });
  const assuntosQ = useQuery({
    queryKey: ["assuntos-all"],
    queryFn: () => api.assuntos.list({ page_size: 200 }),
  });
  const manifestantesQ = useQuery({
    queryKey: ["manifestantes-all"],
    queryFn: () => api.manifestantes.list({ page_size: 200 }),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  const assuntosFiltrados = useMemo(() => {
    const all = assuntosQ.data?.items ?? [];
    if (!form.id_tipo_processo) return all;
    return all.filter((a) => a.id_tipo_processo === form.id_tipo_processo);
  }, [assuntosQ.data, form.id_tipo_processo]);

  function handleTipoChange(v: string) {
    const id = v ? Number(v) : "";
    const novoAssunto =
      typeof id === "number" && form.id_assunto
        ? assuntosQ.data?.items.find((a) => a.id === form.id_assunto)
            ?.id_tipo_processo === id
          ? form.id_assunto
          : ""
        : "";
    setForm({ ...form, id_tipo_processo: id, id_assunto: novoAssunto });
  }

  const createM = useMutation({
    mutationFn: (data: ProcessoCreateInput) => api.processos.create(data),
    onSuccess: (p) => {
      toast.success(`Processo ${p.numero_processo} criado.`);
      router.push(`/processos/${p.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!form.id_assunto || !form.id_manifestante || !form.id_unidade_proprietaria) {
      setErr("Preencha assunto, manifestante e unidade proprietária.");
      return;
    }
    createM.mutate({
      id_assunto: Number(form.id_assunto),
      id_manifestante: Number(form.id_manifestante),
      id_unidade_proprietaria: Number(form.id_unidade_proprietaria),
      observacao: form.observacao || null,
      corpo: form.corpo || null,
      numero_origem: form.numero_origem || null,
      publico: form.publico,
      externo: form.externo,
      virtual: true,
    });
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <Link href="/processos" className="text-sm text-primary hover:underline">
          ← Voltar
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Novo processo</CardTitle>
          <p className="text-sm text-muted-foreground">
            Número será gerado automaticamente após salvar.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
            <div className="sm:col-span-2">
              <Label htmlFor="manif" required>
                Manifestante
              </Label>
              <Select
                id="manif"
                value={form.id_manifestante}
                onChange={(e) =>
                  setForm({
                    ...form,
                    id_manifestante: e.target.value ? Number(e.target.value) : "",
                  })
                }
                required
              >
                <option value="">—</option>
                {manifestantesQ.data?.items.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome ?? "(sem nome)"} {m.cpf_cnpj ? `· ${m.cpf_cnpj}` : ""}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="tipo">Tipo de processo</Label>
              <Select
                id="tipo"
                value={form.id_tipo_processo}
                onChange={(e) => handleTipoChange(e.target.value)}
              >
                <option value="">— Todos —</option>
                {tiposProcessoQ.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.tipo_processo}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="assunto" required>
                Assunto
              </Label>
              <Select
                id="assunto"
                value={form.id_assunto}
                onChange={(e) =>
                  setForm({
                    ...form,
                    id_assunto: e.target.value ? Number(e.target.value) : "",
                  })
                }
                required
              >
                <option value="">—</option>
                {assuntosFiltrados.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.assunto.length > 70 ? a.assunto.slice(0, 70) + "…" : a.assunto}
                  </option>
                ))}
              </Select>
            </div>

            <div className="sm:col-span-2">
              <Label htmlFor="unidade" required>
                Unidade proprietária
              </Label>
              <Select
                id="unidade"
                value={form.id_unidade_proprietaria}
                onChange={(e) =>
                  setForm({
                    ...form,
                    id_unidade_proprietaria: e.target.value ? Number(e.target.value) : "",
                  })
                }
                required
              >
                <option value="">—</option>
                {unidadesQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.unidade_trabalho}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-muted-foreground">
                Sugerida: unidade do usuário ({user?.id_unidade_trabalho ?? "—"})
              </p>
            </div>

            <div className="sm:col-span-2">
              <Label htmlFor="obs">Observação</Label>
              <Textarea
                id="obs"
                value={form.observacao}
                onChange={(e) => setForm({ ...form, observacao: e.target.value })}
                rows={3}
                placeholder="Descreva brevemente o pedido"
              />
            </div>

            <div className="sm:col-span-2">
              <Label htmlFor="corpo">Corpo (opcional)</Label>
              <Textarea
                id="corpo"
                value={form.corpo}
                onChange={(e) => setForm({ ...form, corpo: e.target.value })}
                rows={5}
                placeholder="Conteúdo do processo (texto longo)"
              />
            </div>

            <div>
              <Label htmlFor="origem">Número de origem</Label>
              <Input
                id="origem"
                value={form.numero_origem}
                onChange={(e) => setForm({ ...form, numero_origem: e.target.value })}
                placeholder="Ex: protocolo externo"
              />
            </div>

            <div className="flex flex-wrap items-end gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.publico}
                  onChange={(e) => setForm({ ...form, publico: e.target.checked })}
                />
                Público
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.externo}
                  onChange={(e) => setForm({ ...form, externo: e.target.checked })}
                />
                Externo
              </label>
            </div>

            {err && (
              <div
                role="alert"
                className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground sm:col-span-2"
              >
                {err}
              </div>
            )}

            <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">
              <Link href="/processos">
                <Button variant="secondary" type="button">
                  Cancelar
                </Button>
              </Link>
              <Button type="submit" disabled={createM.isPending}>
                {createM.isPending ? "Abrindo..." : "Abrir processo"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
