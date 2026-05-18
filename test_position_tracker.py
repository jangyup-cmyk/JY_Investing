"""position_tracker.py 단위 테스트

tmp_path + monkeypatch 로 POSITION_FILE 경로를 격리해
실제 positions.json 을 건드리지 않습니다.
"""
import json
import pytest
import position_tracker


@pytest.fixture(autouse=True)
def isolated_pos_file(tmp_path, monkeypatch):
    pf = tmp_path / "positions.json"
    bdir = tmp_path / "backups"
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))
    monkeypatch.setattr(position_tracker, "BACKUP_DIR", str(bdir))
    # 관리자 알림은 no-op으로 차단 (실제 Telegram 호출 방지)
    monkeypatch.setattr(position_tracker, "_safe_admin_alert", lambda *a, **k: None)
    return pf


# ─── add_position ────────────────────────────────────────────────────────────

def test_add_position_creates_entry():
    position_tracker.add_position(
        account_no="99999999",
        stock_code="005930",
        buy_price=70000.0,
        qty=10,
        stop_loss=65000.0,
        take_profit=80000.0,
        stock_name="삼성전자",
    )
    positions = position_tracker.load_all()
    assert "99999999_005930" in positions


def test_add_position_key_format():
    position_tracker.add_position("11111111", "000660", 120000, 5, 110000, 140000)
    key = "11111111_000660"
    p = position_tracker.load_all()[key]
    assert p["account_no"] == "11111111"
    assert p["stock_code"] == "000660"
    assert p["status"] == "open"


def test_add_position_rounds_levels():
    position_tracker.add_position("11111111", "005930", 70000.0, 1, 65432.123, 79876.789)
    p = position_tracker.load_all()["11111111_005930"]
    assert p["stop_loss"] == round(65432.123, 0)
    assert p["take_profit"] == round(79876.789, 0)


def test_add_position_default_buy_date():
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    position_tracker.add_position("11111111", "005930", 70000, 1, 65000, 80000)
    p = position_tracker.load_all()["11111111_005930"]
    assert p["buy_date"] == today


def test_add_position_custom_buy_date():
    position_tracker.add_position("11111111", "005930", 70000, 1, 65000, 80000, buy_date="2025-01-15")
    p = position_tracker.load_all()["11111111_005930"]
    assert p["buy_date"] == "2025-01-15"


# ─── remove_position ─────────────────────────────────────────────────────────

def test_remove_position_deletes_entry():
    position_tracker.add_position("22222222", "005930", 70000, 1, 65000, 80000)
    position_tracker.remove_position("22222222", "005930")
    assert "22222222_005930" not in position_tracker.load_all()


def test_remove_position_missing_key_no_error():
    # 존재하지 않는 키를 제거해도 예외 없이 종료돼야 한다
    position_tracker.remove_position("00000000", "000000")


# ─── get_open_positions ──────────────────────────────────────────────────────

def test_get_open_positions_returns_open_only(tmp_path, monkeypatch):
    positions = {
        "A_001": {"account_no": "A", "stock_code": "001", "status": "open"},
        "A_002": {"account_no": "A", "stock_code": "002", "status": "closed"},
    }
    pf = tmp_path / "positions.json"
    pf.write_text(json.dumps(positions), encoding="utf-8")
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))

    result = position_tracker.get_open_positions()
    assert len(result) == 1
    assert result[0]["stock_code"] == "001"


def test_get_open_positions_empty():
    result = position_tracker.get_open_positions()
    assert result == []


# ─── update_position_levels ──────────────────────────────────────────────────

def test_update_position_levels_success():
    position_tracker.add_position("33333333", "005930", 70000, 1, 65000, 80000)
    ok = position_tracker.update_position_levels("33333333", "005930", 64000, 85000)
    assert ok is True
    p = position_tracker.load_all()["33333333_005930"]
    assert p["stop_loss"] == 64000.0
    assert p["take_profit"] == 85000.0


def test_update_position_levels_missing_key_returns_false():
    ok = position_tracker.update_position_levels("99999999", "999999", 1000, 2000)
    assert ok is False


