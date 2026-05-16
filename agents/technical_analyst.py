import logging
from agents.base_agent import BaseAgent
import analyzer

logger = logging.getLogger(__name__)


class TechnicalAnalyst(BaseAgent):
    """기술 분석 에이전트 - 13개 필터 검증"""
    
    def __init__(self):
        super().__init__("Technical Analyst")
    
    def process(self, input_data: dict) -> dict:
        """
        13대 필터 검증 실행
        
        Args:
            input_data: {
                "stock": dict,
                "open_price": float,
                "high_price": float,
                "prev_close": float,
                "daily_prices": list,
                "daily_opens": list,
                "daily_closes": list,
                "daily_volumes": list,
                "minute_vols": list,
                "user": dict,
                "token": str
            }
        """
        try:
            # 필수 데이터 검증
            required_keys = ["stock", "open_price", "high_price", "daily_prices", "minute_vols"]
            for key in required_keys:
                if key not in input_data:
                    logger.warning(f"필수 데이터 누락: {key}")
                    return {"pass": False, "reason": f"필수 데이터 누락: {key}"}
            
            # 1. 기존의 13대 필수 필터 검증 (강력한 허들)
            result = analyzer.is_valid_stock_final(
                stock=input_data["stock"],
                open_price=input_data.get("open_price", 0),
                high_price=input_data.get("high_price", 0),
                prev_close=input_data.get("prev_close", 0),
                daily_prices=input_data.get("daily_prices", []),
                daily_opens=input_data.get("daily_opens", []),
                daily_closes=input_data.get("daily_closes", []),
                daily_volumes=input_data.get("daily_volumes", []),
                minute_vols=input_data.get("minute_vols", []),
                user=input_data.get("user", {}),
                token=input_data.get("token", "")
            )
            
            if not result.get("pass"):
                logger.info(f"기술 분석 탈락: {input_data['stock']['code']} - {result.get('reason')}")
                return result

            # 2. 추가 고급 지표 계산 (MACD, Stochastic)를 통한 상세 스코어링
            import numpy as np
            import talib

            raw_prices = input_data.get("daily_prices") or []
            if not isinstance(raw_prices, list) or len(raw_prices) < 2:
                logger.warning(f"기술 분석 보조 지표 스킵: daily_prices 부족 ({len(raw_prices) if isinstance(raw_prices, list) else 'None'})")
                result["technical_score"] = 0.5
                return result

            try:
                prices = np.array(raw_prices, dtype=float)
            except (ValueError, TypeError) as e:
                logger.error(f"daily_prices float 변환 실패: {e}")
                result["technical_score"] = 0.5
                return result

            # daily_highs/lows가 없으면 daily_closes로 대체 (STOCH 정확도 저하 감수)
            raw_highs = input_data.get("daily_highs") or input_data.get("daily_closes") or raw_prices
            raw_lows  = input_data.get("daily_lows")  or input_data.get("daily_closes") or raw_prices
            try:
                highs = np.array(raw_highs, dtype=float)
                lows  = np.array(raw_lows,  dtype=float)
            except (ValueError, TypeError):
                highs = prices.copy()
                lows  = prices.copy()

            tech_score = 0.5  # 기본 점수

            if len(prices) >= 34:
                # MACD 분석 (12, 26, 9)
                _, _, macdhist = talib.MACD(prices, fastperiod=12, slowperiod=26, signalperiod=9)
                last   = macdhist[-1]  if len(macdhist) >= 1 else np.nan
                second = macdhist[-2]  if len(macdhist) >= 2 else np.nan
                if not np.isnan(last):
                    if last > 0:
                        tech_score += 0.2  # MACD 양수 → 상승 추세
                    elif not np.isnan(second) and last > second:
                        tech_score += 0.1  # 음수지만 상승 중 → 약한 가점

            min_stoch_len = max(len(highs), len(lows), len(prices))
            if min_stoch_len >= 20:
                # Stochastic 분석 (고가/저가/종가 배열 길이 통일)
                n = min(len(highs), len(lows), len(prices))
                slowk, slowd = talib.STOCH(
                    highs[-n:], lows[-n:], prices[-n:],
                    fastk_period=14, slowk_period=3, slowd_period=3,
                )
                k_last = slowk[-1] if len(slowk) >= 1 else np.nan
                d_last = slowd[-1] if len(slowd) >= 1 else np.nan
                if not np.isnan(k_last):
                    if k_last < 20:
                        tech_score += 0.2   # 과매도 → 매수 찬스
                    elif k_last > 80:
                        tech_score -= 0.2   # 과매수 → 고점 리스크
                    elif not np.isnan(d_last) and k_last > d_last:
                        tech_score += 0.1   # 골든크로스 상태

            tech_score = max(0.0, min(round(tech_score, 2), 1.0))
            
            # 결과에 상세 점수 합산
            result["technical_score"] = tech_score
            
            logger.info(f"기술 분석 통과: {input_data['stock']['code']} - 기술점수: {tech_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"기술 분석 오류: {e}", exc_info=True)
            return {"pass": False, "reason": str(e)}
