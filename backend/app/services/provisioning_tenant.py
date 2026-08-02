"""Provisionamento de tenant — **dois atos**, um por papel de banco (SEC-RLS-00C).

Fonte única usada **tanto pela CLI** (`app/cli/tenant.py`) **quanto pela API
admin** (`routers/admin_tenants.py`).

## Por que dois atos

Até `SEC-RLS-00C` isto era um bloco monolítico numa transação só, e só
funcionava porque um papel de banco podia tudo. O bloco grava em duas famílias
de tabela que pertencem a fronteiras diferentes:

- **plataforma** — `aprimora_py.tenant` e `aprimora_py.tenant_modulo`
  (entitlement: qual município existe e o que ele contratou);
- **negócio do município** — `utils.usuario`, `utils.grupo`,
  `utils.unidade_trabalho`, `utils.tipo_unidade_trabalho`,
  `protocolos.tipo_manifestante` e a trilha `aprimora_py.audit_log`.

O ADR-016 §2.3 nega DML de entitlement ao papel municipal (`aprimora_app`) e
nega DML nas tabelas de negócio ao papel de plataforma (`aprimora_platform`).
Um único papel capaz das duas coisas é exatamente o buraco que a migration 0079
fecha: com `INSERT` em `tenant_modulo` — tabela que **não tem RLS**, por decisão
registrada — qualquer defeito de service no runtime municipal auto-contratava
módulo para qualquer tenant, sem segunda barreira nenhuma.

Daí a partição:

| ato | função | sessão/papel | escreve em |
|---|---|---|---|
| 1. plataforma | `criar_registro_de_tenant` | `aprimora_platform` (`database_plataforma`) | `tenant`, `tenant_modulo` |
| 2. municipal  | `semear_tenant` | papel municipal, com `SET LOCAL app.tenant_id = <novo>` | `utils.*`, `protocolos.*`, `audit_log` |
| 3. plataforma | `ativar_tenant_provisionado` | `aprimora_platform` | `tenant.ativo` |

## O modo de falha, escrito — não implícito

Partir uma transação em duas cria um modo de falha que não existia: o ato 1
comita, o ato 2 falha, e sobra um tenant sem administrador. As três saídas
possíveis eram compensar (apagar), marcar estado incompleto, ou tornar o segundo
ato reexecutável. **A escolha foi marcar + reexecutar, e nunca compensar.**

- **Nunca compensar por `DELETE`.** Apagar tenant não é operação de runtime
  nenhum — a 0076 revogou `DELETE` em `tenant` de `aprimora_app` e
  deliberadamente **não** o concedeu a `aprimora_platform`, com a razão escrita.
  Uma compensação obrigaria a reabrir esse privilégio para tratar um caso raro,
  e o privilégio ficaria aberto o tempo todo.
- **O estado incompleto é marcado, e a marca já existia:** o ato 1 cria o tenant
  com **`ativo = false`**; só o ato 3 o ativa. Um tenant a meio caminho é,
  portanto, **inerte** — o `TenantMiddleware` resolve o subdomínio com
  `slug = :s AND ativo = true`, então ninguém entra nele, nenhum login acontece,
  nada vaza. Não foi preciso inventar coluna de estado: foi preciso parar de
  nascer ativo.
- **O ato 2 é idempotente e reexecutável.** Cada artefato é procurado pela sua
  chave natural dentro do tenant antes de ser criado, e a retomada é um comando
  nomeado: `retomar_provisionamento` (CLI: `python -m app.cli.tenant retomar`).
  Ela **recusa tenant já ativo** — sem essa recusa, "retomar" seria um caminho
  para injetar um super-usuário num município em produção com uma linha de CLI.

Consequência para quem lê os testes: `provisionar_tenant` **não é mais atômico**,
e não tem como ser (duas conexões, dois papéis, duas transações). O que ele
garante é: *ou o tenant está completo e ativo, ou está inerte e retomável*. As
duas metades são verificadas em
`test_admin_tenants.py::test_falha_no_ato_municipal_deixa_tenant_inerte_e_retomavel`.

## Sobre `db_plataforma=None`

`provisionar_tenant` aceita `db_plataforma=None`, e isso **não é um contorno da
fronteira** — a fronteira não é feita de código, é feita de `GRANT`. Depois da
0079, `aprimora_app` não tem `INSERT` em `tenant` nem em `tenant_modulo`: o ato
de plataforma numa sessão municipal **falha alto** com `permission denied`,
jamais escreve. O `None` só é utilizável por credencial administrativa
(`ged_user` hoje, `aprimora_migrator` depois) — CLI, seeds e testes. O caminho
HTTP, que é o único exposto, passa a sessão de plataforma de verdade
(`get_platform_db`). As duas propriedades têm teste em
`test_entitlement_fronteira_sql.py`.

## Pontos que continuam valendo

- Senha do admin: **gerada**, retornada **uma vez**; persistimos só bcrypt
  (`senha` MD5 fica vazio — caminho legado desabilitado).
- SEC-1 (Commit 3): admin inicial nasce com `must_change_password=true`; o
  primeiro login do humano exige troca via `/alterar-senha`.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..config import get_settings
from .audit import log as audit_log
from .modulos import contratar_modulos_iniciais
from ..models import (
    Grupo,
    Nivel,
    Sistema,
    Tenant,
    TipoManifestante,
    TipoUnidadeTrabalho,
    UnidadeTrabalho,
    Usuario,
    UsuarioGrupo,
)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
SLUGS_RESERVADOS = frozenset(
    {"www", "api", "admin", "app", "mail", "static", "assets", "plataforma"}
)

# Chaves naturais dos artefatos do bootstrap municipal. São o que torna o ato 2
# idempotente: a reexecução procura por elas antes de criar. Mudar uma delas sem
# mudar a busca correspondente faria a retomada DUPLICAR o artefato em vez de
# reaproveitá-lo — e a duplicata só apareceria no tenant que precisou de
# retomada, isto é, exatamente no cliente que já teve um problema.
TIPO_UNIDADE_CODIGO = "SEC"
TIPO_UNIDADE_NOME = "Secretaria"
UNIDADE_SIGLA = "PG"
UNIDADE_NOME = "Protocolo Geral"
TIPO_MANIFESTANTE_NOME = "Pessoa Física"
GRUPO_SU_NOME = "Super Usuário"


class ProvisioningError(Exception):
    """Erro de provisionamento — mapeado para 400 na API."""


class SlugIndisponivelError(ProvisioningError):
    """Slug já existe — mapeado para 409 na API."""


class ProvisionamentoIncompletoError(ProvisioningError):
    """Ato de plataforma concluído; ato municipal (ou a ativação) falhou.

    **Não é 400**: o pedido estava correto e a plataforma já registrou o tenant.
    É falha de execução, e o router a mapeia para **500** — mas com mensagem
    operável, porque quem lê a resposta de `/admin/tenants` é um operador.

    Carrega `slug` e `tenant_id` para que a retomada não dependa de alguém achar
    o tenant no banco. Herda de `ProvisioningError` para que quem já captura a
    família (a CLI) continue capturando; quem precisa distinguir põe este
    `except` **antes** do da base.
    """

    def __init__(self, *, slug: str, tenant_id: int, causa: BaseException) -> None:
        self.slug = slug
        self.tenant_id = tenant_id
        self.causa = causa
        super().__init__(
            f"Tenant '{slug}' (id={tenant_id}) foi criado pelo ato de plataforma, "
            f"mas o ato municipal falhou: {type(causa).__name__}: {causa}. "
            "O tenant ficou INATIVO — não resolve por subdomínio e ninguém entra "
            "nele. NADA foi apagado (apagar tenant não é operação de runtime). "
            "Para concluir, repita o ato municipal, que é idempotente: "
            f"`python -m app.cli.tenant retomar --slug {slug} "
            "--admin-email <email> --admin-cpf <cpf>`."
        )


def validar_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not SLUG_RE.match(s):
        raise ProvisioningError(
            "Slug inválido: use 3–50 caracteres [a-z0-9-], sem hífen nas pontas."
        )
    if s in SLUGS_RESERVADOS:
        raise ProvisioningError(f"Slug reservado: {s!r}.")
    return s


# ---------------------------------------------------------------------------
# Ato 1 — PLATAFORMA
# ---------------------------------------------------------------------------


async def criar_registro_de_tenant(
    db_plataforma: AsyncSession,
    *,
    slug: str,
    nome: str,
    cnpj: str | None = None,
    id_cidade: int | None = None,
    plano: str = "basico",
    cor_primaria: str | None = None,
    logo_url: str | None = None,
    limite_usuarios: int | None = None,
    limite_armazenamento_mb: int | None = None,
    modulos: list[str] | None = None,
) -> Tenant:
    """Ato de PLATAFORMA: cria o tenant e a contratação inicial. **Comita.**

    Roda sob `aprimora_platform` (ADR-016 §2.3): as duas tabelas que ele toca
    são de entitlement e nenhuma delas tem RLS.

    Este ato é atômico **em si** — uma transação, um commit. Se a contratação
    falhar, o registro do tenant volta junto e não sobra nada; por isso a
    retomada não precisa refazer contratação.

    O tenant nasce **`ativo = false`** de propósito: é a marca de "incompleto".
    Ver o modo de falha no docstring do módulo.
    """
    slug = validar_slug(slug)

    if (
        await db_plataforma.execute(select(Tenant.id).where(Tenant.slug == slug))
    ).scalar_one_or_none() is not None:
        raise SlugIndisponivelError(f"Slug '{slug}' já existe.")

    tenant = Tenant(
        slug=slug,
        nome=nome,
        cnpj=cnpj,
        id_cidade=id_cidade,
        plano=plano,
        cor_primaria=cor_primaria,
        logo_url=logo_url,
        limite_usuarios=limite_usuarios,
        limite_armazenamento_mb=limite_armazenamento_mb,
        ativo=False,  # INERTE até o ato 3 — ver docstring do módulo
        criado_em=datetime.utcnow(),
    )
    db_plataforma.add(tenant)
    await db_plataforma.flush()  # obtém tenant.id

    await contratar_modulos_iniciais(db_plataforma, tenant.id, modulos)

    await db_plataforma.commit()
    return tenant


# ---------------------------------------------------------------------------
# Ato 2 — MUNICIPAL
# ---------------------------------------------------------------------------


async def semear_tenant(
    db: AsyncSession,
    *,
    tenant_id: int,
    admin_email: str,
    admin_nome: str,
    admin_cpf: str,
    senha: str | None = None,
    ator_usuario_id: int | None = None,
    acao_auditoria: str = "tenant.provisionado",
) -> str | None:
    """Ato MUNICIPAL: povoa o tenant recém-criado. **Comita.**

    Roda no papel municipal, dentro do contexto do tenant ALVO
    (`SET LOCAL app.tenant_id`) — sem isso, sob um papel NOBYPASSRLS as policies
    `WITH CHECK` barram todos os inserts tenant-scoped.

    **Idempotente.** Cada artefato é procurado pela chave natural antes de ser
    criado, e é isso que torna a retomada possível.

    Retorna a senha temporária do admin, ou `None` quando o admin **já existia**
    — caso em que a senha dele não é tocada. Gerar uma senha nova ali seria
    mentir para quem a repassa ao município: a antiga continuaria valendo. O
    `None` só ocorre em retomada; no caminho novo o tenant é vazio por
    construção.
    """
    # `SET` não aceita bind param no Postgres → interpolar o int (seguro).
    #
    # Precisa ser reemitido AQUI, e não uma vez lá em cima: `SET LOCAL` vale pela
    # transação, e o ato 1 comitou. Numa sessão de `get_db` o listener
    # `after_begin` acabou de instalar, nesta transação nova, o tenant que o
    # `TenantMiddleware` resolveu pelo `Host`; esta linha o sobrescreve pelo
    # tenant ALVO. Sem ela o provisionamento pela borda HTTP semearia o tenant
    # de quem chamou.
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))

    # O registro do tenant já foi comitado pelo ato 1; ler daqui serve a duas
    # coisas: montar o payload da trilha com slug/plano, e falhar cedo e claro
    # se alguém chamar o ato 2 para um tenant que não existe (o que, adiante,
    # apareceria como violação de FK longe da causa).
    registro = (
        await db.execute(
            select(Tenant.slug, Tenant.plano).where(Tenant.id == tenant_id)
        )
    ).first()
    if registro is None:
        raise ProvisioningError(
            f"Tenant id={tenant_id} não existe — o ato municipal só roda depois "
            "do ato de plataforma (`criar_registro_de_tenant`)."
        )

    # Pré-requisitos globais: nível valor=0 + o sistema do app corrente.
    # O app vem de settings.app_name — o MESMO filtro que load_permissions usa
    # (Sistema.app == app_name). Fixar o literal aqui já fez o SU do tenant
    # provisionado não ser reconhecido, resultando em 403 em todas as rotas.
    app_name = get_settings().app_name
    nivel_su = (
        await db.execute(select(Nivel).where(Nivel.valor == 0).limit(1))
    ).scalar_one_or_none()
    sistema_app = (
        await db.execute(select(Sistema).where(Sistema.app == app_name).limit(1))
    ).scalar_one_or_none()
    if nivel_su is None or sistema_app is None:
        raise ProvisioningError(
            "Pré-requisitos globais ausentes "
            f"(nível valor=0 ou sistema '{app_name}')."
        )

    tu = (
        await db.execute(
            select(TipoUnidadeTrabalho).where(
                TipoUnidadeTrabalho.tenant_id == tenant_id,
                TipoUnidadeTrabalho.codigo == TIPO_UNIDADE_CODIGO,
                TipoUnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalars().first()
    if tu is None:
        tu = TipoUnidadeTrabalho(
            tenant_id=tenant_id,
            tipo_unidade_trabalho=TIPO_UNIDADE_NOME,
            codigo=TIPO_UNIDADE_CODIGO,
        )
        db.add(tu)
        await db.flush()

    unidade = (
        await db.execute(
            select(UnidadeTrabalho).where(
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.sigla == UNIDADE_SIGLA,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalars().first()
    if unidade is None:
        unidade = UnidadeTrabalho(
            tenant_id=tenant_id,
            unidade_trabalho=UNIDADE_NOME,
            sigla=UNIDADE_SIGLA,
            id_tipo_unidade_trabalho=tu.id,
        )
        db.add(unidade)
        await db.flush()

    tem_tipo_manifestante = (
        await db.execute(
            select(TipoManifestante.id).where(
                TipoManifestante.tenant_id == tenant_id,
                TipoManifestante.tipo_manifestante == TIPO_MANIFESTANTE_NOME,
                TipoManifestante.excluido.is_(False),
            )
        )
    ).scalars().first()
    if tem_tipo_manifestante is None:
        db.add(
            TipoManifestante(
                tenant_id=tenant_id,
                tipo_manifestante=TIPO_MANIFESTANTE_NOME,
                id_categoria=1,
                ativo=True,
            )
        )

    usuario = (
        await db.execute(
            select(Usuario).where(
                Usuario.tenant_id == tenant_id, Usuario.email == admin_email
            )
        )
    ).scalars().first()
    senha_temp: str | None = None
    if usuario is None:
        senha_temp = senha or secrets.token_urlsafe(12)
        usuario = Usuario(
            tenant_id=tenant_id,
            nome=admin_nome,
            email=admin_email,
            cpf=admin_cpf,
            senha="",  # sem MD5 — só bcrypt (caminho legado desabilitado)
            senha_bcrypt=hash_password(senha_temp),
            id_unidade_trabalho=unidade.id,
            ativo=True,
            excluido=False,
            cargo="Administrador",
            app=app_name,
            # SEC-1: admin inicial recebe senha temporária — força troca no
            # primeiro acesso. O guard em get_current_user (Commit 2) já cobre.
            must_change_password=True,
        )
        db.add(usuario)
        await db.flush()

    grupo_su = (
        await db.execute(
            select(Grupo).where(
                Grupo.tenant_id == tenant_id,
                Grupo.grupo == GRUPO_SU_NOME,
                Grupo.excluido.is_(False),
            )
        )
    ).scalars().first()
    if grupo_su is None:
        grupo_su = Grupo(
            tenant_id=tenant_id,
            id_nivel=nivel_su.id,
            id_sistema=sistema_app.id,
            grupo=GRUPO_SU_NOME,
            excluido=False,
        )
        db.add(grupo_su)
        await db.flush()

    tem_vinculo = (
        await db.execute(
            select(UsuarioGrupo.id).where(
                UsuarioGrupo.tenant_id == tenant_id,
                UsuarioGrupo.id_usuario == usuario.id,
                UsuarioGrupo.id_grupo == grupo_su.id,
            )
        )
    ).scalars().first()
    if tem_vinculo is None:
        db.add(
            UsuarioGrupo(
                tenant_id=tenant_id,
                id_usuario=usuario.id,
                id_grupo=grupo_su.id,
                ativo=True,
                excluido=False,
                app=app_name,
            )
        )

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=ator_usuario_id,
        acao=acao_auditoria,
        entidade="tenant",
        id_entidade=tenant_id,
        payload={
            "slug": registro.slug,
            "admin_email": admin_email,
            "plano": registro.plano,
        },
    )

    await db.commit()
    return senha_temp


# ---------------------------------------------------------------------------
# Ato 3 — PLATAFORMA (a marca de "completo")
# ---------------------------------------------------------------------------


async def ativar_tenant_provisionado(
    db_plataforma: AsyncSession, tenant: Tenant
) -> None:
    """Tira o tenant do estado inerte. **Comita.**

    É o ÚNICO ponto que transforma "criado" em "utilizável", e por isso vem
    **depois** do ato municipal: enquanto `ativo = false`, o `TenantMiddleware`
    não resolve o subdomínio e o tenant não recebe login nenhum.
    """
    tenant.ativo = True
    tenant.atualizado_em = datetime.utcnow()
    await db_plataforma.commit()


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------


async def provisionar_tenant(
    db: AsyncSession,
    *,
    slug: str,
    nome: str,
    admin_email: str,
    admin_nome: str,
    admin_cpf: str,
    cnpj: str | None = None,
    id_cidade: int | None = None,
    plano: str = "basico",
    cor_primaria: str | None = None,
    logo_url: str | None = None,
    limite_usuarios: int | None = None,
    limite_armazenamento_mb: int | None = None,
    senha: str | None = None,
    ator_usuario_id: int | None = None,
    modulos: list[str] | None = None,
    db_plataforma: AsyncSession | None = None,
) -> tuple[Tenant, str]:
    """Encadeia os três atos. Retorna `(tenant, senha_temporaria)`.

    `db` é a sessão MUNICIPAL (ato 2). `db_plataforma` é a sessão de plataforma
    (atos 1 e 3); `None` significa "a mesma sessão faz os três", o que só é
    utilizável por credencial administrativa — ver o docstring do módulo.

    Falha do ato 1 (slug inválido, slug duplicado, catálogo de módulos) sobe como
    `ProvisioningError`/`SlugIndisponivelError` e **não deixa nada para trás**.
    Falha dos atos 2 ou 3 sobe como `ProvisionamentoIncompletoError`, com o
    tenant inerte e retomável.
    """
    plataforma = db if db_plataforma is None else db_plataforma

    tenant = await criar_registro_de_tenant(
        plataforma,
        slug=slug,
        nome=nome,
        cnpj=cnpj,
        id_cidade=id_cidade,
        plano=plano,
        cor_primaria=cor_primaria,
        logo_url=logo_url,
        limite_usuarios=limite_usuarios,
        limite_armazenamento_mb=limite_armazenamento_mb,
        modulos=modulos,
    )

    # Copiados para variáveis simples ANTES do `try`, e não lidos do ORM lá
    # dentro. Um `rollback()` EXPIRA os atributos do objeto, então
    # `tenant.slug` no bloco `except` dispararia um lazy load — que, em async,
    # estoura `MissingGreenlet` e SUBSTITUI a exceção real pela do carregamento.
    # O operador receberia um erro de greenlet no lugar da causa e do id de que
    # precisa para retomar.
    tenant_id, tenant_slug = tenant.id, tenant.slug

    try:
        senha_temp = await semear_tenant(
            db,
            tenant_id=tenant_id,
            admin_email=admin_email,
            admin_nome=admin_nome,
            admin_cpf=admin_cpf,
            senha=senha,
            ator_usuario_id=ator_usuario_id,
        )
        if senha_temp is None:
            # Tenant recém-criado não tem usuário nenhum. Chegar aqui significa
            # que o ato 1 devolveu um tenant que já existia — estado impossível
            # que é melhor gritar do que devolver `None` no lugar da senha.
            raise ProvisioningError(
                f"Tenant '{slug}' recém-criado já tinha o usuário "
                f"'{admin_email}'. Estado impossível; investigue antes de repetir."
            )
        await ativar_tenant_provisionado(plataforma, tenant)
    except Exception as exc:
        await db.rollback()
        raise ProvisionamentoIncompletoError(
            slug=tenant_slug, tenant_id=tenant_id, causa=exc
        ) from exc

    return tenant, senha_temp


async def retomar_provisionamento(
    db: AsyncSession,
    *,
    slug: str,
    admin_email: str,
    admin_nome: str,
    admin_cpf: str,
    senha: str | None = None,
    ator_usuario_id: int | None = None,
    db_plataforma: AsyncSession | None = None,
) -> tuple[Tenant, str | None]:
    """Reexecuta os atos 2 e 3 sobre um tenant que ficou inerte.

    É a saída para o modo de falha criado pela partição — ver o docstring do
    módulo. Retorna `(tenant, senha_temporaria | None)`; `None` quando o admin já
    existia e a senha dele foi preservada.

    **Recusa tenant ativo.** Sem essa recusa, "retomar" seria um caminho para
    criar um super-usuário dentro de um município em produção com uma linha de
    CLI — escalada de privilégio, não recuperação.
    """
    plataforma = db if db_plataforma is None else db_plataforma

    tenant = (
        await plataforma.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tenant is None:
        raise ProvisioningError(
            f"Tenant '{slug}' não existe — não há provisionamento a retomar. "
            "Use `create`."
        )
    if tenant.ativo:
        raise ProvisioningError(
            f"Tenant '{slug}' já está ATIVO — nada a retomar. Retomar um tenant "
            "ativo criaria um super-usuário num município em produção; se é isso "
            "que se quer, use a gestão de usuários do próprio tenant."
        )

    # Ver a nota em `provisionar_tenant`: `rollback()` expira o objeto, e ler
    # `tenant.slug` no `except` trocaria a exceção real por `MissingGreenlet`.
    tenant_id, tenant_slug = tenant.id, tenant.slug

    try:
        senha_temp = await semear_tenant(
            db,
            tenant_id=tenant_id,
            admin_email=admin_email,
            admin_nome=admin_nome,
            admin_cpf=admin_cpf,
            senha=senha,
            ator_usuario_id=ator_usuario_id,
            acao_auditoria="tenant.provisionamento_retomado",
        )
        await ativar_tenant_provisionado(plataforma, tenant)
    except Exception as exc:
        await db.rollback()
        raise ProvisionamentoIncompletoError(
            slug=tenant_slug, tenant_id=tenant_id, causa=exc
        ) from exc

    return tenant, senha_temp
