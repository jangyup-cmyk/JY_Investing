from rebalance_channel_weights import _compute_weight


def test_compute_weight_higher_for_better_performance():
    good = _compute_weight(win_rate=0.65, avg_return_pct=4.0, signal_count=20)
    bad = _compute_weight(win_rate=0.45, avg_return_pct=-2.0, signal_count=20)
    assert good > bad


def test_compute_weight_penalizes_small_sample():
    enough_samples = _compute_weight(win_rate=0.55, avg_return_pct=1.0, signal_count=10)
    small_samples = _compute_weight(win_rate=0.55, avg_return_pct=1.0, signal_count=3)
    assert enough_samples > small_samples

