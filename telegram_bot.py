import logging
import threading
import time

import requests

import config

logger = logging.getLogger(__name__)


# ─── 관리자 무음 실패 알림 (admin alert) ──────────────────────────────────────
ADMIN_ALERT_DEDUP_SEC = 30
_ADMIN_ALERT_LOCK = threading.Lock()
_admin_dedup_cache: dict[str, float] = {}
_SEVERITY_ICONS = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}


def _now() -> float:
    """단조 클럭 — 테스트에서 monkeypatch 가능"""
    return time.monotonic()


def send_admin_alert(severity: str, title: str, detail: str = "") -> dict:
    """관리자(TELEGRAM_ADMIN_*)에게 무음 실패 알림.

    severity: 'critical' | 'warning' | 'info' (그 외는 info 로 처리)
    30초 dedup 윈도우 (같은 severity+title+detail 조합은 30초 내 1회만 전송).
    전송 실패 / 예외 발생 시 절대 raise 하지 않고 silent — 매매 흐름 차단 방지.
    """
    if not isinstance(severity, str) or not isinstance(title, str):
        return {"ok": False, "error": "invalid args"}
    if severity not in _SEVERITY_ICONS:
        severity = "info"

    detail = detail or ""
    key = f"{severity}|{title}|{detail[:80]}"
    now = _now()

    with _ADMIN_ALERT_LOCK:
        last = _admin_dedup_cache.get(key, 0.0)
        if now - last < ADMIN_ALERT_DEDUP_SEC:
            return {"ok": False, "deduped": True}
        _admin_dedup_cache[key] = now
        # 오래된 dedup 항목 정리 (메모리 누수 방지)
        cutoff = now - ADMIN_ALERT_DEDUP_SEC * 4
        stale = [k for k, t in _admin_dedup_cache.items() if t < cutoff]
        for k in stale:
            _admin_dedup_cache.pop(k, None)

    icon = _SEVERITY_ICONS[severity]
    text = f"{icon} <b>[{severity.upper()}]</b> {title}"
    if detail:
        text += f"\n\n{detail}"

    try:
        return send_custom_message(
            config.TELEGRAM_ADMIN_BOT_TOKEN,
            config.TELEGRAM_ADMIN_ID,
            text,
        )
    except Exception as exc:
        logger.error(f"send_admin_alert 전송 실패 (silent): {exc}")
        return {"ok": False, "error": str(exc)}


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
