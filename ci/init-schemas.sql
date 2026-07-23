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
