# Plano do Módulo de Protocolo

**Status:** P1 ✅ entregue · **Autor:** Jorge + assist · **Última revisão:** 2026-05-26

## Roadmap

| Fase | Status | Notas |
|---|---|---|
| **P1 — Balcão** | ✅ entregue | Migration 0015, endpoints + 2 PDFs (etiqueta Pimaco + comprovante 2 vias), página `/protocolo/balcao` com botões "Etiqueta"/"Comprovante", smoke OK |
| **P2 — NUP federal** | ✅ entregue | Migration 0017 + service Mod-11, opt-in por tenant, PDFs com NUP, página /configuracoes. Smoke OK |
| **P3 — Portal Cidadão** | ✅ entregue (parcial) | Wizard 3 passos (Dados → Documento → Confirmação), upload de anexo público, rate-limit 5/24h, canal_entrada=portal, auto-classificação CCD via P4, NUP exibido quando configurado. **Pendente:** captcha externo (hCaptcha/Turnstile) e notificação email/WhatsApp |
| **P4 — CCD + TTD** | ✅ entregue | Migration 0016 (22 classes CONARQ + 14 regras TTD), 11 endpoints, 3 páginas + sugestão no balcão, relatório vencendo-prazo |
| P5 — Gov.br | pendente | fora do escopo atual |
| **P6 — Apensamento/Desentranhamento/Volumes** | ✅ entregue | Migration 0018 + 10 endpoints + 3 termos PDF + 3 componentes frontend (árvore apensados, lombadas volumes, modal desentranhar). Smoke OK |
| P7 — Integrações (PNCP/DO/Receita) | pendente | depende P2 |

## 0. Estado atual (pré-protocolo)

Antes de começar P1, o que já está pronto **fora** da lista da seção 2:

- **Workflow obrigatório (strict mode)** — opt-in via `dsl.strict`. Backend bloqueia encaminhamentos fora do trilho; super-user pode override com motivo (audit). Já em uso no fluxo `aquisicao-bens-consumo` v3. Detalhes no README.
- **Permissões granulares de edição** — módulo `auth/perms.py` com `require_permission(codigo, action)` aplicado em ~51 endpoints. Frontend `useAuth().can(codigo, action)` esconde botões sem permissão.
- **Organograma real de Sobral** carregado — 24 secretarias + sub-departamentos típicos (workflow `aquisicao` vincula estados a unidades reais).
- **Editor visual do organograma** com drag-to-reparent + undo + ciclo validation backend.

**O que ainda bloqueia P1:** decisões D1-D6 abaixo. Quando alinhadas, este doc é re-aberto com roteiro detalhado (migrations, schemas, rotas, telas).

## 1. Contexto

Protocolo no setor público brasileiro é a **porta de entrada formal de documentos** numa organização (prefeitura, autarquia, ministério). Toda comunicação externa (de cidadão, fornecedor, outro órgão) que vire processo entra pelo protocolo: ali ela ganha número único, classificação documental, comprovante e direcionamento inicial pra unidade responsável.

Aprimora-py hoje já tem grande parte do que um sistema de protocolo precisa — mas via fluxo "Novo processo" interno. Falta o conjunto que diferencia **abertura de processo interno** (servidor abre por demanda própria) de **protocolo** (alguém de fora — cidadão, empresa, outro órgão — entrega documento que vira processo).

## 2. O que já está pronto

| Recurso | Onde está | Status |
|---|---|---|
| Numeração sequencial por ano | função PG `gerar_numero_processo_string()` | ✅ formato `P000011/2026` |
| Cadastro de manifestante (PF/PJ) | `/manifestantes` | ✅ |
| Classificação por tipo de processo + assunto | `/tipos-processo`, `/assuntos` | ✅ |
| Encaminhamento entre unidades | `/processos/{id}/encaminhamentos` | ✅ |
| Comprovante de recebimento PDF | `/processos/{id}/comprovante-recebimento.pdf` | ✅ |
| Anexos com tipo classificável | `/anexos` + `TipoAnexo` | ✅ |
| Sigilo / público | `Processo.publico` | ✅ |
| Apensamento (processo pai) | `Processo.id_processo_pai` | ✅ schema (UI parcial) |
| Audit log append-only | `audit_log` + service | ✅ |
| Workflow automático por tipo | `tipo_processo_workflow` | ✅ |
| Trail (mini-organograma do percurso) | `processo_trail` service | ✅ |
| Portal cidadão básico | `routers/cidadao.py` | ✅ tracking + auth |