# ─── 백업 회전 + 손상 자동복구 ───────────────────────────────────────────────

import os as _os
import json as _json


def test_backup_created_on_each_save():
    """add_position 후 두 번째 호출 시 첫 번째 상태가 백업되어야 한다."""
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    # 첫 호출 시점에는 기존 파일이 없었으므로 백업 0개
    assert position_tracker.list_backups() == []

    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    # 두 번째 _save 직전에 첫 번째 상태가 백업됨
    backups = position_tracker.list_backups()
    assert len(backups) == 1
    assert backups[0]["valid"] is True
    assert backups[0]["position_count"] == 1  # 첫 번째 add 만 들어있던 상태


def test_backup_rotation_keeps_only_max_backups():
    """MAX_BACKUPS=5 초과 시 가장 오래된 백업은 삭제되어야 한다."""
    # 백업 파일명은 μs 까지 포함하므로 sleep 없이도 유니크
    for i in range(8):
        position_tracker.add_position("A1", f"{i:06d}", 10000 + i, 1, 9000, 12000)
    backups = position_tracker.list_backups()
    assert len(backups) == position_tracker.MAX_BACKUPS  # 5
    # 모두 유효 JSON 이어야 함
    assert all(b["valid"] for b in backups)


def test_load_auto_recovers_from_corrupt_positions_file(isolated_pos_file):
    """positions.json 이 손상되면 가장 최근 유효 백업으로 자동 복구된다."""
    # 1) 유효한 상태 → 자동 백업 트리거 위해 두 번째 저장도 진행
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    assert len(position_tracker.list_backups()) >= 1

    # 2) positions.json 손상시킴 (직접 쓰기)
    isolated_pos_file.write_text("{ broken json", encoding="utf-8")

    # 3) load_all() 호출 시 자동 복구
    recovered = position_tracker.load_all()
    assert isinstance(recovered, dict)
    # 가장 최근 백업이 1번째 add 시점 (1건짜리) 였으므로 복구된 dict 도 1건이어야 함
    assert len(recovered) == 1


def test_load_returns_empty_when_no_backups_and_corrupt(isolated_pos_file):
    """백업이 없는데 파일이 손상되면 빈 dict 반환 (기존 동작 호환)."""
    isolated_pos_file.write_text("totally broken", encoding="utf-8")
    assert position_tracker.load_all() == {}


def test_list_backups_returns_sorted_newest_first():
    """list_backups 는 index=0 이 최신, 메타 필드 모두 포함."""
    position_tracker.add_position("A1", "001", 1000, 1, 900, 1100)
    position_tracker.add_position("A1", "002", 1000, 1, 900, 1100)
    position_tracker.add_position("A1", "003", 1000, 1, 900, 1100)

    backups = position_tracker.list_backups()
    assert len(backups) == 2  # 1번/2번 add 시점의 백업 두 개
    # 필드 검증
    for b in backups:
        assert set(b.keys()) == {"index", "filename", "mtime", "size", "position_count", "valid"}
        assert b["filename"].startswith("positions.")
        assert b["filename"].endswith(".json")
    # 최신 순 — index 0 이 가장 마지막 백업 (2건짜리)
    assert backups[0]["position_count"] >= backups[1]["position_count"]


def test_restore_backup_replaces_current_file(isolated_pos_file):
    """restore_backup(idx) 호출 시 positions.json 이 백업 내용으로 덮어쓰여진다."""
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    position_tracker.add_position("A1", "035720", 50000, 1, 45000, 60000)
    # 현재 3건 보유
    assert len(position_tracker.load_all()) == 3

    # 가장 오래된 백업(1번 add 직후 = 종목 1건짜리)으로 복원
    backups = position_tracker.list_backups()
    # backups[-1] 이 가장 오래된 = 1건짜리
    oldest_count = backups[-1]["position_count"]
    ok = position_tracker.restore_backup(len(backups) - 1)
    assert ok is True
    assert len(position_tracker.load_all()) == oldest_count


def test_restore_backup_invalid_index_returns_false():
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    assert position_tracker.restore_backup(99) is False
    assert position_tracker.restore_backup(-1) is False
