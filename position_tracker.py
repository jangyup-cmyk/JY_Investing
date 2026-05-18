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
CLOSED_POSITIONS_FILE = "closed_positions.json"
BACKUP_DIR = "etc/positions_backups"
MAX_BACKUPS = 5
_lock = threading.Lock()
_closed_lock = threading.Lock()


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _backup_filename() -> str:
    """ISO 타임스탬프 기반 백업 파일명 (Windows 호환 — 콜론 없음, μs 까지 포함해 동일 초 충돌 방지)"""
    return f"positions.{datetime.now().strftime('%Y-%m-%dT%H%M%S-%f')}.json"


def _list_backup_files() -> list:
    """BACKUP_DIR 의 backup 파일을 최신순(이름 내림차순)으로 반환"""
    if not os.path.isdir(BACKUP_DIR):
        return []
    files = [
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("positions.") and f.endswith(".json")
    ]
    return sorted(files, reverse=True)


def _rotate_backups(max_keep: int = MAX_BACKUPS) -> None:
    """최신 max_keep 개를 제외한 오래된 백업 삭제"""
    for old in _list_backup_files()[max_keep:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError as e:
            logger.warning(f"백업 회전 실패 ({old}): {e}")


def _create_backup() -> bool:
    """현재 POSITION_FILE 을 BACKUP_DIR 로 회전 백업.

    파일이 없으면 skip (False 반환).
    내용이 잘못된 JSON 이라도 그대로 보존 — 디버깅/포렌식 목적.
    """
    if not os.path.exists(POSITION_FILE):
        return False
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(BACKUP_DIR, _backup_filename())
        with open(POSITION_FILE, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
        _rotate_backups()
        return True
    except OSError as e:
        logger.warning(f"positions.json 백업 실패: {e}")
        return False


def _try_restore_from_backups() -> dict | None:
    """최신 백업부터 시도하여 첫 번째 유효 JSON dict 반환. 없으면 None."""
    for fname in _list_backup_files():
        path = os.path.join(BACKUP_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                logger.warning(f"positions.json 백업 자동 복구 성공: {fname}")
                _safe_admin_alert(
                    "critical",
                    "positions.json 자동 복구",
                    f"손상된 positions.json 을 백업 '{fname}' 에서 복구했습니다 "
                    f"({len(data)}건). 손상 원인을 점검하세요.",
                )
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def _safe_admin_alert(severity: str, title: str, detail: str = "") -> None:
    """관리자 알림 — 모든 예외 흡수 (매매 흐름 절대 차단 안 함)."""
    try:
        import telegram_bot  # lazy import: 순환 참조 회피
        telegram_bot.send_admin_alert(severity, title, detail)
    except Exception as exc:
        logger.error(f"_safe_admin_alert 실패 (silent): {exc}")


def _load() -> dict:
    """파일에서 포지션 딕셔너리 로드 (스레드 비안전 — 반드시 _lock 획득 후 호출).

    JSON 손상 / IO 오류 시 가장 최근 유효 백업에서 자동 복구를 시도한다.
    백업도 없으면 빈 dict 반환 (기존 동작 유지).
    """
    if not os.path.exists(POSITION_FILE):
        return {}
    try:
        with open(POSITION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"positions.json 로드 실패: {e} — 백업에서 자동 복구 시도")
        recovered = _try_restore_from_backups()
        if recovered is not None:
            return recovered
        logger.error("positions.json 자동 복구 실패: 유효한 백업 없음 — 빈 dict 반환")
        return {}


def _save(positions: dict) -> bool:
    """포지션 딕셔너리를 파일에 저장 (스레드 비안전 — 반드시 _lock 획득 후 호출).

    저장 직전 기존 POSITION_FILE 을 BACKUP_DIR 로 회전 백업.
    반환값: True=성공, False=실패
    """
    _create_backup()
    try:
        with open(POSITION_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.error(f"positions.json 저장 실패: {e}")
        _safe_admin_alert(
            "critical",
            "positions.json 저장 실패",
            f"OSError: {e}\n다음 재시작 시 포지션 소실 위험. 즉시 점검 필요.",
        )
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


def archive_position(
    account_no: str,
    stock_code: str,
    sell_price: float,
    reason: str = "",
) -> bool:
    """매도 체결 정보를 closed_positions.json 에 append.

    현재 열린 포지션을 조회해 PnL 을 계산하고, 새 record 로 추가한다.
    실패 시 False (저장 실패 / 원본 포지션 미존재 등) — 부르는 쪽에서
    remove_position 호출 여부와 무관하게 진행 가능하도록 예외는 던지지 않는다.
    """
    key = f"{account_no}_{stock_code}"
    with _lock:
        positions = _load()
        original = positions.get(key)
    if not original:
        logger.warning(f"[포지션 아카이브] 원본 포지션 없음: {key}")
        return False

    buy_price = float(original.get("buy_price", 0) or 0)
    qty = int(original.get("qty", 0) or 0)
    pnl_amt = (sell_price - buy_price) * qty
    pnl_rate = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

    record = {
        **original,
        "status": "closed",
        "sell_price": round(float(sell_price), 2),
        "sell_reason": reason,
        "closed_at": datetime.now().isoformat(),
        "pnl_amt": round(pnl_amt, 2),
        "pnl_rate": round(pnl_rate, 4),
    }

    with _closed_lock:
        try:
            history: list = []
            if os.path.exists(CLOSED_POSITIONS_FILE):
                with open(CLOSED_POSITIONS_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        history = raw
            history.append(record)
            with open(CLOSED_POSITIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"closed_positions.json 저장 실패: {e}")
            _safe_admin_alert(
                "warning",
                "closed_positions.json 저장 실패",
                f"{key} 매도가={sell_price:,.0f} 사유={reason}\n"
                f"오류: {e}\n매도는 체결되었으나 성과 이력에서 누락됩니다.",
            )
            return False

    logger.info(
        f"[포지션 아카이브] {key} | 매도가={sell_price:,.0f} "
        f"PnL={pnl_amt:+,.0f} ({pnl_rate:+.2f}%) 사유={reason}"
    )
    return True


def load_closed_positions() -> list:
    """closed_positions.json 전체 record 리스트 반환 (없으면 빈 리스트)"""
    with _closed_lock:
        if not os.path.exists(CLOSED_POSITIONS_FILE):
            return []
        try:
            with open(CLOSED_POSITIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"closed_positions.json 로드 실패: {e}")
            return []


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


# ─────────────────────────────────────────
# 백업 관리 공개 API (restore CLI 용)
# ─────────────────────────────────────────

def list_backups() -> list[dict]:
    """모든 백업 파일의 메타데이터를 최신순(index=0 이 최신)으로 반환."""
    result = []
    for i, fname in enumerate(_list_backup_files()):
        path = os.path.join(BACKUP_DIR, fname)
        valid = False
        count = 0
        size = 0
        mtime = "?"
        try:
            stat = os.stat(path)
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                valid = True
                count = len(data)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        result.append({
            "index": i,
            "filename": fname,
            "mtime": mtime,
            "size": size,
            "position_count": count,
            "valid": valid,
        })
    return result


def restore_backup(index: int) -> bool:
    """지정된 인덱스의 백업을 positions.json 으로 복원 (현재 파일은 회전 백업).

    index=0 이 최신. 잘못된 인덱스 또는 손상된 백업이면 False.
    """
    files = _list_backup_files()
    if not 0 <= index < len(files):
        logger.error(f"[복구] 인덱스 범위 초과: {index} (총 {len(files)}개)")
        return False
    src_path = os.path.join(BACKUP_DIR, files[index])
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[복구] 백업 #{index} 로드 실패: {e}")
        return False
    if not isinstance(data, dict):
        logger.error(f"[복구] 백업 #{index} 형식 오류 (dict 아님)")
        return False
    with _lock:
        ok = _save(data)
    if ok:
        logger.info(f"[복구] 백업 #{index} ({files[index]}) → positions.json 복원 완료 ({len(data)}건)")
    return ok
