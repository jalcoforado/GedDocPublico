"""Transporte Regulado PR-1 — Vistorias Regulatorias de Veiculos.

Cobre o servico de dominio: CRUD tenant-scoped para vistorias (inspeções
regulatórias realizadas por auditores). Isolamento RLS cross-tenant,
soft-delete, validações de parecer e data_vistoria, RLS de auditor.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.main import app
from app.models import Usuario
from app.models import usuario as user_models
from app.schemas.transporte_regulado import (
    PermissionarioCreate,
    VeiculoReguladoCreate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaRenovarInput,
    VeiculoVistoriaUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("vis")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Vis", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    h = uuid.uuid4().hex.upper()
    letras = "".join(c for c in h if c.isalpha())[:3].ljust(3, "X")
    digitos = "".join(c for c in h if c.isdigit())[:4].ljust(4, "0")
    return f"{letras}{digitos}"


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


async def _permissionario(admin_engine, tenant_id):
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(nome="Dono", cpf=_cpf(), tipo_servico="taxi"),
        )


async def _veiculo(admin_engine, tenant_id):
    perm = await _permissionario(admin_engine, tenant_id)
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoReguladoCreate(
                id_permissionario=perm.id, placa=_placa(), marca="Fiat", modelo="Uno",
                tipo_servico="taxi",
            ),
        )


async def _usuario(admin_engine, tenant_id, nome="Auditor", cpf=None):
    """Cria um usuario na tenant para servir como auditor."""
    if cpf is None:
        cpf = _cpf()
    async with _sm(admin_engine)() as s:
        from sqlalchemy import text as sa_text
        async with s.begin():
            result = await s.execute(
                sa_text("""
                    INSERT INTO utils.usuario (tenant_id, nome, cpf, email, senha, ativo)
                    VALUES (:tenant_id, :nome, :cpf, :email, :senha, :ativo)
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id,
                    "nome": nome,
                    "cpf": cpf,
                    "email": f"{cpf}@t.local",
                    "senha": "dummy_hash",
                    "ativo": True,
                }
            )
            usuario_id = result.scalar_one()
        return usuario_id


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Emula usuário autenticado por dependency_overrides.

    Mesmo padrão de test_permissoes_modulo.py::_as_user. Existe porque este
    arquivo era inteiramente de service e não tinha harness de HTTP.
    """

    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        arreio_tenant_http(tenant_id, tenant_slug)

    return _setup


@pytest.mark.asyncio
async def test_vistoria_criar_basica(admin_engine):
    """Criar vistoria com dados basicos."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    agora = datetime.utcnow()

    async with _sm(admin_engine)() as s:
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Veiculo passou na vistoria regulatoria.",
                data_vistoria=agora,
            ),
        )

    assert vist.id is not None
    assert vist.tenant_id == tenant.id
    assert vist.id_veiculo == veiculo.id
    assert vist.id_auditor == auditor_id
    assert vist.resultado == "aprovado"
    assert vist.excluido is False
    assert vist.criado_em is not None


@pytest.mark.asyncio
async def test_vistoria_validacao_parecer_minimo(admin_engine):
    """Validacao: parecer deve ter no minimo 10 caracteres."""
    with pytest.raises(ValidationError) as exc:
        VeiculoVistoriaCreate(
            resultado="aprovado",
            parecer="Curto",
            data_vistoria=datetime.utcnow(),
        )

    assert "parecer" in str(exc.value)


@pytest.mark.asyncio
async def test_vistoria_validacao_parecer_vazio(admin_engine):
    """Validacao: parecer nao pode ser vazio apos strip."""
    with pytest.raises(ValidationError) as exc:
        VeiculoVistoriaCreate(
            resultado="aprovado",
            parecer="   ",
            data_vistoria=datetime.utcnow(),
        )

    assert "parecer" in str(exc.value)


