"use client";

import { Building2, Check, ChevronDown } from "lucide-react";
import { useRef, useState } from "react";

import { Popover } from "@/components/ui/popover";
import { useLotacaoAtiva, type LotacaoAtiva } from "@/lib/lotacao-ativa";
import { cn } from "@/lib/utils";

/**
 * A unidade em nome da qual o usuário está trabalhando, no cabeçalho — o
 * equivalente ao "DIRPRE-CDC" do SEI, sempre à vista ao lado do nome.
 *
 * Importa porque as caixas e o painel contam por ela (`unidade_ativa_dep` no
 * backend): com a troca escondida no menu da conta, quem tinha duas lotações
 * via os números mudarem sem saber de qual setor eram.
 *
 * Com 2+ lotações é um botão que abre a lista para trocar; com uma só é
 * rótulo (não há o que escolher, e um botão que não troca nada engana); sem
 * lotação nenhuma, não aparece.
 */
export function UnidadeAtiva() {
  const lotacao = useLotacaoAtiva();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  if (!lotacao.ativa) return null;

  const conteudo = (
    <>
      <Building2 className="h-4 w-4 shrink-0 opacity-90" aria-hidden="true" />
      {/* No celular a pílula tem uma linha do cabeçalho só para ela
          (`Header`), então o nome não leva teto: só trunca se passar da
          largura da tela. De sm em diante divide a linha e ganha um teto;
          o nome completo fica no `title`. */}
      <span className="min-w-0 truncate sm:max-w-[14rem] lg:max-w-[18rem]">
        {lotacao.ativa.nome}
      </span>
    </>
  );

  const pilula = cn(
    "inline-flex h-9 min-w-0 max-w-full items-center gap-1.5 rounded-full px-3",
    "bg-white/15 text-xs font-semibold text-primary-foreground sm:text-sm",
  );

  if (!lotacao.podeTrocar) {
    return (
      <span className={pilula} title={`Unidade: ${lotacao.ativa.nome}`}>
        <span className="sr-only">Unidade: </span>
        {conteudo}
      </span>
    );
  }

  const fechar = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`Unidade: ${lotacao.ativa.nome}. Trocar de unidade`}
        title={lotacao.ativa.nome}
        className={cn(
          pilula,
          "transition-colors duration-fast hover:bg-white/25",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white",
        )}
      >
        {conteudo}
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-fast", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      <Popover open={open} anchorRef={triggerRef} onClose={fechar} placement="bottom-end" className="w-72">
        <div className="px-3 py-2">
          <ListaLotacoes lotacao={lotacao} onEscolher={fechar} />
        </div>
      </Popover>
    </>
  );
}

/**
 * A lista de lotações como radiogroup — a MESMA no cabeçalho e no menu da
 * conta. Recebe o estado de `useLotacaoAtiva` em vez de chamar o hook, para
 * que quem a abre e a lista compartilhem o mesmo `trocando`.
 */
export function ListaLotacoes({
  lotacao,
  onEscolher,
}: {
  lotacao: LotacaoAtiva;
  onEscolher?: () => void;
}) {
  return (
    <div role="radiogroup" aria-label="Lotação ativa">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-foreground-muted">
        <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
        Lotação ativa
      </div>
      <div className="space-y-0.5">
        {lotacao.lotacoes.map((l) => {
          const ativa = l.id === lotacao.ativaId;
          return (
            <button
              key={l.id}
              type="button"
              role="radio"
              aria-checked={ativa}
              disabled={lotacao.trocando}
              onClick={async () => {
                await lotacao.selecionar(l.id);
                onEscolher?.();
              }}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors duration-fast",
                "hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60",
                ativa && "bg-brand/10 font-medium text-brand",
              )}
            >
              <span className="flex min-w-0 items-center gap-1.5">
                <Check
                  className={cn("h-3.5 w-3.5 shrink-0", !ativa && "invisible")}
                  aria-hidden="true"
                />
                <span className="truncate">{l.nome}</span>
              </span>
              {l.principal && (
                <span className="shrink-0 text-[10px] uppercase tracking-wide text-foreground-muted">
                  principal
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
