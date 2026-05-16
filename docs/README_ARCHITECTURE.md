# JY 투자클럽 아키텍처

> 문서 버전: 2026-05-12

이 문서는 `HKUDS_README.md`의 Agent-Native Trading 플랫폼 아키텍처에서 참고한 내용을 우리 프로젝트에 맞춰 정리한 것입니다.

## 주요 설계 원칙

1. **모듈화**
   - 기능별로 명확히 분리된 모듈을 유지합니다.
   - 프로젝트는 데이터, 분석, 거래 실행, 알림, 스케줄링, 웹 UI로 구분됩니다.

2. **서비스 분리**
   - 사용자 인터페이스(대시보드)와 백그라운드 작업(매매/데이터 수집)을 분리합니다.
   - `dashboard.py`는 Flask 웹 서버로 상태 조회/수동 실행 UI를 제공하는 스켈레톤입니다.
   - `scheduler.py`는 백그라운드 스케줄러를 담당합니다.
   - `telegram_listener.py`는 Telethon 기반 Telegram 메시지 수집을 담당합니다.
   - `naver_research_scraper.py`는 네이버 리서치 원문 수집을 담당합니다.

3. **문서 중심 설계**
   - `README.md`와 `docs/`를 통해 프로젝트 구조와 사용법을 명확히 안내합니다.
   - 향후 에이전트와의 통합을 위한 별도 문서도 작성 가능합니다.

## 멀티에이전트 팀 구조

`Tauric_README.md`에서 참고한 멀티에이전트 설계는 우리 프로젝트에 다음과 같이 적용할 수 있습니다.

- **Analyst Team**: 텔레그램 테마 분석 및 13개 기술 필터를 담당.
  - Sentiment Analyst: Telegram 메시지/테마 신호 추출
  - Technical Analyst: `analyzer.py`의 지표 필터링
- **Researcher Team**: Bull/Bear 관점으로 후보 종목을 재평가하고 리스크를 검증.
- **Trader Agent**: `trader.py`에서 분할 주문을 집행하고 취소 로직을 수행.
- **Risk Management**: 시장 지수, VI, 거래대금, 시간대 등의 안전성을 지속 감시.
- **Portfolio Manager**: 최종 매수/매도 결정을 제어하는 정책 계층으로 확장 가능.

위 구조는 우리 프로젝트의 `theme_db.py`, `analyzer.py`, `trader.py`, `scheduler.py` 간 역할 분리를 더욱 명확히 합니다.

## 주요 모듈 매핑

| 우리 프로젝트     | 역할                  | AI-Trader / Tauric 참고 점 |
| ----------------- | --------------------- | -------------------------- |
| `config.py`       | 환경/계좌/필터 설정   | 중앙 설정 관리             |
| `analyzer.py`     | 13대 기술 필터        | Technical Analyst          |
| `trader.py`       | 주문 실행, 취소, 알림 | Trader Agent               |
| `telegram_bot.py` | 개인별 봇 발송        | 알림/사용자 인터페이스     |
| `telegram_listener.py` | Telegram 메시지 수집 | Sentiment Analyst 입력     |
| `naver_research_scraper.py` | 네이버 리서치 수집 | Researcher 입력            |
| `stock_data.py`   | 데이터 수집           | 데이터 레이어              |
| `scheduler.py`    | 스케줄러 관리         | 백그라운드 워커            |
| `dashboard.py`    | 웹 UI 스켈레톤        | 사용자 인터페이스 분리     |
| `theme_db.py`     | 테마 매핑 DB          | Sentiment Analyst          |
| `theme_extractor.py` | 텍스트 기반 종목/테마 추출 | Sentiment Analyst      |

## 현재 테스트 정책

- 기본 테스트: 외부 API와 실계정 세션을 사용하지 않는 테스트만 실행합니다.
- 통합 테스트: 실제 KIS/Telegram 세션을 사용하는 테스트는 `integration` 마커로 분리하며, `RUN_INTEGRATION_TESTS=true`가 없으면 skip합니다.

```powershell
.\venv\Scripts\python.exe -m pytest
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

## 확장 방향

- `service/server/`와 `service/frontend/` 구조는 추후 확장 시 참고할 수 있는 패턴입니다.
- `skills/`나 `docs/README_AGENT.md`는 AI 에이전트 통합 단계에서 추가하면 좋습니다.
