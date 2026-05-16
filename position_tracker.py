"""
position_tracker.py — 포지션(보유 종목) 영속화 관리 모듈

매수 성공 시 positions.json 에 기록하고,
손절/익절 체결 후 제거합니다.
스레드 안전(threading.Lock) 처리가 되어 있어 APScheduler Job 간 충돌 없음.
"""

import json
import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

POSITION_FILE = "positions.json"
_lock = threading.Lock()


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _load() -> dict:
    """파일에서 포지션 딕셔너리 로드 (스레드 비안전 — 반드시 _lock 획득 후 호출)"""
    if not os.path.exists(POSITION_FILE):
        return {}
    try:
        with open(POSITION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"positions.json 로드 실패: {e}")
        return {}


def _save(positions: dict) -> bool:
    """포지션 딕셔너리를 파일에 저장 (스레드 비안전 — 반드시 _lock 획득 후 호출)
    반환값: True=성공, False=실패
    """
    try:
        with open(POSITION_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.error(f"positions.json 저장 실패: {e}")
        return False


# ─────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────

def add_position(
    account_no: str,
    stock_code: str,
    buy_price: float,
    qty: int,
    stop_loss: float,
    take_profit: float,
    stock_name: str = "",
) -> None:
    """매수 체결 후 포지션 등록"""
    key = f"{account_no}_{stock_code}"
    entry = {
        "account_no": account_no,
        "stock_code": stock_code,
        "stock_name": stock_name or stock_code,
        "buy_price": buy_price,
        "qty": qty,
        "stop_loss": round(stop_loss, 0),
        "take_profit": round(take_profit, 0),
        "status": "open",
        "opened_at": datetime.now().isoformat(),
    }
    with _lock:
        positions = _load()
        positions[key] = entry
        if not _save(positions):
            logger.warning(f"[포지션 등록] 저장 실패 — 재시작 시 포지션 소실 위험: {key}")
    logger.info(
        f"[포지션 등록] {account_no} | {stock_code} "
        f"매수가={buy_price:,.0f} 손절={stop_loss:,.0f} 익절={take_profit:,.0f}"
    )


def remove_position(account_no: str, stock_code: str) -> None:
    """손절/익절 체결 후 포지션 제거"""
    key = f"{account_no}_{stock_code}"
    with _lock:
        positions = _load()
        removed = positions.pop(key, None)
        if removed:
            if not _save(positions):
                logger.warning(f"[포지션 제거] 저장 실패 — 재시작 시 포지션 복원 위험: {key}")
            logger.info(f"[포지션 제거] {account_no} | {stock_code}")
        else:
            logger.warning(f"[포지션 제거] 존재하지 않는 키: {key}")


def get_open_positions() -> list[dict]:
    """현재 보유 중인 모든 포지션 반환"""
    with _lock:
        positions = _load()
    return [p for p in positions.values() if p.get("status") == "open"]


def load_all() -> dict:
    """전체 포지션 딕셔너리 반환 (대시보드 등 읽기 전용 용도)"""
    with _lock:
        return _load()
