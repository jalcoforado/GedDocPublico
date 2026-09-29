"""Auth do cidadão (usuário externo).

Senha **só em bcrypt** (`senha_bcrypt`). Cadastro busca duplicidade por CPF/CNPJ
DENTRO do tenant atual — a mesma pessoa pode existir como cidadão em mais de uma
prefeitura, mas no mesmo tenant é único.

Fase 13a: cadastrar e login operam dentro de um tenant.

Até 2026-08-06 o cadastro também gravava `senha=hash_md5(...)` "espelhando
`Positiv\\Hash`" — um hash sem sal, reversível por rainbow table, de senha
escolhida pelo cidadão. Era o ÚLTIMO gravador de MD5 do sistema; todo o resto
(provisionamento, criação de usuário, reset, troca) já gravava `senha=""`. O
racional era compatibilidade com o portal PHP, que este projeto não sustenta
mais. Ver `auth/password.py` para a política, `tests/test_guarda_md5.py` para a
guarda que impede a volta e `tests/test_cidadao_senha_sem_md5.py` para o
comportamento.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password, verify_password
from ..models import UsuarioExterno
from ..schemas.cidadao import CadastroCidadaoRequest


class CidadaoAuthError(Exception):
    pass


def _normaliza_cpf_cnpj(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


async def cadastrar(
    db: AsyncSession,
    payload: CadastroCidadaoRequest,
    *,
    tenant_id: int,
    app: str,
) -> UsuarioExterno:
    cpf_cnpj = _normaliza_cpf_cnpj(payload.cpf_cnpj)
    if len(cpf_cnpj) not in (11, 14):
        raise CidadaoAuthError("CPF/CNPJ inválido")

    existe = (
        await db.execute(
            select(UsuarioExterno).where(
                UsuarioExterno.cpf_cnpj == cpf_cnpj,
                UsuarioExterno.tenant_id == tenant_id,
                UsuarioExterno.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existe is not None:
        raise CidadaoAuthError("Já existe cadastro para este CPF/CNPJ")

    cidadao = UsuarioExterno(
        tenant_id=tenant_id,
        nome=payload.nome.strip(),
        cpf_cnpj=cpf_cnpj,
        email=payload.email.strip().lower(),
        senha="",  # MD5 legado desabilitado — só bcrypt (ver docstring)
        senha_bcrypt=hash_password(payload.senha),
        login_govbr=False,
        ativo=True,
        excluido=False,
        uid=uuid4(),
        data_criacao=datetime.utcnow(),
        data_limite_ativacao=datetime.utcnow() + timedelta(days=365),
        app=app,
        telefone=payload.telefone,
        telefone_whatsapp=payload.telefone_whatsapp,
    )
    db.add(cidadao)
    await db.commit()
    await db.refresh(cidadao)
    return cidadao


async def login(
    db: AsyncSession, *, tenant_id: int, cpf_cnpj: str, senha: str
) -> UsuarioExterno:
    cpf_cnpj_norm = _normaliza_cpf_cnpj(cpf_cnpj)
    cidadao = (
        await db.execute(
            select(UsuarioExterno).where(
                UsuarioExterno.cpf_cnpj == cpf_cnpj_norm,
                UsuarioExterno.tenant_id == tenant_id,
                UsuarioExterno.excluido.is_(False),
                UsuarioExterno.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if cidadao is None:
        raise CidadaoAuthError("CPF/CNPJ ou senha inválidos")
    ok, needs_rehash = verify_password(
        senha, bcrypt_hash=cidadao.senha_bcrypt, md5_hash=cidadao.senha
    )
    if not ok:
        raise CidadaoAuthError("CPF/CNPJ ou senha inválidos")
    if needs_rehash:
        # Conversão da credencial legada no primeiro uso: grava bcrypt e APAGA o
        # MD5 no mesmo ato. Sem o zerar, a linha ficaria para sempre com um hash
        # reversível ao lado do bcrypt — o rehash sozinho não tira nada do banco,
        # só acrescenta. Mesma regra de `services/conta.py` e `usuario_senha.py`.
        cidadao.senha_bcrypt = hash_password(senha)
        cidadao.senha = ""
        await db.commit()
    return cidadao


class CidadaoInativoError(CidadaoAuthError):
    """Cadastro existe e está inativo — o gov.br não o reativa."""


async def login_ou_cadastrar_via_govbr(
    db: AsyncSession,
    *,
    tenant_id: int,
    cpf: str,
    nome: str,
    email: str | None,
    nivel_govbr: str | None,
    app: str,
) -> UsuarioExterno:
    """Login pelo gov.br, provisionando o cidadão no primeiro acesso.

    **Só pode ser chamado com identidade verificada.** `cpf` tem de vir do
    `id_token` com assinatura conferida (`services/govbr_sso.py`) — nunca de
    parâmetro que o navegador controle. Esta função não tem como distinguir um
    do outro; a garantia é do chamador.

    Regras, e o porquê de cada uma:

    - **CPF é a chave.** Normalizado para dígitos; só 11 dígitos passam (o
      gov.br autentica pessoa física). Busca dentro do tenant, ignorando
      excluídos — a mesma regra do cadastro por senha.
    - **Cadastro existente por senha é vinculado**, não duplicado: o gov.br
      prova a posse do CPF com mais força que a senha escolhida no cadastro.
      Nome e e-mail do cadastro NÃO são sobrescritos (são dados que o cidadão
      mantém); o e-mail só é preenchido se estava vazio.
    - **Inativo não é reativado.** `ativo=False` é decisão de alguém da
      prefeitura, e o login pelo gov.br não é autoridade para desfazê-la —
      levanta `CidadaoInativoError` (403 no router). O rascunho reativava.
    - **Excluído não é ressuscitado**: como no cadastro por senha, a busca
      ignora a linha excluída e um cadastro novo nasce. Soft-delete continua
      sendo histórico.
    - **E-mail não é chave nem é único** (`utils.usuario_externo` não tem
      índice único de e-mail), então não há colisão a tratar — e também não se
      usa e-mail para achar cadastro, senão bastaria um e-mail igual para
      herdar a conta de outra pessoa.
    - **Sem corrida de primeiro login.** A tabela não tem unicidade de CPF por
      tenant; dois callbacks simultâneos criariam duas linhas e todo login
      seguinte estouraria em `MultipleResultsFound`. Um advisory lock de
      transação sobre (tenant, CPF) serializa o trecho.
    """
    cpf_norm = _normaliza_cpf_cnpj(cpf or "")
    if len(cpf_norm) != 11:
        raise CidadaoAuthError("CPF inválido na identidade gov.br")

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"usuario_externo:govbr:{tenant_id}:{cpf_norm}"},
    )
    cidadao = (
        await db.execute(
            select(UsuarioExterno).where(
                UsuarioExterno.cpf_cnpj == cpf_norm,
                UsuarioExterno.tenant_id == tenant_id,
                UsuarioExterno.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()

    email_norm = (email or "").strip().lower() or None
    if email_norm is not None and len(email_norm) > 100:
        email_norm = None  # não cabe na coluna; melhor vazio que truncado

    if cidadao is None:
        cidadao = UsuarioExterno(
            tenant_id=tenant_id,
            nome=((nome or "").strip() or "Cidadão")[:100],
            cpf_cnpj=cpf_norm,
            email=email_norm,
            senha="",  # sem senha: só entra pelo gov.br até definir uma
            senha_bcrypt=None,
            login_govbr=True,
            nivel_govbr=nivel_govbr,
            ativo=True,
            excluido=False,
            uid=uuid4(),
            data_criacao=datetime.utcnow(),
            app=app,
            telefone=None,
            telefone_whatsapp=False,
        )
        db.add(cidadao)
    else:
        if not cidadao.ativo:
            await db.rollback()
            raise CidadaoInativoError(
                "Cadastro inativo nesta prefeitura. Procure o atendimento."
            )
        cidadao.login_govbr = True
        if nivel_govbr is not None:
            cidadao.nivel_govbr = nivel_govbr
        if not cidadao.email and email_norm:
            cidadao.email = email_norm

    await db.commit()
    await db.refresh(cidadao)
    return cidadao