## 3. Gaps identificados

### 3.1 Forma de entrada

| Falta | Por quê |
|---|---|
| **Balcão de Protocolo** (UI) | Servidor que recebe documento físico precisa de tela rápida pra abrir protocolo no balcão. Hoje só tem "/processos/novo" pensado em demanda interna |
| **Portal público de abertura** | Cidadão deveria poder protocolar sem login (com captcha) ou via login gov.br. Hoje só tracking, não abertura |
| **Recepção de e-mail oficial** | Documentos chegam por email da Prefeitura — deveria virar protocolo automaticamente |
| **Importação de outro sistema** | Migração de protocolos vindos de outro órgão / sistema legado |

### 3.2 Classificação documental

| Falta | Por quê |
|---|---|
| **Espécie documental** | "Ofício", "Requerimento", "Memorando" etc — distinto de "tipo de processo". Hoje só existe TipoAnexo (tipo do arquivo anexo), não a espécie do documento que originou o protocolo |
| **CCD (Código de Classificação de Documentos)** | Taxonomia hierárquica padrão de arquivística (CONARQ pra federal, varia por município). Hoje "Assunto" é flat e amarrado ao tipo_processo |
| **TTD (Tabela de Temporalidade Documental)** | Diz quanto tempo cada classe de doc deve ser guardada antes de descartar ou recolher ao arquivo permanente. Crítico pra compliance (Lei 8.159/91) |
| **Sigilo gradual** | Hoje publico = bool. Padrão é: ostensivo / reservado / secreto / ultrassecreto (5 níveis com prazo de reclassificação) |

### 3.3 Identificação padronizada

| Falta | Por quê |
|---|---|
| **NUP (Número Único de Protocolo)** federal | Formato `NNNNN.NNNNNN/AAAA-DD` exigido pra integração com sistemas federais (Decreto 8.539/2015). Hoje usamos `P000011/2026` proprietário |
| **Código do órgão** | 5 dígitos iniciais do NUP identificam o órgão. Multi-tenant precisa ter esse campo por tenant |
| **Dígito verificador** | Mod-11 sobre os 15 dígitos restantes |

### 3.4 Manipulação documental

| Falta | Por quê |
|---|---|
| **Apensamento UI** | Schema tem `id_processo_pai` mas falta UI pra apensar/desapensar com termo formal e auditoria |
| **Desentranhamento** | Remover documento de processo já formado, gerando termo. PHP tinha — Python não migrou |
| **Juntada por linha** | Reordenação de documentos no processo (capa + sumário + anexos numerados) |
| **Volume** | Processo grande vira N "volumes" físicos. Schema não modela |

### 3.5 Integrações

| Falta | Por quê |
|---|---|
| **Gov.br SSO** | Cidadão entra com gov.br, sistema confia no nível de autenticação (bronze/prata/ouro) |
| **Diário Oficial** | Publicar abertura de processo público, despacho final |
| **PNCP (Portal Nacional de Contratações Públicas)** | Processos de aquisição precisam ser publicados |
| **Receita Federal (CNPJ/CPF)** | Validar manifestante na hora |

## 4. Decisões pendentes do Jorge

Marcar essas decisões antes de iniciar implementação:

