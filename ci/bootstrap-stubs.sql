-- Pré-requisitos cross-schema para carregar ci/legacy-schema.sql.
-- O dump referencia objetos fora de utils/protocolos/aprimora_py.
-- Idempotente (IF NOT EXISTS / CREATE OR REPLACE).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE OR REPLACE FUNCTION public.trigger_set_timestamp()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE SCHEMA IF NOT EXISTS despesas;
CREATE TABLE IF NOT EXISTS despesas.feempliq (id integer PRIMARY KEY);

CREATE SCHEMA IF NOT EXISTS empresasimples;
CREATE TABLE IF NOT EXISTS empresasimples.cnae_subgrupos (id integer PRIMARY KEY);

CREATE SCHEMA IF NOT EXISTS agendamento;
CREATE TABLE IF NOT EXISTS agendamento.servico_informacao
  (id integer PRIMARY KEY, url varchar, label varchar, id_servico integer);
CREATE TABLE IF NOT EXISTS agendamento.servico_unidade_trabalho (id_servico integer);

-- O trigger legado utils.copia_sistemas_tipochamados() (presente no dump)
-- insere aqui ao inserir em utils.sistema — sem o stub o seed falha.
CREATE SCHEMA IF NOT EXISTS sistema_chamados;
CREATE TABLE IF NOT EXISTS sistema_chamados.tipo_chamado
  (id serial PRIMARY KEY, tipo varchar, permissao_acesso varchar, id_setor integer);
