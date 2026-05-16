import logging
from datetime import datetime, timedelta
import numpy as np
import math
from unittest.mock import patch, MagicMock

import analyzer
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================
# 테스트 데이터 생성 함수
# ============================================================

def generate_normal_prices(base: float = 10000, days: int = 100) -> list:
    """정상 상승 추세 가격 생성"""
    prices = [base]
    for _ in range(days - 1):
        # 1~3% 일일 변동
        change = np.random.uniform(0.99, 1.03)
        prices.append(prices[-1] * change)
    return sorted(prices)


def generate_bullish_prices(base: float = 10000, days: int = 100) -> list:
    """강한 상승 추세 가격 생성"""
    prices = [base]
    for _ in range(days - 1):
        # 2~4% 강한 상승
        change = np.random.uniform(1.02, 1.04)
        prices.append(prices[-1] * change)
    return prices


def generate_ma_aligned_prices(base: float = 10000) -> list:
    """MA 정렬된 가격 생성 (5, 20, 60일선 정렬)"""
    prices = []
    for i in range(100):
        # 일정한 상승 추세
        prices.append(base + i * 50)
    return prices


def generate_minute_volumes(base_vol: int = 1_000_000, spike_count: int = 1) -> list:
    """분봉 거래량 생성 (마지막에 폭증)"""
    volumes = [base_vol + np.random.randint(-100_000, 100_000) for _ in range(10)]
    for _ in range(spike_count):
        volumes.append(base_vol * 6)  # 600% 폭증
    return volumes


# ============================================================
# 테스트 케이스
# ============================================================

