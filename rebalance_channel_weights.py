import json
import logging
from datetime import datetime
from pathlib import Path

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _compute_weight(
    win_rate: float,
    avg_return_pct: float,
    signal_count: int,
    base_weight: float = 1.0,
) -> float:
    """
    성과 기반 채널 가중치 계산.
    - win_rate(0~1)와 avg_return_pct(%)를 결합
    - signal_count가 적으면 과최적화 방지 페널티
    """
    win_component = 0.6 * (win_rate - 0.5) * 2.0  # -0.6 ~ +0.6
    return_component = 0.03 * avg_return_pct       # 수익률 10% -> +0.3
    sample_penalty = -0.2 if signal_count < 5 else 0.0
    raw = base_weight + win_component + return_component + sample_penalty
    return round(_clamp(raw, 0.5, 2.0), 3)


def run() -> None:
    performance_path = Path("etc/channel_performance.json")
    if not performance_path.exists():
        logger.warning(f"성과 파일이 없습니다: {performance_path}")
        return

    try:
        perf = json.loads(performance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"성과 파일 파싱 실패: {exc}")
        return

    channels = perf.get("channels", {})
    if not isinstance(channels, dict) or not channels:
        logger.warning("채널 성과 데이터가 비어 있습니다.")
        return

    weights: dict[str, float] = {}
    for channel_name, metrics in channels.items():
        if not isinstance(metrics, dict):
            continue

        win_rate = float(metrics.get("win_rate", 0.5))
        avg_return_pct = float(metrics.get("avg_return_pct", 0.0))
        signal_count = int(metrics.get("signal_count", 0))
        base_weight = float(metrics.get("base_weight", 1.0))

        weights[channel_name] = _compute_weight(
            win_rate=win_rate,
            avg_return_pct=avg_return_pct,
            signal_count=signal_count,
            base_weight=base_weight,
        )

    output_path = Path(config.CHANNEL_WEIGHTS_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = {
        "generated_at": datetime.now().isoformat(),
        "source": str(performance_path),
        "weights": weights,
    }
    audit_path = Path("etc/telegram_texts/channel_weights_rebalance_report.json")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[리밸런싱 완료] 가중치 채널 수: {len(weights)}")
    logger.info(f"[가중치 파일] {output_path}")
    logger.info(f"[리포트] {audit_path}")


if __name__ == "__main__":
    run()
