import theme_extractor


def test_load_texts_grouped_by_subdir(tmp_path):
    alpha = tmp_path / "channel_alpha"
    alpha.mkdir()
    (alpha / "msg1.txt").write_text("삼성전자 급등 신호", encoding="utf-8")

    beta = tmp_path / "channel_beta"
    beta.mkdir()
    (beta / "msg1.txt").write_text("sk하이닉스 매수 추천", encoding="utf-8")

    grouped = theme_extractor.load_texts_grouped_by_subdir(str(tmp_path))
    assert "channel_alpha" in grouped
    assert "channel_beta" in grouped
    assert len(grouped["channel_alpha"]) >= 1
    assert len(grouped["channel_beta"]) >= 1

