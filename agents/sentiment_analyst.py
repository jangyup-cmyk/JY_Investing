import logging
import requests
import theme_db
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = [
    "상승", "호조", "흑자", "성장", "수주", "돌파", "강세", "급등", "기대",
    "최대", "수혜", "대박", "우상향", "매수", "목표가 상향", "청신호"
]

NEGATIVE_KEYWORDS = [
    "하락", "부진", "적자", "감소", "취소", "붕괴", "약세", "급락", "우려",
    "최저", "악재", "쇼크", "우하향", "매도", "목표가 하향", "적신호", "리스크"
]

# 텔레그램 텍스트 모듈 레벨 캐시 (파이프라인 실행 1회당 1번만 파일 로드)
_telegram_texts_cache: list[str] | None = None


def _get_telegram_texts() -> list[str]:
    """텔레그램 수집 텍스트 파일 로드 (모듈 내 캐시)"""
    global _telegram_texts_cache
    if _telegram_texts_cache is not None:
        return _telegram_texts_cache
    try:
        import config
        import theme_extractor
        _telegram_texts_cache = theme_extractor.load_texts_from_directory(
            config.TEXT_SIGNAL_SOURCE_DIR
        )
        logger.debug(f"텔레그램 텍스트 {len(_telegram_texts_cache)}건 로드")
    except Exception as e:
        logger.warning(f"텔레그램 텍스트 로드 실패: {e}")
        _telegram_texts_cache = []
    return _telegram_texts_cache


def clear_telegram_cache():
    """파이프라인 사이클마다 캐시 초기화 (scheduler에서 호출)"""
    global _telegram_texts_cache
    _telegram_texts_cache = None


class SentimentAnalyst(BaseAgent):
    """뉴스/감정 분석 에이전트 — 텔레그램 수집 데이터 + 네이버 뉴스 병합"""

    def __init__(self):
        super().__init__("Sentiment Analyst")
        self.naver_news_api = "https://m.stock.naver.com/api/news/stock/{stock_code}?pageSize=10"

    def fetch_recent_news(self, stock_code: str) -> list:
        """네이버 모바일 증권 API에서 최근 뉴스 제목 수집"""
        url = self.naver_news_api.format(stock_code=stock_code)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 429:
                logger.warning(f"뉴스 API Rate-limit (429) — 종목: {stock_code}")
                return []
            if res.status_code != 200:
                logger.warning(f"뉴스 API 비정상 응답 ({stock_code}): HTTP {res.status_code}")
                return []
            try:
                data = res.json()
            except ValueError:
                logger.error(f"뉴스 응답 JSON 파싱 실패 ({stock_code}): {res.text[:200]}")
                return []
            if not isinstance(data, list):
                logger.warning(f"뉴스 응답 구조 이상 ({stock_code}): list 기대, {type(data).__name__} 수신")
                return []
            titles = []
            for group in data:
                if not isinstance(group, dict):
                    continue
                for item in group.get("items", []):
                    if isinstance(item, dict):
                        titles.append(item.get("title", ""))
            return titles
        except Exception as e:
            logger.error(f"뉴스 수집 실패 ({stock_code}): {e}")
        return []

    def analyze_news_sentiment(self, texts: list) -> float:
        """텍스트 목록 기반 감정 점수 계산 (0.0 ~ 1.0)"""
        if not texts:
            return 0.5

        pos_count = sum(
            1 for t in texts for kw in POSITIVE_KEYWORDS if kw in t
        )
        neg_count = sum(
            1 for t in texts for kw in NEGATIVE_KEYWORDS if kw in t
        )
        total = pos_count + neg_count
        if total == 0:
            return 0.5
        return round(pos_count / total, 2)

    def analyze_telegram_sentiment(self, stock_code: str) -> tuple[float, int]:
        """
        수집된 텔레그램 텍스트 중 해당 종목 언급 메시지만 필터링해 감정 점수 계산.
        반환: (score 0.0~1.0, 언급된 메시지 수)
        """
        try:
            import theme_extractor
            all_texts = _get_telegram_texts()
            if not all_texts:
                return 0.5, 0

            # 해당 종목이 언급된 텍스트만 추출
            relevant = [
                t for t in all_texts
                if stock_code in theme_extractor.extract_stock_codes(t)
            ]
            if not relevant:
                return 0.5, 0

            score = self.analyze_news_sentiment(relevant)
            return score, len(relevant)
        except Exception as e:
            logger.warning(f"텔레그램 감정 분석 실패 ({stock_code}): {e}")
            return 0.5, 0

    def process(self, input_data: dict) -> dict:
        """
        감정 점수 = 텔레그램 수집 데이터(60%) + 네이버 뉴스(40%)
        텔레그램 언급이 없으면 뉴스만 사용.
        """
        stock_code = input_data.get("stock_code", "")

        # 1. 테마 조회
        themes = theme_db.get_themes_for_code(stock_code)

        # 2. 텔레그램 감정 분석
        tg_score, tg_count = self.analyze_telegram_sentiment(stock_code)

        # 3. 네이버 뉴스 감정 분석
        news_titles = self.fetch_recent_news(stock_code)
        news_score = self.analyze_news_sentiment(news_titles)

        # 4. 가중 병합 — 텔레그램 언급이 있으면 60:40, 없으면 뉴스만
        if tg_count > 0:
            final_score = round(tg_score * 0.6 + news_score * 0.4, 2)
        else:
            final_score = news_score

        logger.info(
            f"감정 분석: {stock_code} — "
            f"텔레그램 {tg_count}건({tg_score:.2f}) / "
            f"뉴스 {len(news_titles)}건({news_score:.2f}) → "
            f"최종 {final_score:.2f}"
        )

        return {
            "stock_code": stock_code,
            "themes": themes,
            "sentiment_score": final_score,
            "telegram_mentions": tg_count,
            "news_analyzed": len(news_titles),
            "confidence": tg_count > 0 or len(news_titles) > 0,
        }
