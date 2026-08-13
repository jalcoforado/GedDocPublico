# Pagamentos — Onda C, fatia C1.3

*Escopo aprovado por Jorge em 2026-08-13. Continua `docs/pagamentos-onda-c-escopo.md`
(2026-07-28), que definiu C1.1 e C1.2.*

## Onde a Onda C está — medido, não lembrado

O item 2.1 do backlog afirma que não existe nada de export ou relatório em Pagamentos, com
`grep` como evidência. **Está desatualizado**: duas fatias já entraram.

| fatia | o que entregou | onde |
|---|---|---|
| C1.1 | export CSV da lista de débitos | PR #15, `services/pagamentos_export.py` |
| C1.2 | relatório de exceções | PR #16, `services/pagamentos_excecoes.py` |
| **C1.3** | **esta fatia** | as 4 listagens restantes + RN-15 estruturada |
| C2 | contábil, bancária, API idempotente | **bloqueada** — depende de spec externa |

A C1.1 previa **cinco** listagens e entregou uma. As outras quatro são esta fatia. O sintoma de
parar no meio não é falta de recurso: é o usuário não conseguir prever quais telas exportam.

## O que entra

### 1. Export das quatro listagens restantes

| listagem | serviço reusado | formatos |
|---|---|---|
| Extrato da conta | `pagamentos_caixa.listar_extrato` | CSV |
| Painel de caixa | `pagamentos_caixa.painel_caixa` | CSV + **PDF** |
| Ordens de pagamento | `pagamentos_autorizacao.listar_ordens` | CSV + **PDF** |
| Conciliação (lançamentos) | `pagamentos_conciliacao.listar_lancamentos` | CSV |

**Reuso do serviço de listagem é obrigatório**, como na C1.1: export que refaz a consulta diverge
da tela no primeiro filtro novo, e a divergência aparece como "o CSV veio diferente do que eu vi"
— reclamação que ninguém consegue reproduzir.

**PDF só nos dois que viram documento.** Painel de caixa e ordem de pagamento são o que se
imprime, assina e arquiva; extrato e lançamentos são material de planilha. `weasyprint` já é
dependência (`services/html_pdf.py`, usado na Ordem de Pagamento individual) — nenhuma
dependência nova. XLSX fica **fora**: `openpyxl` só se pagaria por formatação tipada e múltiplas
abas, que ninguém pediu, e o CSV com `;` + BOM já abre no Excel em pt-BR sem assistente.

### 2. RN-15 vira coluna estruturada

Hoje a exceção de saldo insuficiente existe só como texto concatenado:

```python
justificativa += f" — EXCEÇÃO DE SALDO (RN-15): {excecao_por_conta[conta.id]}"
```

e o relatório de exceções a consulta com `LIKE '%EXCEÇÃO DE SALDO (RN-15)%'`. Funciona e **quebra
em silêncio** no dia em que alguém reescrever a frase — o relatório passa a devolver zero linhas,
que é indistinguível de "não houve exceção". É o pior modo de falha possível num relatório de
compliance.

Entra: `ordem_pagamento.excecao_saldo` (bool, default false) e `justificativa_excecao` (text,
nulo), com migration, backfill a partir do padrão de texto, e a autorização gravando as duas.

**O marcador de texto continua sendo gravado.** Não é redundância esquecida: `debito_historico` é
registro histórico e a frase já está em linhas antigas; o backfill preenche a coluna, mas quem lê
a trilha continua vendo a mesma justificativa de sempre.

## O que NÃO entra

- **XLSX** — decisão acima.
- **C2 inteira** — integração contábil, bancária e API idempotente dependem de contratos externos
  que nenhuma leitura de código revela. Implementar sem a spec seria inventar contrato.
- **Filtros novos** nas listagens. O export exporta o recorte que a tela mostra, nada além.

## Como isto pode dar errado

1. **Rota literal engolida pela paramétrica.** `/exportar.csv` precisa ser declarada ANTES de
   `/{id}` — o FastAPI casa na ordem de declaração e a paramétrica devolve 422 sem chegar ao
   handler. Aconteceu três vezes no transporte; `tests/test_guarda_ordem_rotas.py` cobre.
2. **GET novo sem permissão.** Desde o item 1.0.8 (2026-08-11) toda leitura exige transação;
   `test_leitura_sem_permissao_nao_cresce_sem_decisao` reprova o esquecimento. Os endpoints novos
   herdam o código dos irmãos do mesmo router.
3. **Backfill que erra o alvo.** Um `LIKE` mal escrito preenche zero linhas e o teste de
   "coluna existe" passa mesmo assim. O teste do backfill afirma sobre uma linha criada com o
   texto antigo, e é invertido antes de valer.
4. **O relatório trocar de fonte e mudar o resultado.** Ao passar de `LIKE` para coluna, o número
   de exceções tem de ser o MESMO nas linhas antigas. Há teste comparando as duas fontes sobre o
   mesmo dado.

## Verificação

- Testes por listagem: cabeçalho, uma linha de dado conferida campo a campo, e vazio (que é
  cabeçalho sozinho, não arquivo vazio).
- Um teste HTTP com **usuário comum** por endpoint novo — o bypass de SU esconde gate errado.
- PDF: afirmar sobre o conteúdo extraído, não sobre "gerou bytes".
- Backfill e paridade `LIKE` × coluna, ambos invertidos.
