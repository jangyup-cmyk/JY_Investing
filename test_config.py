#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""config.py 로드 검증"""

from config import USERS

print("✓ config.py 로드 성공!")
print(f"계정 1: {USERS[0]['name']} - {USERS[0]['account_no']}")
print(f"계정 2: {USERS[1]['name']} - {USERS[1]['account_no']}")
print("\n✓ 환경 변수 설정 완료! 3단계 해결됨!")
