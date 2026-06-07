# DEMO-1 — Seed e roteiro de demonstração comercial

> Documento **somente de escopo**. Nada será implementado sem autorização.
> Estado base: `origin/main` em `8900bf1` (TECH-2 publicado).
> Meta: base de dados demonstrativa controlada + roteiro de apresentação,
> sem nova feature de produto.

## 1. Resumo executivo

- **Abordagem proposta:** novo CLI `python -m app.cli.seed_demo` seguindo o
  padrão consolidado de `app/cli/tenant.py` (argparse + asyncio + SessionLocal +
  subcomandos `apply` / `reset` / `status`).
- **Tenant da demo:** **`demo` dedicado** (decisão recomendada — ver §4). O
  tenant `sobral` atual já tem **167 processos legacy** acumulados; misturar
  demo com isso confunde apresentação e dificulta cleanup determinístico.
- **Marcadores:** todos os dados demo carregam prefixo `demo-` em slugs e
  e-mails em domínio reservado `.test` — mesma convenção firmada no TECH-2.
- **Reuso de serviços existentes:** o seed monta dados chamando os mesmos
  services do produto (`servico.criar`, `abertura_processo.abrir`,
  `complementacao_documental.solicitar`, etc.), sem schemas novos nem
  endpoints novos. Garante que a demo exercita o caminho real.
- **Roteiro em `docs/demo-roteiro-apresentacao.md`** com versões de 5, 15 e
  30 minutos e variantes por público (prefeito, gestor de protocolo,
  servidor, TI).

## 2. Inventário do que já existe

### 2.1. Infra de CLI (modelo a seguir)

[backend/app/cli/tenant.py](backend/app/cli/tenant.py) já estabelece o padrão:
- `argparse` com subcomandos.
- `asyncio.run` no entrypoint.
- `SessionLocal()` para a transação.
- Funções privadas `_create`/`_list`/`_set_active` por subcomando.
- Output amigável com banner formatado.

Reusar essa convenção mantém o seed alinhado com o resto da plataforma e
evita inventar padrão novo.

### 2.2. Estado atual do tenant `sobral` (id=1)

| Recurso | Hoje |
|---|---:|
| Serviços (`protocolos.servico`) | **1** |
| Processos (`protocolos.processo`) | **167** |
| Usuários ativos | **2** |
| Unidades de trabalho | **44** |
| Tipos de processo | **3** |
| Tipos de manifestante | **2** |
| Tipos de anexo | **4** |
| Assuntos | **7** |

Sobral tem **catálogos prontos** (assuntos, tipos, unidades) mas também
**167 processos antigos** que poluiriam a demo. Por isso recomendamos tenant
dedicado (ver §4).

### 2.3. Services reutilizáveis (sem schema novo)

| Service | Arquivo | O que faz |
|---|---|---|
| `provisionar_tenant` | `services/provisioning_tenant.py` | Cria tenant + admin + grupo SU + unidade + catálogos mínimos. **Idempotência:** já bloqueia slug duplicado. |
| `Servico` (model) + `services/servico.py` | mesmo | Catálogo (CRUD). |
| `abertura_processo` | `services/abertura_processo.py` | Abre processo a partir de serviço (cidadão ou balcão). |
| `complementacao_documental` | `services/complementacao_documental.py` | Solicita / responde / cancela complementação. |
| `prazos` | `services/prazos.py` | Cálculo + classificação. |
| `assinaturas` | `services/assinaturas.py` | Assinatura digital + validação pública. |
| `anexos` | `services/anexos.py` | Upload e vínculo a documentos. |
| `notificacoes` | `services/notificacoes.py` | Mensagens de fluxo. |

**Não tocar nesses services** — chamar pelo caminho público, com `tenant_id`
do contexto. Se um service estiver acoplado a HTTP demais para uso CLI,
flagar como decisão em aberto (provavelmente todos já são reutilizáveis;
`provisionar_tenant` é a prova).

