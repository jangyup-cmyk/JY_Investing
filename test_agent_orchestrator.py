"""
AgentOrchestrator 게이트 로직 및 PortfolioManager 단위 테스트.

모든 에이전트를 Mock으로 대체해 외부 API 없이 실행.
검증 항목:
  1. Technical 탈락 → researcher/risk/trader/portfolio 미실행
  2. Researcher 반려 → risk/trader/portfolio 미실행
  3. Risk 거부 → trader/portfolio 미실행
  4. 전체 승인 → final_approval=True
  5. 에이전트 예외 → 격리되고 파이프라인 계속
"""

import pytest
from unittest.mock import MagicMock


AGENT_NAMES = ("sentiment", "technical", "researcher", "risk", "trader", "portfolio")


@pytest.fixture()
def orchestrator():
    """모든 에이전트가 MagicMock으로 대체된 오케스트레이터"""
    from agents.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    for name in AGENT_NAMES:
        orch.agents[name] = MagicMock()
        orch.agents[name].process.return_value = {}
    return orch


def _cfg(orch, name: str, return_value: dict):
    orch.agents[name].process.return_value = return_value


# ──────────────────────────────────────────────────────────────────────────────
# 1. Technical 탈락 게이트
# ──────────────────────────────────────────────────────────────────────────────

def test_technical_fail_stops_pipeline(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.7})
    _cfg(orchestrator, "technical", {"pass": False, "reason": "RSI 미달"})

    result = orchestrator.run_flow({"stock_code": "005930"})

    assert result["final_approval"] is False
    orchestrator.agents["researcher"].process.assert_not_called()
    orchestrator.agents["risk"].process.assert_not_called()
    orchestrator.agents["trader"].process.assert_not_called()
    orchestrator.agents["portfolio"].process.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Researcher 반려 게이트
# ──────────────────────────────────────────────────────────────────────────────

def test_researcher_reject_stops_pipeline(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.4})
    _cfg(orchestrator, "technical", {"pass": True, "technical_score": 0.7})
    _cfg(orchestrator, "researcher", {
        "bull_approved": False,
        "final_decision": False,
        "bull_score": 0.35,
    })

    result = orchestrator.run_flow({"stock_code": "005930"})

    assert result["final_approval"] is False
    orchestrator.agents["risk"].process.assert_not_called()
    orchestrator.agents["trader"].process.assert_not_called()
    orchestrator.agents["portfolio"].process.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Risk 거부 게이트
# ──────────────────────────────────────────────────────────────────────────────

def test_risk_reject_stops_pipeline(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.8})
    _cfg(orchestrator, "technical", {"pass": True, "technical_score": 0.8})
    _cfg(orchestrator, "researcher", {
        "bull_approved": True,
        "final_decision": True,
        "bull_score": 0.72,
    })
    _cfg(orchestrator, "risk", {"risk_pass": False, "time_ok": False})

    result = orchestrator.run_flow({"stock_code": "005930"})

    assert result["final_approval"] is False
    orchestrator.agents["trader"].process.assert_not_called()
    orchestrator.agents["portfolio"].process.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 4. 전체 승인 → final_approval=True
# ──────────────────────────────────────────────────────────────────────────────

def test_full_approval_pipeline(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.8})
    _cfg(orchestrator, "technical", {"pass": True, "technical_score": 0.8})
    _cfg(orchestrator, "researcher", {
        "bull_approved": True,
        "final_decision": True,
        "bull_score": 0.75,
    })
    _cfg(orchestrator, "risk", {
        "risk_pass": True,
        "time_ok": True,
        "stop_loss": 9500.0,
        "take_profit": 11000.0,
    })
    _cfg(orchestrator, "trader", {"success": True, "trade_result": {"market_qty": 5}})
    _cfg(orchestrator, "portfolio", {"final_approval": True})

    result = orchestrator.run_flow({"stock_code": "005930"})

    assert result.get("final_approval") is True
    orchestrator.agents["trader"].process.assert_called_once()
    orchestrator.agents["portfolio"].process.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 5. 에이전트 예외 → 격리 (빈 dict 반환, 파이프라인 계속)
