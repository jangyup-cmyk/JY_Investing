import logging
import time
from datetime import datetime

import config
import pytest
import stock_data
from kis_api import KISAPIClient
from trader import check_and_cancel_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_order_cancel")

pytestmark = [pytest.mark.integration, pytest.mark.manual]

def run_test():
    try:
        user = config.USERS[1]
        stock_code = "005930"  # 삼성전자
        client = KISAPIClient(user)
        
        if not client.get_access_token():
            logger.error("토큰 발급 실패")
            return

        # 1. 안전한 지정가 설정 (현재가의 80% 수준으로 매우 낮게 설정하여 체결 방지)
        asking = stock_data.fetch_asking_price(stock_code, user)
        current_price = asking.get("current_price", 0)
        
        if current_price <= 0:
            logger.error("현재가 조회 실패")
            return
            
        safe_limit_price = int(current_price) - 500
        
        logger.info(f"=== 1. 안전한 지정가 매수 주문 (체결 방지용) ===")
        logger.info(f"대상: {stock_code}, 수량: 1주, 지정가: {safe_limit_price}원 (현재가 {current_price}원)")
        
        res_limit = client.order_cash(stock_code, 1, safe_limit_price, "00")
        
        if res_limit.get("rt_cd") == "0":
            order_no = res_limit.get("output", {}).get("ODNO", "")
            logger.info(f"✅ 지정가 주문 성공! 주문번호: {order_no}")
            
            # 2. 취소 대기
            logger.info("=== 2. 5초 대기 후 취소 실행 ===")
            time.sleep(5)
            
            # 3. 주문 취소 실행 (trader.py의 로직 직접 호출)
            logger.info("=== 3. 주문 취소(check_and_cancel_order) 실행 ===")
            check_and_cancel_order(user, stock_code, order_no)
            
            logger.info("✅ 전체 흐름(주문 -> 대기 -> 취소) 테스트 완료")
        else:
            logger.error(f"❌ 주문 실패: {res_limit.get('msg1', res_limit)}")
            
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")

if __name__ == "__main__":
    run_test()
