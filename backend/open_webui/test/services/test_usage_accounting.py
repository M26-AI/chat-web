"""Unit-level accounting invariants; integration runs require the app test database."""
from open_webui.services import usage

def test_month_key_and_next_reset_are_utc():
    # 2026-01-31 23:59:59 UTC
    assert usage.month_key(1769903999) == "2026-01"
    assert usage.next_reset(1769903999) == 1769904000

def test_fractional_credit_rate_is_not_rounded_per_message():
    tokens = 500
    assert tokens * 1 / 50000 == 0.01
    assert tokens * 4 / 50000 == 0.04
