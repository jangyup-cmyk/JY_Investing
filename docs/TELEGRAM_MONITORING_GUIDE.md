# 🔔 텔레그램 실시간 모니터링 가이드

> 문서 버전: 2026-05-12

텔레그램의 대화방 폴더별로 분류된 채널들에서 **실시간으로 메시지를 자동 수집**하고 테마 분석을 수행합니다.

## 📋 목차

1. [사전 준비](#사전-준비)
2. [API 설정](#api-설정)
3. [폴더별 채널 등록](#폴더별-채널-등록)
4. [활성화 및 실행](#활성화-및-실행)
5. [모니터링 확인](#모니터링-확인)
6. [문제 해결](#문제-해결)

---

## 🔧 사전 준비

### Step 1: my.telegram.org에서 API 자격증명 발급

```
1. https://my.telegram.org 접속
2. Phone number 입력 후 인증 코드 입력
3. "API development tools" 클릭
4. 아래 정보 기록:
   - API ID: 123456
   - API Hash: abcdef1234567890...
```

**주의**: 이는 BotFather 봇 토큰과 **다릅니다**.

### Step 2: Telethon 라이브러리 설치

```bash
pip install -r requirements.txt
```

### Step 3: 텍스트 신호 폴더 구조 준비

```
etc/telegram_texts/
├── 투자채널/           # 폴더 1
│   ├── 바이브코딩_20260511_090000.txt
│   └── 기술매매봇_20260511_090100.txt
├── 신호채널/           # 폴더 2
│   └── ...
└── README.md
```

---

## ⚙️ API 설정

### Step 1: .env 파일 수정

`.env.example`을 복사하여 `.env`를 생성하고 아래를 수정합니다:

```bash
# Telegram API 자격증명 (my.telegram.org에서 발급)
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+82010XXXXXXXX

# 세션 파일 (첫 로그인 후 자동 생성)
TELEGRAM_SESSION_FILE=.telegram_session

# 채널별 마지막 수집 메시지 ID 상태 파일
TELEGRAM_LISTENER_STATE_FILE=etc/telegram_listener_state.json

# 모니터링 활성화
TELEGRAM_MONITOR_ENABLED=true

# 폴링 주기 (초 단위, 기본 5분)
TELEGRAM_POLL_INTERVAL=300

# 한 번에 수집할 메시지 개수
TELEGRAM_MESSAGE_FETCH_LIMIT=100
```

### Step 2: 폴더별 채널 ID 확인

텔레그램 GUI 또는 개발자 도구에서 각 폴더의 ID를 확인합니다.

```
메인 폴더: 0
투자채널 폴더: 1
신호채널 폴더: 2
...
```

---

## 📁 폴더별 채널 등록

### .env에서 모니터링 폴더 지정

현재 코드는 `.env`의 `TELEGRAM_MONITOR_FOLDERS`에 지정된 Telegram 폴더 이름을 읽어 채널을 자동 탐색합니다.

```bash
TELEGRAM_MONITOR_FOLDERS=공시속보,애널리스트,경제신문,분석가
```

### config.py에서 직접 채널 그룹 지정

공개 채널 username 또는 채널 ID를 직접 지정할 수도 있습니다:

```python
# config.py

TELEGRAM_CHANNEL_GROUPS: dict = {
    "투자채널": ["@channel_username", "-1001234567890"],
    "신호채널": ["@signal_channel"],
}
```

**실제 연결 확인**:

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

---

## ▶️ 활성화 및 실행

### Option 1: 자동 모드 (권장)

시스템 시작 시 자동으로 모니터링:

```bash
# .env에서 활성화
TELEGRAM_MONITOR_ENABLED=true

# main.py 실행
python main.py
```

### Option 2: 통합 테스트 모드

기본 `pytest`에서는 실제 Telegram 연결 테스트가 제외됩니다. 실제 계정 세션과 외부 API를 사용하는 테스트는 필요할 때만 실행하세요.

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

### 첫 실행 시 인증

첫 실행 시 터미널에서 인증 코드를 요청합니다:

```
Telethon 클라이언트 연결 중...
전화번호 입력 (+82...): [이미 설정됨]
인증 코드 입력: [SMS/텔레그램 앱에서 받은 코드]
```

---

## 📊 모니터링 확인

### 로그 확인

```
✅ Telethon 클라이언트 연결 성공
✅ 텔레그램 폴더별 모니터링 작업 등록됨
🔍 폴더 '투자채널' 모니터링 시작 (간격: 300초)
📥 '바이브코딩' 에서 15개 메시지 수집
🎯 추천 종목: ['005930', '000660', '035720']
💾 메시지 저장: etc/telegram_texts/투자채널/바이브코딩_20260511_090000.txt
```

### 수집된 파일 확인

```
etc/telegram_texts/
├── 투자채널/
│   ├── 바이브코딩_20260511_090000.txt  # 새로 수집된 메시지
│   └── 기술매매봇_20260511_090015.txt
└── 신호채널/
    └── ...
```

### 테마 추출 결과 확인

자동으로 `theme_extractor.extract_from_texts()`가 호출되어:

- 종목/테마 자동 추출
- `themes.json` 자동 업데이트
- 추천 종목 리스트 생성

---

## 🔧 문제 해결

### 1. "Telethon이 설치되지 않았습니다"

```bash
pip install Telethon==1.34.0
# 또는
pip install -r requirements.txt
```

### 2. "인증 실패" 또는 "코드 입력 초과"

```
- 텔레그램 앱을 여러 기기에서 동시 로그인 상태 확인
- 기존 세션 제거 후 재시도
rm .telegram_session*
```

### 3. "권한 없음" 에러

```
- 봇이 채널에 추가되지 않은 경우
- 채널 관리자가 아닌 경우
- → 채널 ID 재확인 및 권한 설정
```

### 4. 메시지가 수집되지 않음

```
a) 폴더 이름 확인
   TELEGRAM_MONITOR_FOLDERS에 실제 Telegram 폴더 이름이 들어 있는지 확인

b) 폴링 간격 확인
   TELEGRAM_POLL_INTERVAL 기본값: 300초 (5분)
   → 짧게 설정 시 API 속도 제한 주의

c) 로그 레벨 상향
   logging.getLogger('telegram_listener').setLevel(logging.DEBUG)
```

### 5. 성능 최적화

```python
# config.py 조정

# 폴링 주기 증가 (API 호출 감소)
TELEGRAM_POLL_INTERVAL = 600  # 10분

# 수집 메시지 수 제한
TELEGRAM_MESSAGE_FETCH_LIMIT = 50

# 실시간성과 비용의 균형을 위해 권장:
# - 개발/테스트: 60초 (1분)
# - 운영: 300초 (5분)
# - 경량 모드: 600초 (10분)
```

---

## 📌 실제 워크플로우

```
Telegram 대화방 폴더
    ↓ (새 메시지 감지)
┌─────────────────────────────────┐
│ telegram_listener.py            │ (5분마다 폴링)
│  - 각 폴더 채널 모니터링        │
│  - 새 메시지 수집               │
│  - etc/telegram_texts/에 저장   │
└─────────────────────────────────┘
    ↓ (메시지 수집)
┌─────────────────────────────────┐
│ theme_extractor.py              │
│  - 종목/테마 추출               │
│  - 점수 기반 추천               │
│  - Watch List 자동 생성         │
└─────────────────────────────────┘
    ↓ (추천 종목)
┌─────────────────────────────────┐
│ scheduler.py                    │
│  - 09:00~10:30 매매 파이프라인  │
│  - 에이전트 팀 실행             │
│  - 주문 실행                    │
└─────────────────────────────────┘
    ↓ (매매 결과)
┌─────────────────────────────────┐
│ telegram_bot.py                 │
│  - 개인별 신호/결과 알림        │
└─────────────────────────────────┘
```

---

## 🎯 다음 단계

1. **API 자격증명 준비**
   - my.telegram.org에서 API ID/Hash 발급

2. **.env 파일 설정**
   - TELEGRAM_API_ID, API_HASH, PHONE 입력

3. **폴더별 채널 등록**
   - .env에서 TELEGRAM_MONITOR_FOLDERS 수정
   - 필요 시 config.py에서 TELEGRAM_CHANNEL_GROUPS 수정

4. **활성화**
   - TELEGRAM_MONITOR_ENABLED=true

5. **실행 및 모니터링**
   - `python main.py`
   - 로그에서 수집 상황 확인

---

## 📚 참고 자료

- [Telethon 문서](https://docs.telethon.dev/)
- [Telegram API 개발자 센터](https://my.telegram.org/)
- [프로젝트 README](../README.md)
