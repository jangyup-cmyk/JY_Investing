import json
import logging
from datetime import datetime
from pathlib import Path

import theme_extractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    source_dirs = [
        "etc/telegram_texts",
        "etc/sub_data",
    ]

    texts: list[str] = []
    for directory in source_dirs:
        loaded = theme_extractor.load_texts_from_directory(directory)
        logger.info(f"[소스] {directory} 텍스트 {len(loaded)}건")
        texts.extend(loaded)

    if not texts:
        logger.warning("분석할 텍스트가 없습니다.")
        return

    updated = theme_extractor.update_theme_mapping_from_texts(texts, min_theme_hits=2)
    result = theme_extractor.extract_from_texts(texts, min_score=3.0)

    report = {
        "generated_at": datetime.now().isoformat(),
        "source_dirs": source_dirs,
        "text_count": len(texts),
        "updated_theme_mappings": updated,
        "recommended_codes": result.get("recommended_codes", []),
        "code_scores": result.get("code_scores", {}),
        "theme_frequency": result.get("theme_frequency", {}),
    }

    output_path = Path("etc/telegram_texts/auto_watchlist_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[완료] themes.json 갱신 종목 수: {updated}")
    logger.info(f"[완료] 추천 종목 수: {len(report['recommended_codes'])}")
    logger.info(f"[리포트] {output_path}")


if __name__ == "__main__":
    run()
