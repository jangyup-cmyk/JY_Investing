import logging
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearcherTeam(BaseAgent):
    """리서치 팀 에이전트 - Bull/Bear 토론 및 최종 판단"""
    
    def __init__(self):
        super().__init__("Researcher Team")
    
    def process(self, input_data: dict) -> dict:
        """
        여러 분석 요소를 종합하여 최종 판단 제시
        
        Args:
            input_data: {
                "technical_pass": bool,
                "sentiment_score": float (0~1),
                "vi_safe": bool,
                "market_bullish": bool,
                "rsi": float,
                "gap_rate": float
            }
        """
        # 각 지표별 점수 추출 (TechnicalAnalyst가 넘겨주는 technical_score 활용)
        technical_score = input_data.get("technical_score", 0.5) if input_data.get("technical_pass", False) else 0.0
        sentiment_score = input_data.get("sentiment_score", 0.5)
        
        # 시장 및 VI 상태 점수
        vi_score = 1.0 if input_data.get("vi_safe", True) else 0.0
        market_score = 1.0 if input_data.get("market_bullish", True) else 0.0
        
        # 가중치 적용 (기술 분석 55%, 감정 25%, 시장 10%, VI 10%)
        # 기술적 분석(MACD, Stoch 등)이 중요도가 높음
        bull_score = (technical_score * 0.55 + sentiment_score * 0.25 + market_score * 0.10 + vi_score * 0.10)
        
        # Bull/Bear 논의 (Threshold 판정)
        # 0.7 이상: 강력 매수(Strong Bull), 0.6~0.7: 매수(Bull), 0.4~0.6: 중립(Neutral), 0.4 미만: 매도(Bear)
        strong_bull = bull_score >= 0.70
        bull_approved = bull_score >= 0.60
        bear_approved = bull_score < 0.40
        neutral_approved = not bull_approved and not bear_approved
        
        # 감정 분석과 기술 분석 간의 크로스체크 (다이버전스 방지)
        # 기술 점수는 높은데 악재 뉴스가 많을 경우(감정 점수 최저) 신뢰도를 깎고 반려 처리
        if technical_score >= 0.6 and sentiment_score <= 0.3:
            bull_approved = False
            neutral_approved = True
            logger.info("기술적 매수 자리이나 악재(감정점수 낮음) 감지로 매수 반려")

        final_decision = bull_approved  # Bull일 때만 진행
        confidence = abs(bull_score - 0.5) / 0.5  # 0.5에서 멀수록 확신도 높음
        
        # 판단 이유 텍스트 생성
        reason = "강력 매수" if strong_bull else ("매수" if bull_approved else ("매도" if bear_approved else "중립"))
        logger.info(f"리서치 팀: {reason} (점수: {bull_score:.2f}) | 기술:{technical_score:.2f}, 감정:{sentiment_score:.2f}, 신뢰도:{confidence:.1%}")
        
        return {
            "bull_approved": bull_approved,
            "neutral_approved": neutral_approved,
            "bear_approved": bear_approved,
            "bull_score": bull_score,
            "final_decision": final_decision,
            "confidence": confidence
        }
