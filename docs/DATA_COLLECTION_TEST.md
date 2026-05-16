# 데이터 수집 테스트 가이드

> 문서 버전: 2026-05-12

## 개요

이 문서는 실제 KIS API로 주식 데이터를 수집하고 테스트하는 방법을 설명합니다.

## 테스트 실행 전 준비

### 1. KIS API 키 설정

`.env.example`을 복사해 `.env`를 만들고 실제 API 키를 입력하세요. API 키를 `config.py`에 직접 하드코딩하지 않습니다.

```powershell
copy .env.example .env
```

`.env`에서 최소한 아래 값을 설정합니다:

```bash
KIS_APP_KEY_JY=your_app_key
KIS_APP_SECRET_JY=your_app_secret
KIS_ACCOUNT_NO_JY=your_account_no
TELEGRAM_BOT_TOKEN_JY=your_bot_token
TELEGRAM_CHANNEL_ID_JY=@your_channel
```

### 2. Python 환경 확인

```bash
python --version  # Python 3.11 이상 필요
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 테스트 실행

### 방법 1: 전체 테스트 스크립트 실행

```bash
.\venv\Scripts\python.exe test_stock_data.py
```

이 스크립트는 다음 7가지를 테스트합니다:

1. **토큰 발급 테스트**: KIS API 토큰이 정상 발급되는지 확인
2. **잔고 조회 테스트**: 계좌 정보 조회
3. **일봉 가격 조회**: 최근 5일 종가 데이터
4. **OHLCV 데이터 조회**: Open, High, Low, Close, Volume
5. **호가 조회**: 현재 매도/매수 호가
6. **전일 종가 조회**: 전일 종가 확인
7. **13대 필터 검증**: 수집된 데이터로 매매 신호 확인

### 방법 2: 개별 함수 테스트

Python 대화형 모드에서:

```python
from config import USERS
from stock_data import fetch_balance, fetch_asking_price

user = USERS[0]

# 잔고 조회
balance = fetch_balance(user)
print(balance)

# 호가 조회
asking = fetch_asking_price("005930", user)  # 삼성전자
print(asking)
```

## 테스트 결과 해석

### 성공 사례

```
2026-05-09 14:30:00 - INFO - ✅ 테스트계좌 토큰 발급 성공
2026-05-09 14:30:01 - INFO - 총 평가액: 5,000,000원
2026-05-09 14:30:02 - INFO - 종목: 005930
2026-05-09 14:30:02 - INFO -   현재가: 70,500원
```

### 오류 사례

| 오류             | 원인        | 해결 방법                     |
| ---------------- | ----------- | ----------------------------- |
| `토큰 발급 실패` | API 키 오류 | `config.py`에서 API 키 확인   |
| `데이터 없음`    | 장 시간 외  | 장 시간(9:00~15:30) 중에 실행 |
| `403 Forbidden`  | 권한 없음   | 모의 투자 계좌 확인           |

## 로그 파일

테스트 실행 결과는 다음에 저장됩니다:

```
logs/trading_20260509.log
```

## 문제 해결

### 1. "토큰 발급 실패"

**원인**: API 키/시크릿이 잘못됨

```bash
# config.py 확인
grep -n "app_key\|app_secret" config.py
```

### 2. "데이터 없음"

**원인**:

- 장 시간이 아님 (09:00 ~ 15:30)
- 종목이 존재하지 않음

**해결**:

```python
# 다른 종목으로 테스트
test_stock_code = "000660"  # SK하이닉스
```

### 3. "API 요청 제한"

**원인**: 너무 자주 요청함

**해결**: 요청 간격 확보

```python
import time
time.sleep(1)  # 1초 대기
```

## 다음 단계

테스트가 성공하면:

1. **테마 분석 엔진 통합**: 텔레그램 메시지 수집과 연결
2. **자동 매매 시뮬레이션**: 실제 주문 없이 신호 생성 테스트
3. **모의 투자 계좌로 실제 테스트**: 실제 주문 시뮬레이션

## 기본 테스트와 통합 테스트

프로젝트 기본 테스트는 외부 API 접속 없이 실행되도록 구성되어 있습니다.

```powershell
.\venv\Scripts\python.exe -m pytest
```

실제 KIS/Telegram 세션을 사용하는 테스트는 명시적 플래그와 함께 별도로 실행합니다.

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

## 참고

- [KIS API 가이드](KIS_API_GUIDE.md)
- [시스템 아키텍처](README_ARCHITECTURE.md)
