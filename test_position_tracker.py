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
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))
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
