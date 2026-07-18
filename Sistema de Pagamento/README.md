# Sistema de Gestão e Autorização de Pagamentos Municipais

Implementação completa dos 13 módulos (M1–M13) e dos requisitos funcionais e
não funcionais descritos em `Requisitos_Sistema_Pagamentos_Municipais.docx`,
em Django 4.2 (Python 3.9) com SQLite por padrão.

## Setup do zero (ambiente novo)

O `venv/` **não vai no zip/repositório** — recrie-o localmente:

```bash
cd "Sistema de Pagamento"
python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> Este projeto foi desenvolvido com **Python 3.9** (única versão disponível no
> ambiente original) e por isso fixa **Django 4.2 LTS** em vez do Django 5.x.
> Se você tiver Python 3.10+, pode atualizar `Django` para 5.x no
> `requirements.txt` sem mudanças de código — nada aqui usa recursos
> exclusivos do 4.2.

## Como rodar

```bash
source venv/bin/activate
python manage.py migrate
python manage.py seed_demo_data # cria cadastros, usuários e pedidos de demonstração
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. O portal público de transparência
(`/transparencia/`) não exige login.

### Credenciais de demonstração

Todas com senha `Municipio@123` e troca obrigatória no primeiro login (RF63):

| Perfil | E-mail |
|---|---|
| Solicitante | solicitante@municipio.gov.br |
| Secretário da Pasta | secretario@municipio.gov.br |
| Autorizador Final | autorizador@municipio.gov.br |
| Tesouraria | tesouraria@municipio.gov.br |
| Controle Interno | controle@municipio.gov.br |
| Administrador | admin@municipio.gov.br |

### Rodando os testes

```bash
python manage.py test
```

## Mapeamento módulo → app Django

| Módulo do documento | App | Conteúdo |
|---|---|---|
| M13 — Segurança/Acesso | `apps.accounts` | login por e-mail, troca obrigatória de senha, bloqueio por tentativas (RF62-66) |
| M1 — Cadastros Básicos | `apps.cadastros` | órgãos, fornecedores, fontes, contas, naturezas, contratos, alçadas (RF01-07) |
| M2, M3, M4, M5, M9 | `apps.pagamentos` | `PedidoPagamento` (agregado central), workflow completo, `services.py` com as regras de negócio, Ordem de Pagamento |
| M6 — Contas e Saldos | `apps.financeiro` | movimentações, saldo comprometido/disponível, lançamento manual |
| M7, M8 — Conciliação | `apps.conciliacao` | upload/parse de extratos, matching automático, pendências, vínculo manual |
| M10 — Painéis/Relatórios | `apps.relatorios` | dashboards, exportação PDF/Excel/CSV, restos a pagar, gestão fiscal |
| M11 — Transparência | `apps.transparencia` | portal público, exportação aberta, anonimização LGPD |
| M12 — Auditoria | `apps.auditoria` | log imutável, captura automática via signals |

A camada de regras de negócio do fluxo de pagamento fica inteira em
`apps/pagamentos/services.py` — segregação de funções (RF64), bloqueio de
saldo insuficiente (RF25), alçada (RF07) e trilha de status são validados ali,
nunca diretamente em views ou no admin.

## Convenções para continuar o desenvolvimento

- **Regras de negócio ficam em `services.py`, nunca em views/admin.** Toda
  transição de status de um pedido passa por uma função em
  `apps/pagamentos/services.py` (ex.: `aprovar_secretario`,
  `autorizar_lote`, `executar_pagamento`). Se for adicionar uma nova regra
  de negócio, esse é o lugar — as views só chamam essas funções e tratam as
  exceções de `apps/pagamentos/exceptions.py`.
- **Choices/enums centralizados em `apps/core/choices.py`** (`StatusPedido`,
  `Criticidade`, `GrupoDespesa`) — reaproveite-os em vez de criar novos
  `TextChoices` espalhados pelos apps.
- **RBAC via `apps/core/permissions.py`** — decorator `@role_required('PAPEL', ...)`
  para function-based views, mixin `RoleRequiredMixin` para class-based
  views. `CONTROLE_INTERNO` e `ADMIN` sempre têm acesso, mesmo sem estar na
  lista de papéis passada.
- **Auditoria é automática, mas precisa de registro manual para novos
  modelos.** `apps/auditoria/apps.py` (`AuditoriaConfig.ready()`) lista
  explicitamente quais modelos são auditados via signals. Um modelo novo
  que precise de trilha de auditoria (RF59) tem que ser adicionado nessa
  lista — não é automático para todo `models.Model`.
- **Dados sensíveis usam `EncryptedTextField`** (`apps/core/fields.py`) —
  use-o para qualquer novo campo de dado bancário/sigiloso, nunca
  `TextField`/`CharField` puro.
- **`apps/core/test_utils.py`** tem um `criar_cenario_basico()` reutilizável
  nos testes (cria órgão, fonte, conta, natureza, fornecedor e um usuário
  por perfil) — use-o em vez de duplicar setup em novos testes.
- O documento de requisitos original (`Requisitos_Sistema_Pagamentos_Municipais.docx`)
  é a fonte da verdade para os RFs/RNFs citados nos comentários e commits —
  vale manter esse hábito de referenciar o número do requisito ao
  implementar algo relacionado a ele.

## Simplificações e pontos de extensão (declarados, não escondidos)

Alguns requisitos dependem de sistemas externos reais (banco, SSO
corporativo, sistema contábil municipal) que não existem neste ambiente de
build. Onde isso ocorre, a interface/contrato foi implementada e documentada,
mas a integração real precisa ser conectada em produção:

- **RF38/RF39 (extrato bancário)** — leitura real de PDF texto e CSV
  (`apps/conciliacao/parsers.py`). Não há OCR de imagem (extrato escaneado
  como foto/scan não é lido) nem conexão Open Finance real — o
  `OpenFinanceExtratoParser` é o ponto de extensão pronto para isso.
- **RF62 (SSO/Active Directory)** — autenticação por e-mail/senha padrão do
  Django. Um backend SSO/SAML real entraria em
  `config/settings.py:AUTHENTICATION_BACKENDS`.
- **RNF07 (integração com o sistema contábil municipal/SIAFIC)** —
  modelada como endpoint REST (`/api/ne-validation/<numero>/`) consultando a
  tabela `NotaEmpenhoReferencia`, que representa localmente o que a
  integração real traria. Não há conexão com um SIAFIC real.
- **RNF01/05/06 (disponibilidade 99%, escalabilidade multiórgão,
  backup/DR)** — são requisitos de infraestrutura de produção, não de
  código; dependem de como o sistema for hospedado (load balancer, réplicas,
  rotina de backup do banco).
- **RNF08 (WCAG)** — HTML semântico, labels e `alt` text foram usados, mas
  não houve auditoria de acessibilidade completa.
- **RF19 (notificações)** — e-mails são enviados de forma síncrona
  (`EMAIL_BACKEND` = console por padrão neste ambiente). Uma fila
  assíncrona (Celery/Redis) é a evolução natural para produção/alto volume.
- Os cadastros básicos (M1, RF01-07) são administrados via **Django Admin**
  em vez de telas customizadas — é uma interface CRUD completa e já
  robusta, adequada para dados de parametrização de back-office.

## Banco de dados em produção

Por padrão usa SQLite (`db.sqlite3`, zero-config). Para PostgreSQL, defina a
variável de ambiente `DATABASE_URL` (ex.:
`postgres://usuario:senha@host:5432/nome_do_banco`) antes de rodar
`migrate` — `config/settings.py` já lê essa variável via `dj-database-url`.
