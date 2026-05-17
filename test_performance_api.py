"""성과 분석 라우트 + position_tracker.archive_position 단위 테스트

KIS API / 외부 호출 없이 closed_positions.json 만 fixture 로 격리한다.
"""
import json
import pytest

import position_tracker
import dashboard


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    pf = tmp_path / "positions.json"
    cf = tmp_path / "closed_positions.json"
    monkeypatch.setattr(position_tracker, "POSITION_FILE", str(pf))
    monkeypatch.setattr(position_tracker, "CLOSED_POSITIONS_FILE", str(cf))
    return pf, cf


@pytest.fixture
def client():
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c


# ─── archive_position ────────────────────────────────────────────────────────

def test_archive_position_computes_pnl(isolated_files):
    _, cf = isolated_files
    position_tracker.add_position("A1", "005930", 70000, 10, 65000, 80000)
    ok = position_tracker.archive_position("A1", "005930", sell_price=77000, reason="익절")
    assert ok is True

    history = json.loads(cf.read_text(encoding="utf-8"))
    assert len(history) == 1
    rec = history[0]
    assert rec["status"] == "closed"
    assert rec["sell_price"] == 77000
    assert rec["sell_reason"] == "익절"
    assert rec["pnl_amt"] == (77000 - 70000) * 10
    assert rec["pnl_rate"] == round((77000 - 70000) / 70000 * 100, 4)


def test_archive_position_missing_original_returns_false():
    ok = position_tracker.archive_position("Z9", "999999", sell_price=100, reason="x")
    assert ok is False


def test_archive_position_appends_multiple(isolated_files):
    _, cf = isolated_files
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.archive_position("A1", "005930", 77000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    position_tracker.archive_position("A1", "000660", 95000, "손절")
    position_tracker.remove_position("A1", "000660")

    history = json.loads(cf.read_text(encoding="utf-8"))
    assert len(history) == 2
    assert {h["stock_code"] for h in history} == {"005930", "000660"}


def test_load_closed_positions_empty():
    assert position_tracker.load_closed_positions() == []


# ─── /api/performance ────────────────────────────────────────────────────────

def test_performance_empty(client):
    res = client.get("/api/performance")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["trade_count"] == 0
    assert body["data"]["win_rate"] == 0.0


def test_performance_with_trades(client, isolated_files):
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.archive_position("A1", "005930", 77000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    position_tracker.archive_position("A1", "000660", 95000, "손절")
    position_tracker.remove_position("A1", "000660")

    res = client.get("/api/performance")
    data = res.get_json()["data"]
    assert data["trade_count"] == 2
    assert data["win_count"] == 1
    assert data["loss_count"] == 1
    assert data["win_rate"] == 50.0
    assert data["total_pnl_amt"] == (77000 - 70000) + (95000 - 100000)
    assert data["best_pnl_rate"] > data["worst_pnl_rate"]


def test_performance_account_filter(client, isolated_files):
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.archive_position("A1", "005930", 77000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("B2", "000660", 100000, 1, 90000, 120000)
    position_tracker.archive_position("B2", "000660", 110000, "익절")
    position_tracker.remove_position("B2", "000660")

    res = client.get("/api/performance?account_no=A1")
    data = res.get_json()["data"]
    assert data["trade_count"] == 1


# ─── /api/performance/by-stock ───────────────────────────────────────────────

def test_performance_by_stock_empty(client):
    res = client.get("/api/performance/by-stock")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"] == []


def test_performance_by_stock_aggregates(client, isolated_files):
    # 같은 종목 두 번 거래
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.archive_position("A1", "005930", 77000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("A1", "005930", 75000, 1, 70000, 85000)
    position_tracker.archive_position("A1", "005930", 80000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("A1", "000660", 100000, 1, 90000, 120000)
    position_tracker.archive_position("A1", "000660", 95000, "손절")
    position_tracker.remove_position("A1", "000660")

    res = client.get("/api/performance/by-stock")
    rows = res.get_json()["data"]
    assert len(rows) == 2
    # 005930 두 거래 합쳐짐
    samsung = next(r for r in rows if r["stock_code"] == "005930")
    assert samsung["trade_count"] == 2
    # 정렬: total_pnl_amt 내림차순
    assert rows[0]["total_pnl_amt"] >= rows[1]["total_pnl_amt"]


def test_performance_by_stock_account_filter(client, isolated_files):
    position_tracker.add_position("A1", "005930", 70000, 1, 65000, 80000)
    position_tracker.archive_position("A1", "005930", 77000, "익절")
    position_tracker.remove_position("A1", "005930")

    position_tracker.add_position("B2", "000660", 100000, 1, 90000, 120000)
    position_tracker.archive_position("B2", "000660", 110000, "익절")
    position_tracker.remove_position("B2", "000660")

    res = client.get("/api/performance/by-stock?account_no=B2")
    rows = res.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["stock_code"] == "000660"
