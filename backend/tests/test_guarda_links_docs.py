"""Guarda dos ponteiros para documentação: todo `.md` citado tem de existir.

Por que isto vira teste, e não disciplina de revisão
----------------------------------------------------
O docstring de uma migration cita o spec como **autoridade** da decisão:

    # 0081_transporte_recadastramento.py
    Spec: `docs/superpowers/specs/2026-08-04-transporte-p5-1-...-design.md`.

Esse ponteiro é a única trilha de "por que esta tabela é assim". Quando ele
aponta para o nada, a resposta não fica errada — fica **inalcançável**, e o
próximo a mexer na tabela reinventa a decisão sem saber que houve uma.

O defeito não tem sintoma. Nada quebra, nenhum teste fica vermelho, o build
passa. Ele só aparece no dia em que alguém segue o ponteiro — e aí o custo já
foi pago.

Medição de 2026-08-27, quando esta guarda nasceu: **4 caminhos quebrados**
citados por 7 arquivos de código.

  - `...p8-workflows-master.md`, citado por 4 migrations (0095–0098). O spec
    nasceu (`d61b3a2`) com sufixo `-design.md`; arquivo com aquele nome **nunca
    existiu**. Ficou quebrado desde o primeiro commit.
  - 3 caminhos em `docs/` que o arquivamento de 2026-08-25 moveu para
    `docs/archive/` sem atualizar quem os citava (migration `0030`,
    `services/pagamentos_excecoes.py`, `models/complementacao_documental.py`).

Os dois modos de falha são diferentes e ambos precisam de rede: o primeiro é
erro de digitação que nenhuma revisão pegou em meses; o segundo é a mudança de
pasta que move o arquivo e esquece os ponteiros.

O que esta guarda NÃO faz
-------------------------
Não confere se o conteúdo apontado ainda é verdade — só que o arquivo existe.
Ponteiro para spec obsoleto passa aqui. Frescor de documento é assunto do
cabeçalho `Última verificação:` (ver `docs/INDEX.md`), não desta guarda.

Não varre `docs/archive/`. Por decisão registrada em `docs/archive/README.md`,
arquivo arquivado **não é atualizado** depois de arquivado — inclusive seus
links. Cobrá-los aqui obrigaria a editar histórico para calar um teste, que é
exatamente o que aquela pasta existe para evitar.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Onde procurar citação. `frontend/` entra sem `node_modules` — as libs
# vendorizadas citam a própria documentação (`docs/configuration.md` do
# @reduxjs/toolkit, por exemplo) e nada disso é nosso.
DIRS_CODIGO = ("backend", "scripts", "ci", ".github", "nginx", "frontend")
EXTENSOES_CODIGO = (".py", ".yml", ".yaml", ".sh", ".sql", ".ts", ".tsx", ".conf")

EXCLUIDOS = ("node_modules", ".git", ".next", "__pycache__", "venv", ".venv")

# Este próprio arquivo. O docstring acima cita caminhos ILUSTRATIVOS — inclusive
# os quatro quebrados que motivaram a guarda, de propósito. São prosa, não
# ponteiro: se a guarda se varresse, para ficar verde teria de apagar a
# explicação de por que existe. Foi o primeiro vermelho dela, ao ser invertida.
AUTO = Path(__file__).resolve()

# Caminho de repositório citado em código: começa por um diretório de topo que
# existe aqui. Ancorar nos nomes reais evita casar `docs/configuration.md` de
# uma lib de terceiro que tenha escapado do filtro de `node_modules`.
TOPOS = ("docs", "backend", "frontend", "scripts", "ci", "nginx", "keys", "tests-e2e")
CITACAO_CODIGO = re.compile(
    r"\b(?:" + "|".join(TOPOS) + r")/[A-Za-z0-9_.()/-]+\.md\b"
)

# Link markdown relativo, para QUALQUER arquivo do repo — não só `.md`.
#
# Limitar a `.md` foi a primeira versão desta guarda, e ela deixou passar 50
# ponteiros quebrados de uma vez: ao mover o changelog do `README.md` para
# `docs/`, todo link `](backend/app/...)` que era relativo à raiz passou a
# resolver a partir de `docs/`. A guarda acusou **um** (o único `.md` do lote) e
# ficou verde sobre os outros 49. Documento que aponta para código é a metade
# mais útil da documentação; era exatamente o que não estava coberto.
# Um nível de parênteses aninhado é obrigatório: as rotas do Next usam grupos
# entre parênteses (`frontend/app/(app)/...`), e um regex ganancioso por `)`
# trunca o caminho em `.../app/(app` — que "não existe" e vira falso positivo.
LINK_MD = re.compile(r"\[[^\]]*\]\(((?:[^()\s#]|\([^()]*\))+)(?:#[^)]*)?\)")

# Extensões e diretórios que valem a pena conferir. Um link pode apontar para
# um diretório (`docs/archive/`) ou para uma âncora de página web; o que
# interessa aqui é o ponteiro para um artefato versionado deste repositório.
def _e_caminho_do_repo(destino: str) -> bool:
    if destino.startswith(("http://", "https://", "mailto:", "#", "<")):
        return False
    # `{id}`, `<slug>` etc. são placeholders de rota em prosa, não caminhos.
    if any(c in destino for c in "{}<>*"):
        return False
    return True


def _arquivos(dirs: tuple[str, ...], extensoes: tuple[str, ...]) -> list[Path]:
    achados: list[Path] = []
    for d in dirs:
        base = RAIZ / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in extensoes:
                continue
            if any(parte in EXCLUIDOS for parte in p.parts):
                continue
            if p.resolve() == AUTO:
                continue
            achados.append(p)
    return achados


def _markdown_vivo() -> list[Path]:
    """Todo `.md` do repo fora de `archive/`, `node_modules` e afins."""
    vivos = []
    for p in RAIZ.rglob("*.md"):
        if any(parte in EXCLUIDOS for parte in p.parts):
            continue
        if "archive" in p.parts:
            continue
        # `.superpowers/` é scratch de execução de plano, git-ignored.
        if ".superpowers" in p.parts:
            continue
        vivos.append(p)
    return vivos


def _texto(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def test_todo_md_citado_em_codigo_existe():
    """Migration/service que cita um spec tem de citar um spec que existe."""
    quebrados: list[str] = []
    total = 0
    for arq in _arquivos(DIRS_CODIGO, EXTENSOES_CODIGO):
        for m in CITACAO_CODIGO.finditer(_texto(arq)):
            total += 1
            alvo = RAIZ / m.group(0)
            if not alvo.is_file():
                quebrados.append(f"{arq.relative_to(RAIZ)} -> {m.group(0)}")

    assert total >= 15, (
        f"a varredura achou só {total} citações — quase certamente o regex ou a "
        "lista de diretórios quebrou, e um teste que não olha nada passa sempre"
    )
    assert not quebrados, (
        "caminho de documentação citado em código não existe:\n  "
        + "\n  ".join(sorted(quebrados))
        + "\n\nMoveu um doc? Atualize quem o cita. Se o destino foi arquivado, "
        "o ponteiro vira `docs/archive/...`."
    )


def test_todo_link_relativo_em_doc_vivo_existe():
    """Link de prosa em documento vivo tem de resolver — doc OU código."""
    quebrados: list[str] = []
    total = 0
    for arq in _markdown_vivo():
        for m in LINK_MD.finditer(_texto(arq)):
            destino = m.group(1)
            if not _e_caminho_do_repo(destino):
                continue
            total += 1
            alvo = (arq.parent / destino).resolve()
            # Aceita arquivo OU diretório: `](archive/)` é ponteiro legítimo.
            if not alvo.exists():
                quebrados.append(f"{arq.relative_to(RAIZ)} -> {destino}")

    # O piso é folgado de propósito — existe para pegar regex quebrado (que
    # zera a conta), não para travar o número.
    assert total >= 50, (
        f"a varredura achou só {total} links — o regex provavelmente quebrou"
    )
    assert not quebrados, (
        "link relativo em documento vivo aponta para caminho inexistente:\n  "
        + "\n  ".join(sorted(quebrados))
    )
