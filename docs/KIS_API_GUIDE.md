# 한국투자증권(KIS) API 연동 가이드

## 1. 사전 준비

### 1.1 개발자 계정 등록

1. [한국투자증권 OpenAPI](https://dev.koreainvestment.com/)에 접속
2. 회원가입 후 **개발자 센터**에서 애플리케이션 등록
3. **App Key와 App Secret** 발급받기

### 1.2 모의 투자 계정 개설

- 실제 거래 계정 대신 **모의 투자 계정** 사용 권장
- 테스트 후 안정성 확보 후 실제 계정으로 전환 가능

---

## 2. 환경 설정 (보안)

### 2.1 .env 파일 생성

**절대 App Key/Secret을 코드에 하드코딩하지 마세요!**

`.env.example` 파일을 참고하여 `.env.local` 파일을 생성합니다:

```bash
# Windows
copy .env.example .env.local
```

### 2.2 .env.local 파일 설정

생성된 `.env.local` 파일에 실제 값을 입력합니다:

```bash
# KIS API 설정 (계좌 1)
KIS_APP_KEY_JY1=pk1234abcd5678efgh
KIS_APP_SECRET_JY1=ps1234abcd5678efgh
KIS_ACCOUNT_NO_JY_Investing1=your_account_no_1
BUDGET_JY1=1000000

# KIS API 설정 (계좌 2)
KIS_APP_KEY_JY2=pk9999xxxx1111yyyy
KIS_APP_SECRET_JY2=ps9999xxxx1111yyyy
KIS_ACCOUNT_NO_JY_Investing2=your_account_no_2
BUDGET_JY2=1000000

# Telegram Bot 토큰 (계좌별 개인 알림용)
TELEGRAM_BOT_TOKEN_JY_Investing1=your_bot_token_1
TELEGRAM_BOT_TOKEN_JY_Investing2=your_bot_token_2

# Telegram 관리자 설정 (긴급 알림용)
TELEGRAM_ADMIN_BOT_TOKEN=your_admin_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id

# 트레이딩 기본 설정
SLIPPAGE_RATE=0.003
STOP_LOSS_RATE=0.05
TAKE_PROFIT_RATE=0.10

# 포트폴리오 리스크 한도
MAX_POSITIONS=5       # 계좌당 최대 동시 보유 종목 수
MIN_CASH_RATE=0.20    # 예산 대비 최소 현금 비율 (20% 미만 시 경고)
```

### 2.3 .gitignore 확인

`.gitignore` 파일에 `.env`가 포함되어 있어야 합니다:

```bash
# .gitignore
.env
.env.local
.env.*.local
```

**중요**: `.env` 파일이 Git에 커밋되지 않아야 합니다!

```bash
# Git 확인
git status  # .env가 listed 아님 확인
```

---

## 3. Python 코드에서 환경 변수 사용

### 3.1 config.py 구조

```python
import os
from dotenv import load_dotenv

load_dotenv(override=False)
load_dotenv(".env.local", override=False)

# 환경 변수에서 읽기 (계좌 1 예시)
app_key = os.getenv("KIS_APP_KEY_JY1")
app_secret = os.getenv("KIS_APP_SECRET_JY1")
account_no = os.getenv("KIS_ACCOUNT_NO_JY_Investing1")
```

### 3.2 자동 검증

`config.py`는 시작 시 자동으로 환경 변수를 검증합니다:

```bash
python main.py
```

만약 `.env.local`이 없거나 값이 없으면:

```
[FAIL] KIS_APP_KEY_JY1   -> 미설정  (계좌1 API Key)
```

`check_config.py`로 전체 환경변수를 한 번에 검증할 수 있습니다:

```powershell
.\venv\Scripts\python.exe check_config.py
```

---

## 4. KIS API 함수 레퍼런스

## 구현된 KIS API 기능

### 1. 주문 (`kis_api.py` - `order_cash`)

- **시장가 주문**: 즉시 체결
- **지정가 주문**: 설정 가격에서 체결

```python
kis_client = KISAPIClient(user)
kis_client.get_access_token()  # 토큰 발급
res = kis_client.order_cash(stock_code, qty, price, order_type="01")  # 01=시장가, 00=지정가
```

### 2. 주문 취소 (`kis_api.py` - `cancel_order`)

- 미체결 주문 자동 취소
- 10분 후 미체결 시 자동 실행

```python
res = kis_client.cancel_order(order_no, qty=0)  # qty=0이면 미체결 전량 취소
```

### 3. 데이터 조회 (`stock_data.py`)

- **일봉 데이터**: `fetch_daily_prices()`, `fetch_daily_ohlcv()`
- **호가 정보**: `fetch_asking_price()`
- **잔고 조회**: `fetch_balance()`
- **전일 종가**: `fetch_previous_close()`

## 토큰 관리

- **자동 갱신**: 매일 오전 8시 50분 (시장 개장 전) 토큰 자동 갱신
- **갱신 로직**: `scheduler.py`의 `refresh_all_tokens()` 함수

## 에러 처리

모든 API 호출은 다음과 같이 오류 처리됩니다:

```python
res = kis_client.order_cash(...)
if res.get("rt_cd") == "0":  # 성공
    order_no = res["output"]["ODNO"]
else:  # 실패
    error_msg = res.get("msg_text", "알 수 없는 오류")
```

## 로깅

`logs/` 디렉터리에 날짜별 로그가 저장됩니다:

- `trading_20260509.log`: 2026년 5월 9일의 모든 거래 로그

## 주의사항

1. **API 속도 제한**: KIS API는 초당 요청 수 제한이 있습니다.
2. **테스트 모드**: 실제 거래 전에 모의 투자 계좌로 반드시 테스트하세요.
3. **보안**: App Key와 App Secret을 절대 공개하지 마세요.

## 다음 단계

- 실계좌 보유 종목은 `sync_positions.py`로 `positions.json`에 동기화
- 전체 시스템은 `main.py`로 실행, 대시보드는 `dashboard.py`로 별도 실행
- 전체 파이프라인은 `README.md` 및 `docs/README_USER.md` 참고
