import pytest

from investigator.budget import BudgetExceeded, Usage, UsageLedger


def test_usage_from_langchain_metadata_separates_cache():
    u = Usage.from_metadata({"input_tokens": 1000, "output_tokens": 50,
                             "input_token_details": {"cache_read": 800, "cache_creation": 0}})
    assert (u.input_tokens, u.cache_read_tokens, u.output_tokens) == (200, 800, 50)


def test_cost_uses_configured_prices(settings):
    u = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert u.cost_usd(settings) == pytest.approx(0.10 + 0.50)


def test_thread_token_budget(settings, tmp_path):
    settings.investigation_token_budget = 100
    ledger = UsageLedger(tmp_path / "u.sqlite", settings)
    ledger.ensure_within_budget("t")
    ledger.record("t", "step", Usage(input_tokens=150))
    with pytest.raises(BudgetExceeded, match="token budget"):
        ledger.ensure_within_budget("t")
    ledger.ensure_within_budget("other-thread")  # other investigations are unaffected


def test_monthly_budget(settings, tmp_path):
    settings.monthly_budget_usd = 0.05
    ledger = UsageLedger(tmp_path / "u.sqlite", settings)
    ledger.record("a", "step", Usage(output_tokens=200_000))  # $0.10
    with pytest.raises(BudgetExceeded, match="Monthly"):
        ledger.ensure_within_budget("b")
