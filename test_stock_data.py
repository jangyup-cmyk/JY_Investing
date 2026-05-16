import json
import logging
import os
from datetime import datetime

import config
import pytest
from kis_api import KISAPIClient
from stock_data import (
    fetch_asking_price,
    fetch_balance,
    fetch_daily_ohlcv,
    fetch_daily_prices,
    fetch_previous_close,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS", "").lower() != "true",
        reason="set RUN_INTEGRATION_TESTS=true to run KIS API integration tests",
    ),
]


def test_token_refresh():
    """토큰 발급 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 1: 토큰 발급 테스트")
    logger.info("=" * 60)
    
    for user in config.USERS:
        kis_client = KISAPIClient(user)
        success = kis_client.get_access_token()
        if success:
            logger.info(f"✅ {user['name']} 토큰 발급 성공")
            logger.info(f"   Token: {kis_client.access_token[:20]}...")
        else:
            logger.error(f"❌ {user['name']} 토큰 발급 실패")
    
    logger.info("")


def test_fetch_balance():
    """잔고 조회 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 2: 잔고 조회 테스트")
    logger.info("=" * 60)
    
    user = config.USERS[0]
    balance = fetch_balance(user)
    
    logger.info(f"계좌: {user['name']} ({user['account_no']})")
    logger.info(f"총 평가액: {balance.get('total_balance', 0):,}원")
    logger.info(f"사용 가능 금액: {balance.get('available_balance', 0):,}원")
    logger.info(f"총 매수금액: {balance.get('total_buy_amount', 0):,}원")
    logger.info(f"총 평가금액: {balance.get('total_eval_amount', 0):,}원")
    
    logger.info("")


def test_fetch_daily_prices():
    """일봉 데이터 조회 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 3: 일봉 가격 데이터 조회 (최근 5일)")
    logger.info("=" * 60)
    
    user = config.USERS[0]
    stock_codes = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, KakaoTalk
    
    for code in stock_codes:
        prices = fetch_daily_prices(code, user, count=5)
        if prices:
            logger.info(f"종목: {code}")
            logger.info(f"  가격 데이터 (최근순): {prices[-5:]}")
        else:
            logger.warning(f"종목: {code} - 데이터 없음")
    
    logger.info("")


def test_fetch_daily_ohlcv():
    """일봉 OHLCV 데이터 조회 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 4: 일봉 OHLCV 데이터 조회 (최근 5일)")
    logger.info("=" * 60)
    
    user = config.USERS[0]
    stock_code = "005930"  # 삼성전자
    
    ohlcv = fetch_daily_ohlcv(stock_code, user, count=5)
    
    if ohlcv["closes"]:
        logger.info(f"종목: {stock_code}")
        logger.info(f"  개수: {len(ohlcv['closes'])}")
        
        for i in range(min(5, len(ohlcv["closes"]))):
            logger.info(
                f"  [{i}] O:{ohlcv['opens'][i]:,.0f} "
                f"H:{ohlcv['highs'][i]:,.0f} "
                f"L:{ohlcv['lows'][i]:,.0f} "
                f"C:{ohlcv['closes'][i]:,.0f} "
                f"V:{ohlcv['volumes'][i]:,}"
            )
    else:
        logger.warning(f"종목: {stock_code} - 데이터 없음")
    
    logger.info("")


def test_fetch_asking_price():
    """호가 데이터 조회 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 5: 현재 호가 조회")
    logger.info("=" * 60)
    
    user = config.USERS[0]
    stock_codes = ["005930", "000660"]  # 삼성전자, SK하이닉스
    
    for code in stock_codes:
        asking = fetch_asking_price(code, user)
        if asking["current_price"] > 0:
            logger.info(f"종목: {code}")
            logger.info(f"  현재가: {asking['current_price']:,.0f}원")
            logger.info(f"  매도호가: {asking['bid1']:,.0f}원 ({asking['bid1_qty']:,}주)")
            logger.info(f"  매수호가: {asking['ask1']:,.0f}원 ({asking['ask1_qty']:,}주)")
        else:
            logger.warning(f"종목: {code} - 데이터 없음")
    
    logger.info("")


def test_fetch_previous_close():
    """전일 종가 조회 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 6: 전일 종가 조회")
    logger.info("=" * 60)
    
    user = config.USERS[0]
    stock_codes = ["005930", "000660", "035720"]
    
    for code in stock_codes:
        prev_close = fetch_previous_close(code, user)
        if prev_close > 0:
            logger.info(f"종목: {code} - 전일 종가: {prev_close:,.0f}원")
        else:
            logger.warning(f"종목: {code} - 데이터 없음")
    
    logger.info("")


