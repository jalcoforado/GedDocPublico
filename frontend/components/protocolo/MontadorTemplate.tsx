"use client";

import {
  AlignCenter,
  AlignLeft,
  Braces,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Copy,
  GripVertical,
  Heading,
  LayoutTemplate,
  Minus,
  PenLine,
  Pilcrow,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import {
  CATALOGO_BLOCOS,
  ROTULO_BLOCO,
  copiarBloco,
  moverPara,
  novoBloco,
  type Bloco,
  type TipoBloco,
} from "@/lib/template-blocos";
import { cn } from "@/lib/utils";

const ICONE: Record<TipoBloco, LucideIcon> = {
  titulo: Heading,
  texto: Pilcrow,
  campo: Braces,
  data_local: CalendarDays,
  assinatura: PenLine,
  separador: Minus,
};

/** Tipos de dado no arrasto: bloco novo (da paleta) × bloco que já está na folha. */
const DT_NOVO = "application/x-aprimora-bloco-novo";
const DT_MOVER = "application/x-aprimora-bloco-mover";

function ehArrastoDeBloco(dt: DataTransfer | null): boolean {
  const tipos = Array.from(dt?.types ?? []);
  return tipos.includes(DT_NOVO) || tipos.includes(DT_MOVER);
}

/** Esqueleto de documento oficial — o ponto de partida de quem não quer folha em branco. */
const ESQUELETO: TipoBloco[] = ["titulo", "texto", "data_local", "assinatura"];

export interface CampoDisponivel {
  chave: string;
  descricao: string;
}

/**
 * Montador de template por blocos (SI-31, primeira versão).
 *
 * - Paleta numa faixa acima da folha: arrastar um bloco para a folha o põe onde for solto;
 *   clicar põe no fim.
 * - Na folha, cada bloco se arrasta pela alça (⋮⋮) para mudar de lugar.
 *   A alça é o único ponto de arrasto — o resto do bloco tem campos de
 *   texto, e um bloco inteiro arrastável roubaria a seleção do texto.
 * - Teclado e leitor de tela: Subir/Descer/Duplicar/Remover em cada bloco,
 *   e cada mudança é anunciada.
 *
 * Arrasto nativo do HTML (como o organograma) — sem biblioteca nova.
 */
export function MontadorTemplate({
  blocos,
  onChange,
  campos,
  onUploadImage,
}: {
  blocos: Bloco[];
  onChange: (blocos: Bloco[]) => void;
  campos: CampoDisponivel[];
  onUploadImage?: (file: File) => Promise<string>;
}) {
  const [alvo, setAlvo] = useState<number | null>(null);
  const [arrastando, setArrastando] = useState<string | null>(null);
  // Bloco cuja alça está pressionada: só ele fica `draggable`.
  const [pegando, setPegando] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [focar, setFocar] = useState<string | null>(null);
  const refs = useRef(new Map<string, HTMLElement>());

  // Bloco recém-posto ganha foco no primeiro campo e entra na vista.
  useEffect(() => {
    if (!focar) return;
    const el = refs.current.get(focar);
    el?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
    el?.querySelector<HTMLElement>("input, select, [contenteditable=true]")?.focus();
    setFocar(null);
  }, [focar, blocos]);

  function inserir(tipo: TipoBloco, pos = blocos.length) {
    const b = novoBloco(tipo);
    const nova = blocos.slice();
    nova.splice(pos, 0, b);
    onChange(nova);
    setFocar(b.id);
    setAviso(`${ROTULO_BLOCO[tipo]} adicionado na posição ${pos + 1} de ${nova.length}.`);
  }

  function mover(de: number, para: number) {
    const nova = moverPara(blocos, de, para);
    if (nova === blocos) return;
    onChange(nova);
    const agora = nova.indexOf(blocos[de]);
    setAviso(`${ROTULO_BLOCO[blocos[de].tipo]} movido para a posição ${agora + 1} de ${nova.length}.`);
  }

  function atualizar(id: string, patch: Partial<Bloco>) {
    onChange(blocos.map((b) => (b.id === id ? ({ ...b, ...patch } as Bloco) : b)));
  }

  function duplicar(i: number) {
    const c = copiarBloco(blocos[i]);
    const nova = blocos.slice();
    nova.splice(i + 1, 0, c);
    onChange(nova);
    setFocar(c.id);
    setAviso(`${ROTULO_BLOCO[c.tipo]} duplicado.`);
  }

  function remover(i: number) {
    onChange(blocos.filter((_, j) => j !== i));
    setAviso(`${ROTULO_BLOCO[blocos[i].tipo]} removido.`);
  }

  function indiceNoPonto(y: number): number {
    for (let i = 0; i < blocos.length; i += 1) {
      const r = refs.current.get(blocos[i].id)?.getBoundingClientRect();
      if (r && y < r.top + r.height / 2) return i;
    }
    return blocos.length;
  }

  function fimDoArrasto() {
    setAlvo(null);
    setArrastando(null);
    setPegando(null);
  }

  return (
    <div className="space-y-2">
      <p aria-live="polite" className="sr-only">
        {aviso}
      </p>

      {/* ── Paleta ──
          Uma faixa de fichas acima da folha, não uma coluna ao lado: a coluna
          comia ~13rem que fazem falta quando a prévia está aberta. Fica presa
          no topo ao rolar — o bloco está sempre à mão para arrastar. A
          descrição de cada bloco vai no `title`. */}
      <div
        role="group"
        aria-labelledby="paleta-blocos-titulo"
        className="sticky top-0 z-sticky flex flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface-1 px-2 py-1.5 shadow-sm"
      >
        <span id="paleta-blocos-titulo" className="mr-1 text-xs font-semibold text-foreground">
          Blocos
          <span className="ml-1 hidden font-normal text-foreground-muted sm:inline">
            · arraste para a folha ou clique
          </span>
        </span>
        {CATALOGO_BLOCOS.map((info) => {
          const Icone = ICONE[info.tipo];
          return (
            <button
              key={info.tipo}
              type="button"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(DT_NOVO, info.tipo);
                e.dataTransfer.effectAllowed = "copy";
              }}
              onDragEnd={fimDoArrasto}
              onClick={() => inserir(info.tipo)}
              aria-label={`Adicionar bloco ${info.rotulo}`}
              title={info.descricao}
              className={cn(
                "inline-flex cursor-grab items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-foreground",
                "transition-colors duration-fast hover:border-brand/50 hover:bg-surface-2 active:cursor-grabbing",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <Icone className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
              {info.rotulo}
            </button>
          );
        })}
      </div>

      {/* ── Folha ── */}
      <div
        role="list"
        aria-label="Blocos do modelo"
        onDragOver={(e) => {
          if (!ehArrastoDeBloco(e.dataTransfer)) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = Array.from(e.dataTransfer.types).includes(DT_NOVO) ? "copy" : "move";
          setAlvo(indiceNoPonto(e.clientY));
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAlvo(null);
        }}
        onDrop={(e) => {
          if (!ehArrastoDeBloco(e.dataTransfer)) return;
          e.preventDefault();
          const pos = alvo ?? indiceNoPonto(e.clientY);
          const tipo = e.dataTransfer.getData(DT_NOVO) as TipoBloco;
          const id = e.dataTransfer.getData(DT_MOVER);
          if (tipo && ROTULO_BLOCO[tipo]) inserir(tipo, pos);
          else if (id) {
            const de = blocos.findIndex((b) => b.id === id);
            if (de >= 0) mover(de, pos);
          }
          fimDoArrasto();
        }}
        className={cn(
          "min-h-[14rem] rounded-lg border bg-surface-1 p-3 transition-colors duration-fast",
          alvo !== null ? "border-brand/60" : "border-border",
        )}
      >
        {blocos.length === 0 ? (
          <div
            className={cn(
              "flex h-full min-h-[12rem] flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed px-6 text-center",
              alvo !== null ? "border-brand bg-brand/5" : "border-border",
            )}
          >
            <LayoutTemplate className="h-8 w-8 text-foreground-subtle" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-foreground">
                {alvo !== null ? "Solte para começar o modelo" : "Arraste um bloco para cá"}
              </p>
              <p className="mt-0.5 text-xs text-foreground-muted">
                ou clique num bloco da lista para ele entrar no fim.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                const nova = ESQUELETO.map(novoBloco);
                onChange(nova);
                setFocar(nova[0].id);
                setAviso("Esqueleto de ofício montado: título, texto, data e local, assinatura.");
              }}
              className="rounded-md text-xs font-medium text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Começar com o esqueleto de um ofício
            </button>
          </div>
        ) : (
          <div className="space-y-0">
            {blocos.map((b, i) => (
              <div key={b.id}>
                <IndicadorSoltar ativo={alvo === i} />
                <CartaoBloco
                  bloco={b}
                  posicao={i}
                  total={blocos.length}
                  campos={campos}
                  onUploadImage={onUploadImage}
                  arrastando={arrastando === b.id}
                  arrastavel={pegando === b.id}
                  registrar={(el) => {
                    if (el) refs.current.set(b.id, el);
                    else refs.current.delete(b.id);
                  }}
                  onPegar={() => setPegando(b.id)}
                  onSoltarAlca={() => setPegando(null)}
                  onDragStart={(e) => {
                    e.dataTransfer.setData(DT_MOVER, b.id);
                    e.dataTransfer.effectAllowed = "move";
                    setArrastando(b.id);
                  }}
                  onDragEnd={fimDoArrasto}
                  onAtualizar={(patch) => atualizar(b.id, patch)}
                  onSubir={() => mover(i, i - 1)}
                  onDescer={() => mover(i, i + 2)}
                  onDuplicar={() => duplicar(i)}
                  onRemover={() => remover(i)}
                />
              </div>
            ))}
            <IndicadorSoltar ativo={alvo === blocos.length} />
          </div>
        )}
      </div>
    </div>
  );
}

