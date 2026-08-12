"""Router do módulo de Protocolo — Fases P1 (Balcão) + P4 (CCD/TTD).

Endpoints P1:
- GET    /api/v2/protocolo/especies-documentais            — lista catálogo (ativas)
- POST   /api/v2/protocolo/especies-documentais            — admin: cadastra espécie
- PUT    /api/v2/protocolo/especies-documentais/{id}       — admin: edita espécie
- DELETE /api/v2/protocolo/especies-documentais/{id}       — admin: soft-delete
- POST   /api/v2/protocolo/balcao                          — registra protocolo de balcão
- GET    /api/v2/protocolo/{id}/etiqueta.pdf
- GET    /api/v2/protocolo/{id}/comprovante.pdf

Endpoints P4 (CCD + TTD + temporalidade):
- GET    /api/v2/protocolo/ccd-classes               — lista plana
- GET    /api/v2/protocolo/ccd-classes/tree          — árvore aninhada
- POST   /api/v2/protocolo/ccd-classes               — admin: cria classe
- PUT    /api/v2/protocolo/ccd-classes/{id}          — admin: edita
- DELETE /api/v2/protocolo/ccd-classes/{id}          — admin: soft-delete

- GET    /api/v2/protocolo/ttd-regras                — lista regras (com detalhes)
- POST   /api/v2/protocolo/ttd-regras                — admin: cria regra
- PUT    /api/v2/protocolo/ttd-regras/{id}           — admin: edita
- DELETE /api/v2/protocolo/ttd-regras/{id}           — admin: soft-delete

- GET    /api/v2/protocolo/sugerir-ccd               — sugestão por assunto/texto
- GET    /api/v2/processos/{id}/temporalidade        — cálculo da temporalidade
- GET    /api/v2/protocolo/vencendo-prazo            — relatório (próximos N dias)
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import (
    Assunto,
    CcdClasse,
    EspecieDocumental,
    Manifestante,
    Processo,
    TtdRegra,
    UnidadeTrabalho,
    Usuario,
)
from ..schemas.ccd import (
    CcdClasseCreate,
    CcdClasseOut,
    CcdClasseTreeNode,
    CcdClasseUpdate,
    SugestaoCcdOut,
    TemporalidadeOut,
    TtdRegraCreate,
    TtdRegraDetail,
    TtdRegraOut,
    TtdRegraUpdate,
)
from ..schemas.protocolo import (
    EspecieDocumentalCreate,
    EspecieDocumentalOut,
    EspecieDocumentalUpdate,
    ProtocoloBalcaoRequest,
    ProtocoloBalcaoResponse,
)
from ..services.pdf_protocolo import (
    gerar_comprovante_protocolo,
    gerar_etiqueta_protocolo,
)
from ..services.protocolo import ProtocoloError, abrir_protocolo_balcao
from ..services.temporalidade import (
    calcular_temporalidade,
    sugerir_ccd_por_assunto,
)

router = APIRouter(prefix="/protocolo", tags=["protocolo"])


# --- Espécies documentais (catálogo) -----------------------------------------
@router.get(
    "/especies-documentais",
    response_model=list[EspecieDocumentalOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_especies(
    incluir_inativas: bool = False,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(EspecieDocumental).where(EspecieDocumental.excluido.is_(False))
    if not incluir_inativas:
        stmt = stmt.where(EspecieDocumental.ativo.is_(True))
    stmt = tenant_filter(stmt, EspecieDocumental, tenant_id).order_by(
        EspecieDocumental.nome
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [EspecieDocumentalOut.model_validate(r) for r in rows]


@router.post(
    "/especies-documentais",
    response_model=EspecieDocumentalOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_especie(
    payload: EspecieDocumentalCreate,
    _: Usuario = Depends(require_permission("catalogo", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Flag única por tenant — checa antes pra erro amigável (DB já garante).
    existing = (
        await db.execute(
            select(EspecieDocumental).where(
                EspecieDocumental.tenant_id == tenant_id,
                EspecieDocumental.flag == payload.flag,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe espécie com flag '{payload.flag}' neste tenant.",
        )
    esp = EspecieDocumental(
        tenant_id=tenant_id,
        flag=payload.flag,
        nome=payload.nome,
        descricao=payload.descricao,
        ativo=True,
        excluido=False,
    )
    db.add(esp)
    await db.commit()
    await db.refresh(esp)
    return EspecieDocumentalOut.model_validate(esp)


@router.put("/especies-documentais/{esp_id}", response_model=EspecieDocumentalOut)
async def update_especie(
    esp_id: int,
    payload: EspecieDocumentalUpdate,
    _: Usuario = Depends(require_permission("catalogo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    esp = (
        await db.execute(
            select(EspecieDocumental).where(
                EspecieDocumental.id == esp_id,
                EspecieDocumental.tenant_id == tenant_id,
                EspecieDocumental.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if esp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Espécie não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(esp, k, v)
    await db.commit()
    await db.refresh(esp)
    return EspecieDocumentalOut.model_validate(esp)


@router.delete(
    "/especies-documentais/{esp_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_especie(
    esp_id: int,
    _: Usuario = Depends(require_permission("catalogo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    esp = (
        await db.execute(
            select(EspecieDocumental).where(
                EspecieDocumental.id == esp_id,
                EspecieDocumental.tenant_id == tenant_id,
                EspecieDocumental.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if esp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Espécie não encontrada")
    esp.excluido = True
    esp.ativo = False
    await db.commit()


# --- Balcão -----------------------------------------------------------------
@router.post(
    "/balcao",
    response_model=ProtocoloBalcaoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def protocolar_balcao(
    payload: ProtocoloBalcaoRequest,
    current: Usuario = Depends(require_permission("processo", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        processo = await abrir_protocolo_balcao(
            db, payload, tenant_id=tenant_id, usuario_id=current.id
        )
    except ProtocoloError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # Resolve nomes pra resposta enriquecida (1 round-trip, joinless via 3 queries).
    especie = (
        await db.execute(
            select(EspecieDocumental.nome).where(
                EspecieDocumental.id == processo.id_especie_documental
            )
        )
    ).scalar_one_or_none() if processo.id_especie_documental else None
    manifestante = (
        await db.execute(
            select(Manifestante.nome).where(Manifestante.id == processo.id_manifestante)
        )
    ).scalar_one()
    assunto = (
        await db.execute(select(Assunto.assunto).where(Assunto.id == processo.id_assunto))
    ).scalar_one()
    unidade = (
        await db.execute(
            select(UnidadeTrabalho.unidade_trabalho).where(
                UnidadeTrabalho.id == processo.id_unidade_proprietaria
            )
        )
    ).scalar_one()

    return ProtocoloBalcaoResponse(
        id=processo.id,
        numero_processo=processo.numero_processo,
        nup=processo.nup,
        data_hora_abertura=processo.data_hora_abertura,
        data_recepcao=processo.data_recepcao,
        canal_entrada=processo.canal_entrada or "balcao",  # type: ignore[arg-type]
        id_especie_documental=processo.id_especie_documental,
        especie_documental=especie,
        manifestante=manifestante,
        assunto=assunto,
        unidade_proprietaria=unidade,
    )


# --- PDFs do protocolo --------------------------------------------------------

async def _load_processo_protocolo(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> tuple[Processo, str | None, str, str, str]:
    """Carrega processo + nomes (espécie, manifestante, assunto, unidade)."""
    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo não encontrado")

    especie_nome: str | None = None
    if processo.id_especie_documental:
        especie_nome = (
            await db.execute(
                select(EspecieDocumental.nome).where(
                    EspecieDocumental.id == processo.id_especie_documental
                )
            )
        ).scalar_one_or_none()

    manifestante_nome = (
        await db.execute(
            select(Manifestante.nome).where(Manifestante.id == processo.id_manifestante)
        )
    ).scalar_one()
    assunto_nome = (
        await db.execute(select(Assunto.assunto).where(Assunto.id == processo.id_assunto))
    ).scalar_one()
    unidade_nome = (
        await db.execute(
            select(UnidadeTrabalho.unidade_trabalho).where(
                UnidadeTrabalho.id == processo.id_unidade_proprietaria
            )
        )
    ).scalar_one()

    return processo, especie_nome, manifestante_nome, assunto_nome, unidade_nome


@router.get(
    "/{processo_id}/etiqueta.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def etiqueta_pdf(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    processo, especie, manif, _assunto, _unidade = await _load_processo_protocolo(
        db, processo_id, tenant_id
    )
    pdf_bytes = gerar_etiqueta_protocolo(
        numero_processo=processo.numero_processo,
        manifestante=manif,
        especie=especie,
        data_recepcao=processo.data_recepcao or processo.data_hora_abertura,
        canal=processo.canal_entrada,
        nup=processo.nup,
    )
    fname = f"etiqueta-{processo.numero_processo.replace('/', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


@router.get(
    "/{processo_id}/comprovante.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def comprovante_pdf(
    processo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    processo, especie, manif, assunto, unidade = await _load_processo_protocolo(
        db, processo_id, tenant_id
    )
    pdf_bytes = gerar_comprovante_protocolo(
        numero_processo=processo.numero_processo,
        manifestante=manif,
        especie=especie,
        assunto=assunto,
        unidade=unidade,
        data_recepcao=processo.data_recepcao or processo.data_hora_abertura,
        observacao=processo.observacao,
        operador_nome=current.nome,
        nup=processo.nup,
    )
    fname = f"comprovante-{processo.numero_processo.replace('/', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# =============================================================================
#  P4 — CCD (Código de Classificação de Documentos)
# =============================================================================

@router.get(
    "/ccd-classes",
    response_model=list[CcdClasseOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_ccd_classes(
    incluir_inativas: bool = False,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CcdClasse).where(CcdClasse.excluido.is_(False))
    if not incluir_inativas:
        stmt = stmt.where(CcdClasse.ativo.is_(True))
    stmt = tenant_filter(stmt, CcdClasse, tenant_id).order_by(CcdClasse.codigo)
    rows = (await db.execute(stmt)).scalars().all()
    return [CcdClasseOut.model_validate(r) for r in rows]


@router.get(
    "/ccd-classes/tree",
    response_model=list[CcdClasseTreeNode],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def tree_ccd_classes(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna árvore aninhada (apenas classes ativas) — UI usa pra exibir."""
    stmt = (
        select(CcdClasse)
        .where(
            CcdClasse.tenant_id == tenant_id,
            CcdClasse.excluido.is_(False),
            CcdClasse.ativo.is_(True),
        )
        .order_by(CcdClasse.codigo)
    )
    rows = (await db.execute(stmt)).scalars().all()
    by_id: dict[int, CcdClasseTreeNode] = {
        r.id: CcdClasseTreeNode(
            id=r.id,
            codigo=r.codigo,
            nome=r.nome,
            descricao=r.descricao,
            palavras_chave=r.palavras_chave,
            ativo=r.ativo,
            filhos=[],
        )
        for r in rows
    }
    roots: list[CcdClasseTreeNode] = []
    for r in rows:
        node = by_id[r.id]
        if r.id_classe_pai and r.id_classe_pai in by_id:
            by_id[r.id_classe_pai].filhos.append(node)
        else:
            roots.append(node)
    return roots


