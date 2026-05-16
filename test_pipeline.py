import logging
import os
import sys
import pytest

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_pipeline")

pytestmark = [pytest.mark.integration, pytest.mark.manual]

def run_test():
    try:
        import config
        from scheduler import run_signal_pipeline, monitor_positions
        from kis_api import KISAPIClient
        
        # 1. KIS API 연결 및 잔고 확인 (테스트)
        logger.info("=== 1. API 연결 및 잔고 테스트 ===")
        for user in config.USERS:
            client = KISAPIClient(user)
            if client.get_access_token():
                logger.info(f"[{user['name']}] 토큰 갱신 성공")
                balance = client.get_balance()
                if balance and "output1" in balance:
                    tot_evlu_amt = balance.get("output2", [{}])[0].get("tot_evlu_amt", "0")
                    logger.info(f"[{user['name']}] 총 평가 금액: {int(tot_evlu_amt):,}원")
                else:
                    logger.warning(f"[{user['name']}] 잔고 조회 실패: {balance}")
            else:
                logger.error(f"[{user['name']}] 토큰 갱신 실패")
        
        # 2. 강제 파이프라인 1회 실행
        logger.info("\n=== 2. 매매 시그널 파이프라인 강제 실행 ===")
        test_watch_list = ["005930"] # 삼성전자 고정 테스트
        logger.info(f"테스트 대상 종목: {test_watch_list}")
        run_signal_pipeline(stock_codes=test_watch_list)
        
        # 3. 모니터링 강제 1회 실행
        logger.info("\n=== 3. 포지션 모니터링 강제 실행 ===")
        monitor_positions()
        
        logger.info("\n✅ 테스트 스크립트 실행 완료")
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    run_test()
