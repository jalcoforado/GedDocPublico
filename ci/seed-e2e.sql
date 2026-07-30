-- Seed E2E da Assinatura v2 — tenant-aware, idempotente, ids fixos.
--
-- USO EXCLUSIVO DE TESTE/E2E. O hash bcrypt do admin abaixo é FIXO e público
-- (senha 'admin123') — NUNCA usar em produção.
--
-- Pressupõe o schema atual já carregado (ci/legacy-schema.sql + `alembic stamp
-- head`). Cria apenas os PRÉ-REQUISITOS ESTÁTICOS; a spec e2e cria
-- processo/anexo/solicitação dinamicamente via API.
--
-- Carregado por: .github/workflows/e2e-assinatura.yml e scripts/seed-e2e.{sh,ps1}.
-- Ids fixos batem com tests-e2e/specs/assinatura-v2.spec.ts
-- (manifestante=1, assunto=1, unidade=3, especie=2, tenant=1).
BEGIN;

-- Desabilita triggers legados do PHP durante o seed (ex.: trigger em
-- utils.sistema que escreve em sistema_chamados.*, auditorias). PK/UNIQUE/CHECK
-- continuam valendo; só triggers (inclusive de FK) são suspensos nesta sessão.
SET session_replication_role = replica;

-- === Permissões base (globais) ============================================
INSERT INTO utils.nivel (id, nivel, valor, excluido)
  VALUES (3, 'Super Usuário', 0, false) ON CONFLICT (id) DO NOTHING;
INSERT INTO utils.sistema (id, sistema, app, url, excluido)
  VALUES (3, 'Aprimora Local', 'sistemas', '', false) ON CONFLICT (id) DO NOTHING;

-- === Tenant Sobral (NUP federal habilitado) ===============================
INSERT INTO aprimora_py.tenant
  (id, slug, nome, ativo, plano, usar_nup_federal, codigo_orgao_nup, criado_em)
  VALUES (1, 'sobral', 'Prefeitura Municipal de Sobral', true, 'basico',
          true, '99001', NOW())
  ON CONFLICT (id) DO NOTHING;

