# Usage, Credits, Subscriptions and Invites (v1.1)

The `b110usagecredits` Alembic migration is additive and creates: `subscription_tier`,
`user_subscription`, `credit_ledger`, `usage_record`, `model_credit_rate`, `coupon`,
`coupon_redemption`, `invite_code`, `invite_redemption`, `usage_setting`, and
`credit_reservation`. It does not
modify users, authentication, conversations, uploads, models, configuration, or the native
maintenance mode. As with all database migrations, downgrading deletes v1.1 data; restore a
backup made before migration instead of running a production downgrade.

Tiers, model rates, manual assignments, ledger adjustments, coupons, invitations and platform
usage are protected admin endpoints below `/api/v1/usage/admin`. Tiers are bootstrapped as Free,
Plus and Pro on first usage. Prices are deliberately labelled `planned_price`; there is no payment
processor, payment-detail collection, or automatic charge in Closed Beta.

Credit debits use provider-reported `prompt_tokens` and `completion_tokens`, with fractional
credits (`tokens * rate / 50000`). The ledger operation uses a DB transaction (`BEGIN IMMEDIATE`
on SQLite), an idempotency request id, balances and daily-limit validation. A provider path which
does not return token metadata is never estimated. Closed Beta streaming is fail-closed: rates
are keyed by the **actual configured model ID**, not its display name, and
`stream_usage_supported` defaults to false. Metered streaming is rejected until an administrator
has verified final provider usage and enables that flag. Enabled metered streams are buffered
until final factual usage is charged; a provider that omits usage returns no model output.

Use `POST /api/v1/usage/admin/invitations/enabled?enabled=true` as an administrator to require
an invitation code during normal signup. Create codes with `POST /api/v1/usage/admin/invites`.
The signup form accepts an optional code and beta invitations never create Plus rewards. Referral
codes are represented separately (`is_referral`) and are intentionally not enabled by this Closed
Beta implementation; enablement must be added alongside a public-launch abuse policy.

Before deploying: take a tested SQLite/database backup, apply the normal application migration
at startup, then build with `docker build -t thatai-chat:1.1.0 .`. Do not run a v1.0 image against
the migrated database. Restore by stopping application writes and restoring the pre-migration
database backup; uploaded files and database backups must be kept together.
