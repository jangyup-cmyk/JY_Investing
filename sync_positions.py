#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sync_positions.py — 실계좌 보유 종목을 positions.json에 동기화

KIS API에서 현재 보유 종목을 읽어 positions.json에 없는 항목을 추가합니다.
이미 추적 중인 종목은 건드리지 않습니다(stop_loss/take_profit 보존).

실행:
    python sync_positions.py
"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import config
import position_tracker
from kis_api import KISAPIClient


def sync_user(user: dict) -> int:
    name = user["name"]
    account_no = user["account_no"]
    print(f"\n{'='*55}")
    print(f"  계좌: {name}  ({account_no})")
    print(f"{'='*55}")

    client = KISAPIClient(user)

    token = client.get_access_token()
    if not token:
        print("  [FAIL] 토큰 발급 실패 — 건너뜀")
        return 0

    data = client.get_balance()
    if not data or "output1" not in data:
        print(f"  [FAIL] 잔고 조회 실패: {data}")
        return 0

    holdings = data.get("output1", [])
    if not holdings:
        print("  보유 종목 없음")
        return 0

    existing = {p["stock_code"] for p in position_tracker.get_open_positions()
                if p["account_no"] == account_no}

    added = 0
    for h in holdings:
        code  = h.get("pdno", "")
        hname = h.get("prdt_name", code)
        qty   = int(h.get("hldg_qty", 0))
        avg   = float(h.get("pchs_avg_pric", 0))

        if not code or qty <= 0 or avg <= 0:
            continue

        stop_loss   = round(avg * (1 - config.STOP_LOSS_RATE))
        take_profit = round(avg * (1 + config.TAKE_PROFIT_RATE))

        if code in existing:
            print(f"  [SKIP] {code} {hname:<14} — 이미 추적 중")
            continue

        position_tracker.add_position(
            account_no=account_no,
            stock_code=code,
            buy_price=avg,
            qty=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            stock_name=hname,
        )
        print(
            f"  [ OK] {code} {hname:<14} {qty:>4}주  "
            f"매입평균={avg:>8,.0f}  손절={stop_loss:>8,.0f}  익절={take_profit:>8,.0f}"
        )
        added += 1

    return added


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("[SYNC] 실계좌 보유 종목 → positions.json 동기화")
    print("=" * 55)

    total = 0
    for user in config.USERS:
        total += sync_user(user)

    print(f"\n{'='*55}")
    print(f"[완료] 총 {total}개 종목 추가됨")
    print(f"{'='*55}")
    if total > 0:
        print("\n[주의] 동기화된 손절/익절가는 현재 평균매입가 기준 추정치입니다.")
        print("       실제 운용 기준에 맞게 positions.json을 검토·수정하세요.")