-- === Unidade ===============================================================
INSERT INTO utils.tipo_unidade_trabalho (id, tipo_unidade_trabalho, excluido, tenant_id)
  VALUES (3, 'Unidade Local', false, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO utils.unidade_trabalho
  (id, unidade_trabalho, sigla, id_tipo_unidade_trabalho, excluido, tenant_id)
  VALUES (3, 'Prefeitura Municipal de Sobral', 'PMS', 3, false, 1)
  ON CONFLICT (id) DO NOTHING;

-- === Super-usuário admin (senha 'admin123' — bcrypt FIXO de teste) ========
INSERT INTO utils.usuario
  (id, tenant_id, nome, email, cpf, senha, senha_bcrypt, id_unidade_trabalho, ativo, excluido)
  VALUES (2, 1, 'Usuário Local', 'admin@local.test', '12345678901',
          '0192023a7bbd73250516f069df18b500',
          '$2b$12$qrrZFXHngrtwHvtXckfjy..79ZlmhvSP5N1PX/PbzWNYojWl9Zf0i',
          3, true, false)
  ON CONFLICT (id) DO NOTHING;

-- Grupo nível 0 (Super Usuário) + vínculo → load_permissions.is_super_usuario
INSERT INTO utils.grupo (id, tenant_id, id_nivel, id_sistema, grupo, excluido)
  VALUES (2, 1, 3, 3, 'Administradores', false) ON CONFLICT (id) DO NOTHING;
INSERT INTO utils.usuario_grupo (id, id_usuario, id_grupo, ativo, excluido, app, tenant_id)
  VALUES (2, 2, 2, true, false, 'sistemas', 1) ON CONFLICT (id) DO NOTHING;

-- === Catálogos de protocolo ===============================================
INSERT INTO protocolos.categoria (id, categoria, tipo, ativo, excluido)
  VALUES (1, 'Pessoa Física', 'PF', true, false) ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.tipo_manifestante (id, tipo_manifestante, id_categoria, ativo, excluido, tenant_id)
  VALUES (1, 'Pessoa Física', 1, true, false, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.manifestante
  (id, id_tipo_manifestante, nome, cpf_cnpj, email, ativo, excluido, tenant_id)
  VALUES (1, 1, 'José da Silva', '11122233344', 'jose@example.com', true, false, 1)
  ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.tipo_processo (id, tipo_processo, exige_processo_pai, ativo, excluido, tenant_id)
  VALUES (1, 'Processo Administrativo', false, true, false, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.assunto
  (id, assunto, id_tipo_processo, exige_processo_pai, ativo, excluido, tenant_id)
  VALUES (1, 'Solicitação de informação', 1, false, true, false, 1)
  ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.especie_documental (id, tenant_id, flag, nome, ativo, excluido, criado_em)
  VALUES (2, 1, 'REQUERIMENTO', 'Requerimento', true, false, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO protocolos.acao
  (id, flag, acao, status_acao, status_movimentacao, texto_acao, ativo, excluido)
  VALUES (1, 'ABERTURA', 'Abertura', 'aberto', 'inicial', 'Processo aberto', true, false)
  ON CONFLICT (id) DO NOTHING;

-- === Contratação de módulos (fatia F1 da modularização) ====================
-- A 0073 faz backfill "para todos os tenants existentes", mas em banco limpo
-- ela roda ANTES deste arquivo — não há tenant para contratar. Sem as linhas
-- abaixo o tenant sobe com zero módulos e o gate de contratação nega 22
-- códigos de transação para TODO MUNDO, inclusive super-usuário: o gate roda
-- antes do bypass de SU, de propósito.
--
-- Fora do CI quem garante isso é o `seed_bootstrap`. Aqui é obrigatório porque
-- o `e2e-assinatura.yml` NÃO roda o seed_bootstrap — só `upgrade head`, este
-- arquivo e o uvicorn. Este é o único ponto que cobre os dois workflows.
--
-- `comum` fica de fora porque não é contratável: está sempre disponível e
-- nunca é bloqueado.
INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo)
SELECT t.id, m.id
  FROM aprimora_py.tenant t
  CROSS JOIN aprimora_py.modulo m
 WHERE m.contratavel = true AND m.ativo = true
 ON CONFLICT DO NOTHING;

-- === Ajusta sequências para não colidir com os ids fixos ==================
SELECT setval(pg_get_serial_sequence('utils.nivel', 'id'), GREATEST((SELECT MAX(id) FROM utils.nivel), 1));
SELECT setval(pg_get_serial_sequence('utils.sistema', 'id'), GREATEST((SELECT MAX(id) FROM utils.sistema), 1));
SELECT setval(pg_get_serial_sequence('aprimora_py.tenant', 'id'), GREATEST((SELECT MAX(id) FROM aprimora_py.tenant), 1));
SELECT setval(pg_get_serial_sequence('utils.tipo_unidade_trabalho', 'id'), GREATEST((SELECT MAX(id) FROM utils.tipo_unidade_trabalho), 1));
SELECT setval(pg_get_serial_sequence('utils.unidade_trabalho', 'id'), GREATEST((SELECT MAX(id) FROM utils.unidade_trabalho), 1));
SELECT setval(pg_get_serial_sequence('utils.usuario', 'id'), GREATEST((SELECT MAX(id) FROM utils.usuario), 1));
SELECT setval(pg_get_serial_sequence('utils.grupo', 'id'), GREATEST((SELECT MAX(id) FROM utils.grupo), 1));
SELECT setval(pg_get_serial_sequence('utils.usuario_grupo', 'id'), GREATEST((SELECT MAX(id) FROM utils.usuario_grupo), 1));
SELECT setval(pg_get_serial_sequence('protocolos.categoria', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.categoria), 1));
SELECT setval(pg_get_serial_sequence('protocolos.tipo_manifestante', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.tipo_manifestante), 1));
SELECT setval(pg_get_serial_sequence('protocolos.manifestante', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.manifestante), 1));
SELECT setval(pg_get_serial_sequence('protocolos.tipo_processo', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.tipo_processo), 1));
SELECT setval(pg_get_serial_sequence('protocolos.assunto', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.assunto), 1));
SELECT setval(pg_get_serial_sequence('protocolos.especie_documental', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.especie_documental), 1));
SELECT setval(pg_get_serial_sequence('protocolos.acao', 'id'), GREATEST((SELECT MAX(id) FROM protocolos.acao), 1));

SET session_replication_role = DEFAULT;
COMMIT;
