"""
Telegram 리스너 테스트 스크립트

텔레그램 API 설정이 올바른지 확인하고 폴더/채널 정보를 출력합니다.
"""

import asyncio
import logging
import os
import config
import pytest

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS", "").lower() != "true",
    reason="set RUN_INTEGRATION_TESTS=true to connect to Telegram",
)
async def test_connection():
    """텔레그램 연결 테스트"""
    logger.info("=" * 80)
    logger.info("📱 Telegram 리스너 테스트 시작")
    logger.info("=" * 80)
    
    # 설정 확인
    logger.info("\n📋 설정 확인:")
    logger.info(f"   API ID: {config.TELEGRAM_API_ID if config.TELEGRAM_API_ID else '❌ 미설정'}")
    logger.info(f"   API Hash: {'✅ 설정됨' if config.TELEGRAM_API_HASH else '❌ 미설정'}")
    logger.info(f"   Phone: {config.TELEGRAM_PHONE if config.TELEGRAM_PHONE else '❌ 미설정'}")
    logger.info(f"   모니터링 활성화: {config.TELEGRAM_MONITOR_ENABLED}")
    logger.info(f"   모니터링 폴더: {config.TELEGRAM_MONITOR_FOLDERS}")
    
    # 필수 정보 확인
    if not all([config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH, config.TELEGRAM_PHONE]):
        logger.error("❌ 필수 설정이 누락되었습니다.")
        logger.error("   .env 파일에서 다음을 설정하세요:")
        logger.error("   - TELEGRAM_API_ID")
        logger.error("   - TELEGRAM_API_HASH")
        logger.error("   - TELEGRAM_PHONE")
        return False
    
    # Telethon 임포트 확인
    try:
        from telegram_listener import TelegramListener
    except ImportError as e:
        logger.error(f"❌ Telethon 라이브러리 임포트 실패: {e}")
        logger.error("   pip install -r requirements.txt 실행하세요.")
        return False
    
    # 리스너 생성 및 연결
    try:
        listener = TelegramListener(
            api_id=config.TELEGRAM_API_ID,
            api_hash=config.TELEGRAM_API_HASH,
            phone_number=config.TELEGRAM_PHONE,
            channel_groups=config.TELEGRAM_CHANNEL_GROUPS,
            folder_names=config.TELEGRAM_MONITOR_FOLDERS,
            session_file=os.getenv("TELEGRAM_TEST_SESSION_FILE", config.TELEGRAM_SESSION_FILE),
            state_file=os.getenv("TELEGRAM_TEST_STATE_FILE", config.TELEGRAM_LISTENER_STATE_FILE),
        )
        
        logger.info("\n🔌 텔레그램 연결 시도...")
        connected = await listener.connect()
        
        if not connected:
            logger.error("❌ 텔레그램 연결 실패")
            return False
        
        logger.info("✅ 텔레그램 연결 성공")
        
        # 폴더별 채널 목록 조회
        logger.info("\n📁 폴더별 채널 조회:")
        
        for folder_name in config.TELEGRAM_MONITOR_FOLDERS:
            logger.info(f"\n   📂 '{folder_name}':")
            
            channels = await listener.get_channels_from_folder(folder_name)
            
            if not channels:
                logger.warning(f"      → 채널을 찾을 수 없습니다.")
            else:
                for i, ch in enumerate(channels, 1):
                    logger.info(
                        f"      {i}. {ch['name']}"
                        f" (ID: {ch['id']}"
                        f"{', @' + ch['username'] if ch['username'] else ''})"
                    )
        
        # 최근 메시지 테스트 (첫 번째 폴더의 첫 번째 채널)
        logger.info("\n📩 최근 메시지 테스트:")
        
        if config.TELEGRAM_MONITOR_FOLDERS:
            first_folder_name = config.TELEGRAM_MONITOR_FOLDERS[0]
            
            channels = await listener.get_channels_from_folder(first_folder_name)
            
            if channels:
                test_channel = channels[0]
                logger.info(f"   '{test_channel['name']}'에서 최근 10개 메시지 수집...")
                
                messages = await listener.fetch_recent_messages(
                    channel_id=test_channel['id'],
                    limit=10,
                    folder_name=first_folder_name,
                )
                
                if messages:
                    logger.info(f"   ✅ {len(messages)}개 메시지 수집 성공")
                    logger.info(f"   💾 저장 위치: {config.TEXT_SIGNAL_SOURCE_DIR}/{first_folder_name}/")
                else:
                    logger.info("   ℹ️  수집된 메시지가 없습니다.")
        
        # 정리
        await listener.disconnect()
        logger.info("\n" + "=" * 80)
        logger.info("✅ 테스트 완료")
        logger.info("=" * 80)
        logger.info("\n📌 다음 단계:")
        logger.info("   1. .env에서 TELEGRAM_MONITOR_FOLDERS 확인")
        logger.info("   2. 필요 시 config.py에서 TELEGRAM_CHANNEL_GROUPS 확인")
        logger.info("   3. .env에서 TELEGRAM_MONITOR_ENABLED=true로 설정")
        logger.info("   4. python main.py로 시스템 시작")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_connection())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\n🛑 사용자가 중단함")
        exit(1)
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
