"""개별 에이전트 단위 테스트

외부 API / DB 의존 없이 에이전트 로직만 검증합니다.
- ResearcherTeam  : 순수 점수 계산 로직
- PortfolioManager: position_tracker / config 모킹
- RiskManagement  : analyzer.is_valid_trading_time 모킹
"""
from unittest.mock import patch, MagicMock
import pytest


# ─── ResearcherTeam ──────────────────────────────────────────────────────────

from agents.researcher_team import ResearcherTeam


def test_researcher_team_bull_approved():
    agent = ResearcherTeam()
    result = agent.process({
        "technical_pass": True,
        "technical_score": 0.8,
        "sentiment_score": 0.7,
        "vi_safe": True,
        "market_bullish": True,
    })
    assert result["bull_approved"] is True
    assert result["bull_score"] >= 0.60


def test_researcher_team_bear_approved():
    agent = ResearcherTeam()
    result = agent.process({
        "technical_pass": False,
        "technical_score": 0.0,
        "sentiment_score": 0.1,
        "vi_safe": False,
        "market_bullish": False,
    })
    assert result["bear_approved"] is True
    assert result["final_decision"] is False


def test_researcher_team_strong_bull():
    agent = ResearcherTeam()
    result = agent.process({
        "technical_pass": True,
        "technical_score": 1.0,
        "sentiment_score": 1.0,
        "vi_safe": True,
        "market_bullish": True,
    })
    # 가중치 합: 1.0*0.55 + 1.0*0.25 + 1.0*0.10 + 1.0*0.10 = 1.0 ≥ 0.70
    assert result["bull_score"] >= 0.70


def test_researcher_team_sentiment_veto():
    """기술 점수 높아도 감정 점수 낮으면 매수 거부"""
    agent = ResearcherTeam()
    result = agent.process({
        "technical_pass": True,
        "technical_score": 0.9,
        "sentiment_score": 0.2,   # ≤ 0.3 → veto
        "vi_safe": True,
        "market_bullish": True,
    })
    assert result["bull_approved"] is False


def test_researcher_team_bull_score_is_float():
    agent = ResearcherTeam()
    result = agent.process({"technical_pass": True, "technical_score": 0.7, "sentiment_score": 0.6})
    assert isinstance(result["bull_score"], float)
    assert 0.0 <= result["bull_score"] <= 1.0


# ─── PortfolioManager ────────────────────────────────────────────────────────

from agents.portfolio_manager import PortfolioManager
import config


def test_portfolio_manager_final_approval(monkeypatch):
    monkeypatch.setattr(config, "MAX_POSITIONS", 5)
    monkeypatch.setattr(config, "MIN_CASH_RATE", 0.2)

    with patch("agents.portfolio_manager.position_tracker.get_open_positions", return_value=[]):
        agent = PortfolioManager()
        result = agent.process({
            "trade_result": {"order_no": "12345"},
            "user": {"account_no": "99999999", "budget": 10_000_000},
            "stock_code": "005930",
        })
    assert result["final_approval"] is True
    assert result["position_count"] == 0


def test_portfolio_manager_no_trade_result():
    agent = PortfolioManager()
    result = agent.process({
        "trade_result": None,
        "user": {"account_no": "99999999"},
        "stock_code": "005930",
    })
    assert result["final_approval"] is False


def test_portfolio_manager_cash_rate_calculated(monkeypatch):
    monkeypatch.setattr(config, "MAX_POSITIONS", 5)
    monkeypatch.setattr(config, "MIN_CASH_RATE", 0.2)

    mock_positions = [
        {"account_no": "99999999", "buy_price": 70000, "qty": 10},
    ]
    with patch("agents.portfolio_manager.position_tracker.get_open_positions", return_value=mock_positions):
        agent = PortfolioManager()
        result = agent.process({
            "trade_result": {"order_no": "99"},
            "user": {"account_no": "99999999", "budget": 10_000_000},
            "stock_code": "000660",
        })
    assert "cash_rate" in result
    assert 0.0 <= result["cash_rate"] <= 1.0


# ─── RiskManagement ──────────────────────────────────────────────────────────

from agents.risk_management import RiskManagement


def test_risk_management_returns_required_fields():
    with patch("agents.risk_management.analyzer.is_valid_trading_time",
               return_value={"ok": True, "reason": "허용"}):
        agent = RiskManagement()
        result = agent.process({
            "current_price": 70000,
            "support_price": 67000,
            "portfolio_value": 10_000_000,
        })
    for field in ("risk_pass", "stop_loss", "take_profit", "position_size", "time_ok"):
        assert field in result


def test_risk_management_blocked_outside_hours():
    with patch("agents.risk_management.analyzer.is_valid_trading_time",
               return_value={"ok": False, "reason": "차단"}):
        agent = RiskManagement()
        result = agent.process({
            "current_price": 70000,
            "support_price": 67000,
        })
    assert result["time_ok"] is False
    assert result["risk_pass"] is False
