# Análise Arquitetural — Plataforma de Protocolo/GED para Prefeituras

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** análise (nenhuma alteração de código feita)

> Documento de avaliação crítica. Confronta 12 sugestões estratégicas recebidas
> com o **código real** do `aprimora-py`. Não assume que as sugestões estão
> corretas — várias já estão implementadas, uma superestima o problema, e há
> lacunas relevantes que elas não citam.

---

## 1. Visão geral do estado atual

**Arquitetura.** Strangler Fig: FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL no backend, Next.js 15 (App Router) no frontend, nginx roteando entre o Python novo e o PHP legado. Celery (worker + beat) para jobs/SLA. Observabilidade via Sentry + logging estruturado. CI no GitHub Actions roda 108 testes a cada PR. **Decisão firme do projeto: o PHP é só modelo inicial; a versão Python é independente.**

**Multi-tenancy — maduro.** `tenant_id` em todas as tabelas de negócio + **RLS no Postgres** (`SET LOCAL app.tenant_id` + policies `tenant_isolation_select/modify`), resolução de tenant por subdomínio do Host. Os testes rodam como role `aprimora_app` (NOBYPASSRLS) — validam RLS de verdade.

**AuthN/Z — maduro.** JWT HS256/RS256 coexistentes (interop PHP no cutover). Senha em MD5 (legado PHP) **+ bcrypt** (Python). Permissões granulares por transação (`require_permission(codigo, action)`) em ~51 endpoints, com bypass de super-usuário e espelhamento no frontend (`useAuth().can()`).

**Protocolo/Processo — forte.** Balcão (P1), NUP federal Mod-11 opt-in por tenant (P2), Portal Cidadão parcial (P3), CCD+TTD (P4), Apensamento/Desentranhamento/Volumes (P6). Workflow BPM com **strict mode** (DSL de trilho obrigatório) + alertas de SLA. Trail (mini-organograma do percurso), comprovantes/etiquetas/capa em PDF.

**Sigilo — recém-implementado (este ciclo).** 5 níveis LAI (ostensivo/interno/reservado/secreto/ultrassecreto), `publico` virou coluna gerada, credencial de acesso por usuário, TCI nos graus legais, enforcement em listagem/detalhe/PDF/ações. **Já separa sigilo legal de restrição administrativa interna** (ver sugestão 6).

**Pontos fracos confirmados (por exploração do código):**
- **Assinatura eletrônica** é o subsistema mais frágil: backend completo (3 tabelas + 5 endpoints, RLS), mas baseada em **verificação de senha MD5**, **sem hash do documento**, sem níveis (simples/avançada/qualificada), **sem auditoria** (ações de assinar não vão pro audit_log), sem IP/carimbo de tempo, e o **frontend está quebrado** (`AssinaturasProcesso.tsx` importa `api.assinaturas` e `SolicitacaoAssinatura` que **não existem** em `lib/api.ts`).
- **GED é intake-only:** anexos por upload, **sem versionamento, sem modelos/minutas, sem geração nato-digital, sem hash/integridade/cadeia de custódia**. Juntada (ordem), desentranhamento (soft-delete + termo) e volumes (informativos) existem.
- **Classificação (CCD/TTD) é seed-only:** taxonomia CONARQ simplificada + 14 regras na migration 0016, sugestão automática funciona, cálculo de temporalidade funciona — mas **não há CRUD admin** pra município gerir seu próprio plano.
- **Portal cidadão é genérico:** assunto livre + corpo + 1 upload opcional, rate-limit 5/24h, sem captcha. `catalogo.py` é apenas lookups de dropdown (não é carta de serviços). `busca.py` é ILIKE keyword (não semântica).
- **Audit log** é append-only (grants só SELECT/INSERT) e tenant-scoped, mas **não é tamper-evident** (sem hash chain).
- **Higiene do repo:** mayoritariamente limpa (sem chaves/segredos reais; `keys/` vazio e gitignored). Exceções: `backend/celerybeat-schedule` (binário pickled) e `tests-e2e/report/` estão versionados; `.gitignore` não os cobre.

---

## 2. Matriz de avaliação das sugestões