## 3. Abordagem proposta — CLI `seed_demo`

### 3.1. Comandos

```bash
docker exec aprimora-py-backend python -m app.cli.seed_demo apply  \
    --tenant demo                    # default; opcionalmente outro slug
docker exec aprimora-py-backend python -m app.cli.seed_demo reset  \
    --tenant demo                    # remove apenas o que o seed criou
docker exec aprimora-py-backend python -m app.cli.seed_demo status \
    --tenant demo                    # mostra o que existe e o que falta
```

Subcomando `apply` é **idempotente**: cada entidade é checada por chave
natural (slug do serviço, identificador estável) antes de inserir. Re-rodar
o `apply` é seguro: cria o que falta, não duplica o que já existe.

Subcomando `reset` apaga **apenas** entidades com prefixo `demo-` no slug ou
e-mail. Não toca em nada que não foi criado pelo seed. Seguro por design.

Subcomando `status` faz dry-run: lista o que existe, o que falta criar, e
quantos itens cada categoria tem hoje.

### 3.2. Salvaguardas

- **Tenant alvo deve existir** (não cria automaticamente; o operador roda
  primeiro `app.cli.tenant create --slug demo ...` ou o seed sugere o
  comando se o slug não existir).
- **Recusa rodar se `--tenant` for slug em allowlist de produção
  conhecida** (ex.: nomes claramente reais como `sobral`, `fortaleza`,
  qualquer slug que **não comece com `demo`** sem flag `--allow-non-demo`
  explícita). Reduz acidente de poluir tenant real.
- **Marca o tenant como demo** em uma coluna ou atributo (avaliar: pode ser
  via `cor_primaria='#888888'` + nome `Prefeitura Demo (não usar em
  produção)`, ou adicionar coluna boolean — esta última seria mudança de
  schema, **fora de escopo**, então preferir convenção de nome).

## 4. Decisão crítica — tenant dedicado vs reusar `sobral`

| Aspecto | `demo` dedicado (recomendado) | Reusar `sobral` |
|---|---|---|
| Limpeza | Trivial — `tenant.deactivate demo` ou DELETE em cascata | Filtragem por prefixo `demo-`; risco de bater em legacy |
| Pollution de catálogos | Zero — fresh tenant | Soma a tipos/assuntos legacy |
| Realismo do dashboard | Limpo, controlado | Mistura demo com 167 processos antigos |
| Esforço de setup | Roda `tenant create` antes | Pula o passo |
| Risco de tocar em dado real | Praticamente zero | Médio — `sobral` é o tenant default de DEV |
| Subdomínio para apresentar | `demo.aprimora.local` | `sobral.aprimora.local` |

**Recomendação: tenant `demo` dedicado.** Custa um comando extra de setup
documentado no roteiro; ganha isolamento total e cleanup determinístico.

## 5. Dados demo propostos

### 5.1. Tenant

| Atributo | Valor |
|---|---|
| Slug | `demo` |
| Nome | `Prefeitura Demo Aprimora (apresentação)` |
| Admin e-mail | `admin@demo.test` |
| Admin senha | gerada pelo `tenant create`, exibida 1x; após login, fluxo SEC-1 obriga troca |
| Cor primária | `#1e3a5f` (mesma do branding default) |

### 5.2. Unidades de trabalho (mínimo 5)

| Slug interno | Nome |
|---|---|
| `demo-protocolo` | Protocolo Geral |
| `demo-obras` | Secretaria de Obras |
| `demo-meio-ambiente` | Secretaria de Meio Ambiente |
| `demo-administracao` | Secretaria de Administração |
| `demo-iluminacao` | Departamento de Iluminação Pública |

### 5.3. Servidores (mínimo 4)

