# 에이전트 팀 구조

이 문서는 `Tauric_README.md`에서 참고한 멀티-에이전트 트레이딩 프레임워크 개념을 우리 프로젝트에 적용하는 방법을 정리합니다.

## 목표

우리 시스템은 텔레그램 테마 신호와 기술적 지표를 결합한 자동매매 시스템입니다. 이를 위해 역할을 분리하여 다음과 같은 에이전트 팀 모델을 적용할 수 있습니다.

## 에이전트 역할

### 1. Sentiment Analyst

- 텔레그램 메시지와 테마 데이터를 분석하여 현재 시장 심리를 파악합니다.
- `theme_db.py`와 연계하여 종목별 테마 매핑을 수행합니다.
- 결과를 매매 후보군으로 필터링하는 초기 단계에 활용합니다.

### 2. Technical Analyst

- `analyzer.py`의 13대 필터를 통해 기술적 조건을 평가합니다.
- 이동평균, RSI, 볼린저밴드, 거래량, 갭상승, 연속양봉, VI, 매물대 등 기준을 점검합니다.
- 매수 후보에 보수적인 기술 검증을 수행합니다.

### 3. Researcher Team

- Bull 관점과 Bear 관점의 연구자를 두어 후보 종목의 장단점을 토론합니다.
- 의견 충돌이 발생하면 보수적인 리스크 측면을 우선하도록 설계합니다.
- 예: 테마의 일시적 과열 여부, 시장 지수 상태, 거래대금 안정성 검토.

### 4. Trader Agent

- `trader.py`가 이 역할을 담당합니다.
- 50% 시장가 + 50% 지정가 분할 매수를 실행하고, 10분 후 미체결 주문을 자동 취소합니다.
- 주문 상태와 알림을 `telegram_bot.py`로 전송합니다.

### 5. Risk Management

- 시장 지수, VI, 거래대금, 시간대 등의 안전성을 모니터링합니다.
- `scheduler.py`와 `analyzer.py`가 이 역할의 핵심 로직을 담당합니다.
- 위험 신호가 감지되면 신규 주문을 차단하거나 알림을 전송합니다.

### 6. Portfolio Manager

- `agents/portfolio_manager.py`가 담당합니다.
- TraderAgent의 주문 체결 결과를 검증하고 최종 승인 여부를 결정합니다.
- `config.MAX_POSITIONS`(계좌당 최대 동시 보유 종목 수) 초과 여부를 경고합니다.
- `config.MIN_CASH_RATE`(최소 현금 비율) 미달 시 경고를 발생시킵니다.
- 주문 미체결(`trade_result=None`)이면 `final_approval=False`를 반환합니다.

## 파이프라인 게이트 로직

각 단계는 조기 종료 게이트를 갖습니다. 탈락 시 이후 에이전트는 **실행되지 않습니다**.

| 단계 | 탈락 조건 | 이후 건너뜀 |
|------|-----------|------------|
| Technical | `pass=False` | Researcher, Risk, Trader, Portfolio |
| Researcher | `final_decision=False` | Risk, Trader, Portfolio |
| Risk | `risk_pass=False` | Trader, Portfolio |

## 적용 방안

1. `theme_db.py`와 텔레그램 테마 분석 로직을 결합하여 초기 후보군을 선별합니다.
2. `analyzer.py`를 통해 기술적 검증을 수행합니다.
3. 연구자 역할은 Bull/Bear 복수 관점으로 평가하며, `bull_score < 0.60`이면 반려합니다.
4. 주문 단계는 `trader.py`에서 자동 실행하고, 취소 및 알림 로직을 분리합니다.
5. 리스크 관리 규칙은 `config.py`의 필터 설정과 `scheduler.py`의 자동 스케줄링으로 강화합니다.

## 문서화

- `docs/README_ARCHITECTURE.md`에서 멀티에이전트 팀 구조와 역할 매핑을 확인하세요.
- 향후 AI 에이전트를 실제 통합할 때는 `skills/`와 `docs/README_AGENT.md`를 기반으로 추가 문서를 작성합니다.