def test_analyzer_with_data():
    """수집된 데이터로 13대 필터 테스트"""
    logger.info("=" * 60)
    logger.info("TEST 7: 수집 데이터로 13대 필터 검증 테스트")
    logger.info("=" * 60)
    
    import analyzer
    
    user = config.USERS[0]
    stock_code = "005930"
    
    # 필요한 데이터 수집
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error("토큰 발급 실패")
        return
    
    daily_data = kis_client.get_daily_price(stock_code, count=100)
    if not daily_data:
        logger.warning("일봉 데이터 없음")
        return
    
    # 데이터 정렬 (오래된 것부터)
    daily_data = sorted(daily_data, key=lambda x: x.get("stck_bsop_date", ""))
    
    # 최신 데이터
    latest = daily_data[-1]
    current_price = float(latest.get("stck_clpr", 0))
    open_price = float(latest.get("stck_oprc", 0))
    high_price = float(latest.get("stck_hgpr", 0))
    low_price = float(latest.get("stck_lwpr", 0))
    
    # 전일 데이터
    prev_close = float(daily_data[-2].get("stck_clpr", 0)) if len(daily_data) > 1 else current_price
    
    # 데이터 추출
    daily_prices = [float(d.get("stck_clpr", 0)) for d in daily_data[-60:]]
    daily_opens = [float(d.get("stck_oprc", 0)) for d in daily_data[-60:]]
    daily_closes = [float(d.get("stck_clpr", 0)) for d in daily_data[-60:]]
    daily_volumes = [int(d.get("acml_vol", 0)) for d in daily_data[-60:]]
    minute_vols = [int(d.get("acml_vol", 0)) for d in daily_data[-11:]]
    
    # 테스트 stock 객체
    stock = {
        "code": stock_code,
        "name": "삼성전자",
        "price": current_price,
        "change_rate": ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0,
    }
    
    logger.info(f"종목: {stock['name']} ({stock_code})")
    logger.info(f"현재가: {current_price:,.0f}원")
    logger.info(f"등락률: {stock['change_rate']:.2f}%")
    
    # 13대 필터 검증
    result = analyzer.is_valid_stock_final(
        stock=stock,
        open_price=open_price,
        high_price=high_price,
        prev_close=prev_close,
        daily_prices=daily_prices,
        daily_opens=daily_opens,
        daily_closes=daily_closes,
        daily_volumes=daily_volumes,
        minute_vols=minute_vols,
        user=user,
        token=kis_client.access_token,
    )
    
    if result["pass"]:
        logger.info("✅ 매매 신호 통과!")
        logger.info(f"   신호 등급: {result.get('grade', 'NONE')}")
        logger.info(f"   RSI: {result.get('rsi', 'N/A')}")
        logger.info(f"   BB 비율: {result.get('bb_ratio', 'N/A')}")
    else:
        logger.info(f"❌ 신호 필터 탈락: {result.get('reason', 'Unknown')}")
    
    logger.info("")


def run_all_tests():
    """모든 테스트 실행"""
    logger.info("\n" + "=" * 60)
    logger.info("JY 투자클럽 데이터 수집 테스트 시작")
    logger.info(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60 + "\n")
    
    try:
        test_token_refresh()
        test_fetch_balance()
        test_fetch_daily_prices()
        test_fetch_daily_ohlcv()
        test_fetch_asking_price()
        test_fetch_previous_close()
        test_analyzer_with_data()
        
        logger.info("=" * 60)
        logger.info("✅ 모든 테스트 완료")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ 테스트 중 오류 발생: {e}", exc_info=True)


if __name__ == "__main__":
    run_all_tests()
