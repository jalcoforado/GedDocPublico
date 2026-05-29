# PR 2e — Proposta Técnica: Validação Pública de Assinatura (código/token)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** PROPOSTA (não implementar)

> Permitir que um terceiro **sem login** valide a autenticidade/integridade de
> uma assinatura via um **código público**, sem expor o conteúdo do documento
> nem metadados sensíveis, e sem vazar a existência de processos sigilosos.
> Este documento é **só proposta** — nada será implementado até aprovação.

## 1. Modelo de token público
- Cada `assinatura_anexo` assinada ganha um **`codigo_validacao`** opaco, aleatório,
  alta entropia (≥128 bits; ex.: `secrets.token_urlsafe(16)` ≈ 22 chars). **Não
  derivável do id**, não sequencial.
- Gerado no ato da assinatura (PR2a/2b já tem o ponto). O **comprovante PDF**
  (PR2b) passa a imprimir o código + a URL pública de validação (+ QR opcional).
- **Token opaco armazenado** (lookup no banco), não HMAC self-contained — porque
  precisa ser **revogável** e refletir o estado atual (sigilo/recusa) a cada
  consulta. (Decisão: opaco-armazenado vs HMAC → opaco.)

## 2. Risco de enumeração (mitigações)
- Token de alta entropia → inviável força bruta.
- **Respostas indistinguíveis** para *inexistente / sigiloso / revogado* (mesma
  resposta neutra) → não revela existência.
- **Rate-limit por IP** (nginx + app/Redis, reusar infra do throttle).
- Nunca expor o id sequencial; só o token. Sem listagem pública.

## 3. O que pode ser exibido SEM autenticação (mínimo)
**Exibir:** resultado (válida/íntegra sim/não), nome do **servidor signatário**
(agente público assinando ato oficial), data/hora, **hash SHA-256** (público,
prova integridade), nível (simples), aviso "assinatura eletrônica interna — não
ICP-Brasil", número do processo **somente se ostensivo**.
**NÃO exibir:** IP, user agent, método de autenticação, evidências internas,
conteúdo do documento, dados do manifestante/cidadão, qualquer dado de processo
não-ostensivo.

## 4. Processo sigiloso
- **Só assinaturas de processo OSTENSIVO** são validáveis publicamente.
- Anexo de processo `interno/reservado/secreto/ultrassecreto` → resposta **neutra
  de indisponibilidade**, idêntica à de token inexistente (não confirma que
  existe uma assinatura sigilosa). Reusar `services/sigilo` para checar o nível
  atual a cada request.

## 5. Dados pessoais / LGPD
- **Minimização:** só o necessário para validar. Sem IP/UA/manifestante.
- Nome do **servidor** signatário: ato público (transparência) — exibível;
  **dados do cidadão/manifestante: não**.
- **Decisão humana (jurídica):** confirmar base legal para exibir o nome do
  servidor + número do processo publicamente; opção de **mascarar** o nome
  (ex.: iniciais) se o jurídico exigir.

## 6. Expiração
- **Sem expiração** por padrão: o valor probatório dura décadas; um comprovante
  deve ser validável a qualquer tempo.
- Porém a validação **re-checa, a cada consulta**, o estado atual (sigilo,
  status da assinatura, revogação) — então deixa de validar se o contexto mudar.

## 7. Revogação
- Campo `validacao_publica_revogada` (+ motivo, usuário, data) em
  `assinatura_anexo`.
- **Revogação automática** quando: assinatura deixa de estar `assinada`
  (recusada/cancelada), anexo desentranhado, ou processo deixa de ser ostensivo.
- Revogado → resposta neutra de indisponibilidade (não vaza).

## 8. Logs / auditoria
- Auditar cada consulta pública: `acao="assinatura.validada_publica"`, payload
  `{resultado, integro, ip}` (+ referência ao `assinatura_anexo` quando válido).
