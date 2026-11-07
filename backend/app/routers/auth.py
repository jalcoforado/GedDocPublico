import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import (
    get_current_user,
    get_current_user_no_password_gate,
    ler_unidade_contexto,
    require_tenant_id,
)
from ..auth.dois_fatores import (
    COOKIE_LEMBRAR,
    VALIDADE_LEMBRAR,
    emitir_desafio,
    emitir_lembrar,
    lembrar_vale,
    ler_desafio,
)
from ..auth.jwt import build_payload, encode_token, get_jwt_secret
from ..auth.password import hash_password, verify_password
from ..auth.perms import require_permission
from ..config import get_settings
from ..database import get_db
from ..models import GoogleCredencial, Usuario, UsuarioExterno
from ..schemas.auth import (
    AlterarSenhaRequest,
    AvisoEnviado,
    ContaConfirmada,
    ConviteInfo,
    DefinirSenhaRequest,
    DoisFatoresRequest,
    EsqueciSenhaRequest,
    ReenviarCodigoRequest,
    TokenContaRequest,
    LoginRequest,
    LoginResponse,
    LotacaoOut,
    MeResponse,
    PermissaoItem,
    TrocarLotacaoRequest,
)
from ..services import conta_email, conta_tokens
from ..services.conta import ContaError, alterar_senha
from ..services.google_oauth_flow import GoogleOAuthFlow
from ..services.minutas import criar_google_doc_para_minuta
from ..services.permissoes import listar_lotacoes, load_permissions, resolver_unidade_ativa

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_settings = get_settings()


async def get_redis() -> Redis:
    """Retorna um cliente Redis para cache de estado OAuth."""
    redis_url = _settings.celery_broker_url  # redis://redis:6379/0
    return await Redis.from_url(redis_url)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    # Login restringido ao tenant resolvido pelo middleware (Fase 13a).
    tenant_id = getattr(request.state, "tenant_id", None)
    stmt = select(Usuario).where(
        Usuario.email == payload.email,
        Usuario.excluido.is_(False),
        Usuario.ativo.is_(True),
    )
    if tenant_id is not None:
        stmt = stmt.where(Usuario.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    ok = False
    needs_rehash = False
    if user is not None:
        ok, needs_rehash = verify_password(
            payload.senha,
            bcrypt_hash=user.senha_bcrypt,
            md5_hash=user.senha,
        )

    if not ok or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    if needs_rehash:
        # Conversão da credencial legada no primeiro uso: bcrypt entra e o MD5
        # sai no mesmo ato. O rehash sozinho só ACRESCENTA — sem o zerar, a
        # linha guardaria um hash reversível ao lado do bcrypt indefinidamente.
        # Efeito colateral desejado: desbloqueia a assinatura, que recusa
        # credencial legada (AssinaturaCredencialLegadaError, HTTP 409).
        user.senha_bcrypt = hash_password(payload.senha)
        user.senha = ""
        await db.commit()

    if user.email_verificado_em is None:
        # Convite ainda não aceito. Na prática quase inalcançável — quem foi
        # convidado não tem senha até abrir o link —, mas a regra vale aqui e
        # não só no fato de a senha ser aleatória.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta ainda não ativada. Abra o link do convite que enviamos para o seu e-mail.",
        )

    secret = await get_jwt_secret(db)
    if _dois_fatores_ativo() and not lembrar_vale(
        secret,
        request.cookies.get(COOKIE_LEMBRAR),
        usuario_id=user.id,
        tenant_id=user.tenant_id,
        senha_bcrypt=user.senha_bcrypt,
    ):
        return await _iniciar_2fa(db, user, secret)

    return _emitir_sessao(response, user, secret, tenant_id=tenant_id)


def _dois_fatores_ativo() -> bool:
    """2FA só vale com SMTP configurado. Sem servidor de e-mail o código nunca
    chegaria e NINGUÉM entraria — trancar a prefeitura inteira é pior do que
    o login seguir só com a senha até o SMTP ser configurado. O log de erro
    é o aviso de que está faltando."""
    settings = get_settings()
    if not settings.dois_fatores_email:
        return False
    if not settings.smtp_host:
        logger.error("dois_fatores_sem_smtp", extra={"efeito": "login só com senha até configurar SMTP_HOST"})
        return False
    return True


