"""Transporte Regulado PR-4 — Documentos e Avaliacoes de Veiculos.

Cobre o servico de dominio: CRUD tenant-scoped para documentos (metadados de CRLV,
CNH, inspecao, etc.) e avaliacoes (pareceres regulatorios). Isolamento RLS cross-tenant,
soft-delete, validacoes de data/parecer, unicidade parcial de tipo_documento por veiculo.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import usuario as user_models
from app.schemas.transporte_regulado import (
    EmpresaCreate,
    PermissionarioCreate,
    VeiculoReguladoCreate,
    VeiculoDocumentoCreate,
    VeiculoDocumentoUpdate,
    VeiculoAvaliacaoCreate,
    VeiculoAvaliacaoUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("doc")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Doc", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    h = uuid.uuid4().hex.upper()
    letras = "".join(c for c in h if c.isalpha())[:3].ljust(3, "X")
    digitos = "".join(c for c in h if c.isdigit())[:4].ljust(4, "0")
    return f"{letras}{digitos}"


def _renavam() -> str:
    return str(uuid.uuid4().int)[:11]


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


def _cnpj() -> str:
    return str(uuid.uuid4().int)[:14]


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


async def _usuario(admin_engine, tenant_id, nome="Avaliador", cpf=None):
    """Cria um usuario na tenant para servir como avaliador."""
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
async def test_documento_criar_basico(admin_engine):
    """Criar documento com dados minimos."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(
                tipo_documento="crlv",
                numero_documento="123456789",
            ),
        )

    assert doc.id is not None
    assert doc.tenant_id == tenant.id
    assert doc.id_veiculo == veiculo.id
    assert doc.tipo_documento == "crlv"
    assert doc.numero_documento == "123456789"
    assert doc.situacao == "pendente"
    assert doc.excluido is False
    assert doc.criado_em is not None


@pytest.mark.asyncio
async def test_documento_criar_com_datas(admin_engine):
    """Criar documento com datas de emissao e validade."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    hoje = date.today()
    proxima_semana = hoje + timedelta(days=7)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(
                tipo_documento="cnh_copia",
                numero_documento="98765432",
                data_emissao=hoje,
                data_validade=proxima_semana,
            ),
        )

    assert doc.data_emissao == hoje
    assert doc.data_validade == proxima_semana


@pytest.mark.asyncio
async def test_documento_validacao_datas_coerentes(admin_engine):
    """Validacao: data_emissao deve ser <= data_validade."""
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    with pytest.raises(ValidationError) as exc:
        VeiculoDocumentoCreate(
            tipo_documento="crlv",
            numero_documento="123",
            data_emissao=hoje,
            data_validade=ontem,
        )

    assert "data_emissao" in str(exc.value)


@pytest.mark.asyncio
async def test_documento_validacao_numero_nao_vazio(admin_engine):
    """Validacao: numero_documento nao pode ser vazio."""
    with pytest.raises(ValidationError) as exc:
        VeiculoDocumentoCreate(
            tipo_documento="crlv",
            numero_documento="   ",
        )

    assert "numero_documento" in str(exc.value)


@pytest.mark.asyncio
async def test_documento_obter(admin_engine):
    """Obter um documento pelo ID."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        criado = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="123"),
        )
        doc_id = criado.id

        obtido = await tr_svc.obter_documento(s, tenant_id=tenant.id, documento_id=doc_id)

    assert obtido.id == doc_id
    assert obtido.numero_documento == "123"


