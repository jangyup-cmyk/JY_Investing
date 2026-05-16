# 사용자 가이드

> 문서 버전: 2026-05-12

## 개요

이 시스템은 텔레그램 테마와 기술적 지표를 결합해 자동으로 주식 매매 신호를 생성하고 실행합니다.

## 준비 단계

1. `.env.example`을 복사해 `.env`를 만들고 KIS/Telegram 값을 입력합니다.
2. `requirements.txt`에 명시된 패키지를 설치합니다.
3. 기본 테스트를 실행해 로컬 환경을 확인합니다.
4. `main.py`를 실행합니다.

```powershell
copy .env.example .env
.\venv\Scripts\python.exe -m pip install -r requirements.txt
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

## 개발자 참고

- 추가 UI가 필요하면 `dashboard.py`를 확장하세요.
- KIS API 연동 코드는 `trader.py`와 `stock_data.py`에 구현합니다.
- 기본 테스트는 실제 Telegram 연결 테스트를 제외합니다.
- 실제 Telegram/KIS 통합 테스트는 필요할 때만 명시적으로 실행하세요:

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```