def _emitir_sessao(
    response: Response, user: Usuario, secret: str, *, tenant_id: int | None
) -> LoginResponse:
    # E1 — a lotação ativa nasce na principal; "alterar setor" troca depois.
    jwt_payload = build_payload(
        user.id, user.email, tenant_id=tenant_id,
        unidade_contexto_id=user.id_unidade_trabalho,
    )
    token = encode_token(jwt_payload, secret)

    response.set_cookie(
        key="aprimora_token",
        value=token,
        max_age=_settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        access_token=token,
        expires_in=_settings.jwt_ttl_seconds,
        usuario_id=user.id,
        usuario_email=user.email,
        nome=user.nome,
        must_change_password=user.must_change_password,
    )


async def _iniciar_2fa(db: AsyncSession, user: Usuario, secret: str) -> LoginResponse:
    """Senha certa, computador não lembrado: manda o código e devolve o
    desafio. Nenhuma sessão é emitida aqui."""
    linha, codigo = await conta_tokens.emitir(
        db,
        conta_tokens.Titular(tenant_id=user.tenant_id, id_usuario=user.id),
        "codigo_2fa",
        respeitar_intervalo=False,
    )
    await db.commit()
    assunto, texto = conta_email.texto_codigo_2fa(
        nome=user.nome, orgao=await conta_email.nome_do_orgao(db, user.tenant_id), codigo=codigo
    )
    await conta_email.enviar_email(
        para=user.email, assunto=assunto, texto=texto, tenant_id=user.tenant_id
    )
    return LoginResponse(
        requer_2fa=True,
        desafio=emitir_desafio(
            secret, usuario_id=user.id, tenant_id=user.tenant_id, id_token=linha.id
        ),
        email_mascarado=conta_email.mascarar_email(user.email),
    )


async def _usuario_do_desafio(
    db: AsyncSession, secret: str, desafio: str
) -> tuple[Usuario, dict]:
    dados = ler_desafio(secret, desafio)
    if dados is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O código expirou. Entre com a sua senha de novo.",
        )
    user = (
        await db.execute(
            select(Usuario).where(
                Usuario.id == int(dados["sub"]),
                Usuario.tenant_id == dados["tid"],
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return user, dados


@router.post("/login/2fa", response_model=LoginResponse)
async def login_2fa(
    payload: DoisFatoresRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Segundo passo do login: o código de 6 dígitos enviado por e-mail."""
    secret = await get_jwt_secret(db)
    user, dados = await _usuario_do_desafio(db, secret, payload.desafio)
    ok = await conta_tokens.conferir_codigo(
        db, dados["tok"], payload.codigo, tenant_id=user.tenant_id
    )
    # Commit também no erro: é ele que grava a tentativa contada.
    await db.commit()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido ou expirado.",
        )
    if payload.lembrar:
        response.set_cookie(
            key=COOKIE_LEMBRAR,
            value=emitir_lembrar(
                secret, usuario_id=user.id, tenant_id=user.tenant_id,
                senha_bcrypt=user.senha_bcrypt,
            ),
            max_age=VALIDADE_LEMBRAR,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return _emitir_sessao(
        response, user, secret, tenant_id=getattr(request.state, "tenant_id", None)
    )


@router.post("/login/2fa/reenviar", response_model=LoginResponse)
async def login_2fa_reenviar(
    payload: ReenviarCodigoRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Manda um código novo (o anterior deixa de valer). Um por minuto."""
    secret = await get_jwt_secret(db)
    user, _ = await _usuario_do_desafio(db, secret, payload.desafio)
    try:
        linha, codigo = await conta_tokens.emitir(
            db,
            conta_tokens.Titular(tenant_id=user.tenant_id, id_usuario=user.id),
            "codigo_2fa",
        )
    except conta_tokens.EnvioRecenteError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Aguarde um minuto para pedir outro código.",
        )
    await db.commit()
    assunto, texto = conta_email.texto_codigo_2fa(
        nome=user.nome, orgao=await conta_email.nome_do_orgao(db, user.tenant_id), codigo=codigo
    )
    await conta_email.enviar_email(
        para=user.email, assunto=assunto, texto=texto, tenant_id=user.tenant_id
    )
    return LoginResponse(
        requer_2fa=True,
        desafio=emitir_desafio(
            secret, usuario_id=user.id, tenant_id=user.tenant_id, id_token=linha.id
        ),
        email_mascarado=conta_email.mascarar_email(user.email),
    )


@router.post("/logout")
async def logout() -> Response:
    """Limpa o cookie de sessão. Sem efeito no JWT (que segue válido até expirar)."""
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="aprimora_token", path="/")
    return resp


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    user: Usuario = Depends(get_current_user_no_password_gate),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(require_tenant_id),
) -> MeResponse:
    unidade_contexto = await ler_unidade_contexto(request, db)
    perms = await load_permissions(
        db, user.id, tenant_id=tenant_id, id_unidade_contexto=unidade_contexto
    )
    lotacoes = await listar_lotacoes(db, tenant_id=tenant_id, usuario=user)
    # A unidade que a TELA mostra tem de ser a que as caixas e o painel
    # contam (`resolver_unidade_ativa`, em `processos.unidade_ativa_dep`).
    # Devolver a claim crua quebraria o caso do token antigo: quem trocou
    # para B e depois perdeu B segue com "B" no JWT, os números voltam para a
    # principal, e o cabeçalho procuraria B numa lista de lotações que não a
    # tem mais — sumindo a unidade justo quando ela mudou.
    #
    # As PERMISSÕES acima continuam pela claim crua, de propósito: é a mesma
    # leitura do gate (`auth/perms.py`), e o menu que o frontend monta com
    # elas tem de bater com o que o gate deixa passar. Reconferir a lotação
    # também no gate é outra decisão (política de acesso), não desta fatia.
    unidade_ativa = await resolver_unidade_ativa(
        db, tenant_id=tenant_id, usuario=user, id_unidade_contexto=unidade_contexto
    )

    return MeResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        cargo=user.cargo,
        id_unidade_trabalho=user.id_unidade_trabalho,
        must_change_password=user.must_change_password,
        is_super_usuario=perms.is_super_usuario,
        permissoes=[
            PermissaoItem(
                codigo=item.codigo,
                transacao=item.transacao,
                inserir=item.inserir,
                atualizar=item.atualizar,
                excluir=item.excluir,
            )
            for item in perms.items
        ],
        unidade_contexto_id=unidade_ativa,
        lotacoes=[LotacaoOut(id=l.id, nome=l.nome, principal=l.principal) for l in lotacoes],
    )


