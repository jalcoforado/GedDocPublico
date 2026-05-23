"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

export default function CidadaoAbrirPage() {
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();
  const [idAssunto, setIdAssunto] = useState<number | null>(null);
  const [corpo, setCorpo] = useState("");
  const [obs, setObs] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const assuntosQ = useQuery({
    queryKey: ["cidadao-assuntos"],
    queryFn: () => api.cidadao.assuntos(),
    enabled: !!cidadao,
  });

  const abrirM = useMutation({
    mutationFn: () => {
      if (!idAssunto) throw new Error("Escolha um assunto");
      return api.cidadao.abrirProcesso({
        id_assunto: idAssunto,
        corpo,
        observacao: obs || undefined,
      });
    },
    onSuccess: (data) => {
      toast.success("Processo aberto.");
      router.push(`/cidadao/processos/${data.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link href="/cidadao/processos" className="text-sm text-primary hover:underline">
        ← Voltar
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Abrir novo processo</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setErr(null);
              abrirM.mutate();
            }}
            className="space-y-3"
            noValidate
          >
            <div>
              <Label htmlFor="assunto" required>
                Assunto
              </Label>
              <Select
                id="assunto"
                value={idAssunto ?? ""}
                onChange={(e) =>
                  setIdAssunto(e.target.value ? Number(e.target.value) : null)
                }
                required
              >
                <option value="">Selecione...</option>
                {assuntosQ.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.assunto}
                    {a.tipo_processo ? ` (${a.tipo_processo})` : ""}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="corpo" required>
                Descreva sua solicitação
              </Label>
              <Textarea
                id="corpo"
                value={corpo}
                onChange={(e) => setCorpo(e.target.value)}
                required
                minLength={10}
                rows={6}
                placeholder="Inclua o máximo de detalhes possível."
              />
              <p className="mt-1 text-xs text-muted-foreground">Mínimo 10 caracteres.</p>
            </div>
            <div>
              <Label htmlFor="obs">Observação adicional (opcional)</Label>
              <Textarea
                id="obs"
                value={obs}
                onChange={(e) => setObs(e.target.value)}
                rows={3}
              />
            </div>
            {err && (
              <div
                role="alert"
                className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
              >
                {err}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={abrirM.isPending}>
                {abrirM.isPending ? "Abrindo..." : "Abrir processo"}
              </Button>
              <Link href="/cidadao/processos">
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
