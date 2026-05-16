import config
import telegram_bot as bot
import logging
import os
import sys
import pytest

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.manual,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS", "").lower() != "true",
        reason="set RUN_INTEGRATION_TESTS=true to send real Telegram messages",
    ),
]

def test_telegram():
    try:
        user = config.USERS[0]
        
        print("=== 매수 시그널 테스트 ===")
        res1 = bot.send_personal_buy_signal(user, "삼성전자", "005930", 80000, 1.5)
        print(f"결과: {res1}\n")
        
        print("=== 미체결 취소 알림 테스트 ===")
        res2 = bot.send_personal_cancel_alert(user, "005930", 10)
        print(f"결과: {res2}\n")
        
        print("=== 매도(익절/손절) 시그널 테스트 ===")
        res3 = bot.send_personal_sell_signal(user, "삼성전자", "005930", 88000, "익절 조건 도달", 10.0)
        print(f"결과: {res3}\n")
        
        print("=== 관리자 알림 테스트 ===")
        res4 = bot.send_admin_message("이것은 관리자용 테스트 알림입니다.")
        print(f"결과: {res4}\n")
        
        print("✅ 텔레그램 알림 발송 테스트 완료!")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    test_telegram()
