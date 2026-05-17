import scheduler


def test_resolve_stock_codes_uses_input_first():
    result = scheduler.resolve_stock_codes(["005930", "000660"])
    assert result == ["005930", "000660"]


def test_run_signal_pipeline_simulate_only():
    result = scheduler.run_signal_pipeline(stock_codes=["005930"], simulate_only=True)
    assert result["simulated"] is True
    assert result["processed"] == 1
    assert result["stock_codes"] == ["005930"]


def test_resolve_weighted_codes_from_channel_report(tmp_path, monkeypatch):
    import json
    import config

    report = tmp_path / "channel_report.json"
    report.write_text(json.dumps({
        "channels": {
            "alpha": {"top_code_scores": {"005930": 0.8, "000660": 0.6}},
            "beta":  {"top_code_scores": {"005930": 0.5, "035420": 0.7}},
        }
    }), encoding="utf-8")

    monkeypatch.setattr(config, "CHANNEL_COMPARISON_REPORT_PATH", str(report))
    monkeypatch.setattr(config, "CHANNEL_WEIGHTS_FILE", str(tmp_path / "no_weights.json"))
    monkeypatch.setattr(config, "CHANNEL_WEIGHTED_TOP_N", 5)

    result = scheduler._resolve_weighted_codes_from_channel_report()
    assert isinstance(result, list)
    assert len(result) >= 1

