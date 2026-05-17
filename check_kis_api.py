"""
KIS API 실계좌 연결 검증 스크립트 (읽기 전용 — 주문 없음)

확인 항목:
  1. 토큰 발급
  2. 잔고 조회
  3. KOSPI 지수 조회

실행:
    .\\venv\\Scripts\\python.exe check_kis_api.py
"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import config
from kis_api import KISAPIClient


def check_user(user: dict):
    name = user["name"]
    print(f"\n{'='*50}")
    print(f"  계좌: {name}  ({user['account_no']})")
    print(f"{'='*50}")

    client = KISAPIClient(user)

    # 1. 토큰 발급
    print("\n[1] 토큰 발급...")
    ok = client.get_access_token()
    if not ok:
        print("  FAIL 토큰 발급 실패 — app_key/app_secret 확인 필요")
        return
    print(f"  OK 토큰 발급 성공")

    # 2. 잔고 조회
    print("\n[2] 잔고 조회...")
    data = client.get_balance()
    if not data or "output2" not in data:
        print(f"  FAIL 잔고 조회 실패: {data}")
        return

    output2 = data.get("output2", [{}])
    summary = output2[0] if output2 else {}
    tot_eval   = int(summary.get("tot_evlu_amt", 0))
    tot_buy    = int(summary.get("pchs_amt_smtl_amt", 0))
    available  = int(summary.get("prvs_rcdl_excc_amt", 0))
    pnl        = int(summary.get("evlu_pfls_smtl_amt", 0))
    pnl_rate   = (pnl / tot_buy * 100) if tot_buy else 0.0

    print(f"  OK 잔고 조회 성공")
    print(f"     총 평가금액  : {tot_eval:>15,} 원")
    print(f"     총 매입금액  : {tot_buy:>15,} 원")
    print(f"     평가 손익    : {pnl:>+15,} 원  ({pnl_rate:+.2f}%)")
    print(f"     주문가능금액 : {available:>15,} 원")

    # 보유 종목
    holdings = data.get("output1", [])
    if holdings:
        print(f"\n  보유 종목 ({len(holdings)}개):")
        for h in holdings:
            code  = h.get("pdno", "")
            hname = h.get("prdt_name", "")
            qty   = int(h.get("hldg_qty", 0))
            avg   = float(h.get("pchs_avg_pric", 0))
            curr  = float(h.get("prpr", 0))
            rate  = float(h.get("evlu_pfls_rt", 0))
            print(f"     {code} {hname:<15} {qty:>5}주  매입:{avg:>8,.0f}  현재:{curr:>8,.0f}  ({rate:+.2f}%)")
    else:
        print("  보유 종목 없음")

    # 3. KOSPI 지수 (공통 — 첫 번째 계좌에서만)
    if user == config.USERS[0]:
        print("\n[3] 시장 지수 조회...")
        kospi = client.get_index_price("0001")
        kosdaq = client.get_index_price("1001")
        if kospi:
            print(f"  KOSPI  : {float(kospi.get('bstp_nmix_prpr', 0)):>8,.2f}  ({float(kospi.get('bstp_nmix_prdy_ctrt', 0)):+.2f}%)")
        if kosdaq:
            print(f"  KOSDAQ : {float(kosdaq.get('bstp_nmix_prpr', 0)):>8,.2f}  ({float(kosdaq.get('bstp_nmix_prdy_ctrt', 0)):+.2f}%)")


if __name__ == "__main__":
    print("KIS API 실계좌 연결 검증 (읽기 전용)")
    for user in config.USERS:
        check_user(user)
    print("\n\nOK 검증 완료")

