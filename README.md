# JY 투자클럽 AI 자동매매 시스템

> 문서 버전: 2026-05-12
> 현재 기본 테스트 상태: `30 passed, 1 deselected`

이 프로젝트는 한국투자증권(KIS) API 기반의 텔레그램 테마 연동 자동매매 시스템입니다. AI 테마 분석, 13개 기술 지표 필터, 다계좌 분할 매수, 개인별 텔레그램 알림을 핵심으로 합니다.

## 주요 구성

- `config.py`: 계좌, 텔레그램, 필터 설정
- `analyzer.py`: 13대 실전 매매 조건 필터
- `trader.py`: 50% 시장가 + 50% 지정가 분할 주문, 10분 미체결 자동 취소
- `telegram_bot.py`: 개인별 텔레그램 봇/채널 알림
- `telegram_listener.py`: ⭐️ **Telethon 기반 폴더별 채널 실시간 메시지 수집** (신규)
- `stock_data.py`: KIS API를 통한 주식 데이터 수집
- `kis_api.py`: ⭐️ 한국투자증권 KIS API 클라이언트 (주문, 취소, 잔고, 데이터 조회)
- `scheduler.py`: APScheduler 백그라운드 스케줄링, 토큰 갱신, 텔레그램 모니터링
- `main.py`: 시스템 진입점
- `dashboard.py`: Flask 기반 대시보드 스켈레톤
- `theme_db.py`: 테마 분류 DB 스켈레톤
- `theme_extractor.py`: 텔레그램/뉴스 자연어에서 종목·테마 자동 추출, 점수 기반 watch list 생성
- `agents/`: 멀티-에이전트 팀 구조 구현 (Sentiment, Technical, Researcher, Risk, Trader, Portfolio)

## AI-Trader 참고 반영

`HKUDS_README.md`에서 참고한 내용:

- 백엔드/백그라운드 작업 분리
- 모듈화된 `service/`, `docs/` 스타일
- 에이전트/도큐먼트 중심 설계

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

**.env 파일 생성** (코드에 API 키 노출 금지):

```bash
# .env.example에서 복사
copy .env.example .env    # Windows
# or
cp .env.example .env      # macOS/Linux
```

**`.env` 파일에 실제 값 입력:**

```bash
# KIS API 키 (한국투자증권 개발자센터에서 발급)
KIS_APP_KEY_JY=your_actual_app_key_here
KIS_APP_SECRET_JY=your_actual_app_secret_here
KIS_ACCOUNT_NO_JY=your_account_no_here

# Telegram Bot 토큰
TELEGRAM_BOT_TOKEN_JY=your_bot_token_here
TELEGRAM_CHANNEL_ID_JY=@your_channel_id

# 기타 설정...
```

### 3단계: 실행

```bash
# 전체 시스템 실행
python main.py

# 또는 데이터 수집 테스트
python test_stock_data.py
```

### 3-1단계: 텔레그램 실시간 모니터링 (선택)

**대화방 폴더별로 텔레그램 채널을 모니터링하여 자동으로 메시지를 수집합니다.**

#### 빠른 시작

```bash
# 1. my.telegram.org에서 API ID/Hash 발급
#    https://my.telegram.org → "API development tools"

# 2. .env 파일에 설정
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=abcdef1234567890...
TELEGRAM_PHONE=+82010XXXXXXXX
TELEGRAM_MONITOR_ENABLED=true

# 3. .env/config.py에서 모니터링 대상 지정
# .env: 텔레그램 폴더 이름 목록
TELEGRAM_MONITOR_FOLDERS=공시속보,애널리스트,경제신문,분석가

# config.py: 직접 채널 그룹을 지정할 수도 있음
TELEGRAM_CHANNEL_GROUPS = {
    "투자채널": ["@channel_username", "-1001234567890"],
}

# 4. 시스템 실행
python main.py
# → 자동으로 텔레그램 폴더 모니터링 시작
```