| # | Sugestão | Classificação | Justificativa técnica (confronto com o código) |
|---|----------|---------------|--------------------------------------------------|
| 1 | Evoluir de MVP de protocolo p/ plataforma GED arquivística robusta | **APLICAR COM AJUSTES** | Correto no diagnóstico, mas a *fundação* arquivística (CCD/TTD/espécie/temporalidade) **já existe**; o que falta é o **ciclo de vida documental** (versionamento, integridade, eliminação). Não é "começar GED", é "amadurecer o GED existente". |
| 2 | Posicionar como solução municipal completa (protocolo+processo+GED+arquivo+portal+IA governada), não só "protocolo digital" | **APLICAR** (posicionamento) | Os blocos já cobrem protocolo/processo/portal/classificação; "arquivo" e "IA governada" são as frentes novas. É decisão de produto, não de código. Alinhado à realidade. |
| 3 | Amadurecer GED: nato-digital, modelos, minutas, versionamento, juntada, peças, metadados obrigatórios, cadeia de custódia, classificação, temporalidade | **PARCIAL: JÁ EXISTE + APLICAR** | **Já existe:** juntada (`AnexoProcesso.ordem`), classificação (CCD), temporalidade (TTD), desentranhamento. **Falta:** versionamento, modelos/minutas, geração nato-digital, metadados obrigatórios, **cadeia de custódia (hash/integridade)**. A cadeia de custódia é a peça crítica e conecta com assinatura + object storage. |
| 4 | Assinatura juridicamente robusta: simples/avançada/qualificada, evidências, hash do doc, trilha, carimbo de tempo, futuro gov.br/ICP-Brasil | **APLICAR** (alta prioridade) | Confirmado: subsistema mais fraco. Hoje é senha-MD5, sem hash do documento, sem níveis, sem auditoria, sem carimbo. **Lei 14.063/2020** rege exatamente assinatura eletrônica no setor público (simples/avançada/qualificada) — a implementação atual não sustenta avançada/qualificada. |
| 5 | Tratar MD5/senha como legado/transição, não solução final | **JÁ É VERDADE / APLICAR** | Confirmado: assinar = `verify_md5(senha, usuario.senha)`. É transicional por design (bcrypt coexiste). Deve ser marcado explicitamente como legado e ter plano de saída. |
| 6 | Separar sigilo legal × restrição administrativa interna × dados pessoais/LGPD | **PARCIAL: JÁ EXISTE + APLICAR** | **Já feito neste ciclo:** ostensivo (público) / interno (restrição administrativa) / reservado-secreto-ultrassecreto (sigilo legal com TCI). **Falta a 3ª dimensão (LGPD):** dado pessoal é **ortogonal** ao grau LAI (um doc ostensivo pode conter dado pessoal). Não deve ser enfiado no mesmo enum — precisa de marcação/base-legal separada. |
| 7 | Portal por serviços (checklist, docs exigidos, prazo, unidade, pendência, complementação, acompanhamento) | **APLICAR** | Confirmado genérico (assunto livre + upload). `catalogo.py` **não** é carta de serviços (só lookups). É build net-new, mas a infra de **workflow + SLA + unidades** já existente sustenta. Alinha com a **Lei 13.460/2017** (carta de serviços). Fluxo de complementação é a maior lacuna de UX. |
| 8 | Preparar p/ interoperabilidade (Tramita GOV.BR, PEN, SEI) | **APLICAR COM AJUSTES** (conceitual agora, implementar depois) | **NUP federal (P2) já é a fundação** (PEN/Tramita usam NUP). Implementação plena depende de padrão XML/SOAP do PEN e é P7. Manter design "interop-ready"; adiar a integração concreta. |
| 9 | IA governada: triagem, classificação sugerida, resumo, minuta, detecção de pendências, busca semântica, apoio à decisão — nunca decisão automática | **APLICAR** | Alinhado ao `CHATBOT-PLAN.md` (já escrito). **Classificação sugerida já existe** (`sugerir_ccd_por_assunto`). Busca é keyword (semântica é net-new). Princípio human-in-the-loop = correto e casa com o plano (tool-calling read-only sob RLS+sigilo + validação factual). |
| 10 | Hardening: limpar chaves, arquivos sensíveis, caches, uploads, artefatos do repo | **APLICAR COM AJUSTES** (escopo bem menor que a sugestão sugere) | **Aqui o projeto está melhor do que a sugestão assume:** sem chaves/segredos reais commitados, `keys/` vazio e gitignored, sem `node_modules`/`__pycache__`. Limpeza real e *pontual*: remover `backend/celerybeat-schedule` (binário pickled) e `tests-e2e/report/` do git + cobrir no `.gitignore`. Débito latente à parte: hash MD5 de senha. |
| 11 | Estratégia comercial: PMEs (prefeituras pequenas/médias), implantação rápida, modelos prontos, baixo custo, conformidade, simplicidade | **APLICAR** (estratégia) | Coerente com o multi-tenant SaaS já construído + CLI de onboarding de tenant. "Modelos prontos" depende de resolver: CRUD de CCD/TTD + seeds por tenant + (futuro) modelos de documento. |
| 12 | Ordem do roadmap: segurança/comercial → assinatura → GED arquivístico → portal por serviços → interop → IA avançada | **APLICAR COM AJUSTES** | Ordenação boa no geral. Ajustes: (a) hardening é pequeno/rápido — fazer já; (b) **consertar o frontend de assinatura + auditar assinatura + hash do documento** são correções imediatas baratas e de alto valor jurídico; (c) a dimensão **LGPD** deve subir (exposição legal); (d) object storage/WORM (já decidido) entra junto da cadeia de custódia. Roadmap refinado na seção 7. |