@pytest.mark.asyncio
async def test_vistoria_validacao_data_futura(admin_engine):
    """Validacao: data_vistoria nao pode ser futura."""
    futuro = datetime.utcnow() + timedelta(days=1)

    with pytest.raises(ValidationError) as exc:
        VeiculoVistoriaCreate(
            resultado="aprovado",
            parecer="Texto com mais de 10 caracteres",
            data_vistoria=futuro,
        )

    assert "data_vistoria" in str(exc.value)


@pytest.mark.asyncio
async def test_vistoria_obter(admin_engine):
    """Obter uma vistoria pelo ID."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        criada = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="reprovado",
                parecer="Veiculo nao passou na vistoria regulatoria.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist_id = criada.id

        obtida = await tr_svc.obter_vistoria(s, tenant_id=tenant.id, vistoria_id=vist_id)

    assert obtida.id == vist_id
    assert obtida.resultado == "reprovado"


@pytest.mark.asyncio
async def test_vistoria_obter_404_nao_existe(admin_engine):
    """Obter vistoria inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_vistoria(s, tenant_id=tenant.id, vistoria_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_obter_404_cross_tenant(admin_engine):
    """Obter vistoria de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant1.id)
    auditor_id = await _usuario(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant1.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Veiculo em bom estado para vistoria regulatoria.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist_id = vist.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_vistoria(s, tenant_id=tenant2.id, vistoria_id=vist_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_listar(admin_engine):
    """Listar vistorias de um veiculo."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor1_id = await _usuario(admin_engine, tenant.id, nome="Auditor1")
    auditor2_id = await _usuario(admin_engine, tenant.id, nome="Auditor2")

    async with _sm(admin_engine)() as s:
        vist1 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor1_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Primeira vistoria com resultado positivo.",
                data_vistoria=datetime.utcnow() - timedelta(days=1),
            ),
        )
        vist2 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor2_id,
            payload=VeiculoVistoriaCreate(
                resultado="condicional",
                parecer="Segunda vistoria com resultado condicional.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vistorias, _ = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(vistorias) == 2
    assert vist1.id in [v.id for v in vistorias]
    assert vist2.id in [v.id for v in vistorias]


@pytest.mark.asyncio
async def test_vistoria_listar_ordenacao_descendente(admin_engine):
    """Listar vistorias retorna ordenadas por data_vistoria descendente."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        agora = datetime.utcnow()
        ontem = agora - timedelta(days=1)

        vist1 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria de ontem realizada.",
                data_vistoria=ontem,
            ),
        )
        vist2 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="condicional",
                parecer="Vistoria de hoje realizada agora.",
                data_vistoria=agora,
            ),
        )
        vistorias, _ = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    # Mais recente primeiro (data_vistoria DESC)
    assert vistorias[0].id == vist2.id
    assert vistorias[1].id == vist1.id


@pytest.mark.asyncio
async def test_vistoria_listar_excluidas_nao_retornadas(admin_engine):
    """Listar vistorias nao inclui excluidas (soft-delete)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor1_id = await _usuario(admin_engine, tenant.id, nome="Auditor1")
    auditor2_id = await _usuario(admin_engine, tenant.id, nome="Auditor2")

    async with _sm(admin_engine)() as s:
        vist1 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor1_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Primeira vistoria regulatoria do veiculo.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist2 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor2_id,
            payload=VeiculoVistoriaCreate(
                resultado="condicional",
                parecer="Segunda vistoria regulatoria realizada.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        await tr_svc.excluir_vistoria(s, tenant_id=tenant.id, vistoria_id=vist1.id)

        vistorias, _ = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(vistorias) == 1
    assert vistorias[0].id == vist2.id


@pytest.mark.asyncio
async def test_vistoria_listar_vazio(admin_engine):
    """Listar vistorias de veiculo sem vistorias retorna lista vazia."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        vistorias, _ = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(vistorias) == 0


@pytest.mark.asyncio
async def test_vistoria_atualizar(admin_engine):
    """Atualizar vistoria."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="pendente",
                parecer="Vistoria em analise e avaliacao.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist_id = vist.id

        atualizada = await tr_svc.atualizar_vistoria(
            s, tenant_id=tenant.id, vistoria_id=vist_id,
            payload=VeiculoVistoriaUpdate(
                resultado="aprovado",
                parecer="Vistoria completa: veiculo aprovado para operacao.",
            ),
        )

    assert atualizada.resultado == "aprovado"
    assert "aprovado" in atualizada.parecer.lower()


@pytest.mark.asyncio
async def test_vistoria_atualizar_parcial(admin_engine):
    """Atualizar vistoria com atualizacao parcial (so parecer)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="pendente",
                parecer="Vistoria com resultado pendente.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist_id = vist.id
        resultado_original = vist.resultado

        atualizada = await tr_svc.atualizar_vistoria(
            s, tenant_id=tenant.id, vistoria_id=vist_id,
            payload=VeiculoVistoriaUpdate(
                parecer="Parecer atualizado com observacoes adicionais.",
            ),
        )

    assert atualizada.resultado == resultado_original
    assert atualizada.parecer == "Parecer atualizado com observacoes adicionais."


@pytest.mark.asyncio
async def test_vistoria_atualizar_404_nao_existe(admin_engine):
    """Atualizar vistoria inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.atualizar_vistoria(
                s, tenant_id=tenant.id, vistoria_id=99999,
                payload=VeiculoVistoriaUpdate(resultado="aprovado"),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_excluir_soft_delete(admin_engine):
    """Excluir vistoria usa soft-delete (excluido=true)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Veiculo em excelentes condicoes para vistoria.",
                data_vistoria=datetime.utcnow(),
            ),
        )
        vist_id = vist.id

        await tr_svc.excluir_vistoria(s, tenant_id=tenant.id, vistoria_id=vist_id)

        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_vistoria(s, tenant_id=tenant.id, vistoria_id=vist_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_criar_auditor_inexistente(admin_engine):
    """Criar vistoria com auditor inexistente falha."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException):
            await tr_svc.criar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=99999,
                payload=VeiculoVistoriaCreate(
                    resultado="aprovado",
                    parecer="Vistoria com auditor inexistente.",
                    data_vistoria=datetime.utcnow(),
                ),
            )


@pytest.mark.asyncio
async def test_vistoria_criar_veiculo_inexistente(admin_engine):
    """Criar vistoria com veiculo inexistente falha."""
    tenant = await _provisionar(admin_engine)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException):
            await tr_svc.criar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=99999, auditor_id=auditor_id,
                payload=VeiculoVistoriaCreate(
                    resultado="aprovado",
                    parecer="Vistoria com veiculo inexistente.",
                    data_vistoria=datetime.utcnow(),
                ),
            )