| E-mail | Nome | Lotação |
|---|---|---|
| `admin@demo.test` | Admin Demo | Protocolo Geral |
| `servidor.obras@demo.test` | Ana Costa | Obras |
| `servidor.protocolo@demo.test` | Bruno Lima | Protocolo |
| `servidor.ambiente@demo.test` | Carla Souza | Meio Ambiente |

### 5.4. Catálogo de serviços (6 itens — cobre todas as variações pedidas)

| Slug | Nome | Documentos exigidos | Prazo | Destacado |
|---|---|---|---|---|
| `demo-poda-arvore` | Solicitação de poda de árvore | Foto da árvore, comprovante de residência | 10 dias | sim |
| `demo-alvara-funcionamento` | Alvará de funcionamento | CNPJ, contrato social, planta baixa | 30 dias | sim |
| `demo-iluminacao-publica` | Solicitação de iluminação pública | (nenhum) | 15 dias | não |
| `demo-ouvidoria` | Manifestação geral (ouvidoria) | (nenhum) | 20 dias | sim |
| `demo-evento-publico` | Licença para evento público | Termo de responsabilidade, plano de segurança | **3 dias** (prazo curto) | sim |
| `demo-certidao-administrativa` | Certidão administrativa | Documento de identidade | 5 dias | não |

**Variações cobertas:** com/sem documentos; prazo curto/médio; destacados;
descrições e orientações cuidadosamente escritas (~3 linhas cada).

### 5.5. Manifestantes (12 — cidadãos demo)

CPF + nome fictícios. Domínio de e-mail: `@cidadao.demo.test`. Padrão:
`maria.silva@cidadao.demo.test`, `joao.santos@cidadao.demo.test`, etc.

CPFs gerados algoritmicamente (válidos pelo dígito verificador) com
prefixo numérico identificável (ex.: começam com `999`).

### 5.6. Processos (mínimo 12, cobrindo todos os estados pedidos)

| # | Serviço | Estado | Ponto da demo |
|---|---|---|---|
| 1 | poda-arvore | aberto, sem mov. | recém-aberto |
| 2 | alvara-funcionamento | aberto, doc pendente | checklist incompleto |
| 3 | alvara-funcionamento | aberto, doc completo | checklist completo |
| 4 | poda-arvore | complementação aberta | aguarda cidadão responder |
| 5 | poda-arvore | complementação respondida | tramitação após resposta |
| 6 | iluminacao-publica | em andamento, prazo OK | dentro do prazo (verde) |
| 7 | evento-publico | em andamento, prazo apertado | **vencendo** (amarelo) |
| 8 | ouvidoria | em andamento, atrasado | **atrasado** (vermelho) |
| 9 | certidao-administrativa | concluído no prazo | métrica positiva |
| 10 | poda-arvore | concluído atrasado | métrica de regressão |
| 11 | certidao-administrativa | concluído + assinado | fluxo de assinatura |
| 12 | alvara-funcionamento | aberto + anexos PDFs | viewer + checklist |

**Datas calculadas relativas a `today()`** para que o seed permaneça realista
ao longo do tempo (não fixar `criado_em='2026-01-15'` que vira dado velho).

### 5.7. Anexos

- 3-5 PDFs sintéticos (gerados em runtime via `reportlab`, já dep do
  projeto): comprovante de residência fake, foto-substituta PDF, planta
  baixa simplificada. Tudo claramente marcado **"DOCUMENTO DEMO — não
  usar"** no rodapé.
- Vinculados a documentos do checklist via `key` estável (D-KEY).

### 5.8. Complementações

- 1 aberta no processo #4 (com mensagem "Por favor, anexe foto da árvore
  com referência de tamanho").
- 1 respondida no processo #5 (resposta do cidadão + anexo + histórico
  visível).

### 5.9. Assinatura

- 1 documento do processo #11 assinado pelo servidor `admin@demo.test`
  via fluxo real (usa `services/assinaturas.py`).
- Validação pública (QR/link) demonstrável.

