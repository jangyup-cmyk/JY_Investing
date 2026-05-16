import scheduler


def test_resolve_stock_codes_uses_input_first():
    result = scheduler.resolve_stock_codes(["005930", "000660"])
    assert result == ["005930", "000660"]


def test_run_signal_pipeline_simulate_only():
    result = scheduler.run_signal_pipeline(stock_codes=["005930"], simulate_only=True)
    assert result["simulated"] is True
    assert result["processed"] == 1
    assert result["stock_codes"] == ["005930"]


def test_resolve_weighted_codes_from_channel_report():
    result = scheduler._resolve_weighted_codes_from_channel_report()
    assert isinstance(result, list)
    assert len(result) >= 1

