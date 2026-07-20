"""Minutas de documento + templates — routers (PR-B).

- `templates_router` (`/templates-documento`): biblioteca de modelos. LEITURA
  (listar/obter/placeholders) exige `processo.atualizar` — mesma população que
  redige documentos (o picker do editor). ESCRITA (criar/editar/excluir) exige a
  transação de admin `minuta_template`.
- `minutas_router`: CRUD de minutas por processo, gated por `processo.atualizar`
  (mesma permissão do upload de anexo). A FINALIZAÇÃO é adicionada no PR-C.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id, require_tenant_slug
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.minuta import (
    MinutaCreate,
    MinutaHistoricoListResponse,
    MinutaListItem,
    MinutaOut,
    MinutaUpdate,
    PlaceholderInfo,
    TemplateDocumentoCreate,
    TemplateDocumentoOut,
    TemplateDocumentoUpdate,
)
from ..services import minutas as svc
from ..services.placeholders import PLACEHOLDERS_DISPONIVEIS

templates_router = APIRouter(prefix="/templates-documento", tags=["minutas"])


@templates_router.get("/placeholders-disponiveis", response_model=list[PlaceholderInfo])
async def list_placeholders(
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    __: int = Depends(require_tenant_id),
) -> list[PlaceholderInfo]:
    return [PlaceholderInfo(**p) for p in PLACEHOLDERS_DISPONIVEIS]


@templates_router.get("", response_model=list[TemplateDocumentoOut])
async def list_templates(
    categoria: str | None = None,
    apenas_ativos: bool = False,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateDocumentoOut]:
    rows = await svc.listar_templates(
        db, tenant_id=tenant_id, categoria=categoria, apenas_ativos=apenas_ativos
    )
    return [TemplateDocumentoOut.model_validate(r) for r in rows]


@templates_router.get("/{template_id}", response_model=TemplateDocumentoOut)
async def get_template(
    template_id: int,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> TemplateDocumentoOut:
    t = await svc.obter_template(db, tenant_id=tenant_id, template_id=template_id)
    return TemplateDocumentoOut.model_validate(t)


@templates_router.post(
    "", response_model=TemplateDocumentoOut, status_code=status.HTTP_201_CREATED
)
async def create_template(
    payload: TemplateDocumentoCreate,
    usuario: Usuario = Depends(require_permission("minuta_template", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> TemplateDocumentoOut:
    t = await svc.criar_template(
        db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload
    )
    return TemplateDocumentoOut.model_validate(t)


@templates_router.put("/{template_id}", response_model=TemplateDocumentoOut)
async def update_template(
    template_id: int,
    payload: TemplateDocumentoUpdate,
    _: Usuario = Depends(require_permission("minuta_template", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> TemplateDocumentoOut:
    t = await svc.atualizar_template(
        db, tenant_id=tenant_id, template_id=template_id, payload=payload
    )
    return TemplateDocumentoOut.model_validate(t)


@templates_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    _: Usuario = Depends(require_permission("minuta_template", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.excluir_template(db, tenant_id=tenant_id, template_id=template_id)


# ================================ Minutas ===================================
minutas_router = APIRouter(tags=["minutas"])


@minutas_router.get(
    "/processos/{processo_id}/minutas", response_model=list[MinutaListItem]
)
async def list_minutas(
    processo_id: int,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[MinutaListItem]:
    rows = await svc.listar_minutas(db, tenant_id=tenant_id, processo_id=processo_id)
    return [MinutaListItem.model_validate(r) for r in rows]


@minutas_router.post(
    "/processos/{processo_id}/minutas",
    response_model=MinutaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_minuta(
    processo_id: int,
    payload: MinutaCreate,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    m = await svc.criar_minuta(
        db,
        tenant_id=tenant_id,
        processo_id=processo_id,
        usuario=usuario,
        payload=payload,
    )
    return MinutaOut.model_validate(m)


@minutas_router.get("/minutas/{minuta_id}", response_model=MinutaOut)
async def get_minuta(
    minuta_id: int,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    m = await svc.obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    return MinutaOut.model_validate(m)


@minutas_router.get("/minutas/{minuta_id}/historico", response_model=MinutaHistoricoListResponse)
async def get_minuta_historico(
    minuta_id: int,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaHistoricoListResponse:
    versoes = await svc.listar_historico_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    return MinutaHistoricoListResponse(versoes=[v for v in versoes])


@minutas_router.put("/minutas/{minuta_id}", response_model=MinutaOut)
async def update_minuta(
    minuta_id: int,
    payload: MinutaUpdate,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    m = await svc.atualizar_minuta(
        db,
        tenant_id=tenant_id,
        minuta_id=minuta_id,
        usuario=usuario,
        payload=payload,
    )
    return MinutaOut.model_validate(m)


@minutas_router.delete(
    "/minutas/{minuta_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_minuta(
    minuta_id: int,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.excluir_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id, usuario_id=usuario.id)


@minutas_router.post("/minutas/{minuta_id}/finalizar", response_model=MinutaOut)
async def finalizar_minuta(
    minuta_id: int,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    m = await svc.finalizar_minuta(
        db,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        minuta_id=minuta_id,
        usuario_id=usuario.id,
    )
    return MinutaOut.model_validate(m)


# ======================== Google Docs (PR-F) ========================


@minutas_router.post("/minutas/{minuta_id}/criar-em-google", response_model=MinutaOut)
async def criar_minuta_em_google(
    minuta_id: int,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    """Create a Google Doc for this minuta.

    Prerequisites:
    - User must have connected Google Docs (GoogleCredencial record exists)
    - Minuta must be in rascunho status
    """
    m = await svc.criar_google_doc_para_minuta(
        db, tenant_id=tenant_id, minuta_id=minuta_id, usuario_id=usuario.id
    )
    return MinutaOut.model_validate(m)


@minutas_router.get("/minutas/{minuta_id}/google-editor-url")
async def get_google_editor_url(
    minuta_id: int,
    _: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Get URL to open Google Docs editor for this minuta.

    Returns:
        {"url": "https://docs.google.com/document/d/.../edit"}
    """
    m = await svc.obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    if not m.google_doc_url:
        raise ValueError("Minuta does not have a Google Doc URL")
    return {"url": m.google_doc_url}


@minutas_router.post("/minutas/{minuta_id}/sincronizar-google", response_model=MinutaOut)
async def sincronizar_minuta_google(
    minuta_id: int,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MinutaOut:
    """Sync latest content from Google Doc.

    Note: For now, this is a placeholder. Full DOCX-to-HTML sync
    would require python-docx parsing and is deferred to v2.
    """
    m = await svc.obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    # Placeholder: just return current minuta
    # TODO: Pull DOCX, extract text, update corpo_html
    return MinutaOut.model_validate(m)


@minutas_router.delete("/minutas/{minuta_id}/arquivar-google", status_code=status.HTTP_204_NO_CONTENT)
async def arquivar_minuta_google(
    minuta_id: int,
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Move Google Doc to trash (soft delete from Google Drive).

    Note: Minuta record is NOT deleted; only the linked Google Doc is archived.
    """
    await svc.arquivar_google_doc_para_minuta(
        db, tenant_id=tenant_id, minuta_id=minuta_id, usuario_id=usuario.id
    )
