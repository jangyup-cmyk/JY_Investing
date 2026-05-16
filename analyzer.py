import math
from datetime import datetime

import numpy as np
import pytz
import talib

import config
from kis_api import KISAPIClient


def is_ma_aligned(prices: list) -> bool:
    if len(prices) < 60:
        return False
    arr = np.array(prices, dtype=float)
    return arr[-1] > talib.SMA(arr, 5)[-1] > talib.SMA(arr, 20)[-1] > talib.SMA(arr, 60)[-1]


def is_volume_surge(minute_vols: list, threshold: int = 500) -> bool:
    if len(minute_vols) < 11:
        return False
    avg = sum(minute_vols[-11:-1]) / 10
    return (minute_vols[-1] / avg * 100) >= threshold if avg > 0 else False


def has_resistance_above(prices: list, volumes: list, current: float, rng: float = 0.05) -> bool:
    upper = current * (1 + rng)
    res_vol = sum(v for p, v in zip(prices, volumes) if current < p <= upper)
    total = sum(volumes)
    return (res_vol / total) > 0.20 if total > 0 else False


def is_bullish_above_open(current: float, open_p: float, min_gain: float = 1.0) -> bool:
    if open_p <= 0:
        return False
    return (current - open_p) / open_p * 100 >= min_gain


def is_near_high(current: float, high: float, threshold: float = 0.98) -> bool:
    return (current / high) >= threshold if high > 0 else False


def get_signal_grade(current: float, high: float) -> str:
    if high <= 0:
        return "NONE"
    ratio = current / high
    if ratio >= 1.0:
        return "BREAK"
    if ratio >= 0.99:
        return "STRONG"
    if ratio >= 0.98:
        return "NORMAL"
    return "NONE"


def get_trading_value_grade(price: float, minute_vol: int) -> dict:
    val = price * minute_vol
    if val >= 1_000_000_000:
        grade = "SUPER"
    elif val >= 500_000_000:
        grade = "STRONG"
    elif val >= 300_000_000:
        grade = "NORMAL"
    else:
        grade = "WEAK"
    return {"val_ok": round(val / 1e8, 1), "grade": grade, "ok": grade != "WEAK"}


def is_rsi_valid(prices: list, rsi_min: float = 40.0, rsi_max: float = 70.0) -> dict:
    if len(prices) < 15:
        return {"ok": False, "rsi": None}
    arr = np.array(prices, dtype=float)
    rsi = talib.RSI(arr, timeperiod=14)[-1]
    if math.isnan(rsi):
        return {"ok": False, "rsi": None}
    return {"ok": rsi_min <= rsi <= rsi_max, "rsi": round(rsi, 1)}


def is_near_bollinger_upper(prices: list, period: int = 20, nbdev: float = 2.0, threshold: float = 0.99) -> dict:
    if len(prices) < period + 1:
        return {"ok": False, "ratio": None}
    arr = np.array(prices, dtype=float)
    upper, _, _ = talib.BBANDS(arr, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)
    ratio = arr[-1] / upper[-1] if upper[-1] > 0 else 0
    return {"ok": ratio >= threshold, "ratio": round(ratio, 4)}


def is_gap_up(open_price: float, prev_close: float, min_gap: float = 1.0) -> dict:
    if prev_close <= 0:
        return {"ok": False, "gap_rate": None}
    gap_rate = (open_price - prev_close) / prev_close * 100
    return {"ok": gap_rate >= min_gap, "gap_rate": round(gap_rate, 2)}


def is_consecutive_bullish(daily_opens: list, daily_closes: list, required_days: int = 2) -> dict:
    if len(daily_opens) < required_days:
        return {"ok": False, "count": 0}
    count = 0
    for i in range(1, required_days + 1):
        if daily_closes[-i] > daily_opens[-i]:
            count += 1
        else:
            break
    return {"ok": count >= required_days, "count": count}


def is_valid_trading_time(h: int = 9, sm: int = 0, eh: int = 10, em: int = 30) -> dict:
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    current = now.hour * 60 + now.minute
    ok = (h * 60 + sm) <= current <= (eh * 60 + em)
    return {"ok": ok, "reason": "허용" if ok else "차단"}


def is_market_bullish(user: dict, token: str = "", min_rate: float = -1.0) -> dict:
    """KOSPI/KOSDAQ 지수 확인 (KISAPIClient 사용)"""
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    if not user or not isinstance(user, dict):
        _logger.error("is_market_bullish: user가 None 또는 dict가 아님 — 장 상태 확인 불가")
        return {"ok": True, "kospi": 0.0, "kosdaq": 0.0}  # API 불가 시 차단하지 않음

    kis_client = KISAPIClient(user)
    results = {}
    for name, code in {"KOSPI": "0001", "KOSDAQ": "1001"}.items():
        try:
            data = kis_client.get_index_price(code)
            if not data or not isinstance(data, dict):
                _logger.warning(f"is_market_bullish: {name} 지수 데이터 비어있음 (API 오류 가능) — 0.0 처리")
                results[name] = 0.0
                continue
            raw = data.get("bstp_nmix_prdy_ctrt")
            if raw is None:
                _logger.warning(f"is_market_bullish: {name} 등락률 필드 누락 — 0.0 처리")
                results[name] = 0.0
            else:
                results[name] = float(raw)
        except (ValueError, TypeError) as e:
            _logger.error(f"is_market_bullish: {name} 등락률 변환 실패: {e} — 0.0 처리")
            results[name] = 0.0
        except Exception as e:
            _logger.error(f"is_market_bullish: {name} 지수 조회 예외: {e} — 0.0 처리")
            results[name] = 0.0
    worst = min(results.values()) if results else 0.0
    return {"ok": worst >= min_rate, "kospi": results.get("KOSPI", 0.0), "kosdaq": results.get("KOSDAQ", 0.0)}


