"use client";

/**
 * IA-1 — assistente conversacional com escopo de UM processo já aberto.
 *
 * Vive dentro da tela do processo, e isso é a fatia inteira: ele não busca,
 * não lista, não encontra. O usuário já atravessou permissão, contratação de
 * módulo e sigilo para chegar até aqui; o assistente só reduz o esforço de ler
 * o que já está na tela. Ver a spec IA-1 §2 para por que a busca ficou fora.
 *
 * **Não guarda histórico em lugar nenhum.** A conversa vive neste componente
 * enquanto a tela está aberta e some ao sair. A razão é LGPD, não preguiça:
 * persistir pergunta e resposta criaria um repositório novo de conteúdo ligado
 * a processo — potencialmente sigiloso — com retenção a definir.
 */

import { Bot, Loader2, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, iaApi } from "@/lib/api";

interface Props {
  processoId: number;
}

interface Turno {
  autor: "usuario" | "assistente";
  texto: string;
}

const SUGESTOES = [
  "Resuma o andamento deste processo.",
  "O que significa a última movimentação?",
  "Como está o prazo?",
];

export function AssistenteProcesso({ processoId }: Props) {
  const [disponivel, setDisponivel] = useState<boolean | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [pergunta, setPergunta] = useState("");
  const [respondendo, setRespondendo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let vivo = true;
    iaApi
      .iaDisponivel()
      .then((r: { disponivel: boolean }) => vivo && setDisponivel(r.disponivel))
      // Falha na checagem = trata como indisponível. Melhor não oferecer do
      // que oferecer algo que vai dar erro quando o usuário já digitou.
      .catch(() => vivo && setDisponivel(false));
    return () => {
      vivo = false;
    };
  }, []);

  // Aborta o stream em curso ao desmontar — sem isto, sair da página deixa a
  // requisição correndo e o `setState` dispara em componente desmontado.
  useEffect(() => () => abortRef.current?.abort(), []);

  async function enviar(texto: string) {
    const limpo = texto.trim();
    if (!limpo || respondendo) return;

    setErro(null);
    setPergunta("");
    setTurnos((t) => [...t, { autor: "usuario", texto: limpo }, { autor: "assistente", texto: "" }]);
    setRespondendo(true);

    const controle = new AbortController();
    abortRef.current = controle;

    try {
      await iaApi.iaPerguntarSobreProcesso(
        processoId,
        limpo,
        (pedaco: string) => {
          // Acumula no último turno, que é sempre o do assistente.
          setTurnos((t) => {
            const copia = [...t];
            const ultimo = copia[copia.length - 1];
            if (ultimo?.autor === "assistente") {
              copia[copia.length - 1] = { ...ultimo, texto: ultimo.texto + pedaco };
            }
            return copia;
          });
        },
        controle.signal,
      );
    } catch (e) {
      if (controle.signal.aborted) return;
      const msg =
        e instanceof ApiError
          ? e.status === 404
            ? "Processo não encontrado."
            : e.message
          : "Não foi possível responder agora.";
      setErro(msg);
      // Remove o turno vazio do assistente — deixá-lo produz uma bolha em
      // branco que parece resposta vazia em vez de erro.
      setTurnos((t) =>
        t[t.length - 1]?.autor === "assistente" && t[t.length - 1]?.texto === ""
          ? t.slice(0, -1)
          : t,
      );
    } finally {
      setRespondendo(false);
      abortRef.current = null;
    }
  }

  // Enquanto verifica, não pisca: não renderiza nada.
  if (disponivel === null || disponivel === false) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-4 w-4" aria-hidden />
          Assistente
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Responde apenas sobre <strong>este</strong> processo, com base no que
          está registrado nele. Não consulta outros processos e não substitui a
          leitura dos autos.
        </p>

        {turnos.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGESTOES.map((s) => (
              <Button
                key={s}
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void enviar(s)}
              >
                {s}
              </Button>
            ))}
          </div>
        )}

        {turnos.length > 0 && (
          <div className="space-y-3" aria-live="polite">
            {turnos.map((t, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <div className="mt-0.5 shrink-0 text-muted-foreground">
                  {t.autor === "usuario" ? (
                    <User className="h-4 w-4" aria-hidden />
                  ) : (
                    <Bot className="h-4 w-4" aria-hidden />
                  )}
                  <span className="sr-only">
                    {t.autor === "usuario" ? "Você" : "Assistente"}
                  </span>
                </div>
                <div className="whitespace-pre-wrap">
                  {t.texto ||
                    (respondendo && i === turnos.length - 1 ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-label="Respondendo" />
                    ) : null)}
                </div>
              </div>
            ))}
          </div>
        )}

        {erro && (
          <div
            role="alert"
            className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {erro}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void enviar(pergunta);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={pergunta}
            onChange={(e) => setPergunta(e.target.value)}
            placeholder="Pergunte sobre este processo..."
            aria-label="Pergunta sobre este processo"
            disabled={respondendo}
            maxLength={1000}
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-50"
          />
          <Button type="submit" size="sm" disabled={respondendo || !pergunta.trim()}>
            {respondendo ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="h-4 w-4" aria-hidden />
            )}
            <span className="sr-only">Enviar pergunta</span>
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