**상세 가이드**: [📖 텔레그램 모니터링 가이드](docs/TELEGRAM_MONITORING_GUIDE.md)

### 테스트 정책

기본 `pytest`는 외부 API나 실계정 세션을 사용하지 않는 테스트만 실행합니다.

```powershell
.\venv\Scripts\python.exe -m pytest
```

실제 KIS/Telegram 계정과 세션 파일을 사용하는 테스트는 `integration` 마커로 분리되어 있고, 명시적 실행 플래그가 없으면 skip됩니다.

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

### 4단계: 자연어 기반 종목/테마 자동 추출(선택)

`scheduler.run_signal_pipeline()`는 `WATCH_LIST`가 비어 있을 때 자동으로 텍스트 파일을 분석해 종목 후보를 만듭니다.

- 입력 폴더: `TEXT_SIGNAL_SOURCE_DIR` (기본값: `etc/telegram_texts`)
- 파일 형식: 폴더 내 `*.txt` (텔레그램 메시지/뉴스 원문)
- 처리 내용:
  - 종목 코드/별칭(alias) 추출
  - 테마 키워드 추출
  - `themes.json` 자동 보강
  - 점수 기반 추천 종목 리스트 생성

예시 `.env` 설정:

```bash
AUTO_BUILD_WATCH_LIST=true
TEXT_SIGNAL_SOURCE_DIR=etc/telegram_texts
THEME_EXTRACTION_MIN_SCORE=2.0
```

즉시 1회 부트스트랩 실행:

```bash
python run_theme_bootstrap.py
```

- 분석 소스: `etc/telegram_texts`, `etc/sub_data`
- 결과 리포트: `etc/telegram_texts/auto_watchlist_report.json`
- 목적: `themes.json` 자동 보강 + 추천 종목 초기 셋 생성

채널별 비교 리포트 생성:

```bash
python compare_channel_signals.py
```

- 입력 구조 예시:
  - `etc/telegram_texts/channel_alpha/*.txt`
  - `etc/telegram_texts/channel_beta/*.txt`
  - `etc/telegram_texts/*.txt` (루트 파일은 `_root` 채널로 집계)
- 결과 리포트: `etc/telegram_texts/channel_comparison_report.json`

채널 가중치 기반 통합 watch list:

- 가중치 파일: `etc/channel_weights.json`
- 기본 동작: `resolve_stock_codes()`가 채널 비교 리포트 + 가중치를 우선 사용
- 설정:

```bash
USE_CHANNEL_WEIGHTED_WATCHLIST=true
CHANNEL_COMPARISON_REPORT_PATH=etc/telegram_texts/channel_comparison_report.json
CHANNEL_WEIGHTS_FILE=etc/channel_weights.json
CHANNEL_WEIGHTED_TOP_N=10
```

주간 채널 가중치 리밸런싱:

```bash
python rebalance_channel_weights.py
```

- 입력 성과 파일: `etc/channel_performance.json`
- 출력 가중치 파일: `etc/channel_weights.json`
- 감사 리포트: `etc/telegram_texts/channel_weights_rebalance_report.json`

### 보안 주의

- ✅ `.env` 파일은 **절대 Git에 커밋하지 마세요**
- ✅ `.gitignore`에 `.env`가 추가되어 있습니다
- ✅ 모의 투자 계좌로 테스트 후 실계정으로 전환 권장

**상세 가이드:** [KIS API 설정 가이드](docs/KIS_API_GUIDE.md)

## 문서

- `docs/README_ARCHITECTURE.md`: 시스템 아키텍처
- `docs/README_AGENT.md`: 에이전트 팀 구조 및 역할
- `docs/README_USER.md`: 사용자 가이드
- `docs/KIS_API_GUIDE.md`: 한국투자증권 API 연동 가이드
- `docs/agent_flow_diagram.md`: 에이전트 흐름 다이어그램 및 코드 구조
- `docs/DATA_COLLECTION_TEST.md`: 데이터 수집 테스트 가이드
