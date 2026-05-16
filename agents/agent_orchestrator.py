import logging
from agents.sentiment_analyst import SentimentAnalyst
from agents.technical_analyst import TechnicalAnalyst
from agents.researcher_team import ResearcherTeam
from agents.risk_management import RiskManagement
from agents.trader_agent import TraderAgent
from agents.portfolio_manager import PortfolioManager

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        self.agents = {
            "sentiment": SentimentAnalyst(),
            "technical": TechnicalAnalyst(),
            "researcher": ResearcherTeam(),
            "risk": RiskManagement(),
            "trader": TraderAgent(),
            "portfolio": PortfolioManager(),
        }

    def _run_agent(self, name: str, input_data: dict) -> dict:
        """단일 에이전트 실행 — 예외 발생 시 격리하고 빈 dict 반환"""
        try:
            result = self.agents[name].process(input_data)
            if not isinstance(result, dict):
                logger.error(f"[{name}] 반환값이 dict가 아님: {type(result).__name__}")
                return {}
            return result
        except Exception as e:
            logger.error(f"[{name}] 에이전트 오류: {e}", exc_info=True)
            return {}

    def run_flow(self, input_data: dict) -> dict:
        # 각 에이전트가 이전 모든 에이전트의 결과를 누적해서 받음
        accumulated = dict(input_data)

        for name in ("sentiment", "technical", "researcher", "risk", "trader", "portfolio"):
            result = self._run_agent(name, accumulated)
            accumulated.update(result)

            # 기술 분석 탈락 시 이후 에이전트(주문 포함) 실행 중단
            if name == "technical" and not accumulated.get("pass", True):
                logger.info(
                    f"[Orchestrator] 기술 분석 탈락 ({accumulated.get('reason', '?')}) "
                    f"— 이후 에이전트 실행 생략"
                )
                accumulated["final_approval"] = False
                break

        return accumulated
