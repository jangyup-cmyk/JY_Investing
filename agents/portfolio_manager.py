from agents.base_agent import BaseAgent

class PortfolioManager(BaseAgent):
    def __init__(self):
        super().__init__("Portfolio Manager")

    def process(self, input_data: dict) -> dict:
        # 최종 승인 (현재는 Trader 결과 기반)
        trade_ok = input_data.get("trade_result") is not None
        return {"final_approval": trade_ok}
