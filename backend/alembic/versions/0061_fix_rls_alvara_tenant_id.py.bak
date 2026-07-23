"""Fix RLS policy for alvara table — use app.tenant_id (not app.current_tenant_id)

The alvara RLS policy was using current_setting('app.current_tenant_id') but the
application sets current_setting('app.tenant_id'). This caused RLS to not filter
correctly, allowing cross-tenant data leakage.

This migration updates the alvara_tenant_isolation policy to use the correct
setting name, matching the pattern from all other tables (0006+).

Fixes: 0053_transporte_regulado_alvara.py

Revision ID: 0061
Revises: 0060
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade():
    # Fix alvara RLS policy: use app.tenant_id with NULLIF safety
    op.execute("""
        DROP POLICY IF EXISTS alvara_tenant_isolation ON transporte_regulado.alvara;
    """)

    op.execute("""
        CREATE POLICY alvara_tenant_isolation ON transporte_regulado.alvara
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int);
    """)


def downgrade():
    op.execute("""
        DROP POLICY IF EXISTS alvara_tenant_isolation ON transporte_regulado.alvara;
    """)

    op.execute("""
        CREATE POLICY alvara_tenant_isolation ON transporte_regulado.alvara
        USING (tenant_id = current_setting('app.current_tenant_id')::int)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::int);
    """)