@router.post("/lotacao-ativa", response_model=MeResponse)
async def trocar_lotacao_ativa(
    payload: TrocarLotacaoRequest,
    response: Response,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(require_tenant_id),
) -> MeResponse:
    """E1 (benchmark SUiTE) — o "alterar setor" do SUiTE: troca a lotação
    ATIVA da sessão entre as que o usuário tem (principal ou secundária).

    JWT é stateless — reemite o token com a claim nova e troca o cookie,
    igual ao login. Devolve `MeResponse` já recalculado no novo contexto,
    então o frontend não precisa de uma segunda chamada a `/auth/me`.
    """
    lotacoes = await listar_lotacoes(db, tenant_id=tenant_id, usuario=user)
    if payload.id_unidade_trabalho not in {l.id for l in lotacoes}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lotação não pertence a este usuário",
        )

    secret = await get_jwt_secret(db)
    jwt_payload = build_payload(
        user.id, user.email, tenant_id=tenant_id,
        unidade_contexto_id=payload.id_unidade_trabalho,
    )
    token = encode_token(jwt_payload, secret)
    response.set_cookie(
        key="aprimora_token",
        value=token,
        max_age=_settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )

    perms = await load_permissions(
        db, user.id, tenant_id=tenant_id,
        id_unidade_contexto=payload.id_unidade_trabalho,
    )
    return MeResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        cargo=user.cargo,
        id_unidade_trabalho=user.id_unidade_trabalho,
        must_change_password=user.must_change_password,
        is_super_usuario=perms.is_super_usuario,
        permissoes=[
            PermissaoItem(
                codigo=item.codigo,
                transacao=item.transacao,
                inserir=item.inserir,
                atualizar=item.atualizar,
                excluir=item.excluir,
            )
            for item in perms.items
        ],
        unidade_contexto_id=payload.id_unidade_trabalho,
        lotacoes=[LotacaoOut(id=l.id, nome=l.nome, principal=l.principal) for l in lotacoes],
    )


