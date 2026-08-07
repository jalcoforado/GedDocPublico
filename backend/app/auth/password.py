"""Verificação e hashing de senhas — bcrypt, com MD5 legado só de LEITURA.

Estratégia transparente (Fase 9.2):
  - `verify_password(plain, bcrypt_hash, md5_hash)`:
      * Tenta bcrypt primeiro (campo `senha_bcrypt`).
      * Cai pra MD5 (campo `senha`) se bcrypt for None ou inválido.
      * Retorna `(ok, needs_rehash)` — `needs_rehash=True` quando autenticou
        via MD5 e ainda não tem bcrypt; o chamador deve popular `senha_bcrypt`
        **e zerar o MD5** (ver abaixo).
  - `hash_password(plain) -> str`: sempre bcrypt.

**MD5 é rampa de saída, não compatibilidade.** Desde 2026-08-06 nenhum caminho
da aplicação GRAVA MD5 — `verify_md5` existe apenas para autenticar credencial
que já estava no banco, e o chamador converte a linha para bcrypt no mesmo ato.
Quem esquecer disso é reprovado por `tests/test_guarda_md5.py`.

O último gravador era o cadastro de cidadão, que escrevia
`senha=hash_md5(payload.senha)` "por compat PHP" — ou seja, criava um hash **sem
sal e reversível por rainbow table** de uma senha escolhida pelo cidadão, num
banco compartilhado, para servir um portal que este projeto decidiu não sustentar
("a versão Python é tratada como independente", CLAUDE.md). O sistema todo já
gravava `senha=""`: provisionamento, criação de usuário, reset e troca. O
cadastro público era a única exceção, e era a mais exposta das portas.

Consequência aceita e deliberada: cidadão cadastrado a partir daqui **não
autentica no portal PHP legado**. Mesma consequência que o admin já tinha desde
o provisionamento por CLI.

`hash_md5` continua exportado porque `verify_md5` o usa e porque os testes
precisam FABRICAR credencial legada para provar que a conversão funciona. Usá-lo
em código de produção é o defeito que a guarda persegue.
"""
from __future__ import annotations

import hashlib

import bcrypt

# Mínimo de caracteres para senha escolhida por pessoa (NIST SP 800-63B §5.1.1.2
# manda 8 para segredo escolhido pelo usuário).
#
# É UM número, e não um por schema, porque a divergência foi o defeito: o
# cadastro público de cidadão exigia 4 e a troca de senha do servidor municipal
# exigia 6 — a porta aberta na rua era mais fraca que a de dentro. O 6 ainda
# estava duplicado entre `schemas/auth.py` e `services/conta.py`, que é como
# números assim se separam com o tempo.
#
# Não vale para LOGIN: quem já tem senha curta continua entrando. Subir o piso
# não pode virar bloqueio retroativo de quem já está cadastrado.
SENHA_MINIMA = 8


def hash_md5(plain: str) -> str:
    return hashlib.md5(plain.encode("utf-8")).hexdigest()


def verify_md5(plain: str, stored_hash: str) -> bool:
    return hash_md5(plain) == stored_hash


def hash_password(plain: str) -> str:
    """Sempre bcrypt. Usar para popular `senha_bcrypt`."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_password(
    plain: str, *, bcrypt_hash: str | None, md5_hash: str | None
) -> tuple[bool, bool]:
    """Retorna (ok, needs_rehash).

    needs_rehash=True quando a senha bateu em MD5 mas não havia bcrypt — o
    chamador deve calcular `hash_password(plain)` e gravar em `senha_bcrypt`.
    """
    if bcrypt_hash and _verify_bcrypt(plain, bcrypt_hash):
        return True, False
    if md5_hash and verify_md5(plain, md5_hash):
        return True, True
    return False, False
