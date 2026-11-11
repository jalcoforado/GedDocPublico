# Relatórios do Protocolo

> **Status:** vivo · **Autoridade sobre:** o que cada número de `/m/protocolo/relatorios` mede, quem vê, e as limitações conhecidas.
> **Última verificação:** 2026-11-11 (SI-34).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Fonte de verdade executável: `backend/app/services/relatorios_comum.py` (as
regras), `relatorios_gerencial.py` (a página) e os testes
`backend/tests/test_relatorios_protocolo_medidas.py` (o que cada número mede) e
`test_relatorios_protocolo_acesso.py` (quem vê). Se este doc divergir deles, o
código vence e este arquivo deve ser corrigido.

## Três telas, três perguntas

| Tela | Pergunta | Onde |
|---|---|---|
| Painel de controle | O que a minha unidade tem para fazer **agora**? | `/m/protocolo/painel` |
| Dashboard executivo | Qual o **panorama**, em gráficos? | `/dashboard` — **fora do menu** (ver Limitações) |
| **Relatórios** | O que aconteceu **no período**, com a lista que prova cada número? | `/m/protocolo/relatorios` |

## A página de relatórios

Uma página, um filtro no topo (período, unidade, tipo, assunto) e cinco seções.
**Cada seção conta pela sua própria data** e diz qual é:

| Seção | Conta | Pela data de |
|---|---|---|
| Entrada | processos abertos, por canal de entrada | abertura |
| Andamento | em andamento, em trânsito, parados | **hoje** — não usa o período |
| Saída | arquivados e tempo médio até arquivar | arquivamento |
| Gargalos | entradas em cada unidade, atrasos, permanência média | entrada na unidade |
| Assinaturas | pedidas, pendentes, concluídas, canceladas, tempo médio | pedido |

Por que não um seletor único de data: com o período pela abertura, a Saída
contaria "abertos em outubro que um dia foram arquivados" — número plausível
que responde outra pergunta.

Cada número tem **"Ver lista"** (a lista que o produziu, com o mesmo recorte na
URL) e **CSV**. O teste garante que o número da seção é o total dessa lista. A
página inteira sai em PDF.

## Definições

- **Período:** dias em **hora de Brasília**, inclusive nas duas pontas. O banco
  grava UTC; "até 10/11" vai até 11/11 03:00 UTC.
- **Situação:** *arquivado* = tem movimentação de arquivamento; *em trânsito* =
  envio ainda não recebido nem desfeito; *em andamento* = o resto. São as
  mesmas condições das caixas de trabalho. O campo `processo.ativo` **não é
  usado**: nenhuma parte do sistema o escreve.
- **Parado:** não arquivado e **sem nenhuma movimentação** (envio, recebimento,
  despacho, assinatura…) há N dias — padrão 15, escolhido na tela.
- **Unidade, em quatro sentidos:** *envolvida* (dona ou onde está agora —
  padrão), *dona* (a unidade proprietária escolhida na abertura), *onde está
  agora*, e *por onde passou* (dona ou quem **recebeu** o processo; envio
  pendente e recusa não contam).
- **Entradas na unidade (Gargalos):** a abertura, na unidade dona, ou um
  recebimento. Envio pendente ou recusado não é entrada.
- **Atraso:** a estadia na unidade terminou (ou segue) depois do **fim do dia**
  do prazo do envio que trouxe o processo — a definição das caixas de trabalho.
- **Assinatura concluída:** realizada **e** com data de fim. Realizada sem data
  de fim conta como pendente.

## Quem vê o quê

- **Qualquer servidor com a transação `processo`** vê os relatórios de **todas
  as unidades** da prefeitura (decisão de 2026-11-10). Não há recorte por
  lotação.
- **Sigilo vale em tudo** — lista, totais, quebras, CSV, PDF e os números da
  página: só entra processo que a credencial de quem consulta alcança, a mesma
  regra de `GET /processos`. Um total que contasse o reservado revelaria que ele
  existe.
- Rascunho de outra pessoa não entra; dados de outra prefeitura não entram,
  nem pedindo a unidade dela.

## Exportação

- **CSV** traz o recorte descrito nas primeiras linhas e a lista completa. Se o
  recorte passar do teto (50 mil processos; 10 mil na tramitação), o CSV é
  **recusado** com o motivo, em vez de sair cortado.
- **PDF** tem lista limitada e diz quando cortou ("os N mais recentes de M");
  os totais contam tudo.

## Limitações conhecidas

- **Fuso fixo `America/Fortaleza`.** O cadastro da prefeitura não guarda fuso;
  vale para os municípios do Ceará. Município em outro fuso precisa desse campo
  antes.
- **Canal de entrada antigo.** O campo é recente: processos anteriores aparecem
  como "Não informado" na seção Entrada.
- **Horas nas outras telas.** Os relatórios mostram hora de Brasília; o detalhe
  do processo e as caixas ainda mostram a hora UTC como se fosse local (3h a
  mais). Card separado.
- **Dashboard executivo** (`/dashboard`) saiu do menu em 2026-08-07 e só abre
  pela URL, para quem tem a transação `dashboard`. O Ctrl+K "dashboard" leva ao
  Início, não a ele. O quadro "Ativos agora" dele ainda conta `processo.ativo`.
- **Download de tarefas em segundo plano** (`/jobs/{id}/resultado`) não confere
  quem pediu o arquivo. Card separado.
