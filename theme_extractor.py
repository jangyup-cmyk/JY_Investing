"""
텔레그램/뉴스 자연어 텍스트에서 종목 코드와 테마를 자동 추출하는 모듈.

설계 반영 포인트:
- 종목 alias dictionary 기반 매칭
- 테마 사전 + 기존 themes.json 기반 매칭
- URL/특수문자 제거 등 기본 노이즈 정리
- 점수 기반 종목-테마 연결
"""

from __future__ import annotations

import hashlib
import logging
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import theme_db

logger = logging.getLogger(__name__)

# 프로젝트에서 자주 쓰는 대표 별칭(필요 시 계속 확장)
STOCK_ALIASES: dict[str, list[str]] = {
    "005930": ["삼성전자", "삼전", "samsung electronics"],
    "000660": ["sk하이닉스", "하이닉스", "hynix"],
    "035420": ["네이버", "naver"],
    "035720": ["카카오", "kakao"],
    "373220": ["lg에너지솔루션", "lg엔솔"],
    "207940": ["삼성바이오로직스", "삼바"],
}
ALIASES_FILE = Path("etc/stock_aliases.json")

URL_PATTERN = re.compile(r"https?://\S+")
NON_TEXT_PATTERN = re.compile(r"[^0-9a-zA-Z가-힣\s%+\-]")
WHITESPACE_PATTERN = re.compile(r"\s+")
CODE_PATTERN = re.compile(r"\b\d{6}\b")


def normalize_text(text: str) -> str:
    """원문 노이즈를 줄인 정규화 텍스트 반환."""
    if not text:
        return ""
    normalized = URL_PATTERN.sub(" ", text)
    normalized = NON_TEXT_PATTERN.sub(" ", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip().lower()
    return normalized


def _load_theme_dictionary() -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """
    themes.json에서 종목->테마와 역방향(테마->종목) 사전 생성.
    """
    code_to_themes = theme_db.get_all_themes()
    theme_to_codes: dict[str, set[str]] = defaultdict(set)
    for code, themes in code_to_themes.items():
        for theme in themes:
            theme_to_codes[str(theme).lower()].add(code)
    return code_to_themes, theme_to_codes


def _load_alias_dictionary() -> dict[str, list[str]]:
    """내장 alias + 외부 alias 파일을 병합해 반환."""
    merged: dict[str, set[str]] = defaultdict(set)

    for code, aliases in STOCK_ALIASES.items():
        for alias in aliases:
            if alias:
                merged[code].add(alias)

    if ALIASES_FILE.exists():
        try:
            file_aliases = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
            if isinstance(file_aliases, dict):
                for code, aliases in file_aliases.items():
                    if isinstance(aliases, list):
                        for alias in aliases:
                            if isinstance(alias, str) and alias.strip():
                                merged[str(code)].add(alias.strip())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"alias 파일 로드 실패 ({ALIASES_FILE}): {exc}")

    return {code: sorted(aliases) for code, aliases in merged.items()}


def extract_stock_codes(text: str, allowed_codes: set[str] | None = None) -> set[str]:
    """텍스트에서 종목 코드/별칭 기반 종목 코드 추출."""
    normalized = normalize_text(text)
    found_codes = set(CODE_PATTERN.findall(normalized))

    aliases_map = _load_alias_dictionary()
    for code, aliases in aliases_map.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if alias_norm and alias_norm in normalized:
                found_codes.add(code)
                break

    if allowed_codes is not None:
        found_codes = {code for code in found_codes if code in allowed_codes}

    return found_codes


def extract_themes(text: str, known_themes: set[str]) -> set[str]:
    """텍스트에서 테마 키워드 추출."""
    normalized = normalize_text(text)
    found_themes = set()
    for theme in known_themes:
        if theme and theme in normalized:
            found_themes.add(theme)
    return found_themes