# P1.1: Renovação/Revalidação de Vistorias


@pytest.mark.asyncio
async def test_vistoria_listar_vencidas_basico(admin_engine):
    """Listar vistorias vencidas (data_validade <= hoje)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)
    amanha = hoje + timedelta(days=1)

    async with _sm(admin_engine)() as s:
        # Vencida ontem
        vist_vencida = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria que venceu ontem.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )
        # Vigente (amanha)
        vist_vigente = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria que ainda eh valida.",
                data_vistoria=datetime.utcnow(),
                data_validade=amanha,
            ),
        )

        vencidas, _ = await tr_svc.listar_vistorias_vencidas(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id
        )

    assert len(vencidas) == 1
    assert vencidas[0].id == vist_vencida.id


@pytest.mark.asyncio
async def test_vistoria_listar_vencidas_ordem_descendente(admin_engine):
    """Listar vencidas retorna ordenadas por data_vistoria descendente."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    hoje = datetime.utcnow().date()
    data_vencida = hoje - timedelta(days=2)

    async with _sm(admin_engine)() as s:
        vist1_dt = datetime.combine(data_vencida, datetime.min.time()) + timedelta(hours=8)
        vist2_dt = datetime.combine(data_vencida, datetime.min.time()) + timedelta(hours=10)

        vist1 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Primeira vistoria vencida (mais antiga).",
                data_vistoria=vist1_dt,
                data_validade=data_vencida,
            ),
        )
        vist2 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Segunda vistoria vencida (mais recente).",
                data_vistoria=vist2_dt,
                data_validade=data_vencida,
            ),
        )

        vencidas, _ = await tr_svc.listar_vistorias_vencidas(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id
        )

    # Mais recente primeiro (data_vistoria DESC)
    assert len(vencidas) == 2
    assert vencidas[0].id == vist2.id
    assert vencidas[1].id == vist1.id


