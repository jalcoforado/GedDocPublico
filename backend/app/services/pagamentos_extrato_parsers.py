"""Parsers de extrato bancário para a conciliação (Onda B / C2.2).

Hoje só OFX (1.x SGML e 2.x XML). CNAB240 entra na Task 2. O CSV já
existente segue em `pagamentos_conciliacao._parse_csv` — não duplicado aqui.

OFX 1.x é SGML: as tags de conteúdo (`<DTPOSTED>`, `<TRNAMT>`, ...) não são
fechadas — só as agregadoras (`<STMTTRN>`, `<BANKTRANLIST>`, ...) costumam
ser. Um parser XML quebra nisso, por isso o scanner abaixo é linha a linha e
não depende de `xml.etree`. OFX 2.x já é XML válido (`xml.etree` da stdlib
resolve).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class OfxParseError(Exception):
    """Levantado quando o conteúdo não é um OFX reconhecível ou tem
    lançamento sem os campos mínimos (DTPOSTED/TRNAMT)."""


@dataclass
class LancamentoParseado:
    data: date
    historico: str
    documento: str | None
    favorecido: str | None
    valor: Decimal  # sempre positivo; o sinal do TRNAMT vira `tipo`
    tipo: str  # "CREDITO" | "DEBITO"
    id_externo: str | None  # FITID; None quando o formato não dá id


_TAG_RE = re.compile(r"^<(/?)([A-Za-z0-9._]+)>(.*)$")


def _parse_data_ofx(v: str) -> date:
    digitos = v.strip()[:8]
    try:
        return datetime.strptime(digitos, "%Y%m%d").date()
    except ValueError:
        raise OfxParseError(f"DTPOSTED inválido: '{v}'")


def _parse_valor_ofx(v: str) -> Decimal:
    s = v.strip().replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise OfxParseError(f"TRNAMT inválido: '{v}'")


def _registro_para_lancamento(reg: dict[str, str]) -> LancamentoParseado:
    dtposted = reg.get("DTPOSTED")
    trnamt = reg.get("TRNAMT")
    if not dtposted or not trnamt:
        raise OfxParseError("Lançamento OFX sem DTPOSTED/TRNAMT")
    data = _parse_data_ofx(dtposted)
    valor_com_sinal = _parse_valor_ofx(trnamt)
    tipo = "DEBITO" if valor_com_sinal < 0 else "CREDITO"
    valor = abs(valor_com_sinal)
    memo = (reg.get("MEMO") or "").strip()
    name = (reg.get("NAME") or "").strip()
    historico = (memo or name or "(sem histórico)")[:255]
    favorecido = (name or memo or None)
    if favorecido:
        favorecido = favorecido[:150] or None
    documento = reg.get("CHECKNUM") or reg.get("REFNUM") or None
    id_externo = reg.get("FITID") or None
    return LancamentoParseado(
        data=data, historico=historico, documento=documento, favorecido=favorecido,
        valor=valor, tipo=tipo, id_externo=id_externo)


def _extrair_registros_sgml(conteudo: str) -> list[dict[str, str]]:
    """Scanner de tags do OFX 1.x (SGML): tags de conteúdo não fecham, mas
    `<STMTTRN>`/`</STMTTRN>` delimitam cada lançamento."""
    blocos: list[dict[str, str]] = []
    atual: dict[str, str] | None = None
    for linha_bruta in conteudo.splitlines():
        linha = linha_bruta.strip()
        if not linha:
            continue
        m = _TAG_RE.match(linha)
        if not m:
            continue
        fechando, tag, valor = m.group(1), m.group(2).upper(), m.group(3).strip()
        if tag == "STMTTRN":
            if fechando:
                if atual is not None:
                    blocos.append(atual)
                    atual = None
            else:
                if atual is not None:  # bloco anterior sem fechamento explícito
                    blocos.append(atual)
                atual = {}
            continue
        if atual is not None and valor:
            atual[tag] = valor
    if atual is not None:
        blocos.append(atual)
    return blocos


def _extrair_registros_xml(conteudo: str) -> list[dict[str, str]]:
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise OfxParseError(f"XML OFX malformado: {e}")
    blocos: list[dict[str, str]] = []
    for stmttrn in raiz.iter("STMTTRN"):
        reg: dict[str, str] = {}
        for filho in stmttrn:
            tag = filho.tag.upper()
            texto = (filho.text or "").strip()
            if texto:
                reg[tag] = texto
        blocos.append(reg)
    return blocos


def _eh_sgml(conteudo: str) -> bool:
    inicio = conteudo.lstrip().upper()
    return inicio.startswith("OFXHEADER:")


def _eh_xml(conteudo: str) -> bool:
    inicio = conteudo.lstrip()
    return inicio.startswith("<?xml") or "<?OFX" in inicio[:200] or inicio.startswith("<OFX>")


def parse_ofx(conteudo: str) -> list[LancamentoParseado]:
    """Detecta OFX 1.x (SGML) x 2.x (XML) pelo cabeçalho e devolve os
    lançamentos de todos os `<STMTTRN>` do arquivo. Levanta `OfxParseError`
    para conteúdo não reconhecido ou lançamento sem campos mínimos."""
    if not conteudo or not conteudo.strip():
        raise OfxParseError("Arquivo OFX vazio")
    if _eh_sgml(conteudo):
        registros = _extrair_registros_sgml(conteudo)
    elif _eh_xml(conteudo):
        registros = _extrair_registros_xml(conteudo)
    else:
        raise OfxParseError(
            "Cabeçalho OFX não reconhecido (esperado 'OFXHEADER:' para 1.x "
            "ou '<?xml'/'<?OFX' para 2.x)")
    if not registros:
        raise OfxParseError("Nenhum lançamento (<STMTTRN>) encontrado no arquivo OFX")
    return [_registro_para_lancamento(r) for r in registros]
