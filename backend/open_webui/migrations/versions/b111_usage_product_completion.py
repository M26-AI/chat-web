"""Complete the additive v1.1.1 usage product schema.

Revision ID: b111usageproduct
Revises: b110usagecredits
"""
from alembic import op
import sqlalchemy as sa
import time
import secrets

revision = "b111usageproduct"
down_revision = "b110usagecredits"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable additions retain every existing subscription and ledger entry.
    with op.batch_alter_table("model_credit_rate") as batch:
        batch.add_column(sa.Column("input_credits_per_50k", sa.Float, nullable=True))
        batch.add_column(sa.Column("output_credits_per_50k", sa.Float, nullable=True))
    op.create_index("ix_usage_record_user_created", "usage_record", ["user_id", "created_at"])
    op.create_index("ix_invite_creator", "invite_code", ["creator_id"])

    # Backfill one persistent personal code per account.  The retry suffix makes
    # this safe for databases which already happen to contain a generated code.
    bind = op.get_bind()
    timestamp = int(time.time())
    users = bind.execute(sa.text("SELECT id FROM user WHERE id NOT IN (SELECT creator_id FROM invite_code WHERE creator_id IS NOT NULL)")).fetchall()
    for (user_id,) in users:
        for _ in range(8):
            code = "THATAI-" + secrets.token_hex(5).upper()
            try:
                bind.execute(sa.text("INSERT INTO invite_code (id,code,creator_id,max_uses,uses,revoked,is_referral,created_at) VALUES (:id,:code,:user,3,0,0,1,:now)"), {"id": secrets.token_hex(16), "code": code, "user": user_id, "now": timestamp})
                break
            except Exception:
                continue


def downgrade():
    op.drop_index("ix_invite_creator", table_name="invite_code")
    op.drop_index("ix_usage_record_user_created", table_name="usage_record")
    with op.batch_alter_table("model_credit_rate") as batch:
        batch.drop_column("output_credits_per_50k")
        batch.drop_column("input_credits_per_50k")
