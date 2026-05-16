import logging

import requests

import config

logger = logging.getLogger(__name__)


def send_custom_message(bot_token: str, channel_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            logger.error(f"Telegram HTTP 오류 ({channel_id}): {res.status_code} {res.text[:200]}")
            try:
                body = res.json()
            except ValueError:
                body = {}
            return {"ok": False, "error": f"HTTP {res.status_code}", **body}
        try:
            return res.json()
        except ValueError:
            logger.error(f"Telegram 응답 JSON 파싱 실패 ({channel_id}): {res.text[:200]}")
            return {"ok": False, "error": "invalid json response"}
    except Exception as exc:
        logger.error(f"Telegram 전송 실패 ({channel_id}): {exc}")
        return {"ok": False, "error": str(exc)}


def send_personal_buy_signal(user: dict, stock_name: str, stock_code: str, price: float, rate: float, 
                             market_qty: int = 0, limit_qty: int = 0) -> dict:
    total_budget = user.get("budget", 0)
    market_amt = market_qty * price
    limit_amt = limit_qty * price
    
    text = (
        f"⭐️ Ai 종목매수 시그널 [VIP 전용]\n"
        f"￣￣￣￣￣￣￣￣￣￣￣￣￣￣￣\n"
        f"매수 종목명 : {stock_name} ({stock_code})\n"
        f"매수 가격 : {price:,}원 👉 {rate:.2f}%\n"
        f"총 예산 : {total_budget:,}원\n\n"
        f"[체결 및 대기 상세]\n"
        f"✅ 1차 시장가 체결 : {int(market_amt):,}원 ({market_qty:,}주)\n"
        f"⏳ 2차 지정가 대기 : {int(limit_amt):,}원 ({limit_qty:,}주)\n"
        f"(*10분 후 미체결 시 자동 취소)\n\n"
        f"매수 계좌 : {user['name']} {user['account_no']}계좌"
    )
    return send_custom_message(user["bot_token"], user["channel_id"], text)


def send_personal_cancel_alert(user: dict, stock_code: str, unfilled_qty: int) -> dict:
    text = (
        f"⚠️ [자동취소] {user['name']}님 계좌의 {stock_code} 미체결 지정가 매수({unfilled_qty}주)"
        f"가 10분 경과로 자동 취소되었습니다."
    )
    return send_custom_message(user["bot_token"], user["channel_id"], text)


def send_personal_sell_signal(user: dict, stock_name: str, stock_code: str, sell_price: float, reason: str, pnl_rate: float) -> dict:
    icon = "🔴" if "손절" in reason else "🔵"
    text = (
        f"{icon} Ai 종목매도 시그널 [{reason}]\n"
        f"￣￣￣￣￣￣￣￣￣￣￣￣￣￣￣\n"
        f"매도 종목명 : {stock_name} ({stock_code})\n"
        f"매도 체결가 : {sell_price:,.0f}원\n"
        f"수익률 : {pnl_rate:+.2f}%\n\n"
        f"매도 계좌 : {user['name']} {user['account_no']}계좌"
    )
    return send_custom_message(user["bot_token"], user["channel_id"], text)



def send_admin_message(text: str) -> dict:
    return send_custom_message(config.TELEGRAM_ADMIN_BOT_TOKEN, config.TELEGRAM_ADMIN_ID, text)