## 6. Estratégia de idempotência

Cada entidade tem **chave natural** verificada antes do INSERT:

| Entidade | Chave natural |
|---|---|
| Tenant | `slug='demo'` |
| Unidade de trabalho | `(tenant_id, slug interno)` ou `nome` |
| Usuário | `(tenant_id, email)` |
| Manifestante | `(tenant_id, cpf)` |
| Serviço | `(tenant_id, slug)` |
| Processo | `(tenant_id, numero)` ou identificador estável criado pelo seed |
| Complementação | `(processo_id, ordem)` |
| Anexo | `(processo_id, nome_arquivo)` |

Re-rodar `apply` em estado parcial:
- Insere o que falta.
- Atualiza (idempotentemente) campos descritivos que tenham mudado no seed
  fonte (nome, descrição, orientações).
- **Não** sobrescreve campos que o operador eventualmente tenha editado
  manualmente fora de campos descritivos.
- Reporta no fim: `criados=N atualizados=M ja_existentes=K`.

## 7. Estratégia de cleanup

Subcomando `reset`:
1. Identifica todos os processos do tenant alvo.
2. Filtra os que têm `numero` ou `metadata.demo=true` (decisão de campo
   pode ser `numero` começando com prefixo demo, OU coluna nova — preferir
   **prefixo no `numero`** para evitar schema change).
3. Para cada processo demo: limpa anexos físicos do storage, audit_log
   relacionado, complementações, prazos, assinaturas, movimentações,
   processo.
4. Limpa serviços, manifestantes, usuários (exceto admin) com prefixo
   `demo-` ou domínio `.test`.
5. Mantém o tenant `demo` por padrão; opcional `--drop-tenant` para
   remover completamente.

**Cleanup SQL é executado pelo CLI** numa transação, ordenando pelas FKs
conhecidas (mesma lição aprendida no TECH-2: `aprimora_py.audit_log`
precisa vir antes de `utils.usuario`).

## 8. Segurança / conformidade

- ❌ Zero dado pessoal real. Todos CPFs gerados (válidos por dígito mas
  reservados; usar prefixo identificável tipo `999.999.xxx-yy`).
- ❌ Zero e-mail real. Apenas `.test` (RFC 6761).
- ❌ Zero URL/telefone real.
- ✅ Tenant nominalmente marcado `Prefeitura Demo Aprimora (apresentação)`
  no `nome` — operador vê na tela que é demo.
- ✅ Banner avisando "ambiente de demonstração" na tela inicial — **fora
  de escopo do DEMO-1**, ficaria como TECH posterior. O nome do tenant
  já alerta.
- ✅ Subdomínio `demo.aprimora.local` (dev) / `demo.aprimora.app` (prod —
  só apontar se quisermos demo online; pode ficar sem DNS).

## 9. Roteiro de demonstração (`docs/demo-roteiro-apresentacao.md`)

Estrutura proposta — 3 versões aninhadas:

### 9.1. Versão **5 minutos** — elevator pitch (prefeito/secretário)

1. **30s — Carta de serviços do cidadão.** Mostrar `/cidadao` no tenant
   demo: 6 serviços com cards, busca, destaques.
2. **1min — Cidadão abre solicitação.** Solicitar `demo-poda-arvore` em
   vivo (CPF pré-preenchido a partir do seed). Mostrar o número de
   protocolo gerado e tela de acompanhamento.
3. **1min — Servidor recebe e tramita.** Login com `admin@demo.test`,
   ver o processo recém-aberto, encaminhar para Secretaria de Obras.
4. **1min — Dashboard executivo.** Mostrar gráfico de prazos
   (verde/amarelo/vermelho), top serviços demandados, processos
   atrasados.
