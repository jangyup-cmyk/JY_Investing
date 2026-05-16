"""
theme_db.py — 테마 분류 외부 DB 모듈

종목 코드에 대해 관련 텔레그램 테마를 연결하거나, 
테마 기반 필터를 확장할 때 사용합니다.
데이터는 themes.json에 영구 저장되며 스레드 안전하게 관리됩니다.
"""

import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

THEME_FILE = "themes.json"
_lock = threading.Lock()

def _load() -> dict:
    """파일에서 테마 딕셔너리 로드 (스레드 비안전 — 반드시 _lock 획득 후 호출)"""
    if not os.path.exists(THEME_FILE):
        return {}
    try:
        with open(THEME_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"themes.json 로드 실패: {e}")
        return {}

def _save(themes: dict) -> None:
    """테마 딕셔너리를 파일에 저장 (스레드 비안전 — 반드시 _lock 획득 후 호출)"""
    try:
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(themes, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"themes.json 저장 실패: {e}")

def get_codes_by_theme(theme_name: str) -> list:
    """특정 테마(키워드)가 포함된 모든 종목 코드 목록 반환"""
    with _lock:
        themes_data = _load()
        matched_codes = []
        for code, themes in themes_data.items():
            if theme_name in themes:
                matched_codes.append(code)
        return matched_codes

def get_themes_for_code(stock_code: str) -> list:
    """주어진 종목 코드의 테마 목록 반환"""
    with _lock:
        themes = _load()
        return themes.get(stock_code, [])

def add_theme_mapping(stock_code: str, themes: list) -> None:
    """특정 종목에 테마 매핑 추가 및 저장"""
    with _lock:
        data = _load()
        data[stock_code] = themes
        _save(data)
        logger.info(f"[{stock_code}] 테마 업데이트: {themes}")

def remove_theme_mapping(stock_code: str) -> bool:
    """특정 종목의 테마 매핑을 삭제"""
    with _lock:
        data = _load()
        if stock_code in data:
            del data[stock_code]
            _save(data)
            logger.info(f"[{stock_code}] 테마 매핑 삭제됨")
            return True
        return False

def get_all_themes() -> dict:
    """전체 테마 매핑 반환 (대시보드 등에서 활용 가능)"""
    with _lock:
        return _load()

def get_unique_theme_list() -> list:
    """등록된 모든 고유 테마(키워드) 목록 반환"""
    with _lock:
        data = _load()
        all_themes = set()
        for themes in data.values():
            all_themes.update(themes)
        return sorted(list(all_themes))