### Onde as sugestões **conflitam** com a abordagem atual
- **Sugestão 10** trata o repo como inseguro/poluído de forma genérica; a realidade é um repo majoritariamente limpo com 2 artefatos pontuais. Aplicar "limpeza ampla" às cegas geraria ruído. Conflito de premissa.
- **Sugestão 6** parcialmente conflita por desconhecer que sigilo legal × interno **acabou de ser separado**; reimplementar criaria retrabalho. O delta real é só LGPD.
- **Sugestão 8** sobre gov.br conflita com a **decisão de escopo atual** (gov.br/mobile fora). Manter como "conceitual/adiado".

### Onde a abordagem atual é **melhor** que a sugestão
- **Multi-tenant + RLS + permissões granulares + sigilo gradual** estão à frente do que a maioria dos sistemas municipais oferece — as sugestões tratam isso como a-fazer quando já é diferencial entregue.
- **NUP federal já implementado** com Mod-11 e opt-in por tenant — adianta a interop (sugestão 8) mais do que ela presume.
- **Segurança do repo** (sugestão 10): o cuidado com `keys/` e segredos já está correto.

### Onde as sugestões **claramente melhoram** o projeto
- **Assinatura juridicamente robusta (4/5)** — endereça o maior risco jurídico e destrava o core do produto (documento com valor probatório).
- **Portal por serviços (7)** — salto de UX e conformidade (Lei 13.460), forte diferencial comercial.
- **Cadeia de custódia/integridade (3)** — torna o acervo confiável a longo prazo.
- **IA governada (9)** — diferencial competitivo real, com o caminho seguro já desenhado.

---

## 3. Lacunas **não** citadas nas 12 sugestões

1. **Assinatura não é auditada** (bug concreto): ações de assinar/solicitar/cancelar não geram `audit_log`. Correção trivial e obrigatória pra valor probatório.
2. **Frontend de assinatura quebrado** (`api.assinaturas`/`SolicitacaoAssinatura` inexistentes) — feature inutilizável hoje.
3. **Audit log sem tamper-evidence** — append-only por grants, mas sem hash chain/HMAC; quem comprometer a role `aprimora_app` pode inserir/alterar. Para valor probatório (Lei 11.419/2006), audit deveria ser encadeado (igual ao WORM que já decidimos pra documentos).
4. **CRUD admin de CCD/TTD ausente** — cada município tem seu próprio plano de classificação; sem isso a "implantação rápida" (sugestão 11) trava. Lacuna comercial.
5. **Workflow de eliminação documental** — TTD calcula datas, mas não há processo de eliminação com edital/termo e guarda do registro (Lei 8.159/91). Só marcação.
6. **Object storage / WORM** — já decidido (filesystem agora → S3-compatible com Object Lock antes do 2º tenant em produção); é pré-requisito de cadeia de custódia, mas as sugestões não o citam.
7. **Acessibilidade (eMAG/WCAG)** — portal público de governo tem exigência legal; o frontend hoje é estilo ferramenta interna.
8. **Backup/restore + DR + garantia de retenção por décadas** — não citado; crítico pra dado público.
9. **Hardening de senha (MD5)** — débito latente; planejar depreciação do MD5 mantendo só bcrypt pós-cutover.
10. **Rate-limit/WAF/captcha no portal público** — parcial (nginx no login, 5/24h); portal de governo é alvo.
11. **LGPD operacional** — além da dimensão de sigilo: direito de acesso/eliminação de dados pessoais (tensão com retenção arquivística), mapeamento de dados, registro de tratamento.

