"""
텔레그램 Telethon 세션 인증 + 폴더별 채널 조회 스크립트

실행 방법:
    .\\venv\\Scripts\\python.exe auth_telegram.py
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv(override=False)
load_dotenv(".env.local", override=False)

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    from telethon.tl.types import DialogFilter
except ImportError:
    print("❌ Telethon이 설치되지 않았습니다.")
    raise SystemExit(1)

API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE    = os.getenv("TELEGRAM_PHONE", "")
SESSION  = os.getenv("TELEGRAM_SESSION_FILE", ".telegram_session")


async def list_folders(client):
    """텔레그램 폴더(필터)별 채널 목록 출력"""
    filters = await client(GetDialogFiltersRequest())

    if not filters:
        print("폴더가 없습니다.")
        return

    for f in filters:
        if not isinstance(f, DialogFilter):
            continue
        print(f"\n📁 폴더: {f.title}")
        if not f.include_peers:
            print("   (채널 없음)")
            continue
        for peer in f.include_peers:
            try:
                entity = await client.get_entity(peer)
                name = getattr(entity, "title", getattr(entity, "first_name", "?"))
                eid = getattr(entity, "id", "?")
                # 채널 ID는 -100 prefix 형식으로 변환
                channel_id = f"-100{eid}" if eid != "?" else "?"
                print(f"   {channel_id}  |  {name}")
            except Exception as e:
                print(f"   (조회 실패: {e})")


async def main():
    print(f"📱 텔레그램 연결 중...")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        print("📨 텔레그램 앱으로 인증 코드가 전송되었습니다.")
        code = input("인증 코드 입력: ").strip()
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            password = input("2단계 인증 비밀번호 입력: ").strip()
            await client.sign_in(password=password)

    me = await client.get_me()
    print(f"✅ {me.first_name} (@{me.username})")

    await list_folders(client)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