| # | Decisão | Default sugerido |
|---|---|---|
| D1 | Adotar NUP federal? Ou ficar com proprietário (`PNNNNNN/AAAA`)? | NUP — desbloqueia integrações federais |
| D2 | Espécie documental + CCD: adotar tabela CONARQ municipal padrão? Ou minimalista (10-15 entradas)? | Minimalista no começo, expandir |
| D3 | Cidadão pode abrir protocolo sem login (anônimo + captcha) ou exige gov.br? | **Com login obrigatório** — evita spam, alinha com LGPD |
| D4 | TTD automatizada (job que descarta documentos vencidos) ou só marcação manual? | Marcação manual no MVP, automação na fase 2 |
| D5 | Balcão é módulo separado ou tela dentro de "Processos"? | Tela separada `/protocolo/balcao` — UX especializada |
| D6 | Apensamento permite cruzar tenants (raríssimo, mas existe em prefeitura X autarquia)? | Não — bloquear no schema |

## 5. Proposta de fases

Quebrar em entregas de 1-3 semanas. Cada uma deploy-ready em produção.

### Fase P1 — Balcão de Protocolo (2 semanas)
**Objetivo:** servidor consegue cadastrar protocolo físico ao receber documento no balcão.

- Backend
  - Migration: adicionar `processo.espécie_documental_id`, `processo.data_recepcao`, `processo.canal_entrada` (`balcao | email | portal | api`)
  - Tabela `especie_documental` (Ofício, Requerimento, Memorando, Declaração, Petição, Carta, Edital, Relatório, Carta, outros)
  - Endpoint `POST /protocolo/balcao` — abre processo + carimba data de recepção + canal
  - Endpoint `GET /protocolo/{numero}/etiqueta.pdf` — etiqueta com barcode + número + data + manifestante + classificação
- Frontend
  - Página `/protocolo/balcao` — formulário otimizado pra digitação rápida (busca de manifestante por CPF/CNPJ com cache, scanner de barcode pra anexar etiqueta de doc, espécie + assunto + unidade destino + sigilo)
  - Etiqueta auto-imprimível ao salvar
  - Comprovante 2 vias (entrega + arquivo)

**Critério de conclusão:** atendente no balcão consegue protocolar 10 documentos em 5 min.

### Fase P2 — NUP federal (1 semana)
**Objetivo:** trocar formato proprietário pelo padrão federal.

- Migration: adicionar `tenant.codigo_orgao_nup` (5 dígitos)
- Função PG nova `gerar_nup_string(tenant_id) → NNNNN.NNNNNN/AAAA-DD`
- Feature flag `usar_nup_federal` por tenant — não-disruptivo
- Manter `numero_processo` legacy + adicionar `nup` ao schema
- Etiquetas e capas mostram NUP quando flag ativa

**Critério de conclusão:** processos novos ganham NUP válido, integração federal habilitada.

### Fase P3 — Portal Cidadão de Protocolo (3 semanas)
**Objetivo:** cidadão protocola pela web sem ir ao balcão.

- Backend
  - Login obrigatório por enquanto (gov.br fica pra P5)
  - `POST /portal/cidadao/protocolar` — cria processo com `canal_entrada=portal`
  - Anti-spam: rate-limit por CPF (5/dia) + captcha (hCaptcha ou Turnstile)
  - Auto-classificação: cidadão escolhe assunto, sistema sugere unidade destino + workflow
- Frontend (portal separado em `/portal` — já existe esqueleto)
  - Wizard 3 passos: Dados → Documento → Confirmação
  - Upload com preview e validação de mime
  - Tela "Meus protocolos" listando todos do CPF + tracking detalhado
  - Notificação por email/WhatsApp (já temos infra) a cada movimento

**Critério de conclusão:** cidadão abre protocolo, recebe número, acompanha sem voltar à prefeitura.

### Fase P4 — Espécie + CCD + TTD (2 semanas)
**Objetivo:** classificação documental padrão, base pra archive management.

- Migration: criar `ccd_classe` (hierárquica), `ttd_regra` (espécie + ccd → anos_corrente + anos_intermediario + destino_final)
- Seed mínimo: 15-20 classes CCD comuns (administração geral, finanças, RH, urbanismo)
- Endpoint admin `/protocolo/ccd` CRUD da árvore
- Carimbo no processo: `id_ccd_classe`, prazo de guarda calculado automaticamente
- Frontend: campo CCD no balcão e portal, sugestão por palavra-chave do assunto