@router.post("/alterar-senha", status_code=status.HTTP_204_NO_CONTENT)
async def alterar_senha_endpoint(
    payload: AlterarSenhaRequest,
    request: Request,
    user: Usuario = Depends(get_current_user_no_password_gate),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Troca self-service de senha. Grava só bcrypt — desbloqueia a assinatura.

    SEC-1 whitelist: esta é justamente a rota que o usuário precisa chamar
    para sair da condição must_change_password=true. Bloqueá-la pelo gate
    seria um deadlock. A própria troca de senha zera a flag (Commit 3,
    D-ZERAR-MD5-ALTERAR) e a partir daí o usuário volta a passar pelo gate.
    """
    try:
        await alterar_senha(
            db,
            usuario=user,
            senha_atual=payload.senha_atual,
            nova_senha=payload.nova_senha,
            request=request,
        )
    except ContaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/google")
async def initiate_google_oauth(
    minuta_id: int,
    processo_id: int,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Inicia o fluxo OAuth com Google.

    Query params:
    - minuta_id (required): ID da minuta a ser editada. 0 quando o usuário
      está só conectando a conta, antes de criar qualquer minuta — nesse
      caso o callback não tenta criar Google Doc nenhum, só guarda a
      credencial e volta pro processo.
    - processo_id (required): ID do processo associado

    Retorna: 307 Redirect para Google consent screen
    """
    oauth_flow = GoogleOAuthFlow(redis)

    try:
        auth_url = await oauth_flow.generate_oauth_url(
            user_id=user.id,
            tenant_id=tenant_id,
            minuta_id=minuta_id,
            processo_id=processo_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar OAuth: {str(e)}",
        )

    return RedirectResponse(url=auth_url, status_code=307)


@router.get("/google/callback")
async def handle_google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Manipula o callback do Google OAuth.

    Query params:
    - code: código de autorização do Google (sucesso)
    - state: token de state para validação (sucesso)
    - error: erro retornado pelo Google (ex: access_denied)

    Em caso de sucesso:
    1. Valida e troca código por tokens (GoogleOAuthFlow)
    2. Auto-cria Google Doc via criar_google_doc_para_minuta
    3. Redireciona para o Google Docs editor

    Em caso de erro:
    1. Redireciona para /minuta-error com código de erro
    """
    # Rejeição do usuário
    if error == "access_denied":
        return RedirectResponse(
            url="/minuta-error?error=access_denied",
            status_code=307,
        )

    # Validação de params obrigatórios
    if not code or not state:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )

    oauth_flow = GoogleOAuthFlow(redis)

    try:
        # Troca código por tokens, valida state, salva credenciais
        context = await oauth_flow.handle_callback(code, state, db=db)
    except ValueError as e:
        error_msg = str(e)
        if "Sessão expirou" in error_msg:
            return RedirectResponse(
                url="/minuta-error?error=state_expired",
                status_code=307,
            )
        else:
            return RedirectResponse(
                url="/minuta-error?error=google_api_error",
                status_code=307,
            )

    # minuta_id=0 é o "só conectar a conta" (RedigirDocumentoDialog permite
    # conectar antes de criar qualquer minuta) — sem minuta pra vincular, não
    # há Google Doc nenhum pra criar. Credenciais já foram salvas acima;
    # só volta pro processo, de onde o usuário segue o fluxo normal.
    minuta_id = context.get("minuta_id")
    if not minuta_id:
        processo_id = context.get("processo_id")
        return RedirectResponse(
            url=f"/m/protocolo/processos/{processo_id}?tab=documentos",
            status_code=307,
        )

    # Auto-cria Google Doc e redireciona para editor
    try:
        minuta = await criar_google_doc_para_minuta(
            db,
            tenant_id=tenant_id,
            minuta_id=minuta_id,
            usuario_id=user.id,
        )
        # Redireciona para o Google Docs editor
        return RedirectResponse(url=minuta.google_doc_url, status_code=307)
    except HTTPException:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )
    except Exception:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )


@router.get("/users/me/google-credential")
async def get_google_credential_status(
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get credential status for current user.

    Returns 200 with {connected: true, connected_at: ...} if credentials exist.
    Returns 404 if user has no non-revoked Google Docs credentials.
    """
    stmt = select(GoogleCredencial).where(
        (GoogleCredencial.tenant_id == tenant_id)
        & (GoogleCredencial.id_usuario == usuario.id)
        & (GoogleCredencial.revogado == False)
    )
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()

    if not cred:
        raise HTTPException(status_code=404, detail="No credentials found")

    return {
        "connected": True,
        "connected_at": cred.criado_em.isoformat(),
    }


# ------------------------------------------------- conta por e-mail (0137)
#
# "Não lembro a senha", convite de servidor e confirmação de e-mail do
# cidadão. Rotas públicas (sem sessão): o tenant vem do host, como no login.
# Os pedidos de envio respondem sempre o mesmo texto, exista a conta ou não —
# senão o formulário viraria um verificador de quais e-mails estão cadastrados.

_AVISO_ESQUECI = (
    "Se houver uma conta com esse e-mail, enviamos um link para criar uma nova "
    "senha. Confira a caixa de entrada e o spam."
)


async def _titular_do_token(db: AsyncSession, linha) -> Usuario | UsuarioExterno:  # noqa: ANN001
    if linha.id_usuario is not None:
        conta = await db.get(Usuario, linha.id_usuario)
    else:
        conta = await db.get(UsuarioExterno, linha.id_usuario_externo)
    if conta is None or conta.excluido or not conta.ativo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link inválido ou expirado.")
    return conta


def _link_invalido() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Este link não vale mais: expirou, já foi usado ou foi substituído por um mais novo.",
    )


