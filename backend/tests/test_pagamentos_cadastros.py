"""Pagamentos PAG-1 — cadastro de Fornecedor.

Cobre o serviço de domínio (`services/pagamentos_cadastros.py`): CRUD
tenant-scoped, cifragem Fernet dos dados bancários em repouso, unicidade de
CNPJ/CPF por tenant, isolamento cross-tenant (404) e reveal decifrado. Mesmo
padrão dos testes de transporte regulado (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, ContaUpdate, ContratoCreate, FornecedorCreate, FornecedorUpdate,
    DadosBancarios, FonteCreate, NaturezaCreate,
)
from app.services import pagamentos_cadastros as svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagcred")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar(engine, tenant_id, *, cnpj_cpf=None, dados_bancarios=None):
    async with _sm(engine)() as s:
        return await svc.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=cnpj_cpf or _doc(), nome="Medlar LTDA",
                dados_bancarios=dados_bancarios,
            ),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_fonte_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ============================ Criação + cifragem =============================
async def test_criar_fornecedor_com_dados_bancarios(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(banco="001", agencia="1234", conta="5678-9", chave_pix="pix@medlar")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        saida = svc.fornecedor_out(c)
        assert saida["tem_dados_bancarios"] is True
        assert c.tenant_id == t.id
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dados_bancarios_fornecedor_decifra_corretamente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(banco="001", agencia="1234", conta="5678-9", chave_pix="pix@medlar")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        async with _sm(admin_engine)() as s:
            revelado = await svc.dados_bancarios_fornecedor(s, tenant_id=t.id, fornecedor_id=c.id)
        assert revelado.chave_pix == "pix@medlar"
        assert revelado.banco == "001"
        assert revelado.agencia == "1234"
        assert revelado.conta == "5678-9"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dados_bancarios_fornecedor_gera_audit_log(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(banco="001", agencia="1234", conta="5678-9", chave_pix="pix@medlar")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        async with _sm(admin_engine)() as s:
            r = await s.execute(text(
                """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
                   VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
                {"t": t.id, "n": "Usuario Reveal", "e": f"{uuid.uuid4().hex[:8]}@t.local",
                 "c": uuid.uuid4().hex[:11]})
            uid = r.scalar_one(); await s.commit()
        async with _sm(admin_engine)() as s:
            await svc.dados_bancarios_fornecedor(s, tenant_id=t.id, fornecedor_id=c.id, usuario_id=uid)
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT count(*) FROM aprimora_py.audit_log "
                "WHERE tenant_id=:t AND acao=:a AND id_entidade=:e AND id_usuario=:u"),
                {"t": t.id, "a": "fornecedor.dados_bancarios_revelados", "e": c.id, "u": uid}
            )).scalar_one()
        assert row == 1
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dados_bancarios_cifrados_em_repouso(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(conta="SEGREDO123")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        async with _sm(admin_engine)() as s:
            row = (
                await s.execute(
                    text("SELECT conta_cif FROM pagamentos.fornecedor WHERE id=:i"), {"i": c.id}
                )
            ).fetchone()
        assert row[0] is not None
        assert "SEGREDO123" not in row[0]
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Unicidade de documento ==========================
async def test_cnpj_cpf_duplicado_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        doc = _doc()
        await _criar(admin_engine, t.id, cnpj_cpf=doc)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, cnpj_cpf=doc)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Re-cifragem no update ===========================
async def test_atualizar_fornecedor_recifra(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar(admin_engine, t.id, dados_bancarios=DadosBancarios(conta="ANTIGO111"))
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=c.id,
                payload=FornecedorUpdate(
                    dados_bancarios=DadosBancarios(conta="NOVOSEGREDO999", chave_pix="novo@pix")
                ),
            )
        assert svc.fornecedor_out(atualizado)["tem_dados_bancarios"] is True
        # cifrado em repouso: sessão nova, SELECT bruto não expõe o texto puro
        async with _sm(admin_engine)() as s:
            row = (
                await s.execute(
                    text("SELECT conta_cif FROM pagamentos.fornecedor WHERE id=:i"), {"i": c.id}
                )
            ).fetchone()
        assert row[0] is not None
        assert "NOVOSEGREDO999" not in row[0]
        # reveal decifra os novos valores
        async with _sm(admin_engine)() as s:
            revelado = await svc.dados_bancarios_fornecedor(s, tenant_id=t.id, fornecedor_id=c.id)
        assert revelado.conta == "NOVOSEGREDO999"
        assert revelado.chave_pix == "novo@pix"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ situacao_cadastral x motivo_pendencia ===========
async def _criar_situacao(engine, tenant_id, *, situacao, motivo):
    async with _sm(engine)() as s:
        return await svc.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Compliance LTDA",
                situacao_cadastral=situacao, motivo_pendencia=motivo,
            ),
        )


