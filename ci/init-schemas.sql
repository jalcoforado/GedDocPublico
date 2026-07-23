-- Initialize minimal schemas and types needed before Alembic migrations
-- This avoids conflicts with aprimora_py tables created by Alembic

-- Create schemas if they don't exist
CREATE SCHEMA IF NOT EXISTS utils;
CREATE SCHEMA IF NOT EXISTS protocolos;
CREATE SCHEMA IF NOT EXISTS aprimora_py;

-- Create enum types for utils schema
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'origem') THEN
    CREATE TYPE utils.origem AS ENUM ('acl', 'agendasol', 'extra');
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipo_pessoa') THEN
    CREATE TYPE utils.tipo_pessoa AS ENUM ('f', 'j');
  END IF;
END
$$;

-- Create stub for utils.usuario table (referenced by FK from aprimora_py.job)
-- Real structure comes from legacy PHP system or local database
CREATE TABLE IF NOT EXISTS utils.usuario (
  id INTEGER PRIMARY KEY,
  login VARCHAR(255),
  nome VARCHAR(500),
  email VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Create stub for utils.unidade_trabalho (if referenced)
CREATE TABLE IF NOT EXISTS utils.unidade_trabalho (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Create stub for utils.usuario_externo (if referenced)
CREATE TABLE IF NOT EXISTS utils.usuario_externo (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(500),
  email VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);