---

## 4. Riscos técnicos

- **Integridade documental inexistente:** sem hash do documento nem WORM, não há prova de não-adulteração — frágil para um acervo que deve durar décadas.
- **Assinatura acoplada a MD5 de senha:** quebra de uma senha = capacidade de assinar; e MD5 é fraco.
- **Audit não encadeado:** comprometimento da role de app permite forjar trilha.
- **Classificação seed-only:** onboarding de novo município exige migration manual; não escala comercialmente.
- **`celerybeat-schedule` versionado (pickled):** ruído de merge + superfície de desserialização.
- **Escala de DB único:** já mapeado em PROTOCOLO-PLAN (particionar `processo` por ano se passar de ~5M linhas; relevante p/ capitais, não p/ Sobral).
- **Storage em filesystem:** durabilidade/isolamento de bytes inferior a object storage (RLS protege o DB, não o disco) — decisão já registrada.

## 5. Riscos jurídicos

- **Lei 14.063/2020 (assinatura no setor público):** a assinatura atual (senha-MD5, sem hash/carimbo) **não sustenta** os níveis avançada/qualificada; só serve como "simples" frágil. Risco direto ao valor jurídico dos atos.
- **Lei 11.419/2006 (processo eletrônico) + valor probatório:** exige integridade/autenticidade — sem hash/WORM/carimbo de tempo, contestável.
- **LAI (Lei 12.527/2011):** sigilo gradual atende grande parte; **falta desclassificação automática no vencimento** do prazo (hoje só registra a data).
- **LGPD (Lei 13.709/2018):** sem dimensão própria de dado pessoal, sem fluxo de direito do titular vs retenção arquivística (Lei 8.159) — tensão não resolvida.
- **Lei 13.460/2017 (usuário de serviços públicos):** portal genérico não entrega carta de serviços/compromissos de prazo esperados.
- **Lei 8.159/91 (arquivos):** sem workflow de eliminação com edital/termo, a destinação final fica incompleta.

## 6. Riscos de produto

- **Core value frágil:** se "documento eletrônico com validade" é a promessa, a assinatura+integridade atuais não entregam — bloqueia venda séria.
- **Onboarding lento:** sem CRUD de CCD/TTD e seeds por tenant, "implantação rápida" (a tese comercial) não se sustenta.
- **Fricção do cidadão:** sem fluxo de complementação/pendência, o cidadão abre errado e não consegue corrigir — gera retrabalho no balcão.
- **Percepção de "só protocolo":** sem GED/arquivo/portal-por-serviço visíveis, o produto é confundido com concorrentes simples.

## 7. Oportunidades de diferenciação

1. **IA governada aterrada nos dados + controle de acesso** (RLS + sigilo) — poucos concorrentes municipais têm; é o `CHATBOT-PLAN`.
2. **Conformidade arquivística "de fábrica"** (CONARQ + plano municipal editável) com onboarding rápido.
3. **Plataforma única** protocolo + processo + GED + arquivo + portal — vs. concorrentes fragmentados.
4. **Base técnica madura** (multi-tenant RLS, permissões, sigilo, NUP) como fosso competitivo já pago.
5. **Carta de serviços (Lei 13.460)** bem-feita como vitrine de cidadania digital.

---

## 8. Roadmap priorizado

### A. Correções críticas imediatas (dias)
1. Remover `backend/celerybeat-schedule` e `tests-e2e/report/` do git + cobrir no `.gitignore`.
2. **Consertar o frontend de assinatura** (definir `SolicitacaoAssinatura` + `api.assinaturas.{solicitar,listarDoProcesso,cancelar}`) — feature está inutilizável.
3. **Auditar assinatura** (`assinatura.solicitada/assinada/cancelada` no audit_log).
4. **Hash SHA-256 do documento** no momento da assinatura (mínimo de integridade) — coluna + cálculo.
5. Alinhar limite de upload (backend 20MB vs wizard cidadão 25MB).

