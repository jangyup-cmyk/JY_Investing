import logging
from agents.base_agent import BaseAgent
import trader
import position_tracker

logger = logging.getLogger(__name__)


class TraderAgent(BaseAgent):
    """매매 에이전트 - 주문 실행"""
    
    def __init__(self):
        super().__init__("Trader Agent")
    
    def process(self, input_data: dict) -> dict:
        """
        50% 시장가 + 50% 지정가 분할 매수 실행
        
        Args:
            input_data: {
                "user": dict,
                "stock": dict,
                "position_size": int (optional)
            }
        """
        try:
            user = input_data.get("user", {})
            stock = input_data.get("stock", {})

            if not user or not stock:
                logger.warning("필수 데이터 누락: user 또는 stock")
                return {"success": False, "reason": "필수 데이터 누락"}

            # 리서치 팀 / 위험 관리 최종 승인 확인
            if not input_data.get("final_decision", False):
                logger.info(f"[TraderAgent] 리서치 팀 매수 미승인 — 주문 건너뜀 ({stock.get('code', '?')})")
                return {"success": False, "reason": "리서치 팀 미승인"}
            if not input_data.get("risk_pass", True):
                logger.info(f"[TraderAgent] 위험 관리 거부 — 주문 건너뜀 ({stock.get('code', '?')})")
                return {"success": False, "reason": "위험 관리 거부"}

            # 중복 매수 방지: 이미 보유 중인 종목이면 건너뜀
            account_no = user.get("account_no", "")
            stock_code = stock.get("code", "")
            open_positions = position_tracker.get_open_positions()
            already_holding = any(
                p["account_no"] == account_no and p["stock_code"] == stock_code
                for p in open_positions
            )
            if already_holding:
                logger.info(f"[TraderAgent] 이미 보유 중 — 중복 매수 건너뜀 ({account_no} / {stock_code})")
                return {"success": False, "reason": "이미 보유 중인 종목"}

            # 주문 및 알림, 포지션 기록 실행 (점수 정보 포함)
            result = trader.trade_and_notify(
                user=user,
                stock=stock,
                bull_score=input_data.get("bull_score", 0.5)
            )
            
            if result:
                logger.info(f"매수 주문 실행: {stock['code']}")
                return {"success": True, "trade_result": result}
            else:
                logger.warning(f"매수 주문 실패: {stock['code']}")
                return {"success": False, "reason": "주문 실패"}
                
        except Exception as e:
            logger.error(f"매매 에이전트 오류: {e}")
            return {"success": False, "reason": str(e)}
