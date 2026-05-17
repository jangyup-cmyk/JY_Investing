"""
Project configuration for JY 투자클럽 AI 자동매매 시스템.
Adapted from 전체 개발 명세서 v3.0 and 1-to-1 Personalized Channel design.

환경 변수에서 설정 로드 (보안 강화):
- .env 파일에 실제 API 키/토큰 저장
- 코드에는 절대 노출 안됨
"""

import os
from dotenv import load_dotenv

# 우선순위: 시스템 환경변수(PS 스크립트) > .env > .env.local
# override=False 이므로 이미 설정된 시스템 환경변수는 덮어쓰지 않음
load_dotenv(override=False)
load_dotenv(".env.local", override=False)


def get_env_or_default(key: str, default: str = None) -> str:
    """환경 변수에서 값을 읽고, 없으면 기본값 반환"""
    value = os.getenv(key, default)
    if value is None or not value.strip() or value.startswith("your_"):
        raise ValueError(
            f"❌ 환경 변수 '{key}'가 설정되지 않았습니다. "
            f".env 파일을 확인하거나 생성하세요."
        )
    return value


# ============================================================================
# 사용자 계좌 설정 (환경 변수에서 로드)
# ============================================================================

USERS = [
    {
        "name": "전장엽(73918950)",
        "account_no": get_env_or_default("KIS_ACCOUNT_NO_JY_Investing1"),
        "budget": int(os.getenv("BUDGET_JY1", "1000000")),
        "app_key": get_env_or_default("KIS_APP_KEY_JY1"),
        "app_secret": get_env_or_default("KIS_APP_SECRET_JY1"),
        "bot_token": get_env_or_default("TELEGRAM_BOT_TOKEN_JY_Investing1"),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_ID_JY_Investing", "-1001234567890"),
    },
    {
        "name": "전장엽(73312646)",
        "account_no": get_env_or_default("KIS_ACCOUNT_NO_JY_Investing2"),
        "budget": int(os.getenv("BUDGET_JY2", "1000000")),
        "app_key": get_env_or_default("KIS_APP_KEY_JY2"),
        "app_secret": get_env_or_default("KIS_APP_SECRET_JY2"),
        "bot_token": get_env_or_default("TELEGRAM_BOT_TOKEN_JY_Investing2"),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_ID_JY_Investing", "-1001234567890"),
    },
]

# ============================================================================
# 텔레그램 관리자 설정 (긴급 알림용)
# ============================================================================

TELEGRAM_ADMIN_BOT_TOKEN = get_env_or_default("TELEGRAM_ADMIN_BOT_TOKEN")
TELEGRAM_ADMIN_ID = get_env_or_default("TELEGRAM_ADMIN_CHAT_ID")

# ============================================================================
# 공통 설정
# ============================================================================

CHANNEL_NAME = "JY 투자클럽"
SLIPPAGE_RATE = float(os.getenv("SLIPPAGE_RATE", "0.003"))
KIS_API_BASE = "https://openapi.koreainvestment.com:9443"

# ============================================================================
# 매매 필터 설정 (13가지 조건)
# ============================================================================

FILTER = {
    "min_change_rate": float(os.getenv("MIN_CHANGE_RATE", "2.0")),
    "max_change_rate": float(os.getenv("MAX_CHANGE_RATE", "15.0")),
    "min_price": int(os.getenv("MIN_PRICE", "1000")),
    "max_price": int(os.getenv("MAX_PRICE", "100000")),
    "ma_aligned": True,
    "min_1min_vol_surge": 500,
    "vap_check": True,
    "min_gain_from_open": 1.0,
    "high_proximity": 0.98,
    "min_trading_value": 300_000_000,
    "rsi_min": 40.0,
    "rsi_max": 70.0,
    "bb_threshold": 0.99,
    "min_gap_rate": 1.0,
    "required_bullish_days": 2,
    "vi_check": True,
    "min_market_rate": -1.0,
    "signal_start_hour": 9,
    "signal_start_min": 0,
    "signal_end_hour": 10,
    "signal_end_min": 30,
}

# ============================================================================
# 모니터링 종목 리스트 (매매 파이프라인 / 손절·익절 모니터링 대상)
# 종목 코드를 추가/제거해서 관리
# ============================================================================

WATCH_LIST: list[str] = [
    # "005930",  # 삼성전자
    # "000660",  # SK하이닉스
    # "035720",  # 카카오
    # 실제 운용할 종목 코드를 여기에 추가
]

# ============================================================================
# 텔레그램/뉴스 자연어 기반 테마-종목 자동 추출 설정
# ============================================================================