# ──────────────────────────────────────────────────────────────────────────────

def test_agent_exception_is_isolated(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.7})
    orchestrator.agents["technical"].process.side_effect = RuntimeError("mock error")

    # 예외가 발생해도 run_flow 자체는 터지지 않아야 함
    result = orchestrator.run_flow({"stock_code": "005930"})
    assert isinstance(result, dict)


# ──────────────────────────────────────────────────────────────────────────────
# 6. bull_score=0.60 경계값 — 정확히 0.60이면 승인
# ──────────────────────────────────────────────────────────────────────────────

def test_researcher_boundary_bull_score(orchestrator):
    _cfg(orchestrator, "sentiment", {"sentiment_score": 0.6})
    _cfg(orchestrator, "technical", {"pass": True, "technical_score": 0.6})
    _cfg(orchestrator, "researcher", {
        "bull_approved": True,
        "final_decision": True,
        "bull_score": 0.60,
    })
    _cfg(orchestrator, "risk", {"risk_pass": True, "time_ok": True})
    _cfg(orchestrator, "trader", {"success": True, "trade_result": {}})
    _cfg(orchestrator, "portfolio", {"final_approval": True})

    result = orchestrator.run_flow({"stock_code": "005930"})

    orchestrator.agents["trader"].process.assert_called_once()
    assert result.get("final_approval") is True


# ──────────────────────────────────────────────────────────────────────────────
# PortfolioManager 단위 테스트
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def portfolio_manager():
    from agents.portfolio_manager import PortfolioManager
    return PortfolioManager()


def test_portfolio_rejects_when_no_trade_result(portfolio_manager):
    result = portfolio_manager.process({"trade_result": None, "user": {}, "stock_code": "005930"})
    assert result["final_approval"] is False
    assert "주문 미체결" in result["portfolio_reason"]


def test_portfolio_approves_on_success(portfolio_manager, tmp_path, monkeypatch):
    import position_tracker as pt

    # positions.json을 임시 경로로 교체해 실제 파일에 영향 없이 테스트
    monkeypatch.setattr(pt, "POSITION_FILE", str(tmp_path / "positions.json"))

    user = {"account_no": "12345678901", "name": "테스트", "budget": 1_000_000}
    result = portfolio_manager.process({
        "trade_result": {"market_qty": 3},
        "user": user,
        "stock_code": "005930",
    })

    assert result["final_approval"] is True
    assert "position_count" in result
    assert "cash_rate" in result


def test_portfolio_warns_over_max_positions(portfolio_manager, tmp_path, monkeypatch):
    import json
    import position_tracker as pt

    # MAX_POSITIONS를 2로 낮춰 초과 상황 유도
    monkeypatch.setattr("config.MAX_POSITIONS", 2)
    monkeypatch.setattr(pt, "POSITION_FILE", str(tmp_path / "positions.json"))

    # 3개 포지션 사전 등록
    positions = {
        f"12345678901_00000{i}": {
            "account_no": "12345678901", "stock_code": f"00000{i}",
            "buy_price": 10000, "qty": 1, "status": "open",
            "stop_loss": 9500, "take_profit": 11000,
            "stock_name": f"종목{i}", "opened_at": "2026-01-01T09:00:00",
        }
        for i in range(3)
    }
    (tmp_path / "positions.json").write_text(json.dumps(positions), encoding="utf-8")

    user = {"account_no": "12345678901", "name": "테스트", "budget": 1_000_000}
    result = portfolio_manager.process({
        "trade_result": {"market_qty": 1},
        "user": user,
        "stock_code": "000005",
    })

    # MAX_POSITIONS 초과여도 이미 체결된 주문은 취소 불가 → 경고만, 승인은 True
    assert result["final_approval"] is True
    assert result["position_count"] >= 3