@router.post(
    "/ccd-classes",
    response_model=CcdClasseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ccd_classe(
    payload: CcdClasseCreate,
    _: Usuario = Depends(require_permission("catalogo", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(CcdClasse).where(
                CcdClasse.tenant_id == tenant_id,
                CcdClasse.codigo == payload.codigo,
                CcdClasse.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Código CCD '{payload.codigo}' já existe."
        )
    if payload.id_classe_pai:
        pai = (
            await db.execute(
                select(CcdClasse).where(
                    CcdClasse.id == payload.id_classe_pai,
                    CcdClasse.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if pai is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Classe pai inexistente")
    classe = CcdClasse(
        tenant_id=tenant_id,
        codigo=payload.codigo,
        nome=payload.nome,
        descricao=payload.descricao,
        id_classe_pai=payload.id_classe_pai,
        palavras_chave=payload.palavras_chave,
        ativo=True,
        excluido=False,
    )
    db.add(classe)
    await db.commit()
    await db.refresh(classe)
    return CcdClasseOut.model_validate(classe)


@router.put("/ccd-classes/{classe_id}", response_model=CcdClasseOut)
async def update_ccd_classe(
    classe_id: int,
    payload: CcdClasseUpdate,
    _: Usuario = Depends(require_permission("catalogo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    classe = (
        await db.execute(
            select(CcdClasse).where(
                CcdClasse.id == classe_id,
                CcdClasse.tenant_id == tenant_id,
                CcdClasse.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if classe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe não encontrada")

    # Bloqueia ciclo: novo pai não pode ser a própria classe nem descendente.
    if payload.id_classe_pai is not None and payload.id_classe_pai != classe.id_classe_pai:
        if payload.id_classe_pai == classe.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Uma classe não pode ser pai de si mesma."
            )
        # walk ancestor chain do candidato — se classe_id aparece, é ciclo
        cur: int | None = payload.id_classe_pai
        visitados: set[int] = set()
        while cur is not None and cur not in visitados:
            visitados.add(cur)
            if cur == classe.id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Movimento criaria ciclo na hierarquia CCD.",
                )
            row = await db.execute(
                select(CcdClasse.id_classe_pai).where(
                    CcdClasse.id == cur, CcdClasse.tenant_id == tenant_id
                )
            )
            cur = row.scalar_one_or_none()

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(classe, k, v)
    await db.commit()
    await db.refresh(classe)
    return CcdClasseOut.model_validate(classe)


@router.delete("/ccd-classes/{classe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ccd_classe(
    classe_id: int,
    _: Usuario = Depends(require_permission("catalogo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    classe = (
        await db.execute(
            select(CcdClasse).where(
                CcdClasse.id == classe_id,
                CcdClasse.tenant_id == tenant_id,
                CcdClasse.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if classe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe não encontrada")
    # Bloqueia se há filhos ativos.
    filhos = (
        await db.execute(
            select(CcdClasse.id).where(
                CcdClasse.id_classe_pai == classe_id,
                CcdClasse.excluido.is_(False),
            )
        )
    ).first()
    if filhos is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Classe possui subclasses — desvincule ou exclua os filhos primeiro.",
        )
    classe.excluido = True
    classe.ativo = False
    await db.commit()


# =============================================================================
#  P4 — TTD (Tabela de Temporalidade Documental)
# =============================================================================

@router.get(
    "/ttd-regras",
    response_model=list[TtdRegraDetail],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_ttd_regras(
    id_ccd_classe: int | None = None,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TtdRegra, CcdClasse.codigo, CcdClasse.nome, EspecieDocumental.nome)
        .join(CcdClasse, CcdClasse.id == TtdRegra.id_ccd_classe)
        .outerjoin(
            EspecieDocumental, EspecieDocumental.id == TtdRegra.id_especie_documental
        )
        .where(TtdRegra.tenant_id == tenant_id, TtdRegra.excluido.is_(False))
        .order_by(CcdClasse.codigo, TtdRegra.id_especie_documental.nullsfirst())
    )
    if id_ccd_classe is not None:
        stmt = stmt.where(TtdRegra.id_ccd_classe == id_ccd_classe)
    rows = (await db.execute(stmt)).all()
    out: list[TtdRegraDetail] = []
    for regra, c_cod, c_nome, e_nome in rows:
        out.append(
            TtdRegraDetail(
                id=regra.id,
                id_ccd_classe=regra.id_ccd_classe,
                id_especie_documental=regra.id_especie_documental,
                anos_corrente=regra.anos_corrente,
                anos_intermediario=regra.anos_intermediario,
                destino_final=regra.destino_final,  # type: ignore[arg-type]
                observacao=regra.observacao,
                ativo=regra.ativo,
                classe_codigo=c_cod,
                classe_nome=c_nome,
                especie_nome=e_nome,
            )
        )
    return out


@router.post(
    "/ttd-regras", response_model=TtdRegraOut, status_code=status.HTTP_201_CREATED
)
async def create_ttd_regra(
    payload: TtdRegraCreate,
    _: Usuario = Depends(require_permission("catalogo", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Validações
    classe = (
        await db.execute(
            select(CcdClasse).where(
                CcdClasse.id == payload.id_ccd_classe,
                CcdClasse.tenant_id == tenant_id,
                CcdClasse.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if classe is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Classe CCD inexistente")
    if payload.id_especie_documental:
        esp = (
            await db.execute(
                select(EspecieDocumental).where(
                    EspecieDocumental.id == payload.id_especie_documental,
                    EspecieDocumental.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if esp is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Espécie inexistente")

    # Duplicada? (índice parcial único também garante, mas erro amigável aqui)
    dup_stmt = select(TtdRegra).where(
        TtdRegra.tenant_id == tenant_id,
        TtdRegra.id_ccd_classe == payload.id_ccd_classe,
        TtdRegra.excluido.is_(False),
    )
    if payload.id_especie_documental is None:
        dup_stmt = dup_stmt.where(TtdRegra.id_especie_documental.is_(None))
    else:
        dup_stmt = dup_stmt.where(
            TtdRegra.id_especie_documental == payload.id_especie_documental
        )
    if (await db.execute(dup_stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe regra TTD pra essa combinação classe+espécie.",
        )

    regra = TtdRegra(
        tenant_id=tenant_id,
        id_ccd_classe=payload.id_ccd_classe,
        id_especie_documental=payload.id_especie_documental,
        anos_corrente=payload.anos_corrente,
        anos_intermediario=payload.anos_intermediario,
        destino_final=payload.destino_final,
        observacao=payload.observacao,
        ativo=True,
        excluido=False,
    )
    db.add(regra)
    await db.commit()
    await db.refresh(regra)
    return TtdRegraOut.model_validate(regra)


@router.put("/ttd-regras/{regra_id}", response_model=TtdRegraOut)
async def update_ttd_regra(
    regra_id: int,
    payload: TtdRegraUpdate,
    _: Usuario = Depends(require_permission("catalogo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    regra = (
        await db.execute(
            select(TtdRegra).where(
                TtdRegra.id == regra_id,
                TtdRegra.tenant_id == tenant_id,
                TtdRegra.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if regra is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regra não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(regra, k, v)
    await db.commit()
    await db.refresh(regra)
    return TtdRegraOut.model_validate(regra)


@router.delete("/ttd-regras/{regra_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ttd_regra(
    regra_id: int,
    _: Usuario = Depends(require_permission("catalogo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    regra = (
        await db.execute(
            select(TtdRegra).where(
                TtdRegra.id == regra_id,
                TtdRegra.tenant_id == tenant_id,
                TtdRegra.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if regra is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regra não encontrada")
    regra.excluido = True
    regra.ativo = False
    await db.commit()


# =============================================================================
#  P4 — Sugestão de CCD + Temporalidade do processo + Relatório vencimento
# =============================================================================

@router.get(
    "/sugerir-ccd",
    response_model=list[SugestaoCcdOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def sugerir_ccd(
    id_assunto: int | None = None,
    texto: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Sugere classes CCD por tokens do assunto + texto livre."""
    if id_assunto is None and not texto:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Informe id_assunto e/ou texto.",
        )
    return await sugerir_ccd_por_assunto(
        db,
        tenant_id=tenant_id,
        id_assunto=id_assunto,
        texto_extra=texto,
        limit=limit,
    )


@router.get(
    "/vencendo-prazo",
    response_model=list[TemporalidadeOut],
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def relatorio_vencendo_prazo(
    dias: int = Query(default=180, ge=1, le=3650, description="Janela em dias"),
    incluir_permanentes: bool = False,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista processos cujo `fim_fase_intermediaria` cai nos próximos N dias.

    Atenção: cálculo em Python (sem WHERE no SQL) porque a regra TTD depende
    de hierarquia da classe — não dá pra resolver tudo em 1 query. Filtra
    processos com classe atribuída e pagina-aplica `dias` em memória.
    Pra escala grande (>5k processos sem regra), tornar em job assíncrono.
    """
    classes_set_stmt = select(Processo.id).where(
        Processo.tenant_id == tenant_id,
        Processo.excluido.is_(False),
        Processo.ativo.is_(True),
        Processo.id_ccd_classe.is_not(None),
    )
    ids = [row.id for row in (await db.execute(classes_set_stmt)).all()]
    limite = date.today() + timedelta(days=dias)
    out: list[TemporalidadeOut] = []
    for pid in ids:
        try:
            t = await calcular_temporalidade(db, pid, tenant_id=tenant_id)
        except ValueError:
            continue
        if t.fim_fase_intermediaria is None:
            continue
        if not incluir_permanentes and t.destino_final == "GUARDA_PERMANENTE":
            continue
        if t.fim_fase_intermediaria <= limite:
            out.append(t)
    out.sort(key=lambda x: x.fim_fase_intermediaria or date.max)
    return out
