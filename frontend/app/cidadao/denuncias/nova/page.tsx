"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type DenunciaCidadaoCreate } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

const MIN_CHARS = 10;

/** Data de hoje no fuso LOCAL, formatada YYYY-MM-DD para o `max` do input.
 * `new Date().toISOString()` converte para UTC antes de fatiar — em
 * UTC-3, à noite, isso já é "amanhã" em UTC e o input aceitava uma data
 * que ainda não chegou no relógio do cidadão. */
function hojeLocalISO(): string {
  const d = new Date();
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

export default function NovaDenunciaPage() {
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();

  const [idTipo, setIdTipo] = useState<number | null>(null);
  const [dataFato, setDataFato] = useState("");
  const [descricao, setDescricao] = useState("");
  const [referencia, setReferencia] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const tiposQ = useQuery({
    queryKey: ["cidadao-denuncias-tipos"],
    queryFn: () => api.cidadaoDenuncias.tipos(),
    enabled: !!cidadao,
  });
  const tiposAtivos = (tiposQ.data ?? []).filter((t) => t.ativo);

  const enviarM = useMutation({
    mutationFn: () => {
      const payload: DenunciaCidadaoCreate = {
        id_tipo: idTipo as number,
        data_fato: dataFato,
        descricao: descricao.trim(),
        referencia_alvo: referencia.trim() === "" ? null : referencia.trim(),
      };
      return api.cidadaoDenuncias.create(payload);
    },
    onSuccess: () => {
      toast.success("Denúncia registrada. Você pode acompanhar a apuração aqui.");
      router.push("/cidadao/denuncias");
    },
    onError: (e: Error) => setErr(e.message),
  });

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <SkeletonLine width="40%" className="h-4" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (!cidadao) return null;

  const trimmedLen = descricao.trim().length;
  const podeEnviar = idTipo !== null && dataFato !== "" && trimmedLen >= MIN_CHARS;

  function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (idTipo === null) {
      setErr("Selecione o tipo da denúncia.");
      return;
    }
    if (dataFato === "") {
      setErr("Informe a data do fato.");
      return;
    }
    if (trimmedLen < MIN_CHARS) {
      setErr(`Descreva com pelo menos ${MIN_CHARS} caracteres.`);
      return;
    }
    enviarM.mutate();
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/denuncias"
        className="
          inline-flex items-center gap-1 rounded text-sm text-primary
          hover:underline focus-visible:outline-none focus-visible:ring-2
          focus-visible:ring-ring
        "
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar às minhas denúncias
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Nova denúncia</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submeter}>
            <div>
              <Label htmlFor="tipo" required>
                Tipo
              </Label>
              {tiposQ.isLoading ? (
                <SkeletonLine width="60%" className="h-10" />
              ) : (
                <Select
                  id="tipo"
                  required
                  value={idTipo ?? ""}
                  onChange={(e) =>
                    setIdTipo(e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">Selecione...</option>
                  {tiposAtivos.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nome}
                    </option>
                  ))}
                </Select>
              )}
            </div>

            <div>
              <Label htmlFor="data_fato" required>
                Data do fato
              </Label>
              <Input
                id="data_fato"
                type="date"
                required
                max={hojeLocalISO()}
                value={dataFato}
                onChange={(e) => setDataFato(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="descricao" required>
                Descreva o que aconteceu
              </Label>
              <Textarea
                id="descricao"
                required
                rows={6}
                minLength={MIN_CHARS}
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                placeholder="Conte com detalhes o que você presenciou. Quanto mais claro, mais fácil a apuração."
              />
              <p className="mt-1 text-xs text-foreground-subtle">
                {trimmedLen}/{MIN_CHARS} caracteres mínimos
              </p>
            </div>

            <div>
              <Label htmlFor="referencia">Referência (opcional)</Label>
              <Input
                id="referencia"
                value={referencia}
                onChange={(e) => setReferencia(e.target.value)}
                placeholder="Ex.: placa do veículo, ponto ou linha"
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

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={!podeEnviar || enviarM.isPending}>
                {enviarM.isPending ? (
                  "Enviando…"
                ) : (
                  <>
                    <CheckCircle2 className="mr-1 h-4 w-4" aria-hidden="true" />
                    Enviar denúncia
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