- **Throttle da auditoria** para não inundar sob enumeração (reusar a política do
  PR2a). Logar tentativas de token inválido de forma agregada (contador), não 1
  linha por tentativa.

## 9. Rate-limit
- nginx `limit_req` no path público (ex.: 20/min/IP) + app-level (Redis) como
  defesa em profundidade. Bloqueio temporário após excesso.

## 10. Matriz de respostas (endpoint público)
| Caso | Resposta |
|---|---|
| Válida + íntegra | 200 `{valido:true, integro:true, signatario, dt, hash, nivel, processo_numero?}` |
| Válida + **hash diverge** | 200 `{valido:true, integro:false, detalhe:"documento alterado após a assinatura"}` |
| Inexistente | 404 **neutro** `{valido:false}` |
| Revogada | **mesma resposta neutra** que inexistente |
| Sigilosa | **mesma resposta neutra** que inexistente |
> *inexistente / revogada / sigilosa* são **indistinguíveis**. Apenas
> ostensivo-não-revogado confirma existência (válida/inválida-hash).

## 11. Comprovante público × interno
- **Público** (este PR): oculta IP, user agent, método, evidências; só o mínimo
  probatório (signatário, data, hash, resultado).
- **Interno** (PR2b, autenticado, `/assinaturas/{id}/comprovante.pdf` + guard de
  sigilo): pode manter os metadados completos. São **dois comprovantes
  distintos**.

## 12. Arquivos prováveis
- Backend: migration (`codigo_validacao`, `validacao_publica_revogada` + motivo/
  usuário/data em `assinatura_anexo`), `services/assinaturas.py` (gerar código no
  assinar; `validar_publico(codigo)`), **novo router público sem auth**
  (`routers/validacao_publica.py`), `schemas`, possível `pdf_comprovante_assinatura`
  (incluir código/QR), nginx conf (rate-limit do path).
- Frontend: página pública de validação (sem login) + QR/código no comprovante.
- Testes: backend + e2e + componente.

## 13. Critérios de aceite
- Endpoint público valida por código **sem autenticação**.
- Token opaco, alta entropia, não enumerável; respostas neutras para
  inexistente/sigiloso/revogado (não vazam existência).
- **Processo sigiloso nunca é validável publicamente.**
- Comprovante público **não** expõe IP/UA/metadados/dados de cidadão.
- Revogação funciona (manual + automática por mudança de estado).
- Rate-limit ativo no path público.
- Auditoria das validações públicas (com throttle).
- Sem regressão; testes verdes.

## 14. Testes obrigatórios
1. código gerado no ato da assinatura (formato/entropia).
2. validação pública de assinatura ostensiva íntegra → `valido:true, integro:true`.
3. documento alterado → `integro:false`.
4. token inexistente → resposta neutra (404).
5. **assinatura de processo sigiloso → resposta neutra** (não vaza).
6. assinatura revogada → resposta neutra.
7. revogação automática quando o processo deixa de ser ostensivo / anexo desentranhado.
8. comprovante público **não contém** IP/UA/método/dados do cidadão.
9. rate-limit do endpoint público dispara após o limite.
10. auditoria registra a validação pública (e não inunda sob enumeração).
11. enumeração: respostas indistinguíveis entre inexistente/sigiloso/revogado.

## 15. Fora de escopo
gov.br, ICP-Brasil, carimbo de tempo externo, assinatura qualificada, hash chain
de audit_log, versionamento completo de GED, mudanças grandes de UI.

## 16. Decisões humanas pendentes
1. Exibir nome completo do servidor signatário publicamente, ou mascarar? (LGPD)
2. Exibir número do processo (ostensivo) na validação pública?
3. Token perpétuo (proposto) vs com expiração opcional configurável?
4. QR code no comprovante agora ou depois?

---

> **Parar aqui.** Proposta apenas — nenhum código alterado. Aguardando sua
> avaliação/decisões (§16) antes de fechar o escopo implementável do PR 2e.
