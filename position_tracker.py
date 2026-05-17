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
    buy_date: str = "",
) -> None:
    """매수 체결 후 포지션 등록.
    buy_date: 실제 매수일 (YYYY-MM-DD). 미전달 시 오늘 날짜로 자동 설정.
    """
    key = f"{account_no}_{stock_code}"
    today = datetime.now().strftime("%Y-%m-%d")
    entry = {
        "account_no": account_no,
        "stock_code": stock_code,
        "stock_name": stock_name or stock_code,
        "buy_price": buy_price,
        "qty": qty,
        "stop_loss": round(stop_loss, 0),
        "take_profit": round(take_profit, 0),
        "status": "open",
        "buy_date": buy_date.strip() or today,   # 실제 매수일 (수정 가능)
        "opened_at": datetime.now().isoformat(),  # 시스템 등록 시각 (내부용)
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


def update_position_levels(
    account_no: str,
    stock_code: str,
    stop_loss: float,
    take_profit: float,
    buy_date: str = "",
) -> bool:
    """손절/익절가 + 매수일 수동 업데이트 (대시보드 편집 UI용)"""
    key = f"{account_no}_{stock_code}"
    with _lock:
        positions = _load()
        if key not in positions:
            logger.warning(f"[손절/익절 수정] 존재하지 않는 키: {key}")
            return False
        positions[key]["stop_loss"] = round(stop_loss, 0)
        positions[key]["take_profit"] = round(take_profit, 0)
        if buy_date and buy_date.strip():
            positions[key]["buy_date"] = buy_date.strip()
        # 기존 포지션에 buy_date 없으면 opened_at 날짜로 초기화
        if "buy_date" not in positions[key]:
            opened = positions[key].get("opened_at", "")
            positions[key]["buy_date"] = opened[:10] if opened else ""
        ok = _save(positions)
    if ok:
        logger.info(f"[포지션 수정] {key} → 손절={stop_loss:,.0f} 익절={take_profit:,.0f}"
                    + (f" 매수일={buy_date}" if buy_date else ""))
    return ok
