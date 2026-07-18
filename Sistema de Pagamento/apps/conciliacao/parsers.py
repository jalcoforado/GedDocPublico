import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


class BaseExtratoParser:
    """Interface para leitura de extratos (RF39). Retorna uma lista de dicts:
    {'data': date, 'historico': str, 'valor': Decimal (positivo), 'tipo': 'CREDITO'|'DEBITO', 'identificador_transacao': str}
    """

    def parse(self, arquivo):
        raise NotImplementedError


def _parse_data(valor):
    valor = valor.strip()
    for formato in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    raise ValueError(f'Formato de data não reconhecido: {valor}')


class CSVExtratoParser(BaseExtratoParser):
    """
    Lê extratos em CSV delimitado por ";" (padrão de exportação de
    planilhas em pt-BR, já que "," é o separador decimal), com cabeçalho:
    data;historico;valor;tipo;identificador (tipo e identificador são
    opcionais — tipo é inferido pelo sinal do valor quando ausente).
    Formato mais confiável que PDF para importação em lote.
    """

    def parse(self, arquivo):
        conteudo = arquivo.read()
        if isinstance(conteudo, bytes):
            conteudo = conteudo.decode('utf-8-sig', errors='ignore')
        leitor = csv.DictReader(io.StringIO(conteudo), delimiter=';')
        lancamentos = []
        for linha in leitor:
            valor_bruto = linha.get('valor', '0').strip().replace('.', '').replace(',', '.')
            try:
                valor = Decimal(valor_bruto)
            except InvalidOperation:
                continue
            tipo = (linha.get('tipo') or '').strip().upper()
            if tipo not in ('CREDITO', 'DEBITO'):
                tipo = 'CREDITO' if valor >= 0 else 'DEBITO'
            lancamentos.append({
                'data': _parse_data(linha['data']),
                'historico': (linha.get('historico') or '').strip(),
                'valor': abs(valor),
                'tipo': tipo,
                'identificador_transacao': (linha.get('identificador') or '').strip(),
            })
        return lancamentos


class PDFTextExtratoParser(BaseExtratoParser):
    """
    RF39 — extrai lançamentos de extratos em PDF nativo (texto selecionável),
    via pdfplumber, com heurística de linha "DATA HISTÓRICO VALOR [D/C]".

    Limitação assumida: não há motor de OCR de imagem neste ambiente —
    extratos digitalizados como imagem (scan) não são lidos. Ver README.
    """

    LINHA_RE = re.compile(
        r'^(?P<data>\d{2}/\d{2}/\d{4})\s+(?P<historico>.+?)\s+(?P<valor>-?[\d.,]+)\s*(?P<sinal>[CD])?$'
    )

    def parse(self, arquivo):
        import pdfplumber

        lancamentos = []
        with pdfplumber.open(arquivo) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text() or ''
                for linha in texto.splitlines():
                    m = self.LINHA_RE.match(linha.strip())
                    if not m:
                        continue
                    valor_str = m.group('valor').replace('.', '').replace(',', '.')
                    try:
                        valor = Decimal(valor_str)
                    except InvalidOperation:
                        continue
                    sinal = m.group('sinal')
                    tipo = 'DEBITO' if sinal == 'D' or valor < 0 else 'CREDITO'
                    lancamentos.append({
                        'data': datetime.strptime(m.group('data'), '%d/%m/%Y').date(),
                        'historico': m.group('historico').strip(),
                        'valor': abs(valor),
                        'tipo': tipo,
                        'identificador_transacao': '',
                    })
        return lancamentos


class OpenFinanceExtratoParser(BaseExtratoParser):
    """
    RF38 — ponto de extensão para integração direta via API bancária
    (Open Finance). Não há credenciais/conexão bancária real disponíveis
    neste ambiente; a chamada real ficaria aqui.
    """

    def parse(self, arquivo):
        raise NotImplementedError(
            'Integração Open Finance não configurada neste ambiente — requer '
            'credenciais bancárias reais e não está disponível neste ambiente de build.'
        )


_PARSERS = {
    'PDF': PDFTextExtratoParser,
    'CSV': CSVExtratoParser,
    'OPEN_FINANCE': OpenFinanceExtratoParser,
}


def get_parser(formato):
    parser_cls = _PARSERS.get(formato)
    if parser_cls is None:
        raise ValueError(f'Formato de extrato não suportado: {formato}')
    return parser_cls()