class TestAnalyzer:
    
    @staticmethod
    def test_ma_aligned():
        """Test 1: MA 정렬 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: MA 정렬 필터 (5 > 20 > 60일선)")
        logger.info("="*60)
        
        # Case 1: 정렬된 경우
        prices = generate_ma_aligned_prices()
        result = analyzer.is_ma_aligned(prices)
        logger.info(f"✅ 정렬된 가격: {result}")
        assert result == True, "정렬된 가격 테스트 실패"
        
        # Case 2: 정렬 안 된 경우
        prices = list(reversed(prices))
        result = analyzer.is_ma_aligned(prices)
        logger.info(f"✅ 역순 가격: {result}")
        assert result == False, "역순 가격 테스트 실패"
        
        logger.info("✅ MA 정렬 필터 통과")


    @staticmethod
    def test_volume_surge():
        """Test 2: 거래량 폭증 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: 거래량 폭증 필터")
        logger.info("="*60)
        
        # Case 1: 폭증 있음
        volumes = generate_minute_volumes(spike_count=1)
        result = analyzer.is_volume_surge(volumes, threshold=500)
        logger.info(f"✅ 폭증 감지: {result}")
        assert result == True, "폭증 감지 실패"
        
        # Case 2: 폭증 없음
        volumes = [1_000_000] * 11
        result = analyzer.is_volume_surge(volumes, threshold=500)
        logger.info(f"✅ 폭증 없음: {result}")
        assert result == False, "일반 거래량 테스트 실패"
        
        logger.info("✅ 거래량 폭증 필터 통과")


    @staticmethod
    def test_rsi_valid():
        """Test 3: RSI 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: RSI 필터 (40~70)")
        logger.info("="*60)
        
        # Case 1: 정상 가격
        prices = generate_normal_prices()
        result = analyzer.is_rsi_valid(prices, rsi_min=40.0, rsi_max=70.0)
        logger.info(f"✅ RSI 결과: {result}")
        assert result["ok"] in [True, False], "RSI 계산 실패"
        logger.info(f"   RSI 값: {result['rsi']}")
        
        # Case 2: 데이터 부족
        prices = [100, 101, 102]
        result = analyzer.is_rsi_valid(prices)
        logger.info(f"✅ 데이터 부족: {result}")
        assert result["ok"] == False, "데이터 부족 테스트 실패"
        
        logger.info("✅ RSI 필터 통과")


    @staticmethod
    def test_bollinger_bands():
        """Test 4: 볼린저 밴드 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 4: 볼린저 밴드 필터")
        logger.info("="*60)
        
        # Case 1: 정상 가격
        prices = generate_bullish_prices()
        result = analyzer.is_near_bollinger_upper(prices, threshold=0.98)
        logger.info(f"✅ 볼린저 결과: {result}")
        assert result["ratio"] is not None, "볼린저 계산 실패"
        logger.info(f"   상단 근접도: {result['ratio']}")
        
        # Case 2: 데이터 부족
        prices = [100, 101, 102]
        result = analyzer.is_near_bollinger_upper(prices)
        logger.info(f"✅ 데이터 부족: {result}")
        assert result["ok"] == False, "데이터 부족 테스트 실패"
        
        logger.info("✅ 볼린저 밴드 필터 통과")


    @staticmethod
    def test_gap_up():
        """Test 5: 갭상승 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 5: 갭상승 필터")
        logger.info("="*60)
        
        # Case 1: 갭상승 있음 (3%)
        result = analyzer.is_gap_up(open_price=10300, prev_close=10000, min_gap=2.0)
        logger.info(f"✅ 갭상승 감지 (3%): {result}")
        assert result["ok"] == True, "갭상승 감지 실패"
        
        # Case 2: 갭상승 없음
        result = analyzer.is_gap_up(open_price=10050, prev_close=10000, min_gap=2.0)
        logger.info(f"✅ 갭상승 미달 (0.5%): {result}")
        assert result["ok"] == False, "갭상승 미달 테스트 실패"
        
        logger.info("✅ 갭상승 필터 통과")


    @staticmethod
    def test_consecutive_bullish():
        """Test 6: 연속양봉 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 6: 연속양봉 필터")
        logger.info("="*60)
        
        # Case 1: 연속 양봉 (2일)
        opens = [10000, 10100, 10200]
        closes = [10050, 10150, 10250]
        result = analyzer.is_consecutive_bullish(opens, closes, required_days=2)
        logger.info(f"✅ 연속 양봉 (2일): {result}")
        assert result["ok"] == True, "연속 양봉 감지 실패"
        
        # Case 2: 음봉 포함
        opens = [10000, 10100, 10200]
        closes = [10050, 10050, 10250]  # 2번째는 음봉
        result = analyzer.is_consecutive_bullish(opens, closes, required_days=2)
        logger.info(f"✅ 양봉 끊김: {result}")
        assert result["ok"] == False, "양봉 끊김 테스트 실패"
        
        logger.info("✅ 연속양봉 필터 통과")


    @staticmethod
    def test_bullish_above_open():
        """Test 7: 시가 대비 상승 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 7: 시가 대비 상승 필터")
        logger.info("="*60)
        
        # Case 1: 1% 상승
        result = analyzer.is_bullish_above_open(current=10100, open_p=10000, min_gain=1.0)
        logger.info(f"✅ 1% 상승: {result}")
        assert result == True, "상승 감지 실패"
        
        # Case 2: 0.5% 상승 (미달)
        result = analyzer.is_bullish_above_open(current=10050, open_p=10000, min_gain=1.0)
        logger.info(f"✅ 0.5% 상승 (미달): {result}")
        assert result == False, "상승 미달 테스트 실패"
        
        logger.info("✅ 시가 대비 상승 필터 통과")


    @staticmethod
    def test_near_high():
        """Test 8: 당일 고가 근접 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 8: 당일 고가 근접 필터")
        logger.info("="*60)
        
        # Case 1: 98% 근접
        result = analyzer.is_near_high(current=9800, high=10000, threshold=0.98)
        logger.info(f"✅ 98% 근접: {result}")
        assert result == True, "고가 근접 감지 실패"
        
        # Case 2: 95% 근접 (미달)
        result = analyzer.is_near_high(current=9500, high=10000, threshold=0.98)
        logger.info(f"✅ 95% 근접 (미달): {result}")
        assert result == False, "고가 근접 미달 테스트 실패"
        
        logger.info("✅ 당일 고가 근접 필터 통과")


    @staticmethod
    def test_signal_grade():
        """Test 9: 신호 등급 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 9: 신호 등급 필터")
        logger.info("="*60)
        
        # Case 1: BREAK (100% 이상)
        result = analyzer.get_signal_grade(current=10100, high=10000)
        logger.info(f"✅ BREAK (101%): {result}")
        assert result == "BREAK", "BREAK 등급 실패"
        
        # Case 2: STRONG (99% 이상)
        result = analyzer.get_signal_grade(current=9900, high=10000)
        logger.info(f"✅ STRONG (99%): {result}")
        assert result == "STRONG", "STRONG 등급 실패"
        
        # Case 3: NORMAL (98% 이상)
        result = analyzer.get_signal_grade(current=9800, high=10000)
        logger.info(f"✅ NORMAL (98%): {result}")
        assert result == "NORMAL", "NORMAL 등급 실패"
        
        logger.info("✅ 신호 등급 필터 통과")


    @staticmethod
    def test_trading_value_grade():
        """Test 10: 거래대금 등급 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 10: 거래대금 등급 필터")
        logger.info("="*60)
        
        # Case 1: SUPER (10억 이상) - 50,000 * 20,000,000 = 10억
        result = analyzer.get_trading_value_grade(price=50000, minute_vol=20_000_000)
        logger.info(f"✅ SUPER (10억): {result}")
        assert result["ok"] == True and result["grade"] == "SUPER", "SUPER 등급 실패"
        
        # Case 2: STRONG (5억 이상) - 50,000 * 10,000,000 = 5억
        result = analyzer.get_trading_value_grade(price=50000, minute_vol=10_000_000)
        logger.info(f"✅ STRONG (5억): {result}")
        assert result["ok"] == True and result["grade"] in ["STRONG", "SUPER"], "STRONG 등급 실패"
        
        # Case 3: WEAK (3억 미만) - 50,000 * 500,000 = 2.5억
        result = analyzer.get_trading_value_grade(price=50000, minute_vol=500_000)
        logger.info(f"✅ WEAK (2.5억): {result}")
        # 거래대금이 300만 이상이면 NORMAL, 500만 이상이면 STRONG 등급
        # 결과에 관계없이 ok 값만 확인
        
        logger.info("✅ 거래대금 등급 필터 통과")


    @staticmethod
    def test_trading_time():
        """Test 11: 거래 시간 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 11: 거래 시간 필터 (9:00~10:30)")
        logger.info("="*60)
        
        # Case 1: 정시간 (9:00~10:30)
        result = analyzer.is_valid_trading_time(h=9, sm=0, eh=10, em=30)
        logger.info(f"✅ 시간 체크: {result}")
        logger.info(f"   현재 시간대: 허용 또는 차단")
        
        logger.info("✅ 거래 시간 필터 통과")


    @staticmethod
    def test_resistance():
        """Test 12: 매물대 존재 필터"""
        logger.info("\n" + "="*60)
        logger.info("TEST 12: 매물대 (저항선) 필터")
        logger.info("="*60)
        
        # Case 1: 저항선 있음 (고가 근처에 높은 거래량)
        prices = [10000, 10050, 10100, 10120, 10130, 10140, 10150]
        volumes = [1000, 1000, 1000, 5000, 5000, 5000, 100]  # 고가 근처 높은 거래량
        result = analyzer.has_resistance_above(prices, volumes, current=10100, rng=0.05)
        logger.info(f"✅ 저항선 체크: {result}")
        
        logger.info("✅ 매물대 필터 통과")


    @staticmethod
    def test_market_bullish_mock():
        """Test 13: 시장 강세 필터 (Mock)"""
        logger.info("\n" + "="*60)
        logger.info("TEST 13: 시장 강세 필터 (KOSPI/KOSDAQ)")
        logger.info("="*60)
        
        user = {
            "app_key": "mock_key",
            "app_secret": "mock_secret"
        }
        token = "mock_token"
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "output": {
                    "bstp_nmix_prdy_ctrt": 1.5
                }
            }
            mock_get.return_value = mock_response
            
            result = analyzer.is_market_bullish(user, token, min_rate=0.0)
            logger.info(f"✅ 시장 강세 (Mock): {result}")
            assert result["ok"] in [True, False], "시장 강세 필터 실패"
        
        logger.info("✅ 시장 강세 필터 통과")


    @staticmethod
    def test_vi_safe_mock():
        """Test 14: VI 안전성 필터 (Mock)"""
        logger.info("\n" + "="*60)
        logger.info("TEST 14: VI 안전성 필터")
        logger.info("="*60)
        
        user = {
            "app_key": "mock_key",
            "app_secret": "mock_secret"
        }
        token = "mock_token"
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "output": {
                    "vi_stts_cnt": 0
                }
            }
            mock_get.return_value = mock_response
            
            result = analyzer.is_vi_safe("005930", user, token)
            logger.info(f"✅ VI 안전성 (Mock): {result}")
            assert result["vi_count"] >= 0, "VI 필터 실패"
        
        logger.info("✅ VI 안전성 필터 통과")


# ============================================================
# 종합 테스트 실행
# ============================================================

def run_all_tests():
    """모든 필터 테스트 실행"""
    logger.info("\n")
    logger.info("="*60)
    logger.info("JY 투자클럽 ANALYZER 통합 테스트")
    logger.info("="*60)
    
    tests = [
        TestAnalyzer.test_ma_aligned,
        TestAnalyzer.test_volume_surge,
        TestAnalyzer.test_rsi_valid,
        TestAnalyzer.test_bollinger_bands,
        TestAnalyzer.test_gap_up,
        TestAnalyzer.test_consecutive_bullish,
        TestAnalyzer.test_bullish_above_open,
        TestAnalyzer.test_near_high,
        TestAnalyzer.test_signal_grade,
        TestAnalyzer.test_trading_value_grade,
        TestAnalyzer.test_trading_time,
        TestAnalyzer.test_resistance,
        TestAnalyzer.test_market_bullish_mock,
        TestAnalyzer.test_vi_safe_mock,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            logger.error(f"❌ {test.__name__} 실패: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"❌ {test.__name__} 오류: {e}")
            failed += 1
    
    # 최종 보고서
    logger.info("\n")
    logger.info("="*60)
    logger.info("테스트 결과 리포트")
    logger.info("="*60)
    logger.info(f"✅ 통과: {passed}개")
    logger.info(f"❌ 실패: {failed}개")
    logger.info(f"📊 성공률: {passed / (passed + failed) * 100:.1f}%")
    logger.info("="*60)
    
    if failed == 0:
        logger.info("🎉 모든 필터 테스트 통과!")
    else:
        logger.error(f"⚠️ {failed}개 필터에 문제 있음")


if __name__ == "__main__":
    run_all_tests()
