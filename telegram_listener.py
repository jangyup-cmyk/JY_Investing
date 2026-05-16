"""
Telethon 기반 텔레그램 폴더별 채널 모니터링 모듈

대화방 폴더별로 분류된 채널들에서 실시간으로 메시지를 수집합니다.
"""

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from telethon import TelegramClient, events, functions, types
    from telethon.sessions import StringSession
except ImportError:
    TelegramClient = None
    logging.warning("⚠️  Telethon이 설치되지 않았습니다. pip install -r requirements.txt를 실행하세요.")

import config

logger = logging.getLogger(__name__)


def _safe_filename_part(value: str, fallback: str = "unknown") -> str:
    """파일명에 사용할 수 있는 안전한 문자열로 변환"""
    safe_value = "".join(c for c in value if c.isalnum() or c in ("_", "-")).strip()
    return safe_value or fallback


def build_message_output_path(
    output_dir: Path,
    folder_name: str,
    channel_name: str,
    timestamp: Optional[datetime] = None,
) -> Path:
    """수집 메시지를 저장할 파일 경로 생성"""
    timestamp = timestamp or datetime.now()
    safe_folder_name = _safe_filename_part(folder_name, fallback="default")
    safe_channel_name = _safe_filename_part(channel_name, fallback="channel")
    filename = f"{safe_channel_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
    return output_dir / safe_folder_name / filename


def save_messages_to_path(filename: Path, messages: List[str]) -> Optional[Path]:
    """메시지를 지정된 파일에 저장하고 저장 경로를 반환"""
    if not messages:
        return None

    filename.parent.mkdir(parents=True, exist_ok=True)
    content = "\n\n".join(messages)
    filename.write_text(content, encoding="utf-8")
    return filename


def load_listener_state(state_file: Path) -> Dict[str, int]:
    """채널별 마지막 수집 메시지 ID 상태를 로드"""
    if not state_file.exists():
        return {}

    try:
        raw_state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"텔레그램 리스너 상태 파일 로드 실패: {e}")
        return {}

    if not isinstance(raw_state, dict):
        logger.warning("텔레그램 리스너 상태 파일 형식이 올바르지 않습니다.")
        return {}

    state: Dict[str, int] = {}
    for channel_id, last_message_id in raw_state.items():
        try:
            state[str(channel_id)] = int(last_message_id)
        except (TypeError, ValueError):
            logger.warning(f"잘못된 메시지 ID 상태를 건너뜁니다: {channel_id}={last_message_id}")
    return state