def is_vi_safe(stock_code: str, user: dict, token: str = "") -> dict:
    """VI(변동성 완화장치) 발동 여부 확인 (KISAPIClient 사용)"""
    kis_client = KISAPIClient(user)
    try:
        data = kis_client.get_vi_status(stock_code)
        vi_count = int(data.get("vi_stts_cnt", 0))
        return {"ok": vi_count == 0, "vi_count": vi_count}
    except Exception:
        return {"ok": True, "vi_count": -1}


def is_valid_stock_final(
    stock: dict,
    open_price: float,
    high_price: float,
    prev_close: float,
    daily_prices: list,
    daily_opens: list,
    daily_closes: list,
    daily_volumes: list,
    minute_vols: list,
    user: dict,
    token: str,
) -> dict:
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    if not stock or not isinstance(stock, dict):
        _logger.error("is_valid_stock_final: stock이 None 또는 dict가 아님")
        return {"pass": False, "reason": "stock 입력값 오류"}
    if not user or not isinstance(user, dict):
        _logger.error(f"is_valid_stock_final: user가 None 또는 dict가 아님 (stock={stock.get('code', '?')})")
        return {"pass": False, "reason": "user 입력값 오류"}
    if not isinstance(daily_prices, list):
        _logger.error(f"is_valid_stock_final: daily_prices가 list가 아님 ({type(daily_prices).__name__})")
        return {"pass": False, "reason": "daily_prices 입력값 오류"}

    f = config.FILTER
    cp = stock.get("price")
    if not cp or cp <= 0:
        return {"pass": False, "reason": "유효하지 않은 현재가"}

    if not (f["min_change_rate"] <= stock["change_rate"] <= f["max_change_rate"]):
        return {"pass": False, "reason": "등락률 범위 초과"}
    if not (f["min_price"] <= cp <= f["max_price"]):
        return {"pass": False, "reason": "주가 범위 초과"}
    if not is_ma_aligned(daily_prices):
        return {"pass": False, "reason": "정배열 미충족"}
    if not is_valid_trading_time(f["signal_start_hour"], f["signal_start_min"], f["signal_end_hour"], f["signal_end_min"])["ok"]:
        return {"pass": False, "reason": "시간외"}

    mr = is_market_bullish(user, token, f["min_market_rate"])
    if not mr["ok"]:
        return {"pass": False, "reason": "하락장 차단"}
    if not is_bullish_above_open(cp, open_price, f["min_gain_from_open"]):
        return {"pass": False, "reason": "시가 지지 미달"}

    gr = is_gap_up(open_price, prev_close, f["min_gap_rate"])
    if not gr["ok"]:
        return {"pass": False, "reason": "갭상승 미달"}

    br = is_consecutive_bullish(daily_opens, daily_closes, f["required_bullish_days"])
    if not br["ok"]:
        return {"pass": False, "reason": "연속양봉 미달"}
    if not is_near_high(cp, high_price, f["high_proximity"]):
        return {"pass": False, "reason": "당일고가 미근접"}

    rr = is_rsi_valid(daily_prices, f["rsi_min"], f["rsi_max"])
    if not rr["ok"]:
        return {"pass": False, "reason": "RSI 미달"}

    bb = is_near_bollinger_upper(daily_prices, threshold=f["bb_threshold"])
    if not bb["ok"]:
        return {"pass": False, "reason": "볼린저 미달"}
    if not is_volume_surge(minute_vols, f["min_1min_vol_surge"]):
        return {"pass": False, "reason": "거래량 폭증 미달"}

    vd = get_trading_value_grade(cp, minute_vols[-1])
    if not vd["ok"]:
        return {"pass": False, "reason": "거래대금 미달"}

    if f["vi_check"] and not is_vi_safe(stock["code"], user, token)["ok"]:
        return {"pass": False, "reason": "VI 발동 이력"}
    if has_resistance_above(daily_prices, daily_volumes, cp):
        return {"pass": False, "reason": "매물대 존재"}

    return {
        "pass": True,
        "grade": get_signal_grade(cp, high_price),
        "rsi": rr["rsi"],
        "bb_ratio": bb["ratio"],
        "gap_rate": gr["gap_rate"],
        "bull_days": br["count"],
        "val_ok": vd["val_ok"],
        "kospi": mr["kospi"],
        "kosdaq": mr["kosdaq"],
    }
