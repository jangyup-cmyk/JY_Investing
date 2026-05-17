#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""환경 설정 검증 스크립트 — .env.local이 올바르게 설정되었는지 확인합니다."""

import os
import sys

# stdout을 UTF-8로 강제 설정 (Windows cp949 환경 대응)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local", override=False)

print("\n" + "=" * 70)
print("[CHECK] JY 투자클럽 환경 설정 검증")
print("=" * 70 + "\n")

required_vars = {
    # 계좌 1
    "KIS_ACCOUNT_NO_JY_Investing1":     "계좌1 계좌번호",
    "KIS_APP_KEY_JY1":                  "계좌1 API Key",
    "KIS_APP_SECRET_JY1":               "계좌1 API Secret",
    "TELEGRAM_BOT_TOKEN_JY_Investing1": "계좌1 봇 토큰",
    # 계좌 2
    "KIS_ACCOUNT_NO_JY_Investing2":     "계좌2 계좌번호",
    "KIS_APP_KEY_JY2":                  "계좌2 API Key",
    "KIS_APP_SECRET_JY2":               "계좌2 API Secret",
    "TELEGRAM_BOT_TOKEN_JY_Investing2": "계좌2 봇 토큰",
    # 공통
    "TELEGRAM_ADMIN_BOT_TOKEN":         "관리자 봇 토큰",
    "TELEGRAM_ADMIN_CHAT_ID":           "관리자 Chat ID",
}

passed = failed = warnings = 0

print("[1] 필수 환경 변수 검증\n")

for var, description in required_vars.items():
    value = os.getenv(var)

    if value is None:
        print(f"  [FAIL] {var:<42} -> 미설정  ({description})")
        failed += 1
    elif value.startswith("your_") or value in ("YOUR_BOT_TOKEN", ""):
        print(f"  [WARN] {var:<42} -> 기본값 미변경  ({description})")
        warnings += 1
    else:
        if any(k in var for k in ("TOKEN", "SECRET", "KEY")):
            display = value[:8] + "..." + value[-4:] if len(value) > 14 else "***"
        else:
            display = value
        print(f"  [ OK ] {var:<42} -> {display}")
        passed += 1

print(f"\n{'='*70}")
print(f"[결과] 정상 {passed} / 경고 {warnings} / 오류 {failed}")
print(f"{'='*70}\n")

if failed > 0:
    print("[ERROR] 설정이 필요합니다!")
    print("   1. .env.example -> .env.local 복사 후 실제 값 입력")
    print("   2. 다시 실행: python check_config.py")
    sys.exit(1)
elif warnings > 0:
    print("[WARN] 기본값이 남아 있습니다. .env.local을 편집하세요.")
    sys.exit(1)
else:
    print("[OK] 모든 환경 변수 정상 — 다음 단계:")
    print("   python check_kis_api.py    # KIS API 실계좌 연결 확인")
    print("   python main.py             # 시스템 시작")
    sys.exit(0)
