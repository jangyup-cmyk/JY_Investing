import logging

from kis_api import KISAPIClient

logger = logging.getLogger(__name__)


def fetch_daily_prices(stock_code: str, user: dict, count: int = 100) -> list:
    """KIS API로 일봉 데이터 조회"""
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error(f"토큰 발급 실패: {stock_code}")
        return []
    
    daily_data = kis_client.get_daily_price(stock_code, count=count)
    prices = []
    for item in daily_data:
        try:
            price = float(item.get("stck_clpr", 0))
            prices.append(price)
        except Exception as e:
            logger.warning(f"가격 파싱 오류 ({stock_code}): {e}")
    
    # kis_api.get_daily_price()가 이미 날짜(stck_bsop_date) 기준으로 정렬 반환
    # sorted()를 사용하면 가격값만 오름차순 정렬되어 날짜 순서가 파괴됨 → TA-Lib 지표 계산 오류
    return prices


def fetch_daily_ohlcv(stock_code: str, user: dict, count: int = 100) -> dict:
    """KIS API로 일봉 OHLCV 데이터 조회"""
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error(f"토큰 발급 실패: {stock_code}")
        return {"opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}
    
    daily_data = kis_client.get_daily_price(stock_code, count=count)
    result = {"opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}
    
    for item in daily_data:
        try:
            result["opens"].append(float(item.get("stck_oprc", 0)))
            result["highs"].append(float(item.get("stck_hgpr", 0)))
            result["lows"].append(float(item.get("stck_lwpr", 0)))
            result["closes"].append(float(item.get("stck_clpr", 0)))
            result["volumes"].append(int(item.get("acml_vol", 0)))
        except Exception as e:
            logger.warning(f"OHLCV 파싱 오류 ({stock_code}): {e}")
    
    return result


def fetch_asking_price(stock_code: str, user: dict) -> dict:
    """KIS API로 현재 호가 조회"""
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error(f"토큰 발급 실패: {stock_code}")
        return {
            "current_price": 0,
            "bid1": 0,
            "ask1": 0,
            "bid1_qty": 0,
            "ask1_qty": 0,
        }
    
    data = kis_client.get_asking_price(stock_code)
    # KIS API 필드명: bidp=매수호가(bid), askp=매도호가(ask)
    # 이전 코드는 askp↔bidp 가 반전되어 있었음
    return {
        "current_price": float(data.get("stck_prpr", 0)),
        "bid1": float(data.get("bidp1", 0)),
        "ask1": float(data.get("askp1", 0)),
        "bid1_qty": int(data.get("bidp_rsqn1", 0)),
        "ask1_qty": int(data.get("askp_rsqn1", 0)),
    }


def fetch_previous_close(stock_code: str, user: dict) -> float:
    """전일 종가 조회"""
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error(f"토큰 발급 실패: {stock_code}")
        return 0.0

    daily_data = kis_client.get_daily_price(stock_code, count=2)
    if not isinstance(daily_data, list) or len(daily_data) < 1:
        logger.warning(f"전일 종가 데이터 부족 ({stock_code}): {len(daily_data) if isinstance(daily_data, list) else 'None'}")
        return 0.0
    try:
        return float(daily_data[0].get("stck_clpr", 0) or 0)
    except (ValueError, TypeError) as e:
        logger.error(f"전일 종가 변환 실패 ({stock_code}): {e}")
        return 0.0


def fetch_balance(user: dict) -> dict:
    """잔고 조회"""
    kis_client = KISAPIClient(user)
    if not kis_client.get_access_token():
        logger.error(f"토큰 발급 실패: {user['name']}")
        return {"total_balance": 0, "available_balance": 0}
    
    data = kis_client.get_balance()
    output = data.get("output", {})
    output2 = data.get("output2", [{}])[0] if data.get("output2") else {}
    
    return {
        "total_balance": int(output.get("tot_evlu_pfls_amt", 0)),
        "available_balance": int(output.get("scts_ord_un_amt", 0)),
        "total_buy_amount": int(output2.get("tot_puchsamt", 0)),
        "total_eval_amount": int(output2.get("tot_evlu_amt", 0)),
    }