def save_listener_state(state_file: Path, state: Dict[str, int]) -> Path:
    """채널별 마지막 수집 메시지 ID 상태를 저장"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = state_file.with_suffix(state_file.suffix + ".tmp")
    tmp_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_file.replace(state_file)
    return state_file


class TelegramListener:
    """Telethon 기반 텔레그램 메시지 수집기 - 채널별 직접 모니터링"""
    
    def __init__(self, api_id: int, api_hash: str, phone_number: str, 
                 channel_groups: Optional[Dict[str, List[str]]] = None,
                 folder_names: Optional[List[str]] = None,
                 session_file: str = "telegram_session",
                 state_file: Optional[str] = None):
        """
        Args:
            api_id: Telegram API ID (my.telegram.org에서 획득)
            api_hash: Telegram API Hash (my.telegram.org에서 획득)
            phone_number: 로그인할 전화번호 (예: "+82..."
            channel_groups: 모니터링할 채널 그룹 {"그룹명": ["@ch1", ...]}
            folder_names: 자동 탐색할 대화방 폴더명 리스트
            session_file: 세션 파일 저장 경로
            state_file: 채널별 마지막 수집 메시지 ID 저장 경로
        """
        if TelegramClient is None:
            raise ImportError("Telethon이 설치되지 않았습니다.")
        
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_file = session_file
        self.state_file = Path(state_file or config.TELEGRAM_LISTENER_STATE_FILE)
        self.client = None
        
        # 채널별 그룹 매핑: {"그룹명": ["@channel1", "channel_id2", ...]}
        # username(@로 시작) 또는 채널 ID 모두 지원
        self.channel_groups: Dict[str, List[str]] = channel_groups or {}
        self.folder_names: List[str] = folder_names or []
        
        # 수집된 메시지 저장 경로
        self.output_dir = Path(config.TEXT_SIGNAL_SOURCE_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def connect(self, max_retries: int = 3) -> bool:
        """텔레그램 클라이언트 연결 (실패 시 지수 백오프 재시도)"""
        for attempt in range(1, max_retries + 1):
            try:
                self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
                await self.client.start(phone=self.phone_number)
                logger.info("✅ Telethon 클라이언트 연결 성공")
                return True
            except Exception as e:
                logger.error(f"❌ Telethon 연결 실패 (시도 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    wait = 2 ** attempt  # 2s, 4s, 8s ...
                    logger.info(f"⏳ {wait}초 후 재연결 시도...")
                    await asyncio.sleep(wait)
        return False
    
    async def disconnect(self):
        """텔레그램 클라이언트 연결 해제"""
        if self.client:
            await self.client.disconnect()
            logger.info("Telethon 클라이언트 연결 해제")
    
    async def get_folder_info(self) -> Dict[str, List[Dict]]:
        """
        등록된 채널 그룹들의 정보를 반환
        
        Returns:
            {"그룹명": [{"name": "채널명", "id": 채널_id, "username": "@..."}, ...], ...}
        """
        if not self.client:
            logger.error("클라이언트가 연결되지 않았습니다.")
            return {}
        
        folder_info = {}
        
        for group_name, channel_refs in self.channel_groups.items():
            channels = []
            for channel_ref in channel_refs:
                try:
                    # username(@로 시작) 또는 ID로 엔티티 조회
                    entity = await self.client.get_entity(channel_ref)
                    
                    channels.append({
                        "name": getattr(entity, 'title', str(channel_ref)),
                        "id": entity.id,
                        "username": f"@{entity.username}" if hasattr(entity, 'username') and entity.username else None,
                    })
                except Exception as e:
                    logger.warning(f"채널 조회 실패 ({channel_ref}): {e}")
            
            folder_info[group_name] = channels
            logger.info(f"✅ '{group_name}' 그룹: {len(channels)}개 채널 확인")
        
        return folder_info
    
    async def get_channels_from_folder(self, folder_name: str) -> List[str]:
        """
        텔레그램 대화방 폴더(DialogFilter)에서 채널 ID들을 추출
        
        Args:
            folder_name: 폴더 이름 (예: '공시속보')
            
        Returns:
            추출된 채널 ID/Username 리스트
        """
        if not self.client:
            return []
            
        try:
            # 1. 모든 대화방 필터(폴더) 가져오기
            filters = await self.client(functions.messages.GetDialogFiltersRequest())
            
            target_filter = None
            for f in filters:
                if hasattr(f, 'title') and f.title == folder_name:
                    target_filter = f
                    break
            
            if not target_filter:
                logger.warning(f"❌ '{folder_name}' 폴더를 찾을 수 없습니다.")
                return []
            
            # 2. 폴더 내 피어(Peers) 추출
            channel_refs = []
            
            # include_peers에 포함된 채널들 확인
            peers = []
            if hasattr(target_filter, 'include_peers'):
                peers.extend(target_filter.include_peers)
            if hasattr(target_filter, 'pinned_peers'):
                peers.extend(target_filter.pinned_peers)
                
            for peer in peers:
                try:
                    # peer 객체에서 엔티티 가져오기
                    entity = await self.client.get_entity(peer)
                    if hasattr(entity, 'broadcast') and entity.broadcast:  # 채널인지 확인
                        ref = f"@{entity.username}" if entity.username else str(entity.id)
                        channel_refs.append(ref)
                except Exception as e:
                    logger.debug(f"Peer 처리 중 오류 (스킵): {e}")
            
            # 중복 제거
            channel_refs = list(set(channel_refs))
            logger.info(f"📂 폴더 '{folder_name}': {len(channel_refs)}개 채널 발견")
            return channel_refs
            
        except Exception as e:
            logger.error(f"폴더 채널 추출 중 오류: {e}")
            return []
    
    async def get_channel_info(self, channel_ref: str) -> Optional[Dict]:
        """
        단일 채널 정보 조회
        
        Args:
            channel_ref: 채널 username (@channel_name) 또는 채널 ID
            
        Returns:
            {"name": "채널명", "id": 채널_id, "username": "@..."}
        """
        if not self.client:
            logger.error("클라이언트가 연결되지 않았습니다.")
            return None
        
        try:
            entity = await self.client.get_entity(channel_ref)
            return {
                "name": getattr(entity, 'title', str(channel_ref)),
                "id": entity.id,
                "username": f"@{entity.username}" if hasattr(entity, 'username') and entity.username else None,
            }
        except Exception as e:
            logger.error(f"채널 조회 실패 ({channel_ref}): {e}")
            return None
    
    async def fetch_recent_messages(self, channel_id: int, limit: int = 100, folder_name: str = "default") -> List[str]:
        """
        특정 채널의 최근 메시지 수집
        
        Args:
            channel_id: 채널 ID
            limit: 수집할 메시지 개수
            folder_name: 폴더명 (파일 저장 시 사용)
            
        Returns:
            수집된 메시지 리스트
        """
        if not self.client:
            logger.error("클라이언트가 연결되지 않았습니다.")
            return []
        
        try:
            messages = []
            entity = await self.client.get_entity(channel_id)
            channel_name = getattr(entity, 'title', str(channel_id))
            
            # 최근 메시지 수집
            async for message in self.client.iter_messages(entity, limit=limit):
                if message.text:
                    messages.append(message.text)
            
            logger.info(f"📥 '{channel_name}' 에서 {len(messages)}개 메시지 수집")
            
            # 메시지를 파일로 저장
            if messages:
                await self._save_messages_to_file(folder_name, channel_name, messages)
            
            return messages
        except Exception as e:
            logger.error(f"메시지 수집 실패 (채널 {channel_id}): {e}")
            return []
    
    async def _save_messages_to_file(self, folder_name: str, channel_name: str, messages: List[str]) -> Optional[Path]:
        """수집한 메시지를 파일로 저장"""
        try:
            filename = build_message_output_path(self.output_dir, folder_name, channel_name)
            saved_path = save_messages_to_path(filename, messages)
            if saved_path:
                logger.info(f"💾 메시지 저장: {saved_path}")
            return saved_path
        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
            return None
    
    async def listen_to_channel_group(self, group_name: str, channel_refs: List[str], poll_interval: int = 300):
        """
        특정 그룹의 모든 채널을 모니터링하고 새 메시지 수집
        
        Args:
            group_name: 그룹 이름 (파일 저장 시 사용)
            channel_refs: 채널 리스트 (username @channel 또는 channel ID)
            poll_interval: 폴링 간격 (초)
        """
        if not self.client:
            logger.error("클라이언트가 연결되지 않았습니다.")
            return
        
        logger.info(f"🔍 그룹 '{group_name}' ({len(channel_refs)}개 채널) 모니터링 시작 (간격: {poll_interval}초)")
        
        last_message_ids = load_listener_state(self.state_file)
        
        try:
            while True:
                for channel_ref in channel_refs:
                    try:
                        # 채널 엔티티 조회
                        entity = await self.client.get_entity(channel_ref)
                        channel_id = entity.id
                        channel_name = getattr(entity, 'title', str(channel_ref))
                        
                        # 새 메시지만 수집
                        state_key = str(channel_id)
                        last_msg_id = last_message_ids.get(state_key, 0)
                        messages = []
                        message_ids = []
                        
                        async for message in self.client.iter_messages(entity, min_id=last_msg_id, limit=10):
                            if message.text:
                                messages.append(message.text)
                                message_ids.append(message.id)
                        
                        if messages:
                            logger.info(f"✨ '{channel_name}' 새 메시지 {len(messages)}개 감지")
                            saved_path = await self._save_messages_to_file(group_name, channel_name, messages)
                            if saved_path and message_ids:
                                last_message_ids[state_key] = max(message_ids)
                                save_listener_state(self.state_file, last_message_ids)
                            
                            # theme_extractor와 연동
                            try:
                                import theme_extractor
                                result = theme_extractor.extract_from_texts(messages)
                                if result.get("recommended_codes"):
                                    logger.info(f"🎯 추천 종목: {result['recommended_codes']}")
                            except Exception as e:
                                logger.warning(f"테마 추출 실패: {e}")
                        
                    except Exception as e:
                        logger.warning(f"채널 '{channel_ref}' 처리 중 오류: {e}")
                
                logger.debug(f"⏳ {poll_interval}초 후 다시 폴링...")
                await asyncio.sleep(poll_interval)
        
        except asyncio.CancelledError:
            logger.info(f"그룹 '{group_name}' 모니터링 중지")
        except Exception as e:
            logger.error(f"모니터링 오류: {e}")
    
    async def listen_to_all_groups(self, poll_interval: int = 300):
        """
        등록된 모든 채널 그룹 및 폴더 내 채널들을 동시에 모니터링
        
        Args:
            poll_interval: 폴링 간격 (초)
        """
        # 1. 폴더에서 채널 자동 추출 및 추가
        for folder_name in self.folder_names:
            channels = await self.get_channels_from_folder(folder_name)
            if channels:
                if folder_name in self.channel_groups:
                    self.channel_groups[folder_name] = list(set(self.channel_groups[folder_name] + channels))
                else:
                    self.channel_groups[folder_name] = channels
        
        if not self.channel_groups:
            logger.warning("모니터링할 채널 그룹이 설정되지 않았습니다.")
            return
            
        tasks = [
            self.listen_to_channel_group(group_name, channel_refs, poll_interval)
            for group_name, channel_refs in self.channel_groups.items()
        ]
        await asyncio.gather(*tasks)

    async def listen_to_multiple_groups(self, channel_group_configs: Dict[str, List[str]], poll_interval: int = 300):
        """
        여러 채널 그룹을 동시에 모니터링
        
        Args:
            channel_group_configs: {"그룹명": ["@channel1", "channel_id2", ...], ...}
            poll_interval: 폴링 간격 (초)
        """
        tasks = [
            self.listen_to_channel_group(group_name, channel_refs, poll_interval)
            for group_name, channel_refs in channel_group_configs.items()
        ]
        await asyncio.gather(*tasks)


# ============================================================================
# 비동기 래퍼 함수 (APScheduler 연동용)
# ============================================================================

def run_telegram_listener_async(listener: TelegramListener, poll_interval: int = 300):
    """
    APScheduler에서 호출할 수 있는 동기 래퍼 함수
    
    Args:
        listener: TelegramListener 인스턴스
        poll_interval: 폴링 간격 (초)
    """
    import time as _time

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    reconnect_delay = 30  # 모니터링 중단 후 재연결 대기 초

    try:
        while True:
            # 1. 연결 (내부적으로 최대 3회 재시도)
            connected = loop.run_until_complete(listener.connect())
            if not connected:
                logger.error(f"텔레그램 연결 최종 실패 — {reconnect_delay}초 후 재시도")
                _time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 300)  # 최대 5분 대기
                continue

            reconnect_delay = 30  # 연결 성공 시 대기 시간 초기화

            # 2. 모니터링 시작
            logger.info(f"🔍 텔레그램 {len(listener.channel_groups)}개 그룹 모니터링 시작")
            try:
                loop.run_until_complete(
                    listener.listen_to_all_groups(poll_interval)
                )
            except asyncio.CancelledError:
                logger.info("텔레그램 모니터링 중지됨")
                break
            except Exception as e:
                logger.error(f"모니터링 중 오류 — {reconnect_delay}초 후 재연결: {e}")
            finally:
                loop.run_until_complete(listener.disconnect())

            _time.sleep(reconnect_delay)

    except Exception as e:
        logger.error(f"리스너 실행 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()


async def main_async():
    """테스트용 메인 함수"""
    import config as cfg
    
    # Telegram API 자격증명 필요
    api_id = getattr(cfg, 'TELEGRAM_API_ID', None)
    api_hash = getattr(cfg, 'TELEGRAM_API_HASH', None)
    phone = getattr(cfg, 'TELEGRAM_PHONE', None)
    
    if not all([api_id, api_hash, phone]):
        logger.error("❌ config에서 TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE을 설정하세요.")
        return
    
    listener = TelegramListener(api_id, api_hash, phone, channel_groups=cfg.TELEGRAM_CHANNEL_GROUPS)
    
    if await listener.connect():
        try:
            await listener.listen_to_all_groups(poll_interval=cfg.TELEGRAM_POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("사용자가 중단함")
        finally:
            await listener.disconnect()


if __name__ == "__main__":
    asyncio.run(main_async())
