import logging
import math
from datetime import datetime, timedelta

import config
import telegram_bot as bot
from kis_api import KISAPIClient
from scheduler import scheduler

logger = logging.getLogger(__name__)


def execute_split_buy(user: dict, stock_code: str, current_price: float, bull_score: float = 0.5) -> dict | None:
    """bull_score에 따른 동적 비중 분할 매수 주문 (시장가 + 지정가)"""
    budget = user["budget"]
    
    # 강력 매수(Strong Bull, 0.7 이상)일 경우 시장가 비중을 70%로 확대, 일반(0.6대)이면 시장가 40%
    if bull_score >= 0.70:
        market_ratio = 0.7
        logger.info(f"[{stock_code}] 강력 매수 (Score: {bull_score:.2f}) -> 시장가 70%, 지정가 30% 진입")
    else:
        market_ratio = 0.4
        logger.info(f"[{stock_code}] 일반 매수 (Score: {bull_score:.2f}) -> 시장가 40%, 지정가 60% 진입")
        
    market_budget = budget * market_ratio
    limit_budget = budget * (1.0 - market_ratio)
    
    qty_market = math.floor(market_budget / current_price)
    qty_limit = math.floor(limit_budget / current_price)
    
    if qty_market <= 0 and qty_limit <= 0:
        logger.warning(f"수량 계산 실패 (예산 부족): market_qty={qty_market}, limit_qty={qty_limit}")
        return None

    kis_client = KISAPIClient(user)

    # 토큰 갱신 및 유효성 확인
    if not kis_client.get_access_token() or not kis_client.access_token:
        logger.error(f"{user['name']} 토큰 발급 실패 또는 빈 토큰 — API 호출 중단")
        return None

    # 시장가 매수
    res_market = kis_client.order_cash(stock_code, qty_market, 0, "01")
    market_success = res_market.get("rt_cd") == "0"
    market_order_no = res_market.get("output", {}).get("ODNO", "") if market_success else ""

    if not market_success:
        logger.warning(f"시장가 주문 실패 ({user['name']}): {stock_code} — {res_market.get('msg_text', '')}")
    logger.info(f"시장가 주문 ({user['name']}): {stock_code} {qty_market}주 - {'성공' if market_success else '실패'}")

    # 지정가 매수
    res_limit = kis_client.order_cash(stock_code, qty_limit, current_price, "00")
    limit_success = res_limit.get("rt_cd") == "0"
    limit_order_no = res_limit.get("output", {}).get("ODNO", "") if limit_success else ""

    if not limit_success:
        logger.warning(f"지정가 주문 실패 ({user['name']}): {stock_code} — {res_limit.get('msg_text', '')}")

    logger.info(f"지정가 주문 ({user['name']}): {stock_code} {qty_limit}주 @ {int(current_price)}원 - {'성공' if limit_success else '실패'}")

    # 부분 실패(market XOR limit) 또는 양쪽 실패 시 관리자 알림
    if not (market_success and limit_success):
        try:
            failed_legs = []
            if not market_success:
                failed_legs.append(f"시장가({qty_market}주) {res_market.get('msg_text','')}")
            if not limit_success:
                failed_legs.append(f"지정가({qty_limit}주 @{int(current_price)}) {res_limit.get('msg_text','')}")
            severity = "critical" if not (market_success or limit_success) else "warning"
            bot.send_admin_alert(
                severity,
                "분할 매수 부분/전체 실패",
                f"{user['name']} | {stock_code}\n" + "\n".join(failed_legs),
            )
        except Exception as _exc:
            logger.error(f"매수 부분실패 알림 전송 실패 (silent): {_exc}")

    # 10분 뒤 미체결 취소 스케줄 등록
    if limit_order_no:
        cancel_time = datetime.now() + timedelta(minutes=10)
        scheduler.add_job(
            check_and_cancel_order,
            trigger="date",
            run_date=cancel_time,
            args=[user, stock_code, limit_order_no],
        )

    return {
        "name": user["name"],
        "account": user["account_no"],
        "market_qty": qty_market,
        "limit_qty": qty_limit,
        "market_order_no": market_order_no,
        "limit_order_no": limit_order_no,
    }


def check_and_cancel_order(user: dict, stock_code: str, order_no: str) -> None:
    """10분 뒤 미체결 주문 취소"""
    kis_client = KISAPIClient(user)

    # 토큰 갱신
    if not kis_client.get_access_token():
        logger.error(f"{user['name']} 토큰 발급 실패")
        return

    # 주문 취소 (미체결 수량 자동 계산)
    res = kis_client.cancel_order(order_no, qty=0)
    if res.get("rt_cd") == "0":
        logger.info(f"주문 취소 성공 ({user['name']}): {order_no}")
        bot.send_personal_cancel_alert(user, stock_code, 0)
    else:
        logger.error(f"주문 취소 실패 ({user['name']}): {order_no} - {res.get('msg_text', '')}")


def trade_and_notify(user: dict, stock: dict, bull_score: float = 0.5) -> dict | None:
    import position_tracker
    import config

    result = execute_split_buy(user, stock["code"], stock["price"], bull_score)
    if result:
        # 분할 매수에 따른 실제 수량 재계산 결과 사용 (이전은 예산을 50% 고정으로 알림 보냄)
        market_qty = result.get("market_qty", 0)
        limit_qty = result.get("limit_qty", 0)
        
        # 텔레그램 메시지는 현재 고정 텍스트를 사용하고 있지만, 향후 개선 가능.
        # 일단은 기존 함수 그대로 호출 (기존 텔레그램 함수가 budget/2로 계산하는 로직은 나중에 분리 필요)
        bot.send_personal_buy_signal(
            user=user,
            stock_name=stock.get("name", stock["code"]),
            stock_code=stock["code"],
            price=stock["price"],
            rate=stock.get("change_rate", 0.0),
            market_qty=market_qty,
            limit_qty=limit_qty
        )
        
        # Calculate stop loss and take profit
        buy_price = stock["price"]
        stop_loss = buy_price * (1.0 - config.STOP_LOSS_RATE)
        take_profit = buy_price * (1.0 + config.TAKE_PROFIT_RATE)
        
        # Total qty is market + limit (assuming both will be filled for tracking)
        total_qty = result.get("market_qty", 0) + result.get("limit_qty", 0)
        
        position_tracker.add_position(
            account_no=user["account_no"],
            stock_code=stock["code"],
            buy_price=buy_price,
            qty=total_qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            stock_name=stock.get("name", stock["code"])
        )
        
    return result


def process_signals_and_trade(stock: dict) -> list:
    results = []
    for user in config.USERS:
        result = trade_and_notify(user, stock)
        if result:
            results.append(result)
    return results