/** Linha que mostra onde o bloco vai cair. Ocupa altura fixa: a folha não pula. */
function IndicadorSoltar({ ativo }: { ativo: boolean }) {
  return (
    <div aria-hidden="true" className="flex h-3 items-center">
      <div
        className={cn(
          "h-0.5 w-full rounded-full transition-colors duration-fast",
          ativo ? "bg-brand" : "bg-transparent",
        )}
      />
    </div>
  );
}

function BotaoIcone({
  label,
  icon: Icone,
  onClick,
  disabled,
  perigo,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  perigo?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast",
        "hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-35",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        perigo && "hover:bg-danger-soft hover:text-danger-soft-foreground",
      )}
    >
      <Icone className="h-3.5 w-3.5" aria-hidden="true" />
    </button>
  );
}

function CartaoBloco({
  bloco: b,
  posicao,
  total,
  campos,
  onUploadImage,
  arrastando,
  arrastavel,
  registrar,
  onPegar,
  onSoltarAlca,
  onDragStart,
  onDragEnd,
  onAtualizar,
  onSubir,
  onDescer,
  onDuplicar,
  onRemover,
}: {
  bloco: Bloco;
  posicao: number;
  total: number;
  campos: CampoDisponivel[];
  onUploadImage?: (file: File) => Promise<string>;
  arrastando: boolean;
  arrastavel: boolean;
  registrar: (el: HTMLElement | null) => void;
  onPegar: () => void;
  onSoltarAlca: () => void;
  onDragStart: (e: React.DragEvent) => void;
  onDragEnd: () => void;
  onAtualizar: (patch: Partial<Bloco>) => void;
  onSubir: () => void;
  onDescer: () => void;
  onDuplicar: () => void;
  onRemover: () => void;
}) {
  const Icone = ICONE[b.tipo];
  const rotulo = ROTULO_BLOCO[b.tipo];
  return (
    <section
      ref={registrar}
      role="listitem"
      aria-label={`${rotulo}, bloco ${posicao + 1} de ${total}`}
      draggable={arrastavel}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        "rounded-lg border border-border bg-card shadow-sm transition-opacity duration-fast",
        arrastando && "opacity-40",
      )}
    >
      <header className="flex items-center gap-1 border-b border-border px-1.5 py-1">
        <span
          onPointerDown={onPegar}
          onPointerUp={onSoltarAlca}
          title="Arraste para mudar de lugar"
          aria-hidden="true"
          className="flex h-7 w-6 cursor-grab items-center justify-center rounded text-foreground-subtle hover:bg-muted hover:text-foreground active:cursor-grabbing"
        >
          <GripVertical className="h-4 w-4" />
        </span>
        <Icone className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
        <span className="ml-1 text-xs font-semibold uppercase tracking-wide text-foreground-muted">
          {rotulo}
        </span>
        <span className="ml-auto flex items-center">
          <BotaoIcone label={`Subir ${rotulo}`} icon={ChevronUp} onClick={onSubir} disabled={posicao === 0} />
          <BotaoIcone
            label={`Descer ${rotulo}`}
            icon={ChevronDown}
            onClick={onDescer}
            disabled={posicao === total - 1}
          />
          <BotaoIcone label={`Duplicar ${rotulo}`} icon={Copy} onClick={onDuplicar} />
          <BotaoIcone label={`Remover ${rotulo}`} icon={Trash2} onClick={onRemover} perigo />
        </span>
      </header>
      <div className="p-3">
        <EditorDoBloco bloco={b} campos={campos} onUploadImage={onUploadImage} onAtualizar={onAtualizar} />
      </div>
    </section>
  );
}

