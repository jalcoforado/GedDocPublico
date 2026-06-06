from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.password import hash_md5, hash_password
from ..auth.perms import require_permission
from ..config import get_settings
from ..database import get_db, tenant_filter
from ..models import Usuario, UsuarioGrupo, UsuarioUnidadeTrabalho
from ..schemas.common import Paginated
from ..schemas.tenant import ResetSenhaResponse
from ..schemas.usuario import (
    UsuarioCreate,
    UsuarioDetail,
    UsuarioOut,
    UsuarioUpdate,
)
from ..services.usuario_senha import resetar_senha_usuario

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=Paginated[UsuarioOut])
async def list_usuarios(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Busca por nome ou email"),
) -> Paginated[UsuarioOut]:
    base = select(Usuario).where(Usuario.excluido.is_(False))
    base = tenant_filter(base, Usuario, tenant_id)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(
            or_(func.lower(Usuario.nome).like(like), func.lower(Usuario.email).like(like))
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    stmt = base.order_by(Usuario.nome).offset((page - 1) * page_size).limit(page_size)
    items = [UsuarioOut.model_validate(u) for u in (await db.execute(stmt)).scalars().all()]

    return Paginated(items=items, total=total, page=page, page_size=page_size)


async def _load_links(
    db: AsyncSession, usuario_id: int, tenant_id: int
) -> tuple[list[int], list[int]]:
    grupos = (
        await db.execute(
            select(UsuarioGrupo.id_grupo).where(
                UsuarioGrupo.id_usuario == usuario_id,
                UsuarioGrupo.tenant_id == tenant_id,
                UsuarioGrupo.excluido.is_(False),
            )
        )
    ).scalars().all()
    unidades = (
        await db.execute(
            select(UsuarioUnidadeTrabalho.id_unidade_trabalho).where(
                UsuarioUnidadeTrabalho.id_usuario == usuario_id,
                UsuarioUnidadeTrabalho.tenant_id == tenant_id,
                UsuarioUnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalars().all()
    return list(grupos), list(unidades)


async def _get_usuario_or_404(
    db: AsyncSession, usuario_id: int, tenant_id: int
) -> Usuario:
    user = (
        await db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return user


@router.get("/{usuario_id}", response_model=UsuarioDetail)
async def get_usuario(
    usuario_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDetail:
    user = await _get_usuario_or_404(db, usuario_id, tenant_id)
    grupos, unidades = await _load_links(db, usuario_id, tenant_id)
    return UsuarioDetail(
        **UsuarioOut.model_validate(user).model_dump(),
        grupos=grupos,
        unidades_extras=unidades,
    )


@router.post("", response_model=UsuarioDetail, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    payload: UsuarioCreate,
    _: Usuario = Depends(require_permission("usuario", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDetail:
    dup = (
        await db.execute(
            select(Usuario).where(
                Usuario.email == payload.email,
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    # SEC-1 (Commit 3): novo usuário nasce com must_change_password=true
    # (senha do payload é tratada como temporária — definida pelo admin) e
    # apenas bcrypt; MD5 legado fica vazio para alinhar com provisionamento e
    # reset administrativo. O usuário será obrigado a trocar a senha no
    # primeiro acesso (guard em get_current_user, Commit 2).
    user = Usuario(
        nome=payload.nome,
        email=payload.email,
        cpf=payload.cpf,
        senha="",  # MD5 legado limpo — só bcrypt
        senha_bcrypt=hash_password(payload.senha),
        id_unidade_trabalho=payload.id_unidade_trabalho,
        cargo=payload.cargo,
        ativo=payload.ativo,
        excluido=False,
        app=get_settings().app_name,
        tenant_id=tenant_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    for gid in payload.grupos:
        db.add(
            UsuarioGrupo(
                id_usuario=user.id,
                id_grupo=gid,
                tenant_id=tenant_id,
                ativo=True,
                excluido=False,
                app=get_settings().app_name,
            )
        )
    await db.commit()
    await db.refresh(user)
    grupos, unidades = await _load_links(db, user.id, tenant_id)
    return UsuarioDetail(
        **UsuarioOut.model_validate(user).model_dump(),
        grupos=grupos,
        unidades_extras=unidades,
    )


@router.put("/{usuario_id}", response_model=UsuarioDetail)
async def update_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    current: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDetail:
    user = await _get_usuario_or_404(db, usuario_id, tenant_id)

    data = payload.model_dump(exclude_unset=True)
    if "senha" in data and data["senha"]:
        plain = data["senha"]
        data["senha"] = hash_md5(plain)
        data["senha_bcrypt"] = hash_password(plain)
    elif "senha" in data:
        data.pop("senha")

    # Sigilo gradual — só super-usuário concede/altera credencial de acesso.
    if "nivel_acesso_sigilo" in data:
        from ..services.permissoes import load_permissions
        from ..services.sigilo import is_nivel_valido

        perms = await load_permissions(db, current.id, tenant_id=tenant_id)
        if not perms.is_super_usuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas super-usuário pode alterar a credencial de sigilo",
            )
        if not is_nivel_valido(data["nivel_acesso_sigilo"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nível de credencial inválido",
            )

    for k, v in data.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    grupos, unidades = await _load_links(db, user.id, tenant_id)
    return UsuarioDetail(
        **UsuarioOut.model_validate(user).model_dump(),
        grupos=grupos,
        unidades_extras=unidades,
    )


@router.post("/{usuario_id}/resetar-senha", response_model=ResetSenhaResponse)
async def resetar_senha(
    usuario_id: int,
    request: Request,
    current: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ResetSenhaResponse:
    """Gera senha temporária para o usuário (do tenant). Retorna a senha **uma
    única vez**; persiste só o hash moderno; audita. Sem cross-tenant."""
    user, senha_temp = await resetar_senha_usuario(
        db,
        usuario_id=usuario_id,
        tenant_id=tenant_id,
        ator_usuario_id=current.id,
        request=request,
    )
    return ResetSenhaResponse(
        id_usuario=user.id,
        senha_temporaria=senha_temp,
        aviso="Copie agora: esta senha temporária só é exibida uma vez.",
    )


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(
    usuario_id: int,
    current: Usuario = Depends(require_permission("usuario", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    if usuario_id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não pode excluir a si mesmo")
    user = await _get_usuario_or_404(db, usuario_id, tenant_id)
    user.excluido = True
    user.ativo = False
    await db.commit()


@router.put("/{usuario_id}/grupos", response_model=UsuarioDetail)
async def set_grupos(
    usuario_id: int,
    grupos: list[int],
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDetail:
    user = await _get_usuario_or_404(db, usuario_id, tenant_id)

    await db.execute(
        delete(UsuarioGrupo).where(
            UsuarioGrupo.id_usuario == usuario_id,
            UsuarioGrupo.tenant_id == tenant_id,
        )
    )
    for gid in grupos:
        db.add(
            UsuarioGrupo(
                id_usuario=usuario_id,
                id_grupo=gid,
                tenant_id=tenant_id,
                ativo=True,
                excluido=False,
                app=get_settings().app_name,
            )
        )
    await db.commit()
    g, u = await _load_links(db, usuario_id, tenant_id)
    return UsuarioDetail(
        **UsuarioOut.model_validate(user).model_dump(),
        grupos=g,
        unidades_extras=u,
    )


@router.put("/{usuario_id}/unidades", response_model=UsuarioDetail)
async def set_unidades(
    usuario_id: int,
    unidades: list[int],
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDetail:
    user = await _get_usuario_or_404(db, usuario_id, tenant_id)

    await db.execute(
        delete(UsuarioUnidadeTrabalho).where(
            UsuarioUnidadeTrabalho.id_usuario == usuario_id,
            UsuarioUnidadeTrabalho.tenant_id == tenant_id,
        )
    )
    for uid in unidades:
        db.add(
            UsuarioUnidadeTrabalho(
                id_usuario=usuario_id,
                id_unidade_trabalho=uid,
                tenant_id=tenant_id,
                excluido=False,
            )
        )
    await db.commit()
    g, u = await _load_links(db, usuario_id, tenant_id)
    return UsuarioDetail(
        **UsuarioOut.model_validate(user).model_dump(),
        grupos=g,
        unidades_extras=u,
    )