async def test_criar_irregular_sem_motivo_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        with pytest.raises(HTTPException) as exc:
            await _criar_situacao(admin_engine, t.id, situacao="IRREGULAR", motivo=None)
        assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_pendente_motivo_em_branco_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        with pytest.raises(HTTPException) as exc:
            await _criar_situacao(admin_engine, t.id, situacao="PENDENTE", motivo="   ")
        assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_irregular_com_motivo_ok(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar_situacao(admin_engine, t.id, situacao="IRREGULAR", motivo="Sancionado CEIS")
        assert c.situacao_cadastral == "IRREGULAR"
        assert c.motivo_pendencia == "Sancionado CEIS"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_regular_limpa_motivo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar_situacao(admin_engine, t.id, situacao="REGULAR", motivo="lixo")
        assert c.motivo_pendencia is None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_para_irregular_sem_motivo_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar(admin_engine, t.id)  # nasce REGULAR
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.atualizar_fornecedor(
                    s, tenant_id=t.id, fornecedor_id=c.id,
                    payload=FornecedorUpdate(situacao_cadastral="IRREGULAR"),
                )
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_para_regular_limpa_motivo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar_situacao(admin_engine, t.id, situacao="IRREGULAR", motivo="Sancionado")
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=c.id,
                payload=FornecedorUpdate(situacao_cadastral="REGULAR"),
            )
        assert atualizado.situacao_cadastral == "REGULAR"
        assert atualizado.motivo_pendencia is None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_esvaziar_motivo_de_irregular_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar_situacao(admin_engine, t.id, situacao="IRREGULAR", motivo="Sancionado")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.atualizar_fornecedor(
                    s, tenant_id=t.id, fornecedor_id=c.id,
                    payload=FornecedorUpdate(motivo_pendencia=""),
                )
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ histórico de situação ===========================
async def test_historico_registra_na_criacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar_situacao(admin_engine, t.id, situacao="PENDENTE", motivo="CND vencida")
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_situacao_historico(s, tenant_id=t.id, fornecedor_id=c.id)
        assert len(hist) == 1
        assert hist[0].situacao == "PENDENTE"
        assert hist[0].motivo == "CND vencida"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_historico_acumula_mudancas_em_ordem(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        # nasce REGULAR -> PENDENTE -> REGULAR -> IRREGULAR
        c = await _criar(admin_engine, t.id)  # REGULAR (baseline)
        for situacao, motivo in [
            ("PENDENTE", "Faltando dados bancários"),
            ("REGULAR", None),
            ("IRREGULAR", "Sancionado CEIS"),
        ]:
            async with _sm(admin_engine)() as s:
                await svc.atualizar_fornecedor(
                    s, tenant_id=t.id, fornecedor_id=c.id,
                    payload=FornecedorUpdate(situacao_cadastral=situacao, motivo_pendencia=motivo),
                )
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_situacao_historico(s, tenant_id=t.id, fornecedor_id=c.id)
        # 1 baseline + 3 mudanças; ordenado do mais recente para o mais antigo
        assert [h.situacao for h in hist] == ["IRREGULAR", "REGULAR", "PENDENTE", "REGULAR"]
        assert hist[0].motivo == "Sancionado CEIS"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_historico_nao_registra_sem_mudanca_de_situacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        c = await _criar(admin_engine, t.id)  # 1 baseline
        # muda só o nome — não deve gerar linha de histórico
        async with _sm(admin_engine)() as s:
            await svc.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=c.id,
                payload=FornecedorUpdate(nome="Novo Nome LTDA"),
            )
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_situacao_historico(s, tenant_id=t.id, fornecedor_id=c.id)
        assert len(hist) == 1
    finally:
        await _cleanup(admin_engine, t.id)


