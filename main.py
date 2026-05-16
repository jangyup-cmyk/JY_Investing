import logging
import time

from logging_config import setup_logging
from scheduler import start_scheduler

logger = logging.getLogger(__name__)


def run() -> None:
    setup_logging()
    start_scheduler()
    logger.info("JY 투자클럽 자동매매 시스템이 시작되었습니다.")
    logger.info("실시간 모니터링 중...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("시스템 종료 중...")


if __name__ == "__main__":
    run()