@pytest.mark.asyncio
async def test_documento_obter_404_nao_existe(admin_engine):
    """Obter documento inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_documento(s, tenant_id=tenant.id, documento_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_documento_obter_404_cross_tenant(admin_engine):
    """Obter documento de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_documento(
            s, tenant_id=tenant1.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="123"),
        )
        doc_id = doc.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_documento(s, tenant_id=tenant2.id, documento_id=doc_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_documento_listar(admin_engine):
    """Listar documentos de um veiculo."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc1 = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="111"),
        )
        doc2 = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="cnh_copia", numero_documento="222"),
        )
        docs, _ = await tr_svc.listar_documentos(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(docs) == 2
    assert doc1.id in [d.id for d in docs]
    assert doc2.id in [d.id for d in docs]


@pytest.mark.asyncio
async def test_documento_listar_excluidos_nao_retornados(admin_engine):
    """Listar documentos nao inclui excluidos (soft-delete)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc1 = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="111"),
        )
        doc2 = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="cnh_copia", numero_documento="222"),
        )
        await tr_svc.excluir_documento(s, tenant_id=tenant.id, documento_id=doc1.id)

        docs, _ = await tr_svc.listar_documentos(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(docs) == 1
    assert docs[0].id == doc2.id


@pytest.mark.asyncio
async def test_documento_atualizar(admin_engine):
    """Atualizar documento."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="123"),
        )
        doc_id = doc.id

        atualizado = await tr_svc.atualizar_documento(
            s, tenant_id=tenant.id, documento_id=doc_id,
            payload=VeiculoDocumentoUpdate(numero_documento="456"),
        )

    assert atualizado.numero_documento == "456"
    assert atualizado.tipo_documento == "crlv"


@pytest.mark.asyncio
async def test_documento_excluir_soft_delete(admin_engine):
    """Excluir documento usa soft-delete (excluido=true)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        doc = await tr_svc.criar_documento(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id,
            payload=VeiculoDocumentoCreate(tipo_documento="crlv", numero_documento="123"),
        )
        doc_id = doc.id

        await tr_svc.excluir_documento(s, tenant_id=tenant.id, documento_id=doc_id)

        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_documento(s, tenant_id=tenant.id, documento_id=doc_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_avaliacao_criar_basica(admin_engine):
    """Criar avaliacao com dados basicos."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador_id = await _usuario(admin_engine, tenant.id)

    agora = datetime.utcnow()

    async with _sm(admin_engine)() as s:
        aval = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="aprovado",
                parecer="Veiculo em perfeito estado de funcionamento.",
                data_avaliacao=agora,
            ),
        )

    assert aval.id is not None
    assert aval.tenant_id == tenant.id
    assert aval.id_veiculo == veiculo.id
    assert aval.id_usuario_avaliador == avaliador_id
    assert aval.resultado == "aprovado"
    assert aval.excluido is False


@pytest.mark.asyncio
async def test_avaliacao_validacao_parecer_minimo(admin_engine):
    """Validacao: parecer deve ter no minimo 10 caracteres."""
    with pytest.raises(ValidationError) as exc:
        VeiculoAvaliacaoCreate(
            resultado="aprovado",
            parecer="Curto",
            data_avaliacao=datetime.utcnow(),
            id_usuario_avaliador=1,
        )

    assert "parecer" in str(exc.value)


@pytest.mark.asyncio
async def test_avaliacao_validacao_data_futura(admin_engine):
    """Validacao: data_avaliacao nao pode ser futura."""
    futuro = datetime.utcnow() + timedelta(days=1)

    with pytest.raises(ValidationError) as exc:
        VeiculoAvaliacaoCreate(
            resultado="aprovado",
            parecer="Texto com mais de 10 caracteres",
            data_avaliacao=futuro,
            id_usuario_avaliador=1,
        )

    assert "data_avaliacao" in str(exc.value)


@pytest.mark.asyncio
async def test_avaliacao_obter(admin_engine):
    """Obter uma avaliacao pelo ID."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        criada = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="reprovado",
                parecer="Veiculo com problemas mecanicos graves.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        aval_id = criada.id

        obtida = await tr_svc.obter_avaliacao(s, tenant_id=tenant.id, avaliacao_id=aval_id)

    assert obtida.id == aval_id
    assert obtida.resultado == "reprovado"


@pytest.mark.asyncio
async def test_avaliacao_obter_404_nao_existe(admin_engine):
    """Obter avaliacao inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_avaliacao(s, tenant_id=tenant.id, avaliacao_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_avaliacao_obter_404_cross_tenant(admin_engine):
    """Obter avaliacao de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant1.id)
    avaliador_id = await _usuario(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        aval = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant1.id, veiculo_id=veiculo.id, usuario_id=avaliador_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="aprovado",
                parecer="Veiculo em bom estado para operacao.",
                data_avaliacao=datetime.utcnow(),
                id_usuario_avaliador=avaliador_id,
            ),
        )
        aval_id = aval.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_avaliacao(s, tenant_id=tenant2.id, avaliacao_id=aval_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_avaliacao_listar(admin_engine):
    """Listar avaliacoes de um veiculo."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador1_id = await _usuario(admin_engine, tenant.id, nome="Avaliador1")
    avaliador2_id = await _usuario(admin_engine, tenant.id, nome="Avaliador2")

    async with _sm(admin_engine)() as s:
        aval1 = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador1_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="aprovado",
                parecer="Primeira avaliacao positiva.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        aval2 = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador2_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="condicional",
                parecer="Segunda avaliacao condicional.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        avaliacoes, _ = await tr_svc.listar_avaliacoes(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(avaliacoes) == 2
    assert aval1.id in [a.id for a in avaliacoes]
    assert aval2.id in [a.id for a in avaliacoes]


@pytest.mark.asyncio
async def test_avaliacao_listar_excluidas_nao_retornadas(admin_engine):
    """Listar avaliacoes nao inclui excluidas (soft-delete)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador1_id = await _usuario(admin_engine, tenant.id, nome="Avaliador1")
    avaliador2_id = await _usuario(admin_engine, tenant.id, nome="Avaliador2")

    async with _sm(admin_engine)() as s:
        aval1 = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador1_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="aprovado",
                parecer="Primeira avaliacao positiva.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        aval2 = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador2_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="condicional",
                parecer="Segunda avaliacao condicional.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        await tr_svc.excluir_avaliacao(s, tenant_id=tenant.id, avaliacao_id=aval1.id)

        avaliacoes, _ = await tr_svc.listar_avaliacoes(s, tenant_id=tenant.id, veiculo_id=veiculo.id)

    assert len(avaliacoes) == 1
    assert avaliacoes[0].id == aval2.id


@pytest.mark.asyncio
async def test_avaliacao_atualizar(admin_engine):
    """Atualizar avaliacao."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        aval = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="pendente",
                parecer="Avaliacao pendente de analise completa.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        aval_id = aval.id

        atualizada = await tr_svc.atualizar_avaliacao(
            s, tenant_id=tenant.id, avaliacao_id=aval_id,
            payload=VeiculoAvaliacaoUpdate(
                resultado="aprovado",
                parecer="Avaliacao completa: veiculo aprovado para operacao.",
            ),
        )

    assert atualizada.resultado == "aprovado"
    assert "aprovado" in atualizada.parecer.lower()


@pytest.mark.asyncio
async def test_avaliacao_excluir_soft_delete(admin_engine):
    """Excluir avaliacao usa soft-delete (excluido=true)."""
    tenant = await _provisionar(admin_engine)
    veiculo = await _veiculo(admin_engine, tenant.id)
    avaliador_id = await _usuario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        aval = await tr_svc.criar_avaliacao(
            s, tenant_id=tenant.id, veiculo_id=veiculo.id, usuario_id=avaliador_id,
            payload=VeiculoAvaliacaoCreate(
                resultado="aprovado",
                parecer="Veiculo em excelentes condicoes.",
                data_avaliacao=datetime.utcnow(),
            ),
        )
        aval_id = aval.id

        await tr_svc.excluir_avaliacao(s, tenant_id=tenant.id, avaliacao_id=aval_id)

        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_avaliacao(s, tenant_id=tenant.id, avaliacao_id=aval_id)

    assert exc.value.status_code == 404
