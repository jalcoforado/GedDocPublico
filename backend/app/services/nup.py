"""NUP — Número Único de Protocolo (Fase P2).

Formato: ``NNNNN.NNNNNN/AAAA-DD``
  - 5 dígitos: código do órgão (atribuído pelo SIORG/MP)
  - 6 dígitos: sequencial por (órgão, ano)
  - 4 dígitos: ano
  - 2 dígitos: verificadores Mod-11

Algoritmo Mod-11 (CONARQ / SIORG):
  - Pesos cíclicos 2..9 aplicados da direita pra esquerda
  - DV1 calculado sobre os 15 dígitos
  - DV2 calculado sobre os 15 + DV1 (16 dígitos)
  - Em ambos: ``resto = soma % 11``; se ``resto == 10`` → 0

Geração concorrência-safe usa ``aprimora_py.nup_sequencia`` com UPSERT:
o INSERT ... ON CONFLICT DO UPDATE RETURNING garante atomicidade — nunca
gera duplicata mesmo com N workers protocolando simultaneamente.
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tenant


_NUP_PATTERN = re.compile(r"^(\d{5})\.(\d{6})/(\d{4})-(\d{2})$")
_PESOS = [2, 3, 4, 5, 6, 7, 8, 9]


class NupError(Exception):
    pass


def calcular_dv_unitario(digitos: str) -> int:
    """Calcula 1 dígito verificador Mod-11 sobre a string de dígitos.

    Pesos 2..9 aplicados da direita pra esquerda, ciclicamente.
    Resto da soma // 11. Se resto == 10, retorna 0.
    """
    if not digitos.isdigit():
        raise NupError("DV exige apenas dígitos")
    soma = 0
    for i, ch in enumerate(reversed(digitos)):
        soma += int(ch) * _PESOS[i % len(_PESOS)]
    resto = soma % 11
    return resto if resto < 10 else 0


def calcular_dvs_nup(quinze_digitos: str) -> str:
    """Retorna os 2 DVs concatenados ('DD') para os 15 dígitos do NUP."""
    if len(quinze_digitos) != 15 or not quinze_digitos.isdigit():
        raise NupError("NUP precisa de exatamente 15 dígitos numéricos")
    dv1 = calcular_dv_unitario(quinze_digitos)
    dv2 = calcular_dv_unitario(quinze_digitos + str(dv1))
    return f"{dv1}{dv2}"


def formatar_nup(codigo_orgao: str, sequencial: int, ano: int) -> str:
    """Monta NUP a partir de componentes — NÃO valida unicidade no banco.

    Retorna string já formatada com DV calculado.
    """
    if not codigo_orgao or len(codigo_orgao) != 5 or not codigo_orgao.isdigit():
        raise NupError(f"codigo_orgao inválido: '{codigo_orgao}' (precisa 5 dígitos)")
    if not 1 <= sequencial <= 999999:
        raise NupError(f"sequencial fora do range 1..999999: {sequencial}")
    if not 1000 <= ano <= 9999:
        raise NupError(f"ano inválido: {ano}")
    seq_str = f"{sequencial:06d}"
    ano_str = f"{ano:04d}"
    quinze = f"{codigo_orgao}{seq_str}{ano_str}"
    dvs = calcular_dvs_nup(quinze)
    return f"{codigo_orgao}.{seq_str}/{ano_str}-{dvs}"


def parsear_nup(nup: str) -> tuple[str, int, int, str]:
    """Faz o parse do NUP retornando (codigo_orgao, sequencial, ano, dvs)."""
    m = _NUP_PATTERN.match(nup.strip())
    if not m:
        raise NupError(f"NUP malformado: '{nup}' — esperado NNNNN.NNNNNN/AAAA-DD")
    return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)


def validar_nup(nup: str) -> bool:
    """Verifica formato + DV. NÃO consulta DB."""
    try:
        codigo, seq, ano, dvs = parsear_nup(nup)
        esperados = calcular_dvs_nup(f"{codigo}{seq:06d}{ano:04d}")
        return esperados == dvs
    except NupError:
        return False


async def _proximo_sequencial(
    db: AsyncSession,
    *,
    tenant_id: int,
    codigo_orgao: str,
    ano: int,
) -> int:
    """UPSERT atômico — retorna próximo sequencial pra (tenant, órgão, ano)."""
    result = await db.execute(
        text(
            """
            INSERT INTO aprimora_py.nup_sequencia
                (tenant_id, codigo_orgao, ano, ultimo_sequencial, atualizado_em)
            VALUES (:tid, :org, :ano, 1, NOW())
            ON CONFLICT (tenant_id, codigo_orgao, ano)
            DO UPDATE SET
                ultimo_sequencial = aprimora_py.nup_sequencia.ultimo_sequencial + 1,
                atualizado_em = NOW()
            RETURNING ultimo_sequencial
            """
        ).bindparams(tid=tenant_id, org=codigo_orgao, ano=ano)
    )
    return int(result.scalar_one())


async def gerar_nup(
    db: AsyncSession,
    *,
    tenant: Tenant,
    ano: int | None = None,
) -> tuple[str, int]:
    """Gera próximo NUP do tenant. Retorna (nup_formatado, sequencial).

    Pré-condições:
      - tenant.usar_nup_federal == True
      - tenant.codigo_orgao_nup preenchido (5 dígitos)

    Falha rápido com NupError se não — caller decide se silencia (no fluxo
    de abertura, NUP é opcional e a flag é por tenant, então um tenant sem
    configuração simplesmente não recebe NUP).
    """
    if not tenant.usar_nup_federal:
        raise NupError(f"Tenant {tenant.slug} não tem usar_nup_federal=true")
    if not tenant.codigo_orgao_nup:
        raise NupError(
            f"Tenant {tenant.slug} sem codigo_orgao_nup — configure em /configuracoes"
        )
    if ano is None:
        ano = datetime.now().year
    sequencial = await _proximo_sequencial(
        db, tenant_id=tenant.id, codigo_orgao=tenant.codigo_orgao_nup, ano=ano
    )
    nup = formatar_nup(tenant.codigo_orgao_nup, sequencial, ano)
    return nup, sequencial
