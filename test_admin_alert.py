"""telegram_bot.send_admin_alert 단위 테스트

requests.post 를 mock 해서 실제 Telegram 호출 없이 검증.
_now() monkeypatch 로 dedup 시간 윈도우를 결정론적으로 시뮬레이션.
"""
from unittest.mock import MagicMock, patch

import pytest

import telegram_bot


@pytest.fixture(autouse=True)
def reset_dedup_state(monkeypatch):
    """각 테스트마다 dedup 캐시 초기화 + 결정론적 시계."""
    telegram_bot._admin_dedup_cache.clear()
    # 시계 — 테스트가 setter 호출해서 진행시킴
    state = {"t": 1000.0}
    monkeypatch.setattr(telegram_bot, "_now", lambda: state["t"])
    return state


def _make_success_response():
    res = MagicMock()
    res.status_code = 200
    res.json.return_value = {"ok": True, "result": {"message_id": 42}}
    return res


# ─── 기본 동작 ───────────────────────────────────────────────────────────────

def test_alert_calls_telegram_api_with_admin_credentials():
    with patch("telegram_bot.requests.post", return_value=_make_success_response()) as mock_post:
        result = telegram_bot.send_admin_alert("critical", "테스트 제목", "테스트 본문")

    assert result.get("ok") is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    # Telegram API URL 형태
    assert "api.telegram.org" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == telegram_bot.config.TELEGRAM_ADMIN_ID
    # 본문에 severity / 제목 / 디테일 / 이모지 포함
    text = payload["text"]
    assert "테스트 제목" in text
    assert "테스트 본문" in text
    assert "CRITICAL" in text
    assert "🚨" in text


def test_alert_with_empty_detail_still_works():
    with patch("telegram_bot.requests.post", return_value=_make_success_response()):
        result = telegram_bot.send_admin_alert("warning", "디테일 없음")
    assert result.get("ok") is True


# ─── 30s dedup ───────────────────────────────────────────────────────────────

def test_dedup_blocks_duplicate_within_window(reset_dedup_state):
    with patch("telegram_bot.requests.post", return_value=_make_success_response()) as mock_post:
        r1 = telegram_bot.send_admin_alert("critical", "X", "Y")
        # 10초 뒤 동일 호출
        reset_dedup_state["t"] += 10.0
        r2 = telegram_bot.send_admin_alert("critical", "X", "Y")

    assert r1.get("ok") is True
    assert r2.get("deduped") is True
    assert mock_post.call_count == 1


def test_dedup_allows_after_window(reset_dedup_state):
    with patch("telegram_bot.requests.post", return_value=_make_success_response()) as mock_post:
        telegram_bot.send_admin_alert("critical", "X", "Y")
        # 31초 뒤 — 윈도우 종료
        reset_dedup_state["t"] += telegram_bot.ADMIN_ALERT_DEDUP_SEC + 1
        r2 = telegram_bot.send_admin_alert("critical", "X", "Y")

    assert r2.get("ok") is True
    assert r2.get("deduped") is not True
    assert mock_post.call_count == 2


def test_dedup_does_not_block_different_keys(reset_dedup_state):
    with patch("telegram_bot.requests.post", return_value=_make_success_response()) as mock_post:
        telegram_bot.send_admin_alert("critical", "제목 A", "디테일")
        telegram_bot.send_admin_alert("critical", "제목 B", "디테일")
        telegram_bot.send_admin_alert("warning",  "제목 A", "디테일")
    # 서로 다른 key 3건 → 3회 호출
    assert mock_post.call_count == 3


# ─── 견고성 (raise 금지) ─────────────────────────────────────────────────────

def test_exception_in_requests_does_not_raise():
    """requests.post 가 예외를 던져도 send_admin_alert 는 raise 하면 안 된다."""
    with patch("telegram_bot.requests.post", side_effect=ConnectionError("network down")):
        # 절대 raise 안 함
        result = telegram_bot.send_admin_alert("critical", "X", "Y")
    assert isinstance(result, dict)
    assert result.get("ok") is False


def test_invalid_severity_falls_back_to_info():
    with patch("telegram_bot.requests.post", return_value=_make_success_response()) as mock_post:
        telegram_bot.send_admin_alert("nonsense_level", "Hi", "There")
    text = mock_post.call_args.kwargs["json"]["text"]
    assert "INFO" in text   # 알 수 없는 severity → info 로 강등
    assert "ℹ️" in text


def test_invalid_args_return_error_without_call():
    with patch("telegram_bot.requests.post") as mock_post:
        r = telegram_bot.send_admin_alert(None, "title")   # type: ignore[arg-type]
    assert r.get("ok") is False
    mock_post.assert_not_called()


# ─── 트리거 지점 통합 (position_tracker 자동복구) ────────────────────────────

def test_auto_recovery_triggers_admin_alert(tmp_path, monkeypatch):
    """positions.json 손상 → _try_restore_from_backups → send_admin_alert 호출."""
    import position_tracker
    pf = tmp_path / "positions.json"
    bdir = tmp_path / "backups"
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))
    monkeypatch.setattr(position_tracker, "BACKUP_DIR", str(bdir))

    captured = []

    def fake_alert(severity, title, detail=""):
        captured.append((severity, title, detail))
        return {"ok": True}

    monkeypatch.setattr(telegram_bot, "send_admin_alert", fake_alert)

    # 유효 백업 생성
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)

    # 손상 → 자동 복구 트리거
    pf.write_text("{ broken", encoding="utf-8")
    recovered = position_tracker.load_all()

    assert isinstance(recovered, dict)
    # 자동복구 알림이 발송됐는지
    assert len(captured) >= 1
    sev, title, _ = captured[0]
    assert sev == "critical"
    assert "복구" in title or "recovery" in title.lower()
