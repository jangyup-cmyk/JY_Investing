#!/usr/bin/env python
"""
환경 설정 검증 스크립트

이 스크립트는 .env 파일이 올바르게 설정되었는지 확인합니다.
"""

import os
import sys
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

print("\n" + "=" * 70)
print("🔍 JY 투자클럽 환경 설정 검증")
print("=" * 70 + "\n")

# 검증할 환경 변수 목록
required_vars = {
    "KIS_APP_KEY_JY": "전장엽님 API Key",
    "KIS_APP_SECRET_JY": "전장엽님 API Secret",
    "KIS_ACCOUNT_NO_JY": "전장엽님 계좌번호",
    "TELEGRAM_BOT_TOKEN_JY": "전장엽님 봇 토큰",
    "TELEGRAM_CHANNEL_ID_JY": "전장엽님 채널 ID",
    "KIS_APP_KEY_YS": "김양선님 API Key",
    "KIS_APP_SECRET_YS": "김양선님 API Secret",
    "KIS_ACCOUNT_NO_YS": "김양선님 계좌번호",
    "TELEGRAM_BOT_TOKEN_YS": "김양선님 봇 토큰",
    "TELEGRAM_CHANNEL_ID_YS": "김양선님 채널 ID",
    "TELEGRAM_ADMIN_BOT_TOKEN": "관리자 봇 토큰",
    "TELEGRAM_ADMIN_CHAT_ID": "관리자 Chat ID",
}

passed = 0
failed = 0
warnings = 0

print("1️⃣ 필수 환경 변수 검증\n")

for var, description in required_vars.items():
    value = os.getenv(var)
    
    if value is None:
        print(f"❌ {var:<30} → 미설정")
        print(f"   설명: {description}")
        failed += 1
    elif value.startswith("your_") or value == "YOUR_BOT_TOKEN":
        print(f"⚠️  {var:<30} → 기본값 (설정 필요)")
        print(f"   현재값: {value}")
        warnings += 1
    else:
        # 토큰은 일부만 표시 (보안)
        if "TOKEN" in var or "SECRET" in var or "KEY" in var:
            display_value = value[:10] + "..." + value[-5:] if len(value) > 20 else "***"
        else:
            display_value = value
        print(f"✅ {var:<30} → {display_value}")
        passed += 1
    print()

print("\n" + "=" * 70)
print("📊 검증 결과")
print("=" * 70)
print(f"✅ 정상: {passed}")
print(f"⚠️  경고: {warnings}")
print(f"❌ 오류: {failed}")
print()

if failed > 0:
    print("🚨 설정이 필요합니다!")
    print("\n해결 방법:")
    print("1. .env 파일 생성: copy .env.example .env  (또는 cp .env.example .env)")
    print("2. .env 파일 편집: 실제 API 키와 토큰 입력")
    print("3. 다시 실행: python check_config.py")
    sys.exit(1)

elif warnings > 0:
    print("⚠️  경고: 기본값 설정이 남아있습니다.")
    print("\n해결 방법:")
    print("1. .env 파일 편집")
    print("2. 'your_'로 시작하는 값들을 실제 값으로 변경")
    print("3. 파일 저장 후 다시 실행: python check_config.py")
    sys.exit(1)

else:
    print("✅ 모든 환경 변수가 올바르게 설정되었습니다!")
    print("\n다음 단계:")
    print("1. 데이터 수집 테스트: python test_stock_data.py")
    print("2. 전체 시스템 실행: python main.py")
    sys.exit(0)