### B. Melhorias para MVP comercial (semanas)
1. **CRUD admin de CCD/TTD** (município gere seu plano) + **seeds por tenant** no onboarding.
2. **Pacote de evidências de assinatura** (hash + IP + carimbo + registro) e **modelagem de níveis** (simples/avançada base, conforme Lei 14.063).
3. **Portal por serviços (MVP)**: catálogo de serviço → documentos exigidos/checklist → unidade responsável → SLA; **fluxo de complementação/pendência**. Reusa workflow+SLA.
4. **Dimensão LGPD** separada do sigilo (tag de dado pessoal + base legal), ortogonal ao grau LAI.
5. **Migração para object storage** (decisão já tomada) + **cadeia de custódia** (hash na ingestão).

### C. Evolução para produto público robusto (meses)
1. **Workflow de eliminação documental** (TTD → edital/termo, Lei 8.159) + **desclassificação automática** de sigilo no vencimento.
2. **Audit tamper-evident** (hash chain/HMAC) para valor probatório.
3. **Assinatura avançada/qualificada** (ICP-Brasil/gov.br) + **carimbo de tempo (ACT)**.
4. **Versionamento + modelos/minutas + geração nato-digital** de documentos.
5. **Acessibilidade (eMAG/WCAG)** no portal + **backup/DR** + garantias de retenção.

### D. Diferenciais competitivos
1. **IA governada** (CHATBOT-PLAN): triagem, classificação sugerida, resumo, minuta, detecção de pendências, **busca semântica** — sempre com revisão humana, sob RLS+sigilo.
2. **Carta de serviços** com UX superior (Lei 13.460).
3. **Implantação rápida** (templates prontos) + **baixo custo** (multi-tenant eficiente).

### E. Adiar (com intenção)
1. **gov.br SSO** e **mobile** (fora do escopo atual declarado).
2. **Interop PEN/Tramita** plena (P7) — manter só "interop-ready" via NUP.
3. **IA avançada** (RAG semântico, agentes autônomos) — depois do MVP de IA governada.
4. **PNCP/DO/Receita** (P7), multi-vertical além de prefeituras.

---

## 9. Recomendações finais

1. **Não tratar tudo como novo.** Sigilo (legal×interno), CCD/TTD, juntada, NUP, multi-tenant e permissões **já existem e são fortes** — evoluir, não reconstruir.
2. **Atacar o elo mais fraco com o maior risco jurídico primeiro:** assinatura (frontend quebrado → auditoria → hash → níveis → ICP/gov.br). É barato começar e destrava o core do produto.
3. **Cadeia de custódia é transversal:** hash de documento + object storage WORM + audit encadeado resolvem integridade de uma vez — planejar como um tema, não três ilhas.
4. **LGPD é dimensão ortogonal** ao sigilo LAI; modelar separado pra não corromper o enum recém-criado.
5. **Onboarding self-service (CCD/TTD + seeds)** é o que viabiliza a tese comercial de "implantação rápida".
6. **Higiene do repo é pontual** — fazer os 2 cleanups e seguir; não há incêndio de segredos.

---

## 10. Próximos passos sugeridos para implementação

(aguardando sua autorização — nada será alterado antes)

1. **PR 1 — Hygiene + assinatura usável:** `.gitignore` + `git rm --cached` dos artefatos; consertar `api.assinaturas`/`SolicitacaoAssinatura`; auditar assinatura; hash do documento. (escopo pequeno, alto valor)
2. **PR 2 — CCD/TTD admin + seeds por tenant.** (destrava onboarding)
3. **PR 3 — Dimensão LGPD** (tag dado pessoal + base legal) separada do sigilo.
4. **Spike — Portal por serviços:** desenhar o modelo `Servico` (docs exigidos, SLA, unidade) reusando workflow; protótipo de fluxo de complementação.
5. **Spike — Assinatura Lei 14.063:** mapear requisitos de avançada/qualificada + carimbo de tempo + caminho gov.br/ICP-Brasil (decisão de provedor é jurídica, não técnica).
6. Revisar **D1–D6 do `CHATBOT-PLAN.md`** quando a frente de IA entrar.

> **Parar aqui.** Aguardando autorização explícita antes de modificar qualquer código.
