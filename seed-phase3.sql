-- Seed mínimo para Fase 3 (processos) em dev
BEGIN;

-- Ações (mínimo: abertura + encaminhamento + arquivamento)
INSERT INTO protocolos.acao (id, flag, acao, status_acao, status_movimentacao, texto_acao, ativo)
VALUES
  (1, 'ABERTURA',       'Abertura',       'aberto',     'inicial',  'Processo aberto',    true),
  (2, 'ENCAMINHAMENTO', 'Encaminhamento', 'tramitando', 'enviado',  'Encaminhado para',   true),
  (3, 'RECEBIMENTO',    'Recebimento',    'tramitando', 'recebido', 'Recebido por',       true),
  (4, 'ARQUIVAMENTO',   'Arquivamento',   'arquivado',  'final',    'Arquivado',          true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.acao_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.acao), 4));

-- Prioridades
INSERT INTO protocolos.prioridade (id, prioridade, fator, cor, ativo) VALUES
  (1, 'Normal',  1, '#cccccc', true),
  (2, 'Alta',    3, '#ff9900', true),
  (3, 'Urgente', 5, '#cc0000', true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.prioridade_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.prioridade), 3));

-- Manifestante de teste (id=1, Pessoa Física, José da Silva)
INSERT INTO protocolos.manifestante (id, id_tipo_manifestante, nome, cpf_cnpj, telefone_celular, email, ativo)
VALUES
  (1, 1, 'José da Silva',       '11122233344', '88999990001', 'jose@example.com', true),
  (2, 1, 'Maria Oliveira',      '55566677788', '88999990002', 'maria@example.com', true),
  (3, 2, 'ACME Construções LTDA','11222333000144', '88999990003', 'contato@acme.com', true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.manifestante_id_seq1', GREATEST((SELECT MAX(id) FROM protocolos.manifestante), 3));

-- Processos (3 exemplos). numero_processo é gerado por função do PG mas vou setar manual
INSERT INTO protocolos.processo
  (id, id_assunto, numero_processo, observacao, id_unidade_proprietaria, id_manifestante,
   data_hora_abertura, id_local_atual, id_usuario, ativo, publico, externo, virtual)
VALUES
  (1, 1, '2026/000001-1', 'Pedido de cópia de processo administrativo anterior.',
   3, 1, '2026-04-15 09:30:00', 3, 2, true, true, false, true),
  (2, 2, '2026/000002-2', 'Requerimento de isenção de IPTU para imóvel rural.',
   3, 2, '2026-05-02 14:20:00', 3, 2, true, true, false, true),
  (3, 3, '2026/000003-3', 'Recurso contra multa de obras sem alvará.',
   3, 3, '2026-05-12 10:00:00', 3, 2, true, false, false, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.processo_id_seq1', GREATEST((SELECT MAX(id) FROM protocolos.processo), 3));

-- Movimentações: abertura para os 3
INSERT INTO protocolos.movimentacao
  (id, id_processo, id_unidade_responsavel, id_acao, id_usuario, data_hora_movimentacao, ativo)
VALUES
  (1, 1, 3, 1, 2, '2026-04-15 09:30:00', true),
  (2, 2, 3, 1, 2, '2026-05-02 14:20:00', true),
  (3, 3, 3, 1, 2, '2026-05-12 10:00:00', true),
  -- encaminhamento do processo 1
  (4, 1, 3, 2, 2, '2026-04-16 11:00:00', true),
  -- recebimento do processo 1
  (5, 1, 3, 3, 2, '2026-04-16 14:30:00', true),
  -- despacho do processo 2
  (6, 2, 3, 2, 2, '2026-05-03 09:15:00', true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.movimentacao_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.movimentacao), 6));

-- Atualizar id_ultima_movimentacao do processo
UPDATE protocolos.processo SET id_ultima_movimentacao = 5 WHERE id = 1;
UPDATE protocolos.processo SET id_ultima_movimentacao = 6 WHERE id = 2;
UPDATE protocolos.processo SET id_ultima_movimentacao = 3 WHERE id = 3;

-- Despachos (vinculados às movs 4 e 6)
INSERT INTO protocolos.despacho
  (id, id_processo, despacho, id_usuario, id_movimentacao, ativo)
VALUES
  (1, 1, 'Encaminho para análise da secretaria competente.', 2, 4, true),
  (2, 2, 'Solicito documentação complementar do requerente.',  2, 6, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.despacho_id_seq1', GREATEST((SELECT MAX(id) FROM protocolos.despacho), 2));

-- Encaminhamentos (vinculados às movs 4 e 6)
INSERT INTO protocolos.encaminhamento
  (id, id_processo, id_unidade_origem, id_unidade_destino, id_prioridade,
   quantidade_folhas, data_prazo, recebido, id_usuario, id_movimentacao, ativo)
VALUES
  (1, 1, 3, 3, 1, 5, '2026-04-30', true, 2, 4, true),
  (2, 2, 3, 3, 2, 8, '2026-05-15', false, 2, 6, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.encaminhamento_id_seq1', GREATEST((SELECT MAX(id) FROM protocolos.encaminhamento), 2));

-- Anexos (3 exemplos)
INSERT INTO protocolos.anexo
  (id, id_tipo_anexo, descricao, publico, qtd_paginas, ativo, id_usuario)
VALUES
  (1, 1, 'RG do requerente',                  true,  1, true, 2),
  (2, 2, 'CPF do requerente',                 true,  1, true, 2),
  (3, 4, 'Requerimento assinado',             true,  2, true, 2)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.anexo_id_seq1', GREATEST((SELECT MAX(id) FROM protocolos.anexo), 3));

-- Vínculo anexo↔processo (todos os 3 anexos no processo 1)
INSERT INTO protocolos.anexo_processo
  (id, id_processo, id_anexo, id_movimentacao, id_usuario, ordem, ativo)
VALUES
  (1, 1, 1, 1, 2, 1, true),
  (2, 1, 2, 1, 2, 2, true),
  (3, 1, 3, 1, 2, 3, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.anexo_processo_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.anexo_processo), 3));

COMMIT;

SELECT 'processo' tabela, count(*) FROM protocolos.processo WHERE excluido = false UNION ALL
SELECT 'movimentacao', count(*) FROM protocolos.movimentacao WHERE excluido = false UNION ALL
SELECT 'despacho', count(*) FROM protocolos.despacho WHERE excluido = false UNION ALL
SELECT 'encaminhamento', count(*) FROM protocolos.encaminhamento WHERE excluido = false UNION ALL
SELECT 'anexo_processo', count(*) FROM protocolos.anexo_processo WHERE excluido = false;