@pytest.mark.asyncio
async def test_vistoria_listar_vencidas_vazio(admin_engine):
    """Listar vencidas de veiculo sem vencidas retorna lista vazia."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    hoje = datetime.utcnow().date()
    amanha = hoje + timedelta(days=1)

    async with _sm(admin_engine)() as s:
        # Só vistorias vigentes
        await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria que ainda eh valida.",
                data_vistoria=datetime.utcnow(),
                data_validade=amanha,
            ),
        )

        vencidas, _ = await tr_svc.listar_vistorias_vencidas(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id
        )

    assert len(vencidas) == 0


@pytest.mark.asyncio
async def test_vistoria_listar_vencidas_sem_data_validade(admin_engine):
    """Listar vencidas exclui vistorias sem data_validade."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        # Vistoria sem data_validade (nao expira)
        await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria permanente sem validade.",
                data_vistoria=datetime.utcnow(),
            ),
        )

        vencidas, _ = await tr_svc.listar_vistorias_vencidas(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id
        )

    assert len(vencidas) == 0


@pytest.mark.asyncio
async def test_vistoria_renovar_basico(admin_engine):
    """Renovar vistoria vencida cria novo registro."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)
    proximo_ano = hoje + timedelta(days=365)

    async with _sm(admin_engine)() as s:
        # Criar vistoria vencida
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria original vencida ontem.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )

        # Renovar
        vist_renovada = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist_original.id, auditor_id=novo_auditor_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Vistoria renovada apos vencimento.",
                data_validade=proximo_ano,
            ),
        )

    assert vist_renovada.id != vist_original.id
    assert vist_renovada.renovada_de == vist_original.id
    assert vist_renovada.id_auditor == novo_auditor_id
    assert vist_renovada.id_veiculo == veiculo.id
    assert vist_renovada.data_validade == proximo_ano


@pytest.mark.asyncio
async def test_vistoria_renovar_com_data_validade(admin_engine):
    """Renovar pode especificar nova data_validade."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)
    nova_data_validade = hoje + timedelta(days=180)

    async with _sm(admin_engine)() as s:
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="condicional",
                parecer="Vistoria original condicional.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )

        vist_renovada = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist_original.id, auditor_id=novo_auditor_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Renovacao apos condicionalidade atendida.",
                data_validade=nova_data_validade,
            ),
        )

    assert vist_renovada.data_validade == nova_data_validade