def extract_signal_from_text(text: str) -> dict:
    """
    텍스트 1건에서 종목/테마 신호를 추출.
    반환:
    {
      "codes": [...],
      "themes": [...],
      "code_scores": {code: score},
      "confidence": float
    }
    """
    code_to_themes, theme_to_codes = _load_theme_dictionary()
    known_themes = set(theme_to_codes.keys())

    aliases_map = _load_alias_dictionary()
    allowed_codes = set(code_to_themes.keys()) | set(aliases_map.keys())
    found_codes = extract_stock_codes(text, allowed_codes=allowed_codes)
    found_themes = extract_themes(text, known_themes)

    code_scores: dict[str, float] = {}
    for code in found_codes:
        base = 1.0
        overlap = len(set(map(str.lower, code_to_themes.get(code, []))) & found_themes)
        code_scores[code] = round(base + overlap * 0.5, 2)

    for theme in found_themes:
        for code in theme_to_codes.get(theme, set()):
            code_scores[code] = round(code_scores.get(code, 0.0) + 0.3, 2)

    confidence = 0.0
    if found_codes:
        confidence += 0.5
    if found_themes:
        confidence += 0.5

    return {
        "codes": sorted(found_codes),
        "themes": sorted(found_themes),
        "code_scores": dict(sorted(code_scores.items(), key=lambda x: x[1], reverse=True)),
        "confidence": round(confidence, 2),
    }


def _text_hash(text: str) -> str:
    """정규화된 텍스트의 SHA256 해시 반환 (중복 판별용)"""
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def deduplicate_texts(texts: list[str]) -> tuple[list[str], int]:
    """
    A방식: SHA256 해시 기반 전역 중복 제거.
    반환: (중복 제거된 텍스트 목록, 제거된 건수)
    """
    seen: set[str] = set()
    unique: list[str] = []
    for text in texts:
        h = _text_hash(text)
        if h not in seen:
            seen.add(h)
            unique.append(text)
    return unique, len(texts) - len(unique)


def extract_from_texts(texts: list[str], min_score: float = 1.0) -> dict:
    """
    텍스트 여러 건에서 집계 신호 생성 (레거시 호환용).
    내부적으로 extract_from_grouped_texts 를 단일 그룹으로 호출.
    """
    return extract_from_grouped_texts({"_all": texts}, min_score=min_score)


def extract_from_grouped_texts(
    text_groups: dict[str, list[str]],
    min_score: float = 1.0,
) -> dict:
    """
    A + C 방식 통합 추출:
      A. SHA256 해시로 전역 중복 텍스트 제거
      C. 종목별 언급 채널 수에 sqrt 정규화 적용 (과대평가 방지)

    Args:
        text_groups: {"그룹명": [텍스트, ...], ...}
        min_score:   추천 최소 점수

    Returns:
        recommended_codes, theme_frequency, code_scores, dedup_stats
    """
    # ── A: 전역 해시 중복 제거 ────────────────────────────────
    global_seen: set[str] = set()
    total_before = 0

    # 그룹별 중복 제거 후 신호 집계
    # channel_code_scores[group][code] = 해당 그룹 내 해당 종목 총점
    channel_code_scores: dict[str, Counter] = {}
    channel_themes: Counter = Counter()

    for group_name, texts in text_groups.items():
        group_counter: Counter = Counter()
        total_before += len(texts)
        for text in texts:
            h = _text_hash(text)
            if h in global_seen:
                continue                     # A: 전역 중복 스킵
            global_seen.add(h)
            signal = extract_signal_from_text(text)
            for code, score in signal["code_scores"].items():
                group_counter[code] += score
            for theme in signal["themes"]:
                channel_themes[theme] += 1
        if group_counter:
            channel_code_scores[group_name] = group_counter

    total_removed = total_before - len(global_seen)

    # ── C: 채널 정규화 (sqrt 감쇠) ───────────────────────────
    # 종목별 몇 개 그룹에서 언급됐는지 집계
    code_group_count: dict[str, int] = {}
    for group_scores in channel_code_scores.values():
        for code in group_scores:
            code_group_count[code] = code_group_count.get(code, 0) + 1

    final_scores: Counter = Counter()
    for group_scores in channel_code_scores.values():
        for code, raw_score in group_scores.items():
            n = code_group_count.get(code, 1)
            # sqrt 정규화: n개 그룹 언급 시 점수를 sqrt(n)으로 나눔
            # 단, 다채널 언급은 약한 보너스(+10%)로 반영
            normalized = raw_score / (n ** 0.5) * (1 + 0.1 * (n - 1))
            final_scores[code] += normalized

    recommended_codes = [
        code for code, score in final_scores.most_common() if score >= min_score
    ]

    logger.info(
        f"[테마추출] 입력 {total_before}건 → 중복제거 후 {len(global_seen)}건 "
        f"({total_removed}건 제거), 추천 {len(recommended_codes)}종목"
    )

    return {
        "recommended_codes": recommended_codes,
        "theme_frequency": dict(channel_themes.most_common()),
        "code_scores": {k: round(v, 2) for k, v in final_scores.most_common()},
        "dedup_stats": {
            "total_before": total_before,
            "unique_after": len(global_seen),
            "removed": total_removed,
            "groups": len(text_groups),
        },
    }


