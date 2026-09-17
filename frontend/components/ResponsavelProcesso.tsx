"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { UserCheck, UserX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, type ProcessoDetail } from "@/lib/api";

/**
 * Quem responde pelo processo (F2).
 *
 * "Sem responsável" é escrito por extenso, não como travessão: é um **estado**
 * — pendente de designação — e não um campo em branco. A diferença importa
 * porque é esse estado que faz o processo aparecer como trabalho que ninguém
 * pegou, em vez de sumir do radar.
 *
 * O que NÃO está aqui, e por quê
 * ------------------------------
 * Não há seletor de "atribuir a outra pessoa". O backend aceita (o endpoint
 * recebe qualquer `id_usuario` e valida a lotação), mas a tela precisaria
 * listar os usuários lotados na unidade do processo, e não existe endpoint de
 * usuários filtrado por unidade. Construí-lo não é trivial como parece:
 * lotação tem DUAS representações simultâneas neste sistema
 * (`usuario.id_unidade_trabalho` e a tabela N:N `usuario_unidade_trabalho`),
 * e um filtro que olhasse só a primeira esconderia justamente o servidor que
 * atua em dois setores.
 *
 * Então esta versão entrega os dois movimentos que não precisam de busca —
 * assumir e liberar — e deixa a designação de terceiros para quando o endpoint
 * existir. O contrato do backend não muda quando isso acontecer.
 */
export function ResponsavelProcesso({
  processo,
  usuarioAtualId,
}: {
  processo: ProcessoDetail;
  usuarioAtualId: number | null;
}) {
  const qc = useQueryClient();
  const toast = useToast();

  const mutar = useMutation({
    mutationFn: (idUsuario: number | null) =>
      api.processos.atribuirResponsavel(processo.id, idUsuario),
    onSuccess: (_, idUsuario) => {
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      qc.invalidateQueries({ queryKey: ["processos"] });
      toast.success(
        idUsuario === null ? "Responsável removido" : "Processo atribuído a você",
      );
    },
    onError: (e: unknown) => {
      // A mensagem do backend é a útil aqui: ela diz POR QUE recusou (lotação
      // em outro setor), e trocá-la por um genérico esconderia a instrução.
      toast.error(e instanceof Error ? e.message : "Não foi possível atribuir");
    },
  });

  const souEu =
    usuarioAtualId !== null && processo.id_usuario_responsavel === usuarioAtualId;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm">
        <span className="text-muted-foreground">Responsável</span>{" "}
        {processo.responsavel ? (
          <b className="text-foreground">{processo.responsavel}</b>
        ) : (
          <b className="text-warning-soft-foreground">Sem responsável</b>
        )}
      </span>

      {!souEu && (
        <Button
          size="sm"
          variant="secondary"
          disabled={mutar.isPending || usuarioAtualId === null}
          onClick={() => usuarioAtualId !== null && mutar.mutate(usuarioAtualId)}
        >
          <UserCheck aria-hidden className="mr-1 h-4 w-4" />
          {/* O rótulo muda porque a ação muda de significado: tomar um processo
              sem dono não é o mesmo ato que tirá-lo de outra pessoa. */}
          {processo.id_usuario_responsavel === null
            ? "Atribuir para mim"
            : "Assumir"}
        </Button>
      )}

      {processo.id_usuario_responsavel !== null && (
        <Button
          size="sm"
          variant="ghost"
          disabled={mutar.isPending}
          onClick={() => mutar.mutate(null)}
        >
          <UserX aria-hidden className="mr-1 h-4 w-4" />
          Remover
        </Button>
      )}
    </div>
  );
}
