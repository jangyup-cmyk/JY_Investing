import logging
import config
import position_tracker
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PortfolioManager(BaseAgent):
    """포트폴리오 관리 에이전트

    TraderAgent 실행 후 포트폴리오 수준의 사후 검증 및 승인 결정.
    검증 항목:
      1. 주문 성공 여부
      2. 계좌별 최대 보유 종목 수 (MAX_POSITIONS)
      3. 예산 대비 현금 최소 비율 (MIN_CASH_RATE)
    """

    def __init__(self):
        super().__init__("Portfolio Manager")

    def process(self, input_data: dict) -> dict:
        trade_result = input_data.get("trade_result")
        user = input_data.get("user", {})
        stock_code = input_data.get("stock_code", "?")

        # 주문 자체가 실패했으면 바로 반려
        if not trade_result:
            return {"final_approval": False, "portfolio_reason": "주문 미체결"}

        account_no = user.get("account_no", "")

        # ── 1. 최대 보유 종목 수 초과 여부 ──────────────────────────────────
        open_positions = position_tracker.get_open_positions()
        account_positions = [p for p in open_positions if p["account_no"] == account_no]
        position_count = len(account_positions)

        if position_count > config.MAX_POSITIONS:
            logger.warning(
                f"[Portfolio] {user.get('name', account_no)} 보유 종목 {position_count}개 "
                f"— MAX_POSITIONS({config.MAX_POSITIONS}) 초과. "
                f"추가 매수 경고 (이미 체결된 주문은 취소 불가)"
            )

        # ── 2. 현금 비율 경고 ────────────────────────────────────────────────
        budget = user.get("budget", 0)
        invested = sum(
            p.get("buy_price", 0) * p.get("qty", 0)
            for p in account_positions
        )
        cash_rate = (budget - invested) / budget if budget > 0 else 1.0

        if cash_rate < config.MIN_CASH_RATE:
            logger.warning(
                f"[Portfolio] {user.get('name', account_no)} 현금 비율 {cash_rate:.1%} "
                f"— MIN_CASH_RATE({config.MIN_CASH_RATE:.0%}) 미달. 과투자 주의"
            )

        # ── 3. 최종 승인 ─────────────────────────────────────────────────────
        logger.info(
            f"[Portfolio] {user.get('name', account_no)} | {stock_code} 매수 승인 "
            f"(보유 {position_count}종목, 현금 {cash_rate:.1%})"
        )
        return {
            "final_approval": True,
            "position_count": position_count,
            "cash_rate": round(cash_rate, 4),
        }
