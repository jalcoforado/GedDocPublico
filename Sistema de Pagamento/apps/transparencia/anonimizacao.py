import re


def mascarar_documento(fornecedor):
    """
    RF58/LGPD — mascara o CPF de fornecedores pessoa física antes da
    exposição pública. CNPJ de pessoa jurídica é informação pública e não
    é mascarado. Dados bancários nunca são incluídos na serialização
    pública (ver transparencia/views.py).
    """
    digitos = re.sub(r'\D', '', fornecedor.cnpj_cpf or '')
    if fornecedor.tipo_pessoa == 'FISICA' and len(digitos) == 11:
        return f"{digitos[:3]}.***.***-{digitos[-2:]}"
    return fornecedor.cnpj_cpf