async def test_historico_grava_usuario(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            id_usuario = (await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id},
            )).scalar_one()
        async with _sm(admin_engine)() as s:
            c = await svc.criar_fornecedor(
                s, tenant_id=t.id, usuario_id=id_usuario,
                payload=FornecedorCreate(
                    tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Com Usuario LTDA",
                    situacao_cadastral="IRREGULAR", motivo_pendencia="Suspenso TCE",
                ),
            )
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_situacao_historico(s, tenant_id=t.id, fornecedor_id=c.id)
        assert hist[0].id_usuario == id_usuario
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cross-tenant 404 =================================
async def test_obter_fornecedor_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ca = await _criar(admin_engine, a.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.obter_fornecedor(s, tenant_id=b.id, fornecedor_id=ca.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ natureza_despesa / fonte_recursos ==============
async def test_natureza_e_fonte_crud(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            natureza = await svc.criar_natureza(
                s, tenant_id=t.id,
                payload=NaturezaCreate(codigo="3.3.90.30", descricao="Material de consumo"),
            )
        assert natureza.codigo == "3.3.90.30"

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_natureza(
                    s, tenant_id=t.id,
                    payload=NaturezaCreate(codigo="3.3.90.30", descricao="dup"),
                )
            assert exc.value.status_code == 409

        async with _sm(admin_engine)() as s:
            fonte = await svc.criar_fonte(
                s, tenant_id=t.id,
                payload=FonteCreate(
                    codigo="500", descricao="Recursos próprios",
                    grupos_despesa_permitidos=["CUSTEIO", "INVESTIMENTO"],
                ),
            )
        assert fonte.grupos_despesa_permitidos == ["CUSTEIO", "INVESTIMENTO"]
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ conta_bancaria (fonte x grupo) ==================
async def test_conta_valida_fonte_grupo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            fonte = await svc.criar_fonte(
                s, tenant_id=t.id,
                payload=FonteCreate(
                    codigo="600", descricao="F", grupos_despesa_permitidos=["CUSTEIO"],
                ),
            )

        # grupo compatível → cria com sucesso
        async with _sm(admin_engine)() as s:
            ok = await svc.criar_conta(
                s, tenant_id=t.id,
                payload=ContaCreate(
                    nome="Conta A", banco="001", agencia="1", conta="2",
                    id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO",
                ),
            )
        assert ok.id is not None
        assert ok.grupo_despesa == "CUSTEIO"

        # grupo incompatível → 422
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_conta(
                    s, tenant_id=t.id,
                    payload=ContaCreate(
                        nome="Conta B", banco="001", agencia="1", conta="3",
                        id_fonte_recursos=fonte.id, grupo_despesa="INVESTIMENTO",
                    ),
                )
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ contrato / alcada ================================
async def test_contrato_e_alcada_crud(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        fornecedor = await _criar(admin_engine, t.id)

        async with _sm(admin_engine)() as s:
            id_unidade = (await s.execute(
                text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t AND excluido=false LIMIT 1"),
                {"t": t.id},
            )).scalar_one()
            id_usuario = (await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id},
            )).scalar_one()

        async with _sm(admin_engine)() as s:
            contrato = await svc.criar_contrato(
                s, tenant_id=t.id,
                payload=ContratoCreate(
                    numero="CT-001/2026", id_fornecedor=fornecedor.id, id_unidade=id_unidade,
                    objeto="Fornecimento", vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                    valor_total="100000.00", categoria="SERVICOS",
                ),
            )
        assert contrato.numero == "CT-001/2026"
        assert contrato.tenant_id == t.id

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_contrato(
                    s, tenant_id=t.id,
                    payload=ContratoCreate(
                        numero="CT-001/2026", id_fornecedor=fornecedor.id, id_unidade=id_unidade,
                        objeto="x", vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                        valor_total="1.00", categoria="SERVICOS",
                    ),
                )
            assert exc.value.status_code == 409

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_contrato(
                    s, tenant_id=t.id,
                    payload=ContratoCreate(
                        numero="CT-002/2026", id_fornecedor=fornecedor.id, id_unidade=999999,
                        objeto="x", vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                        valor_total="1.00", categoria="SERVICOS",
                    ),
                )
            assert exc.value.status_code == 422

        async with _sm(admin_engine)() as s:
            alcada = await svc.criar_alcada(
                s, tenant_id=t.id,
                payload=AlcadaCreate(id_usuario=id_usuario, valor_maximo="500000.00"),
            )
        assert alcada.id_usuario == id_usuario
        assert alcada.tenant_id == t.id

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_alcada(
                    s, tenant_id=t.id,
                    payload=AlcadaCreate(id_usuario=id_usuario, valor_maximo="1.00"),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_trocar_fonte_da_conta_exige_justificativa_e_gera_trilha(admin_engine):
    """RF-CTA-06: trocar a fonte vinculada à conta exige justificativa e preserva
    o histórico (append-only conta_fonte_historico)."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            f1 = await svc.criar_fonte(s, tenant_id=t.id, payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="F1", grupos_despesa_permitidos=["CUSTEIO"]))
            f2 = await svc.criar_fonte(s, tenant_id=t.id, payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="F2", grupos_despesa_permitidos=["CUSTEIO"]))
            conta = await svc.criar_conta(s, tenant_id=t.id, payload=ContaCreate(
                nome="Conta", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
                id_fonte_recursos=f1.id, grupo_despesa="CUSTEIO"))
        # troca sem justificativa → 422
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.atualizar_conta(s, tenant_id=t.id, conta_id=conta.id,
                                          payload=ContaUpdate(id_fonte_recursos=f2.id))
            assert exc.value.status_code == 422
            assert "justificativa" in exc.value.detail.lower()
        # com justificativa → troca e grava a trilha
        async with _sm(admin_engine)() as s:
            c2 = await svc.atualizar_conta(
                s, tenant_id=t.id, conta_id=conta.id, usuario_id=None,
                payload=ContaUpdate(id_fonte_recursos=f2.id,
                                    justificativa_troca_fonte="Reclassificação contábil"))
        assert c2.id_fonte_recursos == f2.id
        async with _sm(admin_engine)() as s:
            rows = (await s.execute(text(
                "SELECT id_fonte_anterior, id_fonte_nova, justificativa "
                "FROM pagamentos.conta_fonte_historico WHERE tenant_id=:t AND id_conta=:c"),
                {"t": t.id, "c": conta.id})).all()
        assert len(rows) == 1
        assert rows[0][0] == f1.id and rows[0][1] == f2.id
        assert rows[0][2] == "Reclassificação contábil"
    finally:
        await _cleanup(admin_engine, t.id)
