-- Seed mínimo para Fase 2 (cadastros simples) em desenvolvimento
BEGIN;

-- Estados (apenas 3 para teste)
INSERT INTO utils.estado (id, estado, uf, id_regiao) VALUES
  (1, 'Ceará', 'CE', NULL),
  (2, 'São Paulo', 'SP', NULL),
  (3, 'Distrito Federal', 'DF', NULL)
ON CONFLICT (id) DO NOTHING;
SELECT setval('utils.estado_id_seq', GREATEST((SELECT MAX(id) FROM utils.estado), 3));

-- Cidades
INSERT INTO utils.cidade (id, cidade, id_estado) VALUES
  (1, 'Sobral', 1),
  (2, 'Fortaleza', 1),
  (3, 'São Paulo', 2)
ON CONFLICT (id) DO NOTHING;
SELECT setval('utils.cidade_id_seq', GREATEST((SELECT MAX(id) FROM utils.cidade), 3));

-- Bairros (de Sobral)
INSERT INTO utils.bairro (id, id_cidade, bairro, ativo) VALUES
  (1, 1, 'Centro', true),
  (2, 1, 'Junco', true),
  (3, 1, 'Dom Expedito', true),
  (4, 2, 'Aldeota', true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('utils.bairro_id_seq', GREATEST((SELECT MAX(id) FROM utils.bairro), 4));

-- Tipo de processo
INSERT INTO protocolos.tipo_processo (id, tipo_processo, exige_processo_pai, ativo) VALUES
  (1, 'Processo Administrativo', false, true),
  (2, 'Processo Apensado', true, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.tipo_processo_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.tipo_processo), 2));

-- Assuntos
INSERT INTO protocolos.assunto (id, assunto, id_tipo_processo, exige_processo_pai, ativo) VALUES
  (1, 'Solicitação de informação', 1, false, true),
  (2, 'Requerimento geral', 1, false, true),
  (3, 'Recurso administrativo', 1, false, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.assunto_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.assunto), 3));

-- Tipos de anexo
INSERT INTO protocolos.tipo_anexo (id, tipo_anexo) VALUES
  (1, 'RG'),
  (2, 'CPF'),
  (3, 'Comprovante de residência'),
  (4, 'Requerimento')
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.tipo_anexo_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.tipo_anexo), 4));

-- Tipo manifestante
INSERT INTO protocolos.tipo_manifestante (id, tipo_manifestante, id_categoria, ativo) VALUES
  (1, 'Pessoa Física', 1, true),
  (2, 'Pessoa Jurídica', 2, true)
ON CONFLICT (id) DO NOTHING;
SELECT setval('protocolos.tipo_manifestante_id_seq', GREATEST((SELECT MAX(id) FROM protocolos.tipo_manifestante), 2));

COMMIT;

SELECT 'estado' tabela, count(*) FROM utils.estado UNION ALL
SELECT 'cidade', count(*) FROM utils.cidade UNION ALL
SELECT 'bairro', count(*) FROM utils.bairro UNION ALL
SELECT 'tipo_processo', count(*) FROM protocolos.tipo_processo UNION ALL
SELECT 'assunto', count(*) FROM protocolos.assunto UNION ALL
SELECT 'tipo_anexo', count(*) FROM protocolos.tipo_anexo UNION ALL
SELECT 'tipo_manifestante', count(*) FROM protocolos.tipo_manifestante;