5. **30s — Assinatura digital + validação pública.** Escanear QR code de
   um documento assinado (processo #11) — abrir a URL pública e mostrar
   a validade.
6. **1min — Pergunta + fechamento.** "Quanto custa hoje processar um
   pedido de poda em papel? Quanto leva? Quantos se perdem?"

### 9.2. Versão **15 minutos** — gestor de protocolo

Tudo do 5min, mais:
- **2min — Checklist documental + complementação:** processo #4 com
  complementação aberta; abrir, mostrar histórico, simular resposta do
  cidadão. Mostrar como o checklist passa de pendente para completo.
- **2min — Prazos em detalhe:** filtros do dashboard (atrasados,
  vencendo), responsáveis, drill-down por serviço.
- **2min — Fluxo de trabalho:** encaminhamentos entre unidades, audit
  trail, comprovante PDF.
- **1min — Reset/transparência:** "Tudo que você viu pode ser exportado.
  Nada do que está aqui é dado real — é um ambiente de demo."

### 9.3. Versão **30 minutos** — equipe técnica / TI

Tudo do 15min, mais:
- **3min — Admin de catálogo:** criar um serviço novo na hora, mostrar
  documentos exigidos com `key` estável.
- **3min — Unidades, grupos, permissões:** organograma, RBAC, sigilo
  gradual.
- **3min — Multi-tenant SaaS:** mostrar o tenant `sobral` lado a lado,
  branding distinto, isolamento RLS, admin de plataforma
  (`/admin/tenants`).
- **3min — Operações:** RUNBOOK, CLI de tenant, backup por tenant,
  observabilidade (health, audit).
- **3min — Roadmap aberto:** o que vem aí, perguntas técnicas.

Cada bloco tem **passo-a-passo concreto** (URL → ação → resultado
esperado) e **fallback** (o que falar se algo demorar a renderizar).

## 10. Testes mínimos

| Teste | Cobertura |
|---|---|
| `pytest tests/test_demo_seed_aplica_sem_erro.py::test_apply_cria_entidades` | seed roda sem exceção; cria N serviços, M processos esperados |
| `::test_apply_idempotente` | rodar `apply` 2x produz o mesmo estado (contagem inalterada) |
| `::test_apply_isola_tenant` | criar dados no tenant `demo` não muda contagem de outros tenants |
| `::test_status_relata_estado` | `status` enxerga corretamente o que existe e o que falta |
| `::test_reset_remove_so_demo` | `reset` apaga só dados demo; usuário-âncora do `provisioning` (admin) sobrevive |
| `::test_cleanup_respeita_fks` | `reset` em estado com audit_log/anexos não dispara FK violation |

Suite completa pré-existente (337 pytest, 243 vitest, tsc=0) deve continuar
verde após o PR.

## 11. Riscos

1. **Service `abertura_processo` pode exigir contexto HTTP (request,
   user)** — se precisar adaptação para CLI, ou criar wrapper que monte
   esse contexto. Análise: `provisioning_tenant` já faz isso sem HTTP
   context, então é viável.
2. **Anexos PDF sintéticos ocupam storage** — usar `reportlab` em RAM e
   gerar PDF pequeno (~5KB). Storage local em `uploads/` é volume montado
   no compose; cleanup remove arquivos físicos também.
3. **Cleanup que apaga audit_log** mexe em histórico — recomendado para
   demo (não há "produção" aqui) mas vale registrar no doc do RUNBOOK.
4. **Prazos calculados em runtime** — se rodar seed numa segunda e demonstrar
   na sexta, o "vencendo" pode virar "atrasado". O seed deve usar offsets
   relativos a `now()` para ficar estável dentro de uma janela de 5 dias.
   Para janelas maiores, re-rodar `seed_demo apply` (idempotente).
5. **Subdomain demo.aprimora.local** precisa estar resolvendo no
   `/etc/hosts` local. Sem isso a URL não funciona — incluir no roteiro
   como pré-req de setup.
6. **Não fazer demo no `sobral`** — se alguém rodar `seed_demo --tenant
   sobral` sem `--allow-non-demo`, o CLI deve recusar (salvaguarda §3.2).
7. **Senha do admin demo** é gerada pelo `tenant create` e exibida 1x.
   No roteiro, o admin precisa ter logado uma vez para cumprir o fluxo
   SEC-1 (troca obrigatória). Documentar passo de bootstrap no roteiro.

## 12. Fora de escopo (reafirmado)

- ❌ Nova feature de produto.
- ❌ Endpoint público novo (o CLI usa `SessionLocal` direto, não HTTP).
- ❌ Alteração de regra de negócio.
- ❌ Migration (nenhuma coluna nova; uso de campos existentes).
- ❌ Integração externa (IA, WhatsApp, gov.br, cobrança).
- ❌ Banner de "ambiente demo" na UI (fica para TECH futuro, se quiser).
- ❌ Mudança em assinatura, RLS, permissões.
- ❌ Dashboard novo, gráfico novo, tela nova.

## 13. Critérios de aceite

1. `python -m app.cli.seed_demo apply --tenant demo` roda em **< 30 s** sem
   erro, em tenant fresh ou em tenant que já tem o seed parcial.
2. Re-rodar `apply` é **no-op em estado pleno** (`criados=0
   atualizados=0`).
3. `python -m app.cli.seed_demo status --tenant demo` lista corretamente
   serviços, processos, etc.
4. `python -m app.cli.seed_demo reset --tenant demo` deixa o tenant
   `demo` limpo (zero serviços demo, zero processos demo).
5. CLI **recusa** `apply --tenant sobral` (ou qualquer slug que não
   comece com `demo`) sem `--allow-non-demo`.
6. Dashboard executivo do tenant `demo` mostra dados em cada faixa de
   prazo (verde/amarelo/vermelho), pelo menos um processo concluído no
   prazo, um concluído atrasado, e processos com assinatura.
7. Validação pública (QR/link) funciona para o documento assinado do
   processo #11.
8. Roteiro `docs/demo-roteiro-apresentacao.md` versão 5min é executável
   em ~5min por um operador novo seguindo o passo-a-passo.
9. `pytest tests/` continua **337+ verde** (com os novos testes de seed).
10. `vitest run` continua **243/243 verde**, `tsc --noEmit` continua **0**.
11. Backend funcional: zero arquivos em `backend/app/services/**`,
    `backend/app/routers/**`, `backend/app/models/**`,
    `backend/alembic/versions/**`, `frontend/**`. Único código novo: CLI
    + testes do CLI.

## 14. Decisões em aberto (preciso de aval antes de implementar)

1. **Tenant `demo` dedicado vs reusar `sobral`?** Recomendo dedicado.
2. **Marcação de "tenant demo"** por convenção de `nome` (sem schema) vs
   coluna nova? Recomendo convenção (sem schema novo).
3. **Cleanup deve apagar audit_log dos processos demo?** Recomendo sim
   (não há histórico precioso em ambiente demo).
4. **Senhas dos usuários demo** geradas (mais seguro mas pede um login
   intermediário pra trocar) vs fixadas em string conhecida pro roteiro
   (`demo123!`)? Recomendo **fixar** para a demo, com aviso explícito no
   nome do tenant — facilita o roteiro de 5min sem o fluxo SEC-1
   intermediário.
5. **Quantidades** das tabelas em §5 são suficientes? Sub-pode aumentar
   se a demo precisar mais densidade no dashboard.
6. **Localização do CLI**: `backend/app/cli/seed_demo.py` (sugerido) vs
   `backend/scripts/seed_demo.py` (não há pasta `scripts/` hoje)?
   Recomendo `cli/` por consistência com `tenant.py` e `backup.py`.

---

**Próximo passo após este doc**: aguardar autorização para implementar,
com as decisões de §14 confirmadas (especialmente §14.1 — tenant dedicado).
