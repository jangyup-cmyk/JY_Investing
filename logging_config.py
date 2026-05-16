import logging
import os
from datetime import datetime

LOG_DIR = "logs"


def setup_logging():
    """로깅 설정"""
    # setup_logging() 호출 시에만 디렉토리 생성 (모듈 import 시 부수효과 방지)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"trading_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)
