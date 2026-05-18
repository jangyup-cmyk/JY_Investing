"""/api/health 엔드포인트 단위 테스트

KIS API 호출 없음 검증, 200/503 분기 검증, 민감정보 미노출 검증.
"""
import json
import time
import pytest

import dashboard
import position_tracker


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    pf = tmp_path / "positions.json"
    cf = tmp_path / "closed_positions.json"
    bdir = tmp_path / "backups"
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))
    monkeypatch.setattr(position_tracker, "CLOSED_POSITIONS_FILE", str(cf))
    monkeypatch.setattr(position_tracker, "BACKUP_DIR", str(bdir))
    monkeypatch.setattr(position_tracker, "_safe_admin_alert", lambda *a, **k: None)
    # kis_api token cache 비우기
    import kis_api
    monkeypatch.setattr(kis_api, "_token_cache", {})
    return pf, cf


@pytest.fixture
def client():
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c


# ─── 기본 응답 형식 ──────────────────────────────────────────────────────────

def test_health_returns_required_fields(client):
    res = client.get("/api/health")
    body = res.get_json()
    assert "status" in body
    assert "checks" in body
    assert "timestamp" in body
    assert body["status"] in {"healthy", "degraded", "unhealthy"}

    checks = body["checks"]
    expected = {
        "scheduler_running", "kis_tokens", "positions_json_valid",
        "positions_open_count", "closed_positions_count",
        "last_log_age_sec", "telegram_listener_alive", "naver_research_alive",
    }
    assert expected.issubset(checks.keys())


# ─── 200 vs 503 분기 ─────────────────────────────────────────────────────────

def test_corrupt_positions_returns_503(client, isolated_state):
    pf, _ = isolated_state
    pf.write_text("{ totally broken", encoding="utf-8")
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.get_json()["status"] == "unhealthy"
    assert res.get_json()["checks"]["positions_json_valid"] is False


def test_valid_state_with_running_scheduler_returns_200(client, monkeypatch):
    # scheduler/log 체크가 'healthy' 신호를 내도록 monkeypatch
    monkeypatch.setattr(dashboard, "_is_scheduler_running", lambda: True)
    monkeypatch.setattr(dashboard, "_check_last_log_age_sec", lambda: 10)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "healthy"


def test_expired_kis_token_returns_503_degraded(client, monkeypatch):
    monkeypatch.setattr(dashboard, "_is_scheduler_running", lambda: True)
    monkeypatch.setattr(dashboard, "_check_last_log_age_sec", lambda: 10)
    # 만료된 토큰 캐시 주입
    import kis_api
    monkeypatch.setattr(kis_api, "_token_cache", {
        "73918950": {"token": "abc", "expire_time": time.time() - 100},
    })
    res = client.get("/api/health")
    assert res.status_code == 503
    body = res.get_json()
    assert body["status"] == "degraded"
    assert "kis_token_expired" in body["checks"]["degraded_reasons"]


def test_stale_logs_marked_degraded(client, monkeypatch):
    monkeypatch.setattr(dashboard, "_is_scheduler_running", lambda: True)
    monkeypatch.setattr(dashboard, "_check_last_log_age_sec", lambda: 600)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert "logs_stale" in res.get_json()["checks"]["degraded_reasons"]


# ─── 보안: 민감 정보 노출 금지 ──────────────────────────────────────────────

def test_account_numbers_are_masked(client, monkeypatch):
    import kis_api
    monkeypatch.setattr(kis_api, "_token_cache", {
        "73918950": {"token": "SUPER-SECRET-TOKEN-VALUE", "expire_time": time.time() + 3600},
    })
    res = client.get("/api/health")
    raw = res.get_data(as_text=True)
    # 원본 계좌번호 노출 금지
    assert "73918950" not in raw
    # 마스킹된 형태는 포함
    body = res.get_json()
    token_keys = list(body["checks"]["kis_tokens"].keys())
    assert any(k.endswith("8950") and "*" in k for k in token_keys)


def test_token_value_never_appears_in_response(client, monkeypatch):
    import kis_api
    monkeypatch.setattr(kis_api, "_token_cache", {
        "12345678": {"token": "SHOULD-NOT-APPEAR", "expire_time": time.time() + 3600},
    })
    res = client.get("/api/health")
    raw = res.get_data(as_text=True)
    assert "SHOULD-NOT-APPEAR" not in raw


# ─── KIS API 미호출 검증 ─────────────────────────────────────────────────────

def test_health_does_not_call_kis_api(client, monkeypatch):
    """health 라우트는 KIS API 를 호출하지 않아야 한다 (캐시만 조회)."""
    from unittest.mock import patch
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        res = client.get("/api/health")
    assert res.status_code in (200, 503)
    mock_get.assert_not_called()
    mock_post.assert_not_called()


# ─── 성능 ────────────────────────────────────────────────────────────────────

def test_health_responds_under_500ms(client):
    start = time.monotonic()
    res = client.get("/api/health")
    elapsed = time.monotonic() - start
    assert res.status_code in (200, 503)
    assert elapsed < 0.5, f"health 응답이 너무 느림: {elapsed:.3f}s"


# ─── 견고성: 내부 오류여도 503 + JSON 응답 ─────────────────────────────────

def test_health_returns_503_json_on_internal_error(client, monkeypatch):
    def boom():
        raise RuntimeError("kaboom")
    monkeypatch.setattr(dashboard, "_check_positions_file_valid", boom)
    res = client.get("/api/health")
    assert res.status_code == 503
    body = res.get_json()
    assert body["status"] == "unhealthy"
