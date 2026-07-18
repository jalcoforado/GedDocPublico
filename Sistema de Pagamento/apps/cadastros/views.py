from django.shortcuts import render

from apps.core.permissions import role_required

# RF01-RF07: os cadastros básicos são administrados via Django Admin
# (interface CRUD completa, com busca/filtros) — esta view é apenas um
# atalho central para as seções relevantes.
SECOES_ADMIN = [
    ('Órgãos/Secretarias (RF01)', '/admin/cadastros/orgaosecretaria/'),
    ('Fornecedores/Credores (RF02)', '/admin/cadastros/fornecedor/'),
    ('Fontes de Recursos', '/admin/cadastros/fonterecursos/'),
    ('Contas Bancárias (RF03)', '/admin/cadastros/contabancaria/'),
    ('Naturezas de Despesa (RF04)', '/admin/cadastros/naturezadespesa/'),
    ('Contratos (RF05)', '/admin/cadastros/contrato/'),
    ('Alçadas de Autorização (RF07)', '/admin/cadastros/alcadaautorizacao/'),
    ('Usuários e Perfis (RF06)', '/admin/accounts/usuario/'),
]


@role_required('ADMIN')
def menu(request):
    return render(request, 'cadastros/menu.html', {'secoes': SECOES_ADMIN})
