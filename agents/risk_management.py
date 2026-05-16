import logging
from agents.base_agent import BaseAgent
import analyzer

logger = logging.getLogger(__name__)


class RiskManagement(BaseAgent):
    """위험 관리 에이전트 - 포지션 크기, 손절, 익절 관리"""
    
    def __init__(self):
        super().__init__("Risk Management")
    
    def process(self, input_data: dict) -> dict:
        """
        위험 관리 판단
        
        Args:
            input_data: {
                "current_price": float,
                "support_price": float,
                "resistance_price": float,
                "portfolio_value": float,
                "max_loss_rate": float (기본 5%),
                "take_profit_rate": float (기본 10%)
            }
        """
        # 거래 시간 확인
        time_check = analyzer.is_valid_trading_time()
        time_ok = time_check["ok"]
        
        current_price = input_data.get("current_price", 0)
        support_price = input_data.get("support_price", current_price * 0.98)
        resistance_price = input_data.get("resistance_price", current_price * 1.10)
        portfolio_value = input_data.get("portfolio_value", 1_000_000)
        max_loss_rate = input_data.get("max_loss_rate", 0.05)  # 5%
        take_profit_rate = input_data.get("take_profit_rate", 0.10)  # 10%
        
        # 손절 설정
        stop_loss = support_price
        stop_loss_rate = (current_price - stop_loss) / current_price if current_price > 0 else 0
        
        # 익절 설정
        take_profit = current_price * (1 + take_profit_rate)
        
        # 포지션 크기 (손절 거리 기반)
        position_size = int(portfolio_value * max_loss_rate / stop_loss_rate) if stop_loss_rate > 0 else 0
        
        risk_pass = time_ok and stop_loss_rate > 0
        
        logger.info(f"위험 관리: 손절={stop_loss:.0f}, 익절={take_profit:.0f}, 포지션={position_size}")
        
        return {
            "risk_pass": risk_pass,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size": position_size,
            "stop_loss_rate": stop_loss_rate,
            "time_ok": time_ok
        }
