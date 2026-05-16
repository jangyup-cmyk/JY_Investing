import theme_extractor


def test_extract_signal_from_text_with_alias_and_theme():
    text = "삼전 AI 반도체 모멘텀 강세"
    signal = theme_extractor.extract_signal_from_text(text)

    assert "005930" in signal["codes"]
    assert "ai" in signal["themes"] or "반도체" in signal["themes"]
    assert signal["confidence"] > 0


def test_extract_from_texts_returns_recommended_codes():
    texts = [
        "삼성전자 AI 반도체 수혜 기대",
        "하이닉스 HBM 메모리 대장",
    ]
    result = theme_extractor.extract_from_texts(texts, min_score=1.0)

    assert "005930" in result["recommended_codes"]
    assert "000660" in result["recommended_codes"]

