import hashlib
import json
import logging
import time
from datetime import datetime

import requests

import config

logger = logging.getLogger(__name__)

# 모듈 레벨 토큰 캐시 (전역 재사용)
_token_cache = {}


class KISAPIClient:
    """한국투자증권 KIS API 클라이언트"""

    def __init__(self, user: dict):
        self.user = user
        self.base_url = config.KIS_API_BASE
        account_no = user.get("account_no", "")
        # 8자리만 저장된 경우 상품코드 "01"(일반주식) 자동 보완
        if len(account_no) == 8:
            account_no = account_no + "01"
            self.user = {**user, "account_no": account_no}
        
        # 캐시에서 토큰 복원
        if account_no in _token_cache:
            cached = _token_cache[account_no]
            self.access_token = cached.get("token", "")
            self.token_expire_time = cached.get("expire_time", 0)
        else:
            self.access_token = user.get("access_token", "")
            self.token_expire_time = user.get("token_expire_time", 0)

    def _generate_hash_key(self, payload: dict) -> str:
        """요청 본문의 해시 키 생성"""
        payload_json = json.dumps(payload)
        hash_obj = hashlib.sha256(payload_json.encode())
        return hash_obj.hexdigest()

    def _get_headers(self, tr_id: str, hash_key: str = "") -> dict:
        """API 요청 헤더 생성"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appkey": self.user["app_key"],
            "appsecret": self.user["app_secret"],
            "tr_id": tr_id,
        }
        if hash_key:
            headers["hashkey"] = hash_key
        return headers

    def get_access_token(self) -> bool:
        """토큰 발급/갱신 (토큰 캐싱 및 재시도 로직 포함)"""
        # 토큰이 유효하면 재사용
        if self.access_token and time.time() < self.token_expire_time - 60:
            logger.debug(f"기존 토큰 재사용 ({self.user.get('name', 'Unknown')})")
            return True
        
        logger.info(f"토큰 재발급 필요 ({self.user.get('name', 'Unknown')})")
        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.user["app_key"],
            "appsecret": self.user["app_secret"],
        }
        
        # 속도 제한 에러 시 재시도
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                res = requests.post(url, json=payload, timeout=5)
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except ValueError:
                        logger.error(f"토큰 응답 JSON 파싱 실패 (attempt {attempt + 1}): {res.text[:200]}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return False
                    token = data.get("access_token", "")
                    if not token:
                        logger.error(f"토큰 응답에 access_token 없음: {data}")
                        return False
                    self.access_token = token
                    self.token_expire_time = time.time() + data.get("expires_in", 3600)
                    self.user["access_token"] = self.access_token
                    self.user["token_expire_time"] = self.token_expire_time

                    # 캐시에 저장
                    account_no = self.user.get("account_no", "")
                    if account_no:
                        _token_cache[account_no] = {
                            "token": self.access_token,
                            "expire_time": self.token_expire_time
                        }

                    logger.info(f"✅ 토큰 발급 성공 ({self.user.get('name', 'Unknown')})")
                    return True
                elif res.status_code == 403:
                    try:
                        error_code = res.json().get("error_code", "")
                    except ValueError:
                        error_code = ""
                    if error_code == "EGW00133" and attempt < max_retries - 1:
                        # 속도 제한: 대기 후 재시도
                        logger.warning(f"API 속도 제한, {retry_delay}초 대기 후 재시도 (시도 {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    logger.error(f"토큰 발급 실패: {res.status_code} {res.text}")
                    return False
                else:
                    logger.error(f"토큰 발급 실패: {res.status_code} {res.text}")
                    return False
            except Exception as e:
                logger.error(f"토큰 발급 오류: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return False
        
        return False

    def order_cash(self, stock_code: str, qty: int, price: float, order_type: str = "01") -> dict:
        """주식 매수/매도 주문 (현물)
        order_type: 01=시장가, 00=지정가
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        payload = {
            "CANO": self.user["account_no"][:8],
            "ACNT_PRDT_CD": self.user["account_no"][8:],
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0" if order_type == "01" else str(int(price)),
            "SLL_TYPE": "00",
        }
        hash_key = self._generate_hash_key(payload)
        headers = self._get_headers("TTTC0802U", hash_key)
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                try:
                    return res.json()
                except ValueError:
                    logger.error(f"order_cash JSON 파싱 실패 ({stock_code}): {res.text[:200]}")
                    return {"rt_cd": "-1", "msg_text": "invalid json response", "success": False}
            else:
                logger.error(f"order_cash HTTP 오류 ({stock_code}): {res.status_code} {res.text[:200]}")
                return {"rt_cd": "-1", "msg_text": res.text, "success": False}
        except Exception as e:
            logger.error(f"order_cash 예외 ({stock_code}): {e}")
            return {"rt_cd": "-1", "msg_text": str(e), "success": False}

    def order_sell(self, stock_code: str, qty: int, price: float = 0, order_type: str = "01") -> dict:
        """주식 매도 주문 (현물 시장가)
        order_type: 01=시장가(기본), 00=지정가
        손절·익절 자동 실행에 사용 — 기본 시장가로 즉시 체결
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        payload = {
            "CANO": self.user["account_no"][:8],
            "ACNT_PRDT_CD": self.user["account_no"][8:],
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0" if order_type == "01" else str(int(price)),
            "SLL_TYPE": "01",  # 01 = 매도
        }
        hash_key = self._generate_hash_key(payload)
        headers = self._get_headers("TTTC0801U", hash_key)  # 매도 TR_ID
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                try:
                    return res.json()
                except ValueError:
                    logger.error(f"order_sell JSON 파싱 실패 ({stock_code}): {res.text[:200]}")
                    return {"rt_cd": "-1", "msg_text": "invalid json response", "success": False}
            else:
                logger.error(f"매도 주문 실패 ({stock_code}): {res.status_code} {res.text[:200]}")
                return {"rt_cd": "-1", "msg_text": res.text, "success": False}
        except Exception as e:
            logger.error(f"매도 주문 오류 ({stock_code}): {e}")
            return {"rt_cd": "-1", "msg_text": str(e), "success": False}

    def cancel_order(self, order_no: str, qty: int = 0) -> dict:
        """주문 취소"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl"
        payload = {
            "CANO": self.user["account_no"][:8],
            "ACNT_PRDT_CD": self.user["account_no"][8:],
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0",
        }
        hash_key = self._generate_hash_key(payload)
        headers = self._get_headers("TTTC0803U", hash_key)
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                return res.json()
            else:
                return {"success": False, "error": res.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_balance(self) -> dict:
        """잔고 조회"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO": self.user["account_no"][:8],
            "ACNT_PRDT_CD": self.user["account_no"][8:],
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "Y",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK": "",
            "CTX_AREA_NK": "",
        }
        headers = self._get_headers("TTTC8434R")
        try:
            res = requests.get(url, params=params, headers=headers, timeout=5)
            if res.status_code == 200:
                return res.json()
            else:
                return {"success": False, "error": res.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_daily_price(self, stock_code: str, end_date: str = "", count: int = 100) -> list:
        """일봉 데이터 조회"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
            "fid_org_adj_prc": "0",
            "fid_period_div_code": "D",
            "fid_end_dt": end_date,
            "fid_start_dt": "",
            "fid_rpt_code": "ALL",
            "fid_candle_tp_cd": "61",
        }
        headers = self._get_headers("FHKST03010000")
        try:
            res = requests.get(url, params=params, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                output = data.get("output2", [])
                return sorted(output, key=lambda x: x.get("stck_bsop_date", ""))[:count]
            else:
                return []
        except Exception as e:
            logger.error(f"일봉 데이터 조회 오류 ({stock_code}): {e}")
            return []

    def get_asking_price(self, stock_code: str) -> dict:
        """호가 데이터 조회"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }
        headers = self._get_headers("FHKST01010200")  # 호가조회 TR_ID
        try:
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                data = res.json()
                output1 = data.get("output1", {})
                output2 = data.get("output2", {})
                return {**output1, **output2}
            else:
                return {}
        except Exception as e:
            logger.error(f"호가 조회 오류 ({stock_code}): {e}")
            return {}

    def get_index_price(self, index_code: str) -> dict:
        """KOSPI/KOSDAQ 지수 조회
        index_code: '0001' = KOSPI, '1001' = KOSDAQ
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
        params = {
            "fid_cond_mrkt_div_code": "U",
            "fid_input_iscd": index_code,
        }
        headers = self._get_headers("FHPUP02100000")
        try:
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                return res.json().get("output", {})
            else:
                logger.warning(f"지수 조회 실패 ({index_code}): {res.status_code}")
                return {}
        except Exception as e:
            logger.error(f"지수 조회 오류 ({index_code}): {e}")
            return {}

    def get_stock_name(self, stock_code: str) -> str:
        """주식 현재가 시세 조회로 종목명(hts_kor_isnm) 반환.
        조회 실패 시 빈 문자열 반환.
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }
        headers = self._get_headers("FHKST01010100")
        try:
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                return res.json().get("output", {}).get("hts_kor_isnm", "")
        except Exception as e:
            logger.debug(f"종목명 조회 오류 ({stock_code}): {e}")
        return ""

    def get_vi_status(self, stock_code: str) -> dict:
        """VI (변동성 완화장치) 발동 상태 조회"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-vi-status"
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }
        headers = self._get_headers("FHPST01810000")
        try:
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                return res.json().get("output", {})
            else:
                logger.warning(f"VI 조회 실패 ({stock_code}): {res.status_code}")
                return {}
        except Exception as e:
            logger.error(f"VI 조회 오류 ({stock_code}): {e}")
            return {}
