# Pagamentos — Onda C: escopo

**Escrito em:** 2026-07-28 · **Status:** rascunho para validação. **Não autorizado a iniciar.**

> **Aviso que muda como ler este documento.** A spec municipal que define a Onda C **não está
> versionada neste repositório**. Os códigos `RF-*`/`RN-*` aparecem por todo o backend
> (`RF-AUT-02..17`, `RF-VAL-01/02/06`, `RF-EXT-01..10`, `RN-01/11/14/15`), mas nenhum `.md` do
> repo os define — as Ondas A e B foram implementadas contra um documento externo.
>
> Portanto: **a Fatia C1 abaixo é derivada de evidência no código**, não da spec. Ela descreve o
> que é possível e coerente com o que já existe. A **Fatia C2 não foi escopada de propósito** —
> depende de contratos externos que nenhuma leitura de código revela.
>
> Ao receber a spec, confronte C1 com ela antes de implementar. Onde divergir, a spec vence.

---

## Por que a divisão em duas fatias

O backlog resume a Onda C em quatro frentes: relatórios de exceção, export PDF/XLSX/CSV,
integrações contábil e bancária, API idempotente. Elas não têm o mesmo grau de incerteza:

| frente | depende da spec? | por quê |
|---|---|---|
| Export CSV/PDF | **não** | é o mesmo dado que as telas já mostram, noutro formato |
| Relatórios de exceção | **parcialmente** | os estados de exceção já existem no modelo; *quais* interessam ao município, não |
| Export XLSX | decisão, não spec | dependência nova (ver custo abaixo) |
| Integração contábil | **sim** | layout de arquivo é definido pelo sistema contábil da prefeitura |
| Integração bancária | **sim** | CNAB/API do banco; o próprio spec joga isso para a "3ª etapa" |
| API idempotente | **sim** | quem consome, e com que garantia, é requisito externo |

Implementar C1 sem a spec é seguro porque **não inventa regra de negócio** — expõe o que já
está decidido e implementado. Implementar C2 sem a spec seria inventar contrato.

---

## Fatia C1 — exportações e relatórios de exceção

### C1.1 Exportações

Cinco listagens já existem, com filtros implementados, e não têm export:

| origem | filtros já existentes |
|---|---|
| Débitos (`listar_debitos`) | status, fonte, natureza, credor, contrato, urgência, competência (RF-PNL-02) |
| Extrato da conta (`listar_extrato`) | conta |
| Painel de caixa (`painel_caixa`) | — (todas as contas, com os 5 saldos) |
| Ordens de pagamento (`listar_ordens`) | — |
| Conciliação: lançamentos e pendências | extrato |

**Custo por formato, medido nas dependências atuais:**

- **CSV** — barato. Precedente pronto em `transporte_regulado.gerar_csv_alvaras()`; só `csv` da
  stdlib.
- **PDF** — barato. `weasyprint==63.1` já é dependência e `services/html_pdf.py` já converte
  HTML→PDF (é como a Ordem de Pagamento é gerada hoje).
- **XLSX** — **dependência nova**: `openpyxl` não está em `pyproject.toml`. É a única das três que
  custa algo além de código.

**Decisão pendente:** XLSX entra? Se o consumo real é "abrir no Excel", CSV com separador `;` e
BOM UTF-8 resolve sem dependência. XLSX só se justifica por formatação (colunas tipadas, moeda,
múltiplas abas).

### C1.2 Relatórios de exceção

Os estados de exceção **já existem no modelo** — o que falta é reuni-los. Cada linha abaixo é
verificável hoje:

| exceção | onde está | observação |
|---|---|---|
| Autorização com saldo insuficiente (RN-15) | `debito_historico.justificativa` | ⚠️ ver dívida abaixo |
| Fornecedor IRREGULAR/PENDENTE com débito ativo | `fornecedor.situacao_cadastral` | bloqueio já existe na autorização |
| Débitos SUSPENSOS | `debito.status` | + justificativa no histórico |
| Débitos DEVOLVIDOS | `debito.status` | quantas vezes, por quem |
| Pagamento sem liquidação confirmada | `debito.liquidacao_confirmada` | RN-01 barra, mas o relatório mostra tentativas |
| Lançamentos de extrato não conciliados | `lancamento_extrato.conciliado` | envelhecimento por dias |
| Débitos PAGOS não conciliados | cruzamento parcela↔conciliação | é o que impede o status CONCILIADO |
| Conta abaixo do saldo mínimo | `painel_caixa.abaixo_minimo` | já calculado |
| Débito urgente sem justificativa | `urgente` + `justificativa_urgencia` | |

**Dívida descoberta ao escopar — a exceção RN-15 não é consultável de forma robusta.**
`autorizar_lote` grava a justificativa concatenada em texto livre:

```python
justificativa += f" — EXCEÇÃO DE SALDO (RN-15): {excecao_por_conta[conta.id]}"
```

Um relatório teria de fazer `LIKE '%EXCEÇÃO DE SALDO (RN-15)%'`. Funciona, mas quebra se alguém
mudar o texto. **Recomendação:** antes do relatório, promover a exceção a coluna estruturada
(`ordem_pagamento.excecao_saldo` bool + `justificativa_excecao`), com migration e backfill a
partir do padrão de texto. É barato agora e o custo cresce com o volume.

---

## Fatia C2 — não escopada

Precisa da spec e de contratos externos:

- **Integração contábil** — layout do arquivo, periodicidade, plano de contas de destino,
  conciliação de retorno.
- **Integração bancária** — CNAB (240/400?) ou API; qual banco; homologação. O próprio spec
  municipal já joga a API bancária real para a "3ª etapa" — não confundir com o que a Onda C
  entrega.
- **API idempotente** — quem consome, qual granularidade da chave de idempotência, qual janela de
  retenção, e o que acontece com replay divergente.

---

## O que preciso para fechar o escopo

1. **A spec municipal** — sem ela, C1 é inferência e C2 não existe.
2. **XLSX entra?** (decisão de dependência, não de requisito)
3. **A promoção da exceção RN-15 a coluna estruturada entra na Onda C** ou fica como dívida
   registrada?

---

## Como este documento se relaciona com o processo

O processo do repositório é: escopo fechado em doc → autorização humana → implementar → testes →
autorização → commit. Este documento é a **primeira etapa, ainda incompleta** — ele não está
autorizado a virar implementação, e a parte que depende da spec sequer está escrita.
