"""Alembic env — sincrono via psycopg2.

Decisões:
- `target_metadata = None`: NÃO usamos autogenerate. As únicas mudanças que
  versionamos são aquelas escritas manualmente — porque o `Base.metadata` do
  app referencia tabelas legadas (utils.usuario, protocolos.processo, ...) que
  pertencem ao PHP e o Alembic autogenerate iria querer dropar colunas que o
  Python não mapeia.
- `version_table_schema = 'aprimora_py'`: tabela `alembic_version` mora no
  schema do Python pra isolamento (cria-se via DDL em env.py antes do Alembic
  tentar criar a tabela de versão).
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

target_metadata = None

VERSION_TABLE_SCHEMA = "aprimora_py"


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{VERSION_TABLE_SCHEMA}"'))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=VERSION_TABLE_SCHEMA,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