@router.post("/esqueci-senha", response_model=AvisoEnviado, status_code=status.HTTP_202_ACCEPTED)
async def esqueci_senha(
    payload: EsqueciSenhaRequest,
    request: Request,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AvisoEnviado:
    user = (
        await db.execute(
            select(Usuario).where(
                Usuario.email == payload.email.strip(),
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        return AvisoEnviado(detail=_AVISO_ESQUECI)
    # Convite pendente: o "esqueci" vira reenvio do convite — é o link que
    # essa pessoa precisa, e o de redefinição a deixaria sem e-mail confirmado.
    finalidade = "convite" if user.email_verificado_em is None else "redefinir_senha"
    try:
        _, token = await conta_tokens.emitir(
            db, conta_tokens.Titular(tenant_id=tenant_id, id_usuario=user.id), finalidade
        )
    except conta_tokens.EnvioRecenteError:
        return AvisoEnviado(detail=_AVISO_ESQUECI)
    await db.commit()
    orgao = await conta_email.nome_do_orgao(db, tenant_id)
    if finalidade == "convite":
        assunto, texto = conta_email.texto_convite(
            nome=user.nome, orgao=orgao, url=conta_email.link(request, "/login/convite", token)
        )
    else:
        assunto, texto = conta_email.texto_redefinir_senha(
            nome=user.nome, orgao=orgao, url=conta_email.link(request, "/login/redefinir-senha", token)
        )
    await conta_email.enviar_email(para=user.email, assunto=assunto, texto=texto, tenant_id=tenant_id)
    return AvisoEnviado(detail=_AVISO_ESQUECI)


@router.post("/redefinir-senha", response_model=ContaConfirmada)
async def redefinir_senha(
    payload: DefinirSenhaRequest,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContaConfirmada:
    """Nova senha pelo link do e-mail — vale para servidor e para cidadão."""
    linha = await conta_tokens.consumir(db, payload.token, ("redefinir_senha",), tenant_id=tenant_id)
    if linha is None:
        raise _link_invalido()
    conta = await _titular_do_token(db, linha)
    conta.senha_bcrypt = hash_password(payload.nova_senha)
    conta.senha = ""
    # Quem abriu o link provou que lê aquela caixa de e-mail.
    conta.email_verificado_em = conta.email_verificado_em or datetime.utcnow()
    if isinstance(conta, Usuario):
        conta.must_change_password = False
    await db.commit()
    return ContaConfirmada(tipo="servidor" if isinstance(conta, Usuario) else "cidadao")


@router.post("/convite/info", response_model=ConviteInfo)
async def convite_info(
    payload: TokenContaRequest,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ConviteInfo:
    """Nome e e-mail do convite, para a tela de ativação — sem consumi-lo."""
    linha = await conta_tokens.localizar(db, payload.token, ("convite",), tenant_id=tenant_id)
    if linha is None:
        raise _link_invalido()
    user = await _titular_do_token(db, linha)
    return ConviteInfo(nome=user.nome, email=user.email)


@router.post("/convite/aceitar", response_model=ContaConfirmada)
async def convite_aceitar(
    payload: DefinirSenhaRequest,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContaConfirmada:
    """Ativa a conta do servidor convidado: confirma o e-mail e grava a senha
    que ELE escolheu — o administrador nunca chega a conhecê-la."""
    linha = await conta_tokens.consumir(db, payload.token, ("convite",), tenant_id=tenant_id)
    if linha is None:
        raise _link_invalido()
    user = await _titular_do_token(db, linha)
    user.senha_bcrypt = hash_password(payload.nova_senha)
    user.senha = ""
    user.email_verificado_em = datetime.utcnow()
    user.must_change_password = False
    await db.commit()
    return ContaConfirmada(tipo="servidor")


@router.post("/verificar-email", response_model=ContaConfirmada)
async def verificar_email(
    payload: TokenContaRequest,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContaConfirmada:
    """Confirma o e-mail do cidadão que se cadastrou pelo portal."""
    linha = await conta_tokens.consumir(db, payload.token, ("verificar_email",), tenant_id=tenant_id)
    if linha is None:
        raise _link_invalido()
    conta = await _titular_do_token(db, linha)
    conta.email_verificado_em = conta.email_verificado_em or datetime.utcnow()
    await db.commit()
    return ContaConfirmada(tipo="servidor" if isinstance(conta, Usuario) else "cidadao")