**Critério de conclusão:** todo protocolo tem CCD; relatório mostra processos vencendo prazo de guarda.

### Fase P5 — Gov.br integration (3 semanas)
**Objetivo:** cidadão entra com gov.br no portal.

- Backend
  - OIDC client (gov.br homologação + produção)
  - Mapping nível autenticação (bronze/prata/ouro) → permissões no portal
  - Validação de identidade via API CPF gov.br
- Frontend
  - Botão "Entrar com gov.br" no `/portal/login`
  - Indicador visual do nível
- Política
  - Documentos sensíveis (ex.: requerimento de aposentadoria) exigem nível ouro
  - Cadastro automático de manifestante com dados retornados

**Critério de conclusão:** cidadão entra com gov.br, evita digitar dados, sistema confia na identidade.

### Fase P6 — Apensamento + Desentranhamento + Volumes (2 semanas)
**Objetivo:** ações documentais avançadas, completar paridade com PHP.

- Backend
  - `POST /processos/{id}/apensar` — body `{id_processo_apensado, motivo}`
  - `POST /processos/{id}/desapensar` — gera termo
  - `POST /processos/{id}/desentranhar-anexo/{anexo_id}` — termo formal
  - Modelo `processo_volume` quando passar de N páginas
- Frontend
  - Botões na ficha do processo com confirm e termo PDF
  - Visualização da árvore de apensados

**Critério de conclusão:** desentranhamento e apensamento funcionam com termo PDF auditável.

### Fase P7 — Integrações governamentais (4 semanas)
**Objetivo:** PNCP + Diário Oficial + Receita Federal validação.

- PNCP: publicar processos de aquisição quando estado workflow `licitacao`
- Diário Oficial municipal: enviar minutas pra publicação
- Validação CPF/CNPJ via API Receita (Serpro ou similar)

**Critério de conclusão:** processo de aquisição vira publicação automática.

## 6. Esforço total estimado

| Fase | Semanas | Dependências |
|---|---|---|
| P1 Balcão | 2 | — |
| P2 NUP federal | 1 | — (independente) |
| P3 Portal Cidadão | 3 | P1 (espécie + canal_entrada) |
| P4 CCD + TTD | 2 | P1 |
| P5 Gov.br | 3 | P3 |
| P6 Apensamento | 2 | — (independente) |
| P7 Integrações | 4 | P2 (NUP) |
| **Total** | **17 semanas** | (~4 meses, paralelizando algumas) |

Paralelização possível: P1 + P2, depois P3 + P4 + P6, depois P5 + P7. Reduz pra ~10 semanas com 2-3 frentes simultâneas.

## 7. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Gov.br homologação demora | Alta | Iniciar paperwork em paralelo com P1 |
| CCD municipal Sobral indisponível | Média | Começar com tabela genérica CONARQ, refinar com arquivista da Prefeitura |
| Volume gigante (>10k protocolos/dia em pico de IPTU) | Baixa pra Sobral, Alta pra capitais | Indexar por (tenant_id, criado_em), particionamento por ano da tabela processo se passar 5M rows |
| LGPD: cidadão pede exclusão de seus protocolos | Certa | Endpoint `DELETE /portal/cidadao/me/dados-pessoais` + anonimização (já que apagar audit log é ilegal) |
| Servidor protocola coisa errada | Certa | UI de correção pré-processamento (até X minutos depois), depois só via desentranhamento auditado |

## 8. Próximos passos

1. **Jorge revisa decisões D1-D6** desse doc
2. **Smoke do gov.br homologação** — paperwork pra obter credenciais (3-6 semanas externas)
3. **Conversar com Arquivo Municipal de Sobral** sobre CCD/TTD vigente
4. **Definir feature flag rollout** — começar com tenant Sobral em opt-in, depois global
5. **Começar implementação por P1 Balcão** (maior valor imediato, menor dependência)

---

**Quando estiver alinhado nas decisões**, eu reabro este doc com o roteiro detalhado da Fase P1 (migrations, schemas, rotas, telas) pra começar a codar.
