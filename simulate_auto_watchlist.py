import json
import logging
from pathlib import Path

import config
from scheduler import resolve_stock_codes, run_signal_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    resolved = resolve_stock_codes(config.WATCH_LIST)
    summary = run_signal_pipeline(stock_codes=resolved, simulate_only=True)

    report = {
        "auto_build_watch_list": config.AUTO_BUILD_WATCH_LIST,
        "use_channel_weighted_watchlist": config.USE_CHANNEL_WEIGHTED_WATCHLIST,
        "channel_comparison_report_path": config.CHANNEL_COMPARISON_REPORT_PATH,
        "channel_weights_file": config.CHANNEL_WEIGHTS_FILE,
        "channel_weighted_top_n": config.CHANNEL_WEIGHTED_TOP_N,
        "text_signal_source_dir": config.TEXT_SIGNAL_SOURCE_DIR,
        "theme_extraction_min_score": config.THEME_EXTRACTION_MIN_SCORE,
        "resolved_stock_codes": resolved,
        "pipeline_simulation": summary,
    }

    output = Path("etc/telegram_texts/pipeline_simulation_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[시뮬레이션 완료] 종목 {len(resolved)}개")
    logger.info(f"[리포트] {output}")


if __name__ == "__main__":
    run()
