# CLAUDE.md — JY 투자클럽 자동매매 시스템

Claude Code가 이 프로젝트에서 작업할 때 따라야 할 워크플로우와 규칙입니다.
superpowers (https://github.com/obra/superpowers) 방법론을 이 프로젝트에 맞게 적용했습니다.

---

## 1. 프로젝트 핵심 맥락

- **실거래 시스템** — 실제 계좌(계좌1: 73918950, 계좌2: 73312646)에 영향을 미치는 코드를 다룹니다.
- **매매 시간**: 09:00~10:30 KST. 이 시간대 코드 수정은 실행 중인 스케줄러에 영향을 줄 수 있습니다.
- **positions.json**: 손절/익절 모니터링의 근거 파일. 손상되면 실계좌 포지션 보호가 중단됩니다.
- **API 비용**: KIS API 과호출 시 속도 제한이 걸립니다. 불필요한 실계좌 호출을 삼가세요.
- **테스트 기준**: `pytest`에서 `37 passed, 9 deselected` 유지가 기본입니다.

---

## 2. 설계 우선 원칙 (brainstorming)

**구현 전 반드시 설계를 제시하고 사용자 승인을 받습니다.**

- 새 기능 또는 아키텍처 변경 요청 시: 코드를 바로 작성하지 않고 2~3가지 접근 방식과 트레이드오프를 먼저 제시합니다.
- 설계 문서는 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`에 저장합니다.
- 설계 승인 전에는 파일을 생성하거나 편집하지 않습니다.

**적용 기준:**
- 에이전트 파이프라인 구조 변경 → 설계 필수
- 단순 버그 수정 (1~2파일) → 설계 생략 가능
- KIS API 호출 방식 변경 → 설계 필수 (실계좌 영향)

---

## 3. 구현 계획 작성 (writing-plans)

설계 승인 후 구현을 시작하기 전, 각 작업을 2~5분 단위의 원자적 단계로 분해합니다.

**계획 품질 기준:**
- 각 단계에 정확한 파일 경로와 함수명 포함
- 코드가 필요한 단계에는 완전한 코드 블록 포함 ("나중에 추가" 금지)
- 각 단계 끝에 검증 명령 포함 (`pytest`, `python check_config.py` 등)
- 타입/함수 참조는 실제 존재하는 것만 사용

---

## 4. 테스트 주도 개발 (test-driven-development)

**새 로직을 추가할 때 테스트를 먼저 작성합니다.**

```
RED → GREEN → REFACTOR
```

1. **RED**: 실패하는 테스트 작성 → `pytest` 실행으로 실패 확인
2. **GREEN**: 테스트를 통과시키는 최소한의 코드 작성
3. **REFACTOR**: 기능 유지하며 코드 정리

**이 프로젝트 테스트 규칙:**
- 외부 API(KIS, Telegram)를 호출하는 테스트는 `@pytest.mark.integration` 마킹
- `positions.json`을 수정하는 테스트는 `tmp_path`와 `monkeypatch` 사용
- `config.USERS`에 접근하는 테스트는 환경변수 모킹 필수

---

## 5. 체계적 디버깅 (systematic-debugging)

**수정 전 반드시 근본 원인을 파악합니다.**

```
원인 파악 → 패턴 분석 → 가설 → 검증 → 수정
```

- 오류 메시지를 끝까지 읽습니다 (마지막 줄이 핵심인 경우가 많음).
- 같은 수정을 3번 이상 시도했다면 아키텍처 문제를 의심합니다.
- KIS API 오류 코드는 `rt_cd` 필드를 확인합니다 ("0" = 성공).

**이 프로젝트 주요 경계점:**
- Telegram → `telegram_listener.py` → `theme_extractor.py`
- `scheduler.py` → `agents/agent_orchestrator.py` → `trader.py`
- `trader.py` → `kis_api.py` → KIS REST API
- `monitor_positions()` → `kis_api.py` → 손절/익절 주문

---

## 6. 완료 전 검증 (verification-before-completion)

**"작동할 것 같다"는 주장은 금지. 반드시 실행 결과를 첨부합니다.**

작업 완료를 선언하기 전 필수 실행:
```powershell
python -m pytest --tb=short -q   # 37 passed 확인
python check_config.py            # 환경변수 이상 없음 확인
```

파일 수정 후:
- `positions.json` 수정 → JSON 유효성 확인 (`python -c "import json; json.load(open('positions.json'))"`)
- `kis_api.py` 수정 → `check_kis_api.py` 실행
- 에이전트 로직 수정 → `test_agent_orchestrator.py` 명시적 실행

---

## 7. 서브에이전트 활용 (subagent-driven-development)

독립적으로 병렬 처리 가능한 작업은 서브에이전트로 분산합니다.

**병렬 적합 작업:**
- 여러 파일의 동시 탐색/읽기
- 독립적인 버그 수정 (파일 간 의존성 없음)
- 문서 여러 개 동시 업데이트

**순차 필요 작업:**
- `positions.json` 읽기 → 수정 → 저장
- KIS API 토큰 발급 → API 호출
- 테스트 실행 → 결과 확인 → 수정

---

## 8. 실계좌 보호 규칙

Claude Code가 반드시 지켜야 할 안전 규칙입니다.

| 행동 | 규칙 |
|------|------|
| `positions.json` 수정 | 사용자 확인 후 진행 |
| KIS 주문 관련 코드 수정 | 설계 승인 필수 |
| `monitor_positions()` 수정 | 테스트 통과 필수 |
| 환경변수 파일(`.env.local`) 수정 | 금지 (사용자 직접 관리) |
| 실계좌 API 직접 호출 | 읽기 전용만 허용 (주문 API 호출 금지) |

---

## 9. 주요 파일 참조

```
main.py                    # 진입점
config.py                  # 환경변수 로드 (USERS, FILTER, MAX_POSITIONS)
scheduler.py               # APScheduler 잡 관리
kis_api.py                 # KIS REST API 클라이언트
trader.py                  # 분할 매수 주문 실행
analyzer.py                # 13대 기술적 필터
agents/
  agent_orchestrator.py    # 파이프라인 게이트 로직
  trader_agent.py          # 중복 매수 방지
  portfolio_manager.py     # MAX_POSITIONS/MIN_CASH_RATE 검증
position_tracker.py        # positions.json 스레드 안전 관리
dashboard.py               # Flask 대시보드
sync_positions.py          # 실계좌 → positions.json 동기화
```

---

## 10. 테스트 실행 참조

```powershell
# 전체 (외부 API 제외)
python -m pytest --tb=short -q

# 에이전트 게이트 로직만
python -m pytest test_agent_orchestrator.py -v

# 통합 테스트 (KIS/Telegram 실연결)
$env:RUN_INTEGRATION_TESTS="true"; python -m pytest -m integration
```
