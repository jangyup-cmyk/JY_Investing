"""agent_telemetry + orchestrator 통합 거부 기록 단위 테스트.

tmp_path + monkeypatch 로 REJECTION_FILE 격리.
"""
import json
from unittest.mock import MagicMock
from datetime import datetime, timedelta

import pytest

import agent_telemetry
import dashboard


AGENT_NAMES = ("sentiment", "technical", "researcher", "risk", "trader", "portfolio")


@pytest.fixture(autouse=True)
def isolated_rejection_file(tmp_path, monkeypatch):
    rf = tmp_path / "agent_rejections.json"
    monkeypatch.setattr(agent_telemetry, "REJECTION_FILE", str(rf))
    return rf


@pytest.fixture
def client():
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c


@pytest.fixture
def orchestrator():
    """모든 에이전트가 MagicMock으로 대체된 오케스트레이터."""
    from agents.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    for name in AGENT_NAMES:
        orch.agents[name] = MagicMock()
        orch.agents[name].process.return_value = {}
    return orch


def _cfg(orch, name, return_value):
    orch.agents[name].process.return_value = return_value


# ─── 핵심 record/load/summarize 동작 ──────────────────────────────────────────

def test_record_rejection_creates_entry(isolated_rejection_file):
    ok = agent_telemetry.record_rejection("005930", "technical", "RSI 미달")
    assert ok is True
    data = json.loads(isolated_rejection_file.read_text(encoding="utf-8"))
    assert len(data) == 1
    rec = data[0]
    assert rec["stock_code"] == "005930"
    assert rec["stage"] == "technical"
    assert rec["reason"] == "RSI 미달"
    assert "timestamp" in rec


def test_record_rejection_appends_multiple(isolated_rejection_file):
    for i in range(5):
        agent_telemetry.record_rejection(f"00000{i}", "technical", f"r{i}")
    data = json.loads(isolated_rejection_file.read_text(encoding="utf-8"))
    assert len(data) == 5


def test_record_rejection_rotates_at_max(monkeypatch, isolated_rejection_file):
    monkeypatch.setattr(agent_telemetry, "MAX_REJECTION_RECORDS", 10)
    for i in range(25):
        agent_telemetry.record_rejection(f"{i:06d}", "technical", "x")
    data = json.loads(isolated_rejection_file.read_text(encoding="utf-8"))
    assert len(data) == 10
    # 최신 10개가 남음 — 마지막 record 의 code 는 "000024"
    assert data[-1]["stock_code"] == "000024"


def test_record_rejection_silent_on_failure(monkeypatch):
    """파일 쓰기가 실패해도 raise 하지 않고 False 반환."""
    monkeypatch.setattr(
        agent_telemetry, "REJECTION_FILE",
        "/nonexistent/path/that/cannot/be/written/agent_rejections.json",
    )
    ok = agent_telemetry.record_rejection("005930", "technical", "RSI 미달")
    assert ok is False


def test_summarize_by_stage_and_top_reasons(isolated_rejection_file):
    agent_telemetry.record_rejection("A", "technical", "RSI 미달")
    agent_telemetry.record_rejection("B", "technical", "RSI 미달")
    agent_telemetry.record_rejection("C", "technical", "거래량 미달")
    agent_telemetry.record_rejection("D", "risk", "장 종료")
    agent_telemetry.record_rejection("E", "researcher", "bull_score=0.40")

    summary = agent_telemetry.summarize_rejections(days=7)
    assert summary["total"] == 5
    # 단계별 카운트 — technical=3 이 가장 위
    assert summary["by_stage"][0]["stage"] == "technical"
    assert summary["by_stage"][0]["count"] == 3
    # 사유 Top — "technical: RSI 미달" 이 2회로 1위
    assert summary["top_reasons"][0]["label"] == "technical: RSI 미달"
    assert summary["top_reasons"][0]["count"] == 2


def test_summarize_filters_by_window(isolated_rejection_file):
    """1일 윈도우는 오래된 record 를 제외해야 한다."""
    old_ts = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    new_ts = datetime.now().isoformat(timespec="seconds")
    isolated_rejection_file.write_text(json.dumps([
        {"timestamp": old_ts, "stock_code": "OLD", "stage": "technical", "reason": "old"},
        {"timestamp": new_ts, "stock_code": "NEW", "stage": "technical", "reason": "new"},
    ]), encoding="utf-8")

    s1 = agent_telemetry.summarize_rejections(days=1)
    assert s1["total"] == 1
    s30 = agent_telemetry.summarize_rejections(days=30)
    assert s30["total"] == 2


# ─── orchestrator 통합 (3개 거부 지점) ──────────────────────────────────────

def test_orchestrator_technical_fail_records_rejection(orchestrator, isolated_rejection_file):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.7})
    _cfg(orchestrator, "technical", {"pass": False, "reason": "RSI 미달"})

    orchestrator.run_flow({"stock_code": "005930"})

    records = agent_telemetry.load_rejections()
    assert len(records) == 1
    assert records[0]["stage"] == "technical"
    assert records[0]["stock_code"] == "005930"
    assert records[0]["reason"] == "RSI 미달"


def test_orchestrator_researcher_reject_records_rejection(orchestrator):
    _cfg(orchestrator, "technical", {"pass": True})
    _cfg(orchestrator, "researcher", {"final_decision": False, "bull_score": 0.42})

    orchestrator.run_flow({"stock_code": "000660"})
    records = agent_telemetry.load_rejections()
    assert len(records) == 1
    assert records[0]["stage"] == "researcher"
    assert "0.42" in records[0]["reason"]


def test_orchestrator_risk_reject_records_rejection(orchestrator):
    _cfg(orchestrator, "technical", {"pass": True})
    _cfg(orchestrator, "researcher", {"final_decision": True, "bull_score": 0.75})
    _cfg(orchestrator, "risk", {"risk_pass": False, "time_ok": False})

    orchestrator.run_flow({"stock_code": "035720"})
    records = agent_telemetry.load_rejections()
    assert len(records) == 1
    assert records[0]["stage"] == "risk"


def test_orchestrator_success_records_nothing(orchestrator):
    _cfg(orchestrator, "technical", {"pass": True})
    _cfg(orchestrator, "researcher", {"final_decision": True, "bull_score": 0.8})
    _cfg(orchestrator, "risk", {"risk_pass": True})
    _cfg(orchestrator, "trader", {})
    _cfg(orchestrator, "portfolio", {})

    orchestrator.run_flow({"stock_code": "005930"})
    assert agent_telemetry.load_rejections() == []


# ─── /api/rejections/summary 라우트 ──────────────────────────────────────────

def test_rejections_summary_route_empty(client):
    res = client.get("/api/rejections/summary")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["total"] == 0


def test_rejections_summary_route_with_data(client):
    agent_telemetry.record_rejection("A", "technical", "RSI 미달")
    agent_telemetry.record_rejection("B", "risk", "장 종료")
    res = client.get("/api/rejections/summary?days=7&top=5")
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["total"] == 2
    stages = {row["stage"]: row["count"] for row in body["data"]["by_stage"]}
    assert stages == {"technical": 1, "risk": 1}


def test_rejections_summary_route_clamps_days(client):
    res = client.get("/api/rejections/summary?days=99999")
    body = res.get_json()
    assert body["data"]["window_days"] == 90   # 상한 클램프
    res2 = client.get("/api/rejections/summary?days=0")
    assert res2.get_json()["data"]["window_days"] == 1  # 하한 클램프
