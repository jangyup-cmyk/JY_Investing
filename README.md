# JY 투자클럽 AI 자동매매 시스템

[![tests](https://github.com/jangyup-cmyk/JY_Investing/actions/workflows/test.yml/badge.svg)](https://github.com/jangyup-cmyk/JY_Investing/actions/workflows/test.yml)

> 문서 버전: 2026-05-18
> 현재 테스트 상태: `68 passed, 9 deselected (integration/manual 제외)`

이 프로젝트는 한국투자증권(KIS) API 기반의 텔레그램 테마 연동 자동매매 시스템입니다. AI 테마 분석, 13개 기술 지표 필터, 다계좌 분할 매수, 개인별 텔레그램 알림을 핵심으로 합니다.

## 주요 구성

- `config.py`: 계좌, 텔레그램, 필터 설정 (필수 환경변수 미설정 시 ValueError 발생)
- `analyzer.py`: 13대 실전 매매 조건 필터
- `trader.py`: bull_score 기반 동적 비중 분할 주문 (70% 또는 40% 시장가 + 잔여 지정가), 10분 미체결 자동 취소
- `telegram_bot.py`: 개인별 텔레그램 봇/채널 알림
- `telegram_listener.py`: Telethon 기반 폴더별 채널 실시간 메시지 수집 (지수 백오프 재연결)
- `stock_data.py`: KIS API를 통한 주식 데이터 수집
- `kis_api.py`: 한국투자증권 KIS API 클라이언트 (주문, 취소, 잔고, 데이터 조회, 모듈 레벨 토큰 캐싱)
- `scheduler.py`: APScheduler 백그라운드 스케줄링, 토큰 갱신, 텔레그램 모니터링
- `main.py`: 시스템 진입점
- `dashboard.py`: Flask 기반 모니터링 대시보드 (`/api/balance`, `/api/positions`, `/api/logs`, `/api/system-status`, `/api/ai-costs`)
- `sync_positions.py`: 실계좌 보유 종목 → `positions.json` 자동 동기화 (손절/익절가 자동 산출)
- `theme_db.py`: 테마 분류 DB
- `theme_extractor.py`: 텔레그램/뉴스 자연어에서 종목·테마 자동 추출, 점수 기반 watch list 생성
- `agents/`: 멀티-에이전트 팀 (Sentiment → Technical → Researcher → Risk → Trader → Portfolio)
- `check_config.py`: 실행 전 환경변수 검증 스크립트
- `check_kis_api.py`: KIS API 실계좌 연결 검증 (읽기 전용)
- `CLAUDE.md`: Claude Code 작업 워크플로우 및 실계좌 보호 규칙

## 시작하기

### 1단계: 환경 준비

```powershell
# Python 3.11 이상 필요
python --version

# 의존성 설치
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 기본 테스트 실행
.\venv\Scripts\python.exe -m pytest
```

### 2단계: 환경 변수 설정 (중요!)

```bash
# .env.example에서 복사
copy .env.example .env.local    # Windows
```

**`.env.local` 파일에 실제 값 입력:**

```bash
# 계좌 1
KIS_ACCOUNT_NO_JY_Investing1=your_account_no
KIS_APP_KEY_JY1=your_app_key
KIS_APP_SECRET_JY1=your_app_secret
TELEGRAM_BOT_TOKEN_JY_Investing1=your_bot_token

# 계좌 2
KIS_ACCOUNT_NO_JY_Investing2=your_account_no_2
KIS_APP_KEY_JY2=your_app_key_2
KIS_APP_SECRET_JY2=your_app_secret_2
TELEGRAM_BOT_TOKEN_JY_Investing2=your_bot_token_2

# 공통
TELEGRAM_CHANNEL_ID_JY_Investing=-100xxxxxxxxxx
TELEGRAM_ADMIN_BOT_TOKEN=your_admin_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id
```

### 3단계: 실행 전 검증

```bash
# 환경변수 검증
python check_config.py

# KIS API 실계좌 연결 확인 (읽기 전용)
python check_kis_api.py
```

### 4단계: 실행

```bash
# 전체 시스템 실행
python main.py

# 대시보드 (별도 터미널)
python dashboard.py
# → http://127.0.0.1:5000
```

### 텔레그램 실시간 모니터링 (선택)

```bash
# .env.local에 설정
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=abcdef1234567890...
TELEGRAM_PHONE=+82010XXXXXXXX
TELEGRAM_MONITOR_ENABLED=true
TELEGRAM_MONITOR_FOLDERS=공시속보,애널리스트,경제신문,분석가
```

**상세 가이드**: [📖 텔레그램 모니터링 가이드](docs/TELEGRAM_MONITORING_GUIDE.md)

### 테스트 정책

기본 `pytest`는 외부 API나 실계정 세션을 사용하지 않는 테스트만 실행합니다.

```powershell
.\venv\Scripts\python.exe -m pytest
```

실제 KIS/Telegram 계정과 세션 파일을 사용하는 통합 테스트는 명시적 실행 플래그가 없으면 skip됩니다.

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

### 자연어 기반 종목/테마 자동 추출 (선택)

`scheduler.run_signal_pipeline()`는 `WATCH_LIST`가 비어 있을 때 자동으로 텍스트 파일을 분석해 종목 후보를 만듭니다.

```bash
AUTO_BUILD_WATCH_LIST=true
TEXT_SIGNAL_SOURCE_DIR=etc/telegram_texts
THEME_EXTRACTION_MIN_SCORE=2.0
```

즉시 부트스트랩:
```bash
python run_theme_bootstrap.py
```

채널별 비교 리포트:
```bash
python compare_channel_signals.py
```

채널 가중치 리밸런싱:
```bash
python rebalance_channel_weights.py
```

### 보안 주의

- ✅ `.env.local` 파일은 **절대 Git에 커밋하지 마세요**
- ✅ `.gitignore`에 `.env*` 가 추가되어 있습니다
- ✅ 모의 투자 계좌로 테스트 후 실계정으로 전환 권장

**상세 가이드:** [KIS API 설정 가이드](docs/KIS_API_GUIDE.md)

## 에이전트 파이프라인

```
입력 데이터
    ↓
[Sentiment Analyst]  텔레그램 + 네이버 뉴스 감정 점수
    ↓
[Technical Analyst]  13개 필터 + MACD/Stoch 스코어 → 탈락 시 중단
    ↓
[Researcher Team]    bull_score 계산 → 0.60 미만 시 중단
    ↓
[Risk Management]    손절/익절 설정, 거래 시간 확인 → 거부 시 중단
    ↓
[Trader Agent]       동적 비중 분할 매수 실행
    ↓
[Portfolio Manager]  최종 승인 기록
```

## 문서

- `docs/README_ARCHITECTURE.md`: 시스템 아키텍처
- `docs/README_AGENT.md`: 에이전트 팀 구조 및 역할
- `docs/README_USER.md`: 사용자 가이드
- `docs/KIS_API_GUIDE.md`: 한국투자증권 API 연동 가이드
- `docs/agent_flow_diagram.md`: 에이전트 흐름 다이어그램 및 코드 구조
- `docs/DATA_COLLECTION_TEST.md`: 데이터 수집 테스트 가이드
