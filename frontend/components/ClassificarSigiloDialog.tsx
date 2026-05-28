"use client";

import { useMutation } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  GRAUS_SIGILO_LEGAL,
  NIVEL_PRAZO_MAX,
  NIVEL_SIGILO_LABEL,
  type ClassificarSigiloInput,
  type NivelSigilo,
  type ProcessoDetail,
} from "@/lib/api";

const NIVEIS: NivelSigilo[] = [
  "ostensivo",
  "interno",
  "reservado",
  "secreto",
  "ultrassecreto",
];

export function ClassificarSigiloDialog({
  processo,
  onClassified,
}: {
  processo: ProcessoDetail;
  onClassified: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [nivel, setNivel] = useState<NivelSigilo>(processo.nivel_sigilo);
  const [fundamento, setFundamento] = useState(processo.sigilo_fundamento_legal ?? "");
  const [autoridade, setAutoridade] = useState(processo.sigilo_autoridade ?? "");
  const [prazo, setPrazo] = useState<string>(
    processo.sigilo_prazo_anos ? String(processo.sigilo_prazo_anos) : "",
  );
  const [err, setErr] = useState<string | null>(null);

  const exigeTci = GRAUS_SIGILO_LEGAL.includes(nivel);
  const prazoMax = NIVEL_PRAZO_MAX[nivel];

  function reset() {
    setNivel(processo.nivel_sigilo);
    setFundamento(processo.sigilo_fundamento_legal ?? "");
    setAutoridade(processo.sigilo_autoridade ?? "");
    setPrazo(processo.sigilo_prazo_anos ? String(processo.sigilo_prazo_anos) : "");
    setErr(null);
  }

  const mut = useMutation({
    mutationFn: () => {
      const payload: ClassificarSigiloInput = { nivel };
      if (exigeTci) {
        payload.fundamento_legal = fundamento.trim();
        payload.autoridade = autoridade.trim();
        payload.prazo_anos = prazo ? Number(prazo) : null;
      }
      return api.processos.classificarSigilo(processo.id, payload);
    },
    onSuccess: () => {
      toast.success(`Classificado como ${NIVEL_SIGILO_LABEL[nivel]}.`);
      setOpen(false);
      onClassified();
    },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          reset();
          setOpen(true);
        }}
        title="Classificar sigilo (LAI)"
      >
        <Lock className="h-4 w-4" aria-hidden="true" />
        Classificar
      </Button>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Classificar sigilo"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={mut.isPending}>
              Cancelar
            </Button>
            <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
              {mut.isPending ? "Salvando..." : "Salvar classificação"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground-muted">
            Nível atual:{" "}
            <strong className="text-foreground">
              {NIVEL_SIGILO_LABEL[processo.nivel_sigilo]}
            </strong>
            . Graus de sigilo legal (Reservado/Secreto/Ultrassecreto) exigem
            fundamento, autoridade e prazo (LAI, Lei 12.527/2011).
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="nivel-sigilo">Nível</Label>
            <Select
              id="nivel-sigilo"
              value={nivel}
              onChange={(e) => {
                setNivel(e.target.value as NivelSigilo);
                setErr(null);
              }}
            >
              {NIVEIS.map((n) => (
                <option key={n} value={n}>
                  {NIVEL_SIGILO_LABEL[n]}
                </option>
              ))}
            </Select>
          </div>

          {exigeTci && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="fundamento">Fundamento legal</Label>
                <Textarea
                  id="fundamento"
                  value={fundamento}
                  onChange={(e) => setFundamento(e.target.value)}
                  placeholder="Ex.: Art. 23, VIII da Lei 12.527/2011"
                  rows={2}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="autoridade">Autoridade classificadora</Label>
                <Input
                  id="autoridade"
                  value={autoridade}
                  onChange={(e) => setAutoridade(e.target.value)}
                  placeholder="Cargo/nome de quem classifica"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="prazo">
                  Prazo de restrição (anos) — máximo {prazoMax}
                </Label>
                <Input
                  id="prazo"
                  type="number"
                  min={1}
                  max={prazoMax}
                  value={prazo}
                  onChange={(e) => setPrazo(e.target.value)}
                  placeholder={`Padrão: ${prazoMax} anos`}
                />
              </div>
            </>
          )}

          {err && <p className="text-sm text-danger">{err}</p>}
        </div>
      </Dialog>
    </>
  );
}