@pytest.mark.asyncio
async def test_vistoria_renovar_vistoria_inexistente(admin_engine):
    """Renovar vistoria inexistente falha."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id,
                vistoria_id=99999, auditor_id=auditor_id,
                payload=VeiculoVistoriaRenovarInput(
                    resultado="aprovado",
                    parecer="Renovacao de vistoria inexistente.",
                    data_validade=datetime.utcnow().date() + timedelta(days=365),
                ),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_renovar_vistoria_vigente(admin_engine):
    """Renovar vistoria que ainda eh vigente falha."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    amanha = hoje + timedelta(days=1)

    async with _sm(admin_engine)() as s:
        # Criar vistoria vigente
        vist_vigente = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria que ainda eh valida.",
                data_vistoria=datetime.utcnow(),
                data_validade=amanha,
            ),
        )

        # Tentar renovar
        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id,
                vistoria_id=vist_vigente.id, auditor_id=novo_auditor_id,
                payload=VeiculoVistoriaRenovarInput(
                    resultado="aprovado",
                    parecer="Renovacao de vistoria vigente.",
                    data_validade=hoje + timedelta(days=365),
                ),
            )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_vistoria_renovar_auditor_inexistente(admin_engine):
    """Renovar com auditor inexistente falha."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    async with _sm(admin_engine)() as s:
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria vencida.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )

        with pytest.raises(HTTPException):
            await tr_svc.renovar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id,
                vistoria_id=vist_original.id, auditor_id=99999,
                payload=VeiculoVistoriaRenovarInput(
                    resultado="aprovado",
                    parecer="Renovacao com auditor inexistente.",
                    data_validade=hoje + timedelta(days=365),
                ),
            )


@pytest.mark.asyncio
async def test_vistoria_renovar_cross_tenant_404(admin_engine):
    """Renovar vistoria de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    veiculo1 = await _veiculo(admin_engine, tenant1.id)
    auditor1_id = await _usuario(admin_engine, tenant1.id)
    auditor2_id = await _usuario(admin_engine, tenant2.id)

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    async with _sm(admin_engine)() as s:
        # Criar vistoria em tenant1
        vist = await tr_svc.criar_vistoria(
            s, tenant_id=tenant1.id, veiculo_id=veiculo1.id, auditor_id=auditor1_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria de tenant1.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )

    # Tentar renovar como tenant2
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_vistoria(
                s, tenant_id=tenant2.id, veiculo_id=veiculo1.id,
                vistoria_id=vist.id, auditor_id=auditor2_id,
                payload=VeiculoVistoriaRenovarInput(
                    resultado="aprovado",
                    parecer="Tentativa cross-tenant.",
                    data_validade=hoje + timedelta(days=365),
                ),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vistoria_renovacao_cria_nova_com_novo_id(admin_engine):
    """Renovacao cria novo registro com ID diferente do original."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    async with _sm(admin_engine)() as s:
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria original.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )
        vist_id_original = vist_original.id

        vist_renovada = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist_id_original, auditor_id=novo_auditor_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Vistoria renovada.",
                data_validade=hoje + timedelta(days=365),
            ),
        )

    assert vist_renovada.id != vist_id_original


@pytest.mark.asyncio
async def test_vistoria_renovacao_copia_campos_basicos(admin_engine):
    """Renovacao copia resultado, parecer, observacoes da entrada."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    async with _sm(admin_engine)() as s:
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria original.",
                observacoes="Observações da vistoria original.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )

        vist_renovada = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist_original.id, auditor_id=novo_auditor_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="condicional",
                parecer="Vistoria renovada com resultado diferente.",
                observacoes="Observações da renovação.",
                data_validade=hoje + timedelta(days=365),
            ),
        )

    assert vist_renovada.resultado == "condicional"
    assert vist_renovada.parecer == "Vistoria renovada com resultado diferente."
    assert vist_renovada.observacoes == "Observações da renovação."


