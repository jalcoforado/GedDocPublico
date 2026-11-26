"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertOctagon, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { marcarDenunciaRegistrada } from "@/components/cidadao/DenunciaRegistrada";
import { ResumoErros } from "@/components/cidadao/ResumoErros";
import { useErrosDepoisDaTentativa } from "@/components/cidadao/useErrosDepoisDaTentativa";
import { Alert } from "@/components/ui/alert";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
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

type Campo = "tipo" | "data_fato" | "descricao";
/** Como o campo aparece no "Falta: ..." da barra de ações. */
const FALTA: Record<Campo, string> = { tipo: "o tipo", data_fato: "a data", descricao: "a descrição" };
const ROTULO: Record<Campo, string> = {
  tipo: "O que aconteceu",
  data_fato: "Quando aconteceu",
  descricao: "Conte como foi",
};

export default function NovaDenunciaPage() {
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();
  const formRef = useRef<HTMLFormElement>(null);

  const [idTipo, setIdTipo] = useState<number | null>(null);
  // Já vem com hoje — a maioria denuncia no dia; a dica diz que dá para mudar.
  const [dataFato, setDataFato] = useState(hojeLocalISO);
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
      marcarDenunciaRegistrada();
      toast.success("Denúncia registrada. Você pode acompanhar a apuração aqui.");
      router.push("/cidadao/denuncias");
    },
    onError: (e: Error) => setErr(e.message),
  });

  const trimmedLen = descricao.trim().length;
  const hoje = hojeLocalISO();
  const erros: Record<Campo, string | null> = {
    tipo: idTipo === null ? "Escolha o que aconteceu. Se nenhuma opção servir, escolha a mais parecida." : null,
    data_fato: !dataFato
      ? "Informe o dia em que aconteceu."
      : dataFato > hoje
        ? "A data não pode ser depois de hoje."
        : null,
    descricao:
      trimmedLen >= MIN_CHARS
        ? null
        : trimmedLen === 0
          ? "Conte o que você viu."
          : `Escreva um pouco mais: faltam ${MIN_CHARS - trimmedLen} letras.`,
  };
  const v = useErrosDepoisDaTentativa(erros);

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <SkeletonLine width="40%" className="h-4" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (!cidadao) return null;

  const errosVisiveis = (Object.keys(erros) as Campo[])
    .filter((c) => v.erro(c))
    .map((c) => ({ campoId: c, rotulo: ROTULO[c] }));
  const faltando = (Object.keys(erros) as Campo[]).filter((c) => erros[c]).map((c) => FALTA[c]);

  function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!v.tentar()) {
      setTimeout(() => focarPrimeiroInvalido(formRef.current ?? document), 0);
      return;
    }
    enviarM.mutate();
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/denuncias"
        className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar para Minhas denúncias
      </Link>

      <PageHeader
        icon={AlertOctagon}
        title="Nova denúncia"
        description="Viu algo errado no transporte (táxi, mototáxi, transporte escolar)? Conte aqui: a fiscalização apura e você acompanha a situação."
      />

      <form ref={formRef} className="space-y-4" onSubmit={submeter} noValidate>
        <ResumoErros erros={errosVisiveis} />

        <SectionCard title="Sua denúncia">
          <FormField label="O que aconteceu" required error={v.erro("tipo")} hint="Escolha a opção mais parecida com o que você viu.">
            {tiposQ.isLoading ? (
              <SkeletonLine width="60%" className="h-11" />
            ) : (
              <Select
                id="tipo"
                value={idTipo ?? ""}
                onChange={(e) => setIdTipo(e.target.value ? Number(e.target.value) : null)}
                onBlur={v.sair("tipo")}
              >
                <option value="">Escolha uma opção…</option>
                {tiposAtivos.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nome}
                  </option>
                ))}
              </Select>
            )}
          </FormField>

          <FormField
            label="Quando aconteceu"
            required
            error={v.erro("data_fato")}
            hint="Já vem com a data de hoje. Se foi em outro dia, mude aqui."
          >
            <Input
              id="data_fato"
              type="date"
              max={hoje}
              value={dataFato}
              onChange={(e) => setDataFato(e.target.value)}
              onBlur={v.sair("data_fato")}
              className="sm:max-w-56"
            />
          </FormField>

          <FormField
            label="Conte como foi"
            required
            error={v.erro("descricao")}
            hint={
              <>
                O que você viu, onde e a que horas. Quanto mais claro, mais fácil a apuração.{" "}
                <span className="tabular-nums">
                  ({trimmedLen < MIN_CHARS ? `mínimo ${MIN_CHARS} letras, ${trimmedLen} até agora` : "ok"})
                </span>
              </>
            }
          >
            <Textarea
              id="descricao"
              rows={6}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              onBlur={v.sair("descricao")}
              placeholder="Ex.: Por volta das 7h, na parada da Praça da Matriz, o motorista do táxi cobrou acima do taxímetro."
            />
          </FormField>

          <FormField
            label="Placa, ponto ou linha"
            opcional
            hint="Ajuda a encontrar o responsável. Se não souber, pode deixar em branco."
          >
            <Input
              id="referencia"
              value={referencia}
              onChange={(e) => setReferencia(e.target.value)}
              placeholder="Ex.: ABC1D23"
              autoCapitalize="characters"
            />
          </FormField>
        </SectionCard>

        {err && <Alert intent="danger">{err}</Alert>}

        {/* Acima da barra de navegação do celular (ver `--barra-inferior` no layout). */}
        <BarraAcoesFormulario
          className="bottom-[var(--barra-inferior,0px)] sm:bottom-0"
          status={faltando.length ? `Falta: ${faltando.join(", ")}.` : "Tudo pronto para enviar."}
        >
          <Button asChild variant="ghost">
            <Link href="/cidadao/denuncias">Cancelar</Link>
          </Button>
          <Button type="submit" loading={enviarM.isPending}>
            {enviarM.isPending ? "Enviando…" : "Enviar denúncia"}
          </Button>
        </BarraAcoesFormulario>
      </form>
    </div>
  );
}
