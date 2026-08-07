"""Guarda: nenhum caminho de produção GRAVA MD5.

Contexto. `utils.usuario` e `utils.usuario_externo` são tabelas do PHP legado e
têm duas colunas de senha: `senha` (MD5, sem sal) e `senha_bcrypt`. O sistema
inteiro migrou para gravar só bcrypt — provisionamento, criação de usuário,
reset e troca todos escrevem `senha=""`. O **cadastro público de cidadão** ficou
para trás e seguiu gravando `hash_md5(payload.senha)` até 2026-08-06, "por
compat PHP".

Por que isso importa mais do que parece: MD5 sem sal de senha escolhida por
pessoa é reversível por rainbow table em tempo de consulta. A senha estava, na
prática, em claro — num banco compartilhado com o legado, para servir um portal
que este projeto decidiu não sustentar. E era a porta MAIS exposta: qualquer um
se cadastra pela rua, sem convite e sem servidor no meio.

O que esta guarda trava:

1. `hash_md5` não é chamado em `app/` — só definido em `auth/password.py`, onde
   `verify_md5` o consome para AUTENTICAR credencial que já estava no banco.
2. Nada além de string vazia é gravado na coluna `senha` — nem por atribuição
   (`u.senha = x`) nem por construtor de modelo (`UsuarioExterno(senha=x)`).

O que ela NÃO trava, e é deliberado: `verify_md5` continua vivo. Apagá-lo hoje
trancaria para fora todo usuário cujo banco só tem MD5 e que ainda não fez
login. A rampa de saída é o login: autentica por MD5, grava bcrypt e **zera o
MD5** no mesmo ato (`routers/auth.py`, `services/cidadao_auth.py`). O dia em que
`verify_md5` puder morrer é o dia em que sobrar zero linha com `senha <> ''` —
isso é uma medição no banco, não um teste.

**Por que `ast` e não regex.** A primeira versão varria linha a linha com
expressão regular e produziu cinco falsos positivos de duas espécies: leu o
texto DESTE docstring como se fosse código, e não distinguiu
`provisionar_tenant(senha=<senha em claro>)` — argumento de função que aplica
bcrypt lá dentro — de gravação na coluna. Uma guarda que grita no caso legítimo
é desligada por quem tropeça nela, e aí não guarda mais nada.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# `auth/password.py` é a casa da função: define `hash_md5` e o `verify_md5` que
# a chama. É o único lugar onde o nome pode aparecer.
CASA = APP / "auth" / "password.py"


def _arquivos_de_producao() -> list[Path]:
    return [p for p in sorted(APP.rglob("*.py")) if p != CASA]


def _arvore(arquivo: Path) -> ast.Module:
    return ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))


def _nome_chamado(no: ast.Call) -> str:
    """`hash_md5(...)` → 'hash_md5'; `password.hash_md5(...)` → 'hash_md5'."""
    alvo = no.func
    if isinstance(alvo, ast.Name):
        return alvo.id
    if isinstance(alvo, ast.Attribute):
        return alvo.attr
    return ""


def _e_string_vazia(no: ast.expr) -> bool:
    return isinstance(no, ast.Constant) and no.value == ""


def test_nenhum_codigo_de_producao_chama_hash_md5() -> None:
    """MD5 é rampa de saída: só se lê, nunca se escreve."""
    infratores: list[str] = []
    for arquivo in _arquivos_de_producao():
        for no in ast.walk(_arvore(arquivo)):
            if isinstance(no, ast.Call) and _nome_chamado(no) == "hash_md5":
                infratores.append(f"{arquivo.relative_to(APP.parent)}:{no.lineno}")

    assert not infratores, (
        "`hash_md5` chamado em código de produção: "
        + "; ".join(infratores)
        + ". MD5 sem sal de senha escolhida por pessoa é reversível por rainbow "
        "table — gravá-lo é guardar a senha em claro. Grave só "
        '`senha_bcrypt=hash_password(...)` e deixe `senha=""`. Se a intenção '
        "for autenticar credencial legada, use `verify_password`, que já cai "
        "no MD5 sozinho e devolve `needs_rehash`."
    )


def test_nada_alem_de_vazio_e_gravado_na_coluna_senha() -> None:
    """Pega o mesmo defeito pelo outro lado.

    O teste acima procura o NOME da função; este procura o DESTINO. Um helper
    novo chamado `hash_legado()` passaria naquele e seria pego aqui.

    Só conta como gravação o que vai para a coluna: atributo `.senha` de um
    objeto, ou argumento `senha=` de um construtor de modelo (chamada a um nome
    que começa com maiúscula). `provisionar_tenant(senha=...)` recebe a senha em
    CLARO e aplica bcrypt lá dentro — não é gravação, e não entra aqui.
    """
    infratores: list[str] = []
    for arquivo in _arquivos_de_producao():
        rel = arquivo.relative_to(APP.parent)
        for no in ast.walk(_arvore(arquivo)):
            if isinstance(no, ast.Assign):
                for alvo in no.targets:
                    if (
                        isinstance(alvo, ast.Attribute)
                        and alvo.attr == "senha"
                        and not _e_string_vazia(no.value)
                    ):
                        infratores.append(f"{rel}:{no.lineno}: <obj>.senha = ...")
            elif isinstance(no, ast.Call):
                chamado = _nome_chamado(no)
                if not (chamado[:1].isupper()):
                    continue  # não é construtor de modelo
                for kw in no.keywords:
                    if kw.arg == "senha" and not _e_string_vazia(kw.value):
                        infratores.append(f"{rel}:{no.lineno}: {chamado}(senha=...)")

    assert not infratores, (
        "Gravação na coluna `senha` (MD5 legado) com valor calculado: "
        + "; ".join(infratores)
        + '. Essa coluna só pode receber `""`. A senha vai para `senha_bcrypt`, '
        "via `hash_password(...)`."
    )


def test_a_guarda_enxerga_o_arquivo_certo() -> None:
    """Controle contra verde por vacuidade.

    Se `auth/password.py` for renomeado ou movido, `CASA` deixa de existir, a
    exclusão vira inócua e os dois testes acima passam a afirmar sobre um
    conjunto que não inclui o arquivo mais importante — em silêncio.
    """
    assert CASA.exists(), (
        f"`{CASA}` não existe. A guarda exclui esse caminho da varredura; se o "
        "módulo mudou de lugar, atualize CASA."
    )
    texto = CASA.read_text(encoding="utf-8")
    assert "def hash_md5" in texto, (
        "`hash_md5` não está mais em auth/password.py. Se foi removido de vez "
        "(todas as linhas já convertidas para bcrypt), remova esta guarda "
        "inteira — ela virou decorativa. Se só mudou de arquivo, atualize CASA."
    )
    assert len(_arquivos_de_producao()) > 50, (
        "a varredura achou pouquíssimos arquivos em app/ — o caminho está "
        "errado e os testes acima estão verdes por não olharem nada."
    )