TEXT_SIGNAL_SOURCE_DIR: str = os.getenv("TEXT_SIGNAL_SOURCE_DIR", "etc/telegram_texts")
AUTO_BUILD_WATCH_LIST: bool = os.getenv("AUTO_BUILD_WATCH_LIST", "true").lower() == "true"
THEME_EXTRACTION_MIN_SCORE: float = float(os.getenv("THEME_EXTRACTION_MIN_SCORE", "2.0"))
USE_CHANNEL_WEIGHTED_WATCHLIST: bool = os.getenv("USE_CHANNEL_WEIGHTED_WATCHLIST", "true").lower() == "true"
CHANNEL_COMPARISON_REPORT_PATH: str = os.getenv(
    "CHANNEL_COMPARISON_REPORT_PATH", "etc/telegram_texts/channel_comparison_report.json"
)
CHANNEL_WEIGHTS_FILE: str = os.getenv("CHANNEL_WEIGHTS_FILE", "etc/channel_weights.json")
CHANNEL_WEIGHTED_TOP_N: int = int(os.getenv("CHANNEL_WEIGHTED_TOP_N", "10"))

# ============================================================================
# 손절 / 익절 비율 설정 (.env로 오버라이드 가능)
# ============================================================================

STOP_LOSS_RATE: float = float(os.getenv("STOP_LOSS_RATE", "0.05"))      # 기본 5% 손절
TAKE_PROFIT_RATE: float = float(os.getenv("TAKE_PROFIT_RATE", "0.10"))  # 기본 10% 익절

# ============================================================================
# 포트폴리오 리스크 한도 설정
# ============================================================================

MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "5"))
# 계좌 예산 대비 최소 현금 비율 — 이 비율 이하로 투자하면 추가 매수 중단
MIN_CASH_RATE: float = float(os.getenv("MIN_CASH_RATE", "0.20"))

# ============================================================================
# 텔레그램 실시간 모니터링 설정 (Telethon 기반)
# ============================================================================

# Telethon 라이브러리를 사용한 채널별 모니터링
# 1. my.telegram.org에서 Telegram API ID/Hash 발급
# 2. .env에 TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE 설정
# 3. 첫 실행 시 인증 코드 입력 필요

TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE: str = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SESSION_FILE: str = os.getenv("TELEGRAM_SESSION_FILE", ".telegram_session")
TELEGRAM_LISTENER_STATE_FILE: str = os.getenv("TELEGRAM_LISTENER_STATE_FILE", "etc/telegram_listener_state.json")

# 모니터링할 채널 그룹 설정 (폴더별 분류)
# 형식: "그룹명": ["@username1", "@username2", chat_id, ...]
# 
# 채널 찾기 방법:
# 1. 공개 채널: @channelname
# 2. 비공개 채널/DM: 숫자 ID (스크린샷에 보이는 ID 사용)
# 3. 그룹: @groupname 또는 ID
#
# 예시:
# 채널 그룹 설정 파일 경로 (채널 추가/삭제 시 이 파일만 편집)
CHANNEL_GROUPS_FILE: str = os.getenv("CHANNEL_GROUPS_FILE", "etc/channel_groups.json")

def _load_channel_groups(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"채널 그룹 파일 로드 실패 ({path}): {e}")
        return {}

TELEGRAM_CHANNEL_GROUPS: dict = _load_channel_groups(CHANNEL_GROUPS_FILE)

# 자동 탐색할 텔레그램 대화방 폴더명 리스트
TELEGRAM_MONITOR_FOLDERS: list = [
    f.strip() for f in os.getenv("TELEGRAM_MONITOR_FOLDERS", "공시속보, 증권사, 경제신문, 분석가").split(",") if f.strip()
]

# 모니터링 설정
TELEGRAM_MONITOR_ENABLED: bool = os.getenv("TELEGRAM_MONITOR_ENABLED", "false").lower() == "true"
TELEGRAM_MESSAGE_FETCH_LIMIT: int = int(os.getenv("TELEGRAM_MESSAGE_FETCH_LIMIT", "100"))

# 텔레그램 메시지 수집 주기
TELEGRAM_POLL_INTERVAL: int = int(os.getenv("TELEGRAM_POLL_INTERVAL", "300"))

# 네이버 리서치 수집 설정
NAVER_RESEARCH_ENABLED: bool = os.getenv("NAVER_RESEARCH_ENABLED", "true").lower() == "true"
NAVER_RESEARCH_POLL_INTERVAL: int = int(os.getenv("NAVER_RESEARCH_POLL_INTERVAL", "3600"))  # 1시간
NAVER_RESEARCH_SOURCE_DIR: str = os.getenv("NAVER_RESEARCH_SOURCE_DIR", "etc/naver_research")

NAVER_RESEARCH_CATEGORIES = {
    "company": "company_list.naver",
    "industry": "industry_list.naver",
    "invest": "invest_list.naver",
    "market_info": "market_info_list.naver",
    "economy": "economy_list.naver",
    "debenture": "debenture_list.naver"
}
