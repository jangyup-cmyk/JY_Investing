import theme_extractor


def test_load_texts_grouped_by_subdir():
    grouped = theme_extractor.load_texts_grouped_by_subdir("etc/telegram_texts")
    assert "channel_alpha" in grouped
    assert "channel_beta" in grouped
    assert len(grouped["channel_alpha"]) >= 1
    assert len(grouped["channel_beta"]) >= 1

