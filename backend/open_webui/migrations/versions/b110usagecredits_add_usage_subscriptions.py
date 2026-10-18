"""ThatAI Chat v1.1 usage, subscriptions, promotions and invitations.

Revision ID: b110usagecredits
Revises: 3781e22d8b01
"""
from alembic import op
import sqlalchemy as sa
import json
import time

revision = "b110usagecredits"
down_revision = "3781e22d8b01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("subscription_tier", sa.Column("id", sa.Text, primary_key=True), sa.Column("name", sa.Text, unique=True, nullable=False), sa.Column("monthly_credits", sa.Float, nullable=False), sa.Column("daily_limit", sa.Float), sa.Column("agent_credits", sa.Float, nullable=False, server_default="0"), sa.Column("price_cents", sa.Integer), sa.Column("currency", sa.Text, nullable=False, server_default="EUR"), sa.Column("planned_price", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("features", sa.JSON), sa.Column("model_rules", sa.JSON), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("created_at", sa.BigInteger, nullable=False), sa.Column("updated_at", sa.BigInteger, nullable=False))
    op.create_table("user_subscription", sa.Column("id", sa.Text, primary_key=True), sa.Column("user_id", sa.Text, nullable=False, index=True), sa.Column("tier_id", sa.Text, nullable=False), sa.Column("status", sa.Text, nullable=False), sa.Column("access_status", sa.Text, nullable=False), sa.Column("billing_status", sa.Text, nullable=False), sa.Column("starts_at", sa.BigInteger, nullable=False), sa.Column("ends_at", sa.BigInteger), sa.Column("created_at", sa.BigInteger, nullable=False), sa.Column("updated_at", sa.BigInteger, nullable=False))
    op.create_table("credit_ledger", sa.Column("id", sa.Text, primary_key=True), sa.Column("user_id", sa.Text, nullable=False, index=True), sa.Column("kind", sa.Text, nullable=False), sa.Column("bucket", sa.Text, nullable=False), sa.Column("amount", sa.Float, nullable=False), sa.Column("balance_after", sa.Float), sa.Column("request_id", sa.Text, unique=True), sa.Column("model_id", sa.Text), sa.Column("input_tokens", sa.BigInteger), sa.Column("output_tokens", sa.BigInteger), sa.Column("metadata", sa.JSON), sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_table("usage_record", sa.Column("id", sa.Text, primary_key=True), sa.Column("user_id", sa.Text, nullable=False, index=True), sa.Column("model_id", sa.Text, nullable=False), sa.Column("input_tokens", sa.BigInteger, nullable=False), sa.Column("output_tokens", sa.BigInteger, nullable=False), sa.Column("credits", sa.Float, nullable=False), sa.Column("request_id", sa.Text, unique=True, nullable=False), sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_table("model_credit_rate", sa.Column("model_id", sa.Text, primary_key=True), sa.Column("credits_per_50k", sa.Float, nullable=False), sa.Column("fair_use", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("stream_usage_supported", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("updated_at", sa.BigInteger, nullable=False))
    op.create_table("coupon", sa.Column("id", sa.Text, primary_key=True), sa.Column("code", sa.Text, unique=True, nullable=False), sa.Column("tier_id", sa.Text), sa.Column("free_days", sa.Integer, nullable=False, server_default="0"), sa.Column("percent_off", sa.Float), sa.Column("amount_off_cents", sa.Integer), sa.Column("bonus_credits", sa.Float, nullable=False, server_default="0"), sa.Column("starts_at", sa.BigInteger), sa.Column("expires_at", sa.BigInteger), sa.Column("max_redemptions", sa.Integer), sa.Column("max_per_user", sa.Integer, nullable=False, server_default="1"), sa.Column("eligible_groups", sa.JSON), sa.Column("combinable", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("apply_after_current", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_table("coupon_redemption", sa.Column("id", sa.Text, primary_key=True), sa.Column("coupon_id", sa.Text, nullable=False), sa.Column("user_id", sa.Text, nullable=False), sa.Column("subscription_id", sa.Text), sa.Column("created_at", sa.BigInteger, nullable=False), sa.UniqueConstraint("coupon_id", "user_id", "id", name="uq_coupon_user_redemption"))
    op.create_table("invite_code", sa.Column("id", sa.Text, primary_key=True), sa.Column("code", sa.Text, unique=True, nullable=False), sa.Column("creator_id", sa.Text), sa.Column("max_uses", sa.Integer, nullable=False, server_default="1"), sa.Column("uses", sa.Integer, nullable=False, server_default="0"), sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("is_referral", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_table("invite_redemption", sa.Column("id", sa.Text, primary_key=True), sa.Column("invite_id", sa.Text, nullable=False), sa.Column("user_id", sa.Text, unique=True, nullable=False), sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_table("usage_setting", sa.Column("key", sa.Text, primary_key=True), sa.Column("value", sa.JSON, nullable=False), sa.Column("updated_at", sa.BigInteger, nullable=False))
    # One short-lived row per metered user prevents concurrent billable calls
    # from racing between preflight and provider-reported final usage.
    op.create_table("credit_reservation", sa.Column("user_id", sa.Text, primary_key=True), sa.Column("request_id", sa.Text, unique=True, nullable=False), sa.Column("expires_at", sa.BigInteger, nullable=False))
    created_at = int(time.time())
    tiers = sa.table("subscription_tier", sa.column("id", sa.Text), sa.column("name", sa.Text), sa.column("monthly_credits", sa.Float), sa.column("daily_limit", sa.Float), sa.column("agent_credits", sa.Float), sa.column("price_cents", sa.Integer), sa.column("currency", sa.Text), sa.column("planned_price", sa.Boolean), sa.column("features", sa.JSON), sa.column("model_rules", sa.JSON), sa.column("active", sa.Boolean), sa.column("created_at", sa.BigInteger), sa.column("updated_at", sa.BigInteger))
    op.bulk_insert(tiers, [
        {"id":"free","name":"Free","monthly_credits":100,"daily_limit":20,"agent_credits":0,"price_cents":None,"currency":"EUR","planned_price":True,"features":{},"model_rules":{"mini":True,"standard":True,"pro":False},"active":True,"created_at":created_at,"updated_at":created_at},
        {"id":"plus","name":"Plus","monthly_credits":1000,"daily_limit":None,"agent_credits":0,"price_cents":499,"currency":"EUR","planned_price":True,"features":{},"model_rules":{"mini":True,"standard":True,"pro":True,"code":True,"design":True},"active":True,"created_at":created_at,"updated_at":created_at},
        {"id":"pro","name":"Pro","monthly_credits":5000,"daily_limit":None,"agent_credits":1000,"price_cents":999,"currency":"EUR","planned_price":True,"features":{},"model_rules":{"mini":True,"standard":True,"pro":True,"agents":True,"api_pass":True},"active":True,"created_at":created_at,"updated_at":created_at},
    ])
    # Store rates against the actual configured model primary key, never its
    # human-facing name. Deployments without these model records configure IDs
    # through the admin API before enabling metering.
    for name, rate, fair in (("ThatAI Mini", 0, 1), ("ThatAI Standard", 1, 0), ("ThatAI Pro", 4, 0)):
        op.execute(sa.text("INSERT INTO model_credit_rate (model_id,credits_per_50k,fair_use,enabled,stream_usage_supported,updated_at) SELECT id,:rate,:fair,1,0,:updated_at FROM model WHERE name=:name").bindparams(name=name, rate=rate, fair=fair, updated_at=created_at))

def downgrade():
    # Deliberately destructive; restore a pre-v1.1 backup instead of downgrading production.
    for name in ("credit_reservation", "usage_setting", "invite_redemption", "invite_code", "coupon_redemption", "coupon", "model_credit_rate", "usage_record", "credit_ledger", "user_subscription", "subscription_tier"):
        op.drop_table(name)
