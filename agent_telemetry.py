"""에이전트 파이프라인 거부 사유 텔레메트리 (관측성).

agent_rejections.json 에 거부 record 를 append, MAX_REJECTION_RECORDS 개수로 회전.
record_rejection 은 절대 raise 하지 않으며, 실패해도 매매 흐름을 막지 않는다.
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

REJECTION_FILE = "agent_rejections.json"
MAX_REJECTION_RECORDS = 1000
_lock = threading.Lock()


def record_rejection(
    stock_code: str,
    stage: str,
    reason: str,
    extra: dict | None = None,
) -> bool:
    """거부 record 1건을 파일에 append. 실패도 silent (False 반환).

    stage 표준 값: 'technical' | 'researcher' | 'risk' | 'trader' | 'portfolio'
    """
    try:
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "stock_code": str(stock_code or ""),
            "stage": str(stage or "unknown"),
            "reason": str(reason or ""),
        }
        if isinstance(extra, dict) and extra:
            record["extra"] = extra

        with _lock:
            history: list = []
            if os.path.exists(REJECTION_FILE):
                try:
                    with open(REJECTION_FILE, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, list):
                        history = raw
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"agent_rejections.json 손상 — 덮어쓰기 진행: {e}")

            history.append(record)
            if len(history) > MAX_REJECTION_RECORDS:
                history = history[-MAX_REJECTION_RECORDS:]

            with open(REJECTION_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"record_rejection 실패 (silent): {e}")
        return False


def load_rejections() -> list:
    """전체 record 리스트 반환 (없으면 빈 리스트)."""
    with _lock:
        if not os.path.exists(REJECTION_FILE):
            return []
        try:
            with open(REJECTION_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"agent_rejections.json 로드 실패: {e}")
            return []


def summarize_rejections(days: int = 7, top_reasons: int = 10) -> dict:
    """최근 N일 거부 사유 요약.

    반환:
      {
        "window_days": int,
        "total": int,
        "by_stage": [{"stage": "technical", "count": 42}, ...],
        "top_reasons": [{"label": "technical: RSI 미달", "count": 31}, ...],
      }
    """
    records = load_rejections()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

    filtered = [r for r in records if str(r.get("timestamp", "")) >= cutoff]

    by_stage: dict = {}
    by_reason: dict = {}
    for r in filtered:
        stage = str(r.get("stage", "unknown")) or "unknown"
        reason = str(r.get("reason", "")).strip()
        by_stage[stage] = by_stage.get(stage, 0) + 1
        key = f"{stage}: {reason}" if reason else stage
        by_reason[key] = by_reason.get(key, 0) + 1

    top = sorted(by_reason.items(), key=lambda kv: -kv[1])[: max(1, int(top_reasons))]

    return {
        "window_days": int(days),
        "total": len(filtered),
        "by_stage": [
            {"stage": s, "count": c}
            for s, c in sorted(by_stage.items(), key=lambda kv: -kv[1])
        ],
        "top_reasons": [{"label": k, "count": v} for k, v in top],
    }