function EditorDoBloco({
  bloco: b,
  campos,
  onUploadImage,
  onAtualizar,
}: {
  bloco: Bloco;
  campos: CampoDisponivel[];
  onUploadImage?: (file: File) => Promise<string>;
  onAtualizar: (patch: Partial<Bloco>) => void;
}) {
  switch (b.tipo) {
    case "titulo":
      return (
        <div className="flex items-end gap-2">
          <div className="min-w-0 flex-1 space-y-1">
            <Label htmlFor={`${b.id}-texto`}>Texto do título</Label>
            <Input
              id={`${b.id}-texto`}
              value={b.texto}
              onChange={(e) => onAtualizar({ texto: e.target.value })}
              placeholder="Ex.: Ofício de encaminhamento"
            />
          </div>
          <div role="group" aria-label="Alinhamento do título" className="flex rounded-md border border-border p-0.5">
            {(
              [
                ["center", "Centralizado", AlignCenter],
                ["left", "À esquerda", AlignLeft],
              ] as const
            ).map(([valor, nome, I]) => (
              <button
                key={valor}
                type="button"
                aria-pressed={b.alinhamento === valor}
                aria-label={nome}
                title={nome}
                onClick={() => onAtualizar({ alinhamento: valor })}
                className={cn(
                  "inline-flex h-8 w-8 items-center justify-center rounded transition-colors duration-fast",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  b.alinhamento === valor ? "bg-brand/10 text-brand" : "text-foreground-muted hover:bg-muted",
                )}
              >
                <I className="h-4 w-4" aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      );
    case "texto":
      return (
        <RichTextEditor
          value={b.html}
          onChange={(html) => onAtualizar({ html })}
          minHeight={96}
          placeholder="Escreva o texto. “Inserir campo…” põe um dado do processo onde está o cursor."
          ariaLabel="Texto do bloco"
          campos={campos}
          onUploadImage={onUploadImage}
        />
      );
    case "campo":
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`${b.id}-rotulo`}>
              Rótulo <span className="text-xs font-normal text-foreground-subtle">opcional</span>
            </Label>
            <Input
              id={`${b.id}-rotulo`}
              value={b.rotulo}
              onChange={(e) => onAtualizar({ rotulo: e.target.value })}
              placeholder="Ex.: Processo"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${b.id}-chave`}>Dado do processo</Label>
            <Select
              id={`${b.id}-chave`}
              value={b.chave}
              onChange={(e) => onAtualizar({ chave: e.target.value })}
            >
              {/* A chave gravada continua escolhida mesmo se sair do catálogo. */}
              {!campos.some((c) => c.chave === b.chave) && (
                <option value={b.chave}>{`{{${b.chave}}}`}</option>
              )}
              {campos.map((c) => (
                <option key={c.chave} value={c.chave}>
                  {c.descricao}
                </option>
              ))}
            </Select>
          </div>
        </div>
      );
    case "data_local":
      return (
        <div className="space-y-1">
          <Label htmlFor={`${b.id}-local`}>Cidade</Label>
          <Input
            id={`${b.id}-local`}
            value={b.local}
            onChange={(e) => onAtualizar({ local: e.target.value })}
            placeholder="Ex.: Itaitinga"
          />
          <p className="text-xs text-foreground-muted">
            A data é a do dia em que o documento for redigido.
          </p>
        </div>
      );
    case "assinatura":
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`${b.id}-nome`}>Nome</Label>
            <Input
              id={`${b.id}-nome`}
              value={b.nome}
              onChange={(e) => onAtualizar({ nome: e.target.value })}
            />
            <p className="text-xs text-foreground-muted">
              {"{{usuario.nome}}"} = quem redigir o documento.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${b.id}-cargo`}>
              Cargo <span className="text-xs font-normal text-foreground-subtle">opcional</span>
            </Label>
            <Input
              id={`${b.id}-cargo`}
              value={b.cargo}
              onChange={(e) => onAtualizar({ cargo: e.target.value })}
              placeholder="Ex.: Secretário de Administração"
            />
          </div>
        </div>
      );
    case "separador":
      return <p className="text-xs text-foreground-muted">Linha horizontal entre duas partes do documento.</p>;
  }
}
