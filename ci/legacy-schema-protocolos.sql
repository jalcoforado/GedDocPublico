-- Extract from legacy-schema.sql: only protocolos and utils schemas
-- Alembic handles aprimora_py tables independently

-- Source: legacy-schema.sql (PHP legacy system)
-- Contains schemas, types, functions, and protocolos/utils tables
-- Everything before aprimora_py tables

-- Setup
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET row_security = off;

-- Schemas
CREATE SCHEMA IF NOT EXISTS utils;
CREATE SCHEMA IF NOT EXISTS protocolos;

-- Enums
CREATE TYPE IF NOT EXISTS utils.origem AS ENUM ('acl', 'agendasol', 'extra');
CREATE TYPE IF NOT EXISTS utils.tipo_pessoa AS ENUM ('f', 'j');

-- Note: For full functionality, load the complete legacy-schema.sql
-- This file is a minimal stub to satisfy migration dependencies.
-- In production, load full legacy PHP schema from backup or migration.

-- Stub tables for utils (referenced by migrations)
CREATE TABLE IF NOT EXISTS utils.usuario (
  id INTEGER PRIMARY KEY,
  login VARCHAR(255),
  nome VARCHAR(500),
  email VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS utils.cidade (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(255),
  uf VARCHAR(2),
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS utils.grupo (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS utils.unidade_trabalho (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS utils.usuario_externo (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(500),
  email VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Protocolos stub tables (for ALTER TABLE statements in migrations)
CREATE TABLE IF NOT EXISTS protocolos.tipo_manifestante (
  id INTEGER PRIMARY KEY,
  nome VARCHAR(255),
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Grant permissions
GRANT USAGE ON SCHEMA utils TO ged_user;
GRANT USAGE ON SCHEMA protocolos TO ged_user;
GRANT ALL ON ALL TABLES IN SCHEMA utils TO ged_user;
GRANT ALL ON ALL TABLES IN SCHEMA protocolos TO ged_user;
