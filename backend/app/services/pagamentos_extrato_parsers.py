"""Parsers de extrato bancário para a conciliação (Onda B / C2.2).

OFX (1.x SGML e 2.x XML) e CNAB240 (registro detalhe tipo 3, segmento E). O
CSV já existente segue em `pagamentos_conciliacao._parse_csv` — não
duplicado aqui.

OFX 1.x é SGML: as tags de conteúdo (`<DTPOSTED>`, `<TRNAMT>`, ...) não são
fechadas — só as agregadoras (`<STMTTRN>`, `<BANKTRANLIST>`, ...) costumam
ser. Um parser XML quebra nisso, por isso o scanner abaixo é linha a linha e
não depende de `xml.etree`. OFX 2.x já é XML válido (`xml.etree` da stdlib
resolve).

CNAB240 é posicional (240 colunas fixas por linha) — layout FEBRABAN de
extrato construído à mão na fixture de teste, que é a "spec executável" até
chegar arquivo real do banco do piloto (o desvio por banco é adaptação
futura). `_parse_valor_ofx` NÃO é reaproveitado aqui: o OFX vem em texto
decimal com separador (às vezes milhar), o CNAB traz o valor como inteiro em
centavos em posições fixas — formatos incompatíveis, parser próprio.
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


class Cnab240ParseError(Exception):
    """Levantado quando o CNAB240 tem linha de tamanho diferente de 240 ou
    campo posicional inválido (data/valor)."""


_CNAB_TAM_LINHA = 240
_CNAB_TIPOS_PULADOS = {"0", "1", "5", "9"}  # header/trailer de arquivo e lote


def _parse_data_cnab(v: str) -> date:
    try:
        return datetime.strptime(v, "%d%m%Y").date()
    except ValueError:
        raise Cnab240ParseError(f"Data de lançamento CNAB240 inválida: '{v}'")


def _parse_valor_cnab(digitos: str, sinal: str) -> tuple[Decimal, str]:
    try:
        centavos = int(digitos)
    except ValueError:
        raise Cnab240ParseError(f"Valor CNAB240 inválido: '{digitos}'")
    valor = Decimal(centavos) / Decimal(100)
    tipo = "DEBITO" if sinal.strip().upper() == "D" else "CREDITO"
    return valor, tipo


def parse_cnab240(conteudo: str) -> list[LancamentoParseado]:
    """Layout FEBRABAN de extrato — registro detalhe (tipo 3), segmento E,
    linhas fixas de 240 posições (1-based, documentado também na fixture de
    teste):

      1-3    código do banco
      4-7    lote de serviço
      8      tipo de registro ('0' header arquivo, '1' header lote,
             '3' detalhe, '5' trailer lote, '9' trailer arquivo — só '3' é
             lançamento; os demais são pulados)
      9-13   nº sequencial do registro no lote (não usado)
      14     código de segmento ('E' = lançamento de extrato)
      15-20  filler (não usado)
      21-28  data do lançamento, DDMMAAAA
      29-43  valor do lançamento, 15 dígitos, inteiro em centavos (sem sinal)
      44     sinal do valor ('D' débito | 'C' crédito)
      45-49  nº do documento, 5 dígitos zero-padded (zerado/vazio -> sem
             documento; `documento=None`/`id_externo=None`)
      50-89  histórico/complemento, 40 chars
      90-240 filler (não usado)

    Linha com tamanho != 240 levanta `Cnab240ParseError` citando o nº da
    linha (1-based). Aceita \\r\\n e linha final vazia (trailing newline) sem
    contá-la como violação de tamanho.
    """
    if not conteudo or not conteudo.strip():
        raise Cnab240ParseError("Arquivo CNAB240 vazio")
    linhas = conteudo.splitlines()
    while linhas and linhas[-1].strip() == "":
        linhas.pop()
    if not linhas:
        raise Cnab240ParseError("Arquivo CNAB240 vazio")
    lancamentos: list[LancamentoParseado] = []
    for i, linha in enumerate(linhas, start=1):
        if len(linha) != _CNAB_TAM_LINHA:
            raise Cnab240ParseError(
                f"Linha {i}: tamanho {len(linha)} (esperado {_CNAB_TAM_LINHA})")
        tipo_registro = linha[7]
        if tipo_registro in _CNAB_TIPOS_PULADOS:
            continue
        data = _parse_data_cnab(linha[20:28])
        valor, tipo = _parse_valor_cnab(linha[28:43], linha[43])
        doc_raw = linha[44:49].strip()
        documento = doc_raw.lstrip("0") or None if doc_raw else None
        historico = (linha[49:89].strip() or "(sem histórico)")[:255]
        lancamentos.append(LancamentoParseado(
            data=data, historico=historico, documento=documento, favorecido=None,
            valor=valor, tipo=tipo, id_externo=documento))
    if not lancamentos:
        raise Cnab240ParseError("Nenhum lançamento (segmento E) encontrado no arquivo CNAB240")
    return lancamentos