@pytest.mark.asyncio
async def test_vistoria_renovacao_atualiza_criado_em(admin_engine):
    """Criado_em da renovacao eh atual (diferente do original)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor_id = await _usuario(admin_engine, tenant.id)
    novo_auditor_id = await _usuario(admin_engine, tenant.id, nome="Novo Auditor")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    async with _sm(admin_engine)() as s:
        vist_original = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria original.",
                data_vistoria=datetime.combine(ontem, datetime.min.time()),
                data_validade=ontem,
            ),
        )
        criado_em_original = vist_original.criado_em

        vist_renovada = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist_original.id, auditor_id=novo_auditor_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Vistoria renovada.",
                data_validade=hoje + timedelta(days=365),
            ),
        )

    # criado_em da renovação é mais recente
    assert vist_renovada.criado_em > criado_em_original


@pytest.mark.asyncio
async def test_vistoria_renovacao_historico_chain(admin_engine):
    """Pode renovar uma renovacao (chain de renovacoes)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    auditor1_id = await _usuario(admin_engine, tenant.id, nome="Auditor1")
    auditor2_id = await _usuario(admin_engine, tenant.id, nome="Auditor2")
    auditor3_id = await _usuario(admin_engine, tenant.id, nome="Auditor3")

    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)
    semana_passada = hoje - timedelta(days=7)

    async with _sm(admin_engine)() as s:
        # Vistoria original
        vist1 = await tr_svc.criar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor1_id,
            payload=VeiculoVistoriaCreate(
                resultado="aprovado",
                parecer="Vistoria original.",
                data_vistoria=datetime.combine(semana_passada, datetime.min.time()),
                data_validade=semana_passada,
            ),
        )

        # Primeira renovacao
        vist2 = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist1.id, auditor_id=auditor2_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Primeira renovacao.",
                data_validade=ontem,
            ),
        )
        assert vist2.renovada_de == vist1.id

        # Segunda renovacao (renovar a renovacao)
        vist3 = await tr_svc.renovar_vistoria(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            vistoria_id=vist2.id, auditor_id=auditor3_id,
            payload=VeiculoVistoriaRenovarInput(
                resultado="aprovado",
                parecer="Segunda renovacao (renovacao da renovacao).",
                data_validade=hoje + timedelta(days=365),
            ),
        )
        assert vist3.renovada_de == vist2.id
        assert vist3.renovada_de != vist1.id


@pytest.mark.asyncio
async def test_http_vencidas_nao_e_engolida_por_vistoria_id(admin_engine):
    """A rota /vencidas tem de ser alcançável por HTTP, não só pelo service.

    O FastAPI casa rotas na ordem de declaração. Com `/{vistoria_id}: int`
    declarada antes, esta requisição batia nela, falhava a validação do int e
    voltava 422 sem nunca chegar no handler. Os dois testes de vencidas acima
    chamam o service direto — endpoint morto, service verde.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        veiculo = await _veiculo(admin_engine, tenant.id)
        auditor_id = await _usuario(admin_engine, tenant.id)

        ontem = datetime.utcnow().date() - timedelta(days=1)
        async with _sm(admin_engine)() as s:
            vencida = await tr_svc.criar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
                payload=VeiculoVistoriaCreate(
                    resultado="aprovado",
                    parecer="Vistoria que venceu ontem.",
                    data_vistoria=datetime.combine(ontem, datetime.min.time()),
                    data_validade=ontem,
                ),
            )

        async with _sm(admin_engine)() as s:
            # ORDER BY id ASC é obrigatório aqui, não estético: o tenant tem
            # duas linhas em utils.usuario neste ponto — o admin/SU criado por
            # `provisionar_tenant` e o auditor criado acima por `_usuario`.
            # Sem ordenação, `LIMIT 1` devolve uma linha arbitrária do seq
            # scan; se pegar o auditor (sem grupo/SU), `require_permission`
            # barra com 403 antes de a rota /vencidas sequer ser resolvida.
            # O admin é sempre inserido primeiro, então id ASC garante ele.
            su_id = int((await s.execute(
                text(
                    "SELECT id FROM utils.usuario WHERE tenant_id=:t "
                    "ORDER BY id ASC LIMIT 1"
                ),
                {"t": tenant.id},
            )).scalar_one())

        _as_user(admin_engine, su_id, tenant.id, tenant.slug)()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                f"/api/v2/transporte-regulado/veiculos/{veiculo.id}/vistorias/vencidas"
            )

        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()["items"]] == [vencida.id]
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
