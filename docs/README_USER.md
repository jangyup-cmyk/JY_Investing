# 사용자 가이드

> 문서 버전: 2026-05-17

## 개요

이 시스템은 텔레그램 테마와 기술적 지표를 결합해 자동으로 주식 매매 신호를 생성하고 실행합니다.

## 준비 단계

1. `.env.example`을 복사해 `.env.local`을 만들고 KIS/Telegram 값을 입력합니다.
2. `requirements.txt`에 명시된 패키지를 설치합니다.
3. 환경변수와 KIS API 연결을 검증합니다.
4. 실계좌 보유 종목을 `positions.json`에 동기화합니다.
5. `main.py`를 실행합니다.

```powershell
copy .env.example .env.local
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe check_config.py    # 환경변수 검증
.\venv\Scripts\python.exe check_kis_api.py   # KIS API 실계좌 확인
.\venv\Scripts\python.exe sync_positions.py  # 실계좌 포지션 동기화
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe main.py
```

## 동작 흐름

1. `scheduler.py`가 시스템 스케줄을 관리합니다.
2. `stock_data.py`는 주식 데이터를 수집합니다.
3. `analyzer.py`는 13대 필터 기준을 평가합니다.
4. `trader.py`는 포착된 종목을 50% 시장가, 50% 지정가로 주문합니다.
5. `telegram_bot.py`는 개인별 Telegram 봇으로 매매 알림을 전송합니다.

## 알림

- 매수 신호 발생 시 개인별 텔레그램에 알림이 발송됩니다.
- 지정가 미체결 시 10분 후 자동 취소 알림이 발송됩니다.

## Flask 대시보드

`dashboard.py`를 실행하면 `http://127.0.0.1:5000`에서 웹 대시보드에 접근할 수 있습니다.

```powershell
.\venv\Scripts\python.exe dashboard.py
```

| 엔드포인트 | 설명 |
|------------|------|
| `GET /api/config` | 계좌 설정 및 매매 필터 조회 |
| `GET /api/balance` | 실계좌 잔고 및 보유 종목 조회 |
| `GET /api/positions` | `positions.json` 추적 포지션 조회 |
| `GET /api/logs` | 최근 로그 조회 |
| `GET /api/system-status` | 스케줄러 상태, 텔레그램 모니터, 서버 시간 조회 |
| `GET /api/ai-costs` | Claude Code 개발 비용 (모델별 토큰/USD 집계) |

## 개발자 참고

- KIS API 연동 코드는 `kis_api.py`에 구현되어 있습니다.
- 기본 테스트는 실제 Telegram/KIS 연결 테스트를 제외합니다.
- 실제 Telegram/KIS 통합 테스트는 필요할 때만 명시적으로 실행하세요:

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```
