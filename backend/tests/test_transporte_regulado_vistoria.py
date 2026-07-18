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
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import usuario as user_models
from app.schemas.transporte_regulado import (
    PermissionarioCreate,
    VeiculoReguladoCreate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


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
        vistorias = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

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
        vistorias = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

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

        vistorias = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(vistorias) == 1
    assert vistorias[0].id == vist2.id


@pytest.mark.asyncio
async def test_vistoria_listar_vazio(admin_engine):
    """Listar vistorias de veiculo sem vistorias retorna lista vazia."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        vistorias = await tr_svc.listar_vistorias(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

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
