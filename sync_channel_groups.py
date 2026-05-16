"""
텔레그램 폴더 구조를 읽어 channel_groups.json과
config.TELEGRAM_CHANNEL_GROUPS를 자동 갱신하는 모듈.

스케줄러 시작 시 및 주기적으로 호출됨.
텔레그램 앱에서 폴더 채널을 추가/삭제하면 자동 반영됨.
"""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 동기화에서 제외할 폴더명 (시스템/봇 폴더)
_EXCLUDE_FOLDERS = {"텔레그램", "Telegram", "Archived"}


async def _fetch_folder_channels(api_id: int, api_hash: str, session_file: str) -> dict:
    """텔레그램 폴더별 채널 ID 목록 반환"""
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.messages import GetDialogFiltersRequest
        from telethon.tl.types import DialogFilter
    except ImportError:
        logger.error("Telethon 미설치 — 채널 그룹 동기화 불가")
        return {}

    client = TelegramClient(session_file, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("텔레그램 세션 미인증 — auth_telegram.py를 먼저 실행하세요")
            return {}

        filters = await client(GetDialogFiltersRequest())
        groups = {}

        for f in filters:
            if not isinstance(f, DialogFilter):
                continue
            if f.title in _EXCLUDE_FOLDERS:
                continue
            if not f.include_peers:
                continue

            channels = []
            for peer in f.include_peers:
                try:
                    entity = await client.get_entity(peer)
                    eid = getattr(entity, "id", None)
                    if eid:
                        channels.append(f"-100{eid}")
                except Exception as e:
                    logger.debug(f"채널 조회 실패 (폴더: {f.title}): {e}")

            if channels:
                groups[f.title] = channels

        return groups

    except Exception as e:
        logger.error(f"텔레그램 폴더 조회 오류: {e}")
        return {}
    finally:
        await client.disconnect()


def sync_channel_groups() -> bool:
    """
    텔레그램 폴더를 읽어 channel_groups.json과 config.TELEGRAM_CHANNEL_GROUPS 갱신.
    변경이 있으면 True, 없거나 실패하면 False 반환.
    """
    import config

    new_groups = asyncio.run(_fetch_folder_channels(
        api_id=config.TELEGRAM_API_ID,
        api_hash=config.TELEGRAM_API_HASH,
        session_file=config.TELEGRAM_SESSION_FILE,
    ))

    if not new_groups:
        logger.warning("채널 그룹 동기화 실패 — 기존 설정 유지")
        return False

    # 변경 여부 확인
    if new_groups == config.TELEGRAM_CHANNEL_GROUPS:
        logger.debug("채널 그룹 변경 없음")
        return False

    # JSON 파일 저장
    groups_path = Path(config.CHANNEL_GROUPS_FILE)
    groups_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        groups_path.write_text(
            json.dumps(new_groups, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error(f"channel_groups.json 저장 실패: {e}")
        return False

    # config 딕셔너리 in-place 업데이트 (리스너 재시작 불필요)
    added = set(new_groups) - set(config.TELEGRAM_CHANNEL_GROUPS)
    removed = set(config.TELEGRAM_CHANNEL_GROUPS) - set(new_groups)

    config.TELEGRAM_CHANNEL_GROUPS.clear()
    config.TELEGRAM_CHANNEL_GROUPS.update(new_groups)

    total = sum(len(v) for v in new_groups.values())
    logger.info(
        f"✅ 채널 그룹 동기화 완료 — "
        f"{len(new_groups)}개 그룹 / {total}개 채널"
        + (f" | 추가 폴더: {added}" if added else "")
        + (f" | 제거 폴더: {removed}" if removed else "")
    )
    return True