def load_texts_from_directory(directory: str) -> list[str]:
    """디렉터리 내 txt 파일 텍스트를 로드."""
    target = Path(directory)
    if not target.exists():
        return []

    texts: list[str] = []
    for file_path in sorted(target.glob("*.txt")):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            if content:
                texts.append(content)
        except OSError as exc:
            logger.warning(f"텍스트 파일 로드 실패 ({file_path}): {exc}")
    return texts


def load_texts_grouped_by_subdir(base_directory: str) -> dict[str, list[str]]:
    """
    base_directory 하위 폴더 단위로 txt 텍스트를 로드.
    - 하위 폴더가 있으면 폴더명을 채널명으로 사용
    - base_directory 루트 txt는 "_root" 그룹으로 반환
    """
    base = Path(base_directory)
    grouped: dict[str, list[str]] = {}
    if not base.exists():
        return grouped

    root_texts = load_texts_from_directory(str(base))
    if root_texts:
        grouped["_root"] = root_texts

    for child in sorted(base.iterdir()):
        if child.is_dir():
            texts = load_texts_from_directory(str(child))
            if texts:
                grouped[child.name] = texts
    return grouped


def update_theme_mapping_from_texts(texts: list[str], min_theme_hits: int = 1) -> int:
    """
    텍스트 집계 결과로 themes.json을 자동 보강.
    - 종목이 텍스트에서 확인되고
    - 해당 테마가 최소 min_theme_hits 이상 언급된 경우
    매핑에 추가.
    """
    code_to_themes, _ = _load_theme_dictionary()
    canonical_theme_by_lower: dict[str, str] = {}
    for themes in code_to_themes.values():
        for theme in themes:
            lower = str(theme).lower()
            if lower not in canonical_theme_by_lower:
                canonical_theme_by_lower[lower] = str(theme)
    theme_hits: Counter[str] = Counter()
    code_theme_hits: dict[str, Counter[str]] = defaultdict(Counter)

    for text in texts:
        signal = extract_signal_from_text(text)
        for theme in signal["themes"]:
            theme_hits[theme] += 1
            for code in signal["codes"]:
                code_theme_hits[code][theme] += 1

    updated_count = 0
    for code, counter in code_theme_hits.items():
        current = set(code_to_themes.get(code, []))
        current_by_lower = {str(theme).lower(): str(theme) for theme in current}
        new_themes = {
            theme
            for theme, hits in counter.items()
            if hits >= min_theme_hits and theme_hits[theme] >= min_theme_hits
        }
        merged_lower = set(current_by_lower.keys()) | set(new_themes)
        merged = sorted(
            [
                current_by_lower.get(
                    lower_theme, canonical_theme_by_lower.get(lower_theme, lower_theme)
                )
                for lower_theme in merged_lower
            ]
        )
        if merged and merged != sorted(current):
            theme_db.add_theme_mapping(code, merged)
            updated_count += 1

    return updated_count
