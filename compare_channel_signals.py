import json
import logging
from datetime import datetime
from pathlib import Path

import config
import theme_extractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    grouped = theme_extractor.load_texts_grouped_by_subdir(config.TEXT_SIGNAL_SOURCE_DIR)
    if not grouped:
        logger.warning(f"채널 텍스트가 없습니다: {config.TEXT_SIGNAL_SOURCE_DIR}")
        return

    channel_reports: dict[str, dict] = {}
    for channel, texts in grouped.items():
        aggregated = theme_extractor.extract_from_texts(
            texts, min_score=config.THEME_EXTRACTION_MIN_SCORE
        )
        channel_reports[channel] = {
            "text_count": len(texts),
            "recommended_codes": aggregated.get("recommended_codes", []),
            "top_code_scores": dict(list(aggregated.get("code_scores", {}).items())[:10]),
            "top_theme_frequency": dict(list(aggregated.get("theme_frequency", {}).items())[:10]),
        }

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "source_dir": config.TEXT_SIGNAL_SOURCE_DIR,
        "channels": channel_reports,
    }

    output_path = Path("etc/telegram_texts/channel_comparison_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[채널 비교 완료] 채널 수: {len(channel_reports)}")
    logger.info(f"[리포트] {output_path}")


if __name__ == "__main__":
    run()
