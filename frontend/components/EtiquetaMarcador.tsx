import type { MarcadorMini } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Etiqueta de um marcador: bolinha na cor do marcador + nome em cor de token.
 *
 * A cor vem do banco, escolhida por quem cadastrou o marcador, e pode ser
 * qualquer uma. Até aqui ela pintava o TEXTO (e um fundo translúcido dela
 * mesma): um marcador amarelo ficava ilegível no tema claro, um azul-escuro no
 * escuro. Restringir a cor à bolinha mantém o reconhecimento de relance — que é
 * o que o ícone colorido do SEI dá — e deixa o contraste do nome por conta dos
 * tokens, que já são calibrados para os dois temas.
 */
export function EtiquetaMarcador({
  marcador,
  className,
}: {
  marcador: MarcadorMini;
  className?: string;
}) {
  return (
    <span
      title={marcador.nome}
      className={cn(
        "inline-flex max-w-[10rem] items-center gap-1 rounded-badge border border-border bg-muted px-1.5 py-0.5 font-sans text-[11px] font-medium normal-case leading-none text-foreground",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="h-2 w-2 shrink-0 rounded-full border border-border"
        style={{ backgroundColor: marcador.cor }}
      />
      <span className="truncate">{marcador.nome}</span>
    </span>
  );
}

/** Quantas etiquetas cabem numa linha de tabela antes de virar "+N". */
export const MAX_MARCADORES_VISIVEIS = 3;

/**
 * Os marcadores de um processo numa linha de listagem: no máximo
 * `MAX_MARCADORES_VISIVEIS` etiquetas e um "+N" para o resto.
 *
 * Linha de tabela não pode crescer para baixo a cada marcador novo — a lista
 * deixaria de ser lida de cima a baixo. O "+N" leva os nomes escondidos no
 * `title`, e o leitor de tela recebe a lista inteira de uma vez, num texto só:
 * etiqueta por etiqueta, mais o "+2", ele leria fragmentos sem dizer o que são.
 *
 * Sem marcadores não desenha nada, nem o contêiner: a linha vazia não ganha
 * espaço em branco.
 */
export function MarcadoresDaLinha({
  marcadores,
  className,
}: {
  marcadores: MarcadorMini[] | null | undefined;
  className?: string;
}) {
  if (!marcadores || marcadores.length === 0) return null;
  const visiveis = marcadores.slice(0, MAX_MARCADORES_VISIVEIS);
  const ocultos = marcadores.slice(MAX_MARCADORES_VISIVEIS);
  const todos = marcadores.map((m) => m.nome).join(", ");
  return (
    <div className={cn("mt-1 flex flex-wrap items-center gap-1", className)}>
      <span className="sr-only">Marcadores: {todos}</span>
      <span aria-hidden="true" className="contents">
        {visiveis.map((m) => (
          <EtiquetaMarcador key={m.id} marcador={m} />
        ))}
        {ocultos.length > 0 && (
          <span
            title={ocultos.map((m) => m.nome).join(", ")}
            className="inline-flex items-center rounded-badge border border-border px-1.5 py-0.5 font-sans text-[11px] font-medium leading-none text-foreground-muted"
          >
            +{ocultos.length}
          </span>
        )}
      </span>
    </div>
  );
}
