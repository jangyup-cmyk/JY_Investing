# 🎯 텔레그램 폴더별 실시간 모니터링 - 구현 완료

> 문서 버전: 2026-05-12

텔레그램 대화방 폴더별로 분류된 채널들에서 **실시간으로 메시지를 자동 수집**하는 기능이 구현되었습니다.

---

## ✨ 구현 내용

### 1. **telegram_listener.py** (신규)

- **Telethon 기반** 텔레그램 메시지 실시간 수집
- 폴더별 채널 자동 감지
- 새 메시지만 선별 수집
- `etc/telegram_texts/폴더명/` 자동 저장
- `theme_extractor`와 자동 연동

### 2. **requirements.txt** (업데이트)

```diff
+ Telethon==1.34.0
+ cryptg==0.6.0
```

### 3. **config.py** (추가)

```python
# Telethon API 자격증명
TELEGRAM_API_ID = 123456
TELEGRAM_API_HASH = "abcdef..."
TELEGRAM_PHONE = "+82..."

# 모니터링 폴더 설정
TELEGRAM_MONITOR_FOLDERS = ["공시속보", "애널리스트", "경제신문", "분석가"]

# 직접 채널 그룹을 지정할 수도 있음
TELEGRAM_CHANNEL_GROUPS = {
    "투자채널": ["@channel_username", "-1001234567890"],
}

# 모니터링 옵션
TELEGRAM_MONITOR_ENABLED = false  # true로 변경하면 활성화
TELEGRAM_POLL_INTERVAL = 300      # 5분마다 폴링
```

### 4. **scheduler.py** (추가)

- `start_telegram_listener()` 함수
- 백그라운드 모니터링 작업 등록
- 시스템 시작 시 자동 활성화

### 5. **.env.example** (신규)

- 모든 환경 변수 설정 템플릿
- Telethon API 자격증명 정보 포함

### 6. **docs/TELEGRAM_MONITORING_GUIDE.md** (신규)

- 상세한 설정 및 사용 가이드
- 문제 해결 방법
- 실제 워크플로우

### 7. **test_telegram_listener.py** (신규)

- 텔레그램 연결 테스트
- 폴더/채널 목록 확인
- 메시지 수집 테스트

### 8. **README.md** (업데이트)

- telegram_listener.py 추가
- 3-1단계: 텔레그램 모니터링 가이드 추가

---

## 🚀 빠른 시작 (3단계)

### Step 1: API 자격증명 발급 (5분)

```
1. https://my.telegram.org 접속
2. Phone number 로그인
3. "API development tools" 클릭
4. 아래 정보 기록:
   - API ID: ______
   - API Hash: ______
```

### Step 2: 환경 설정 (2분)

```bash
# .env 파일 수정
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=abcdef1234567890...
TELEGRAM_PHONE=+82010XXXXXXXX
TELEGRAM_MONITOR_ENABLED=true
```

### Step 3: 폴더/채널 설정 (1분)

```bash
# .env 수정
TELEGRAM_MONITOR_FOLDERS=공시속보,애널리스트,경제신문,분석가
```

---

## 📊 실행 방법

### 방법 1: 자동 모드 (권장)

```bash
python main.py
# → 자동으로 텔레그램 모니터링 시작
```

### 방법 2: 테스트 모드

```powershell
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
# → 실제 Telegram 연결 테스트
```

---

## 📈 워크플로우

```
📱 Telegram 채널 (폴더별 분류)
    ↓ (5분마다 폴링)
🔍 telegram_listener.py (Telethon)
    - 새 메시지 감지
    - etc/telegram_texts/폴더명/에 저장
    ↓
🤖 theme_extractor.py (자동 호출)
    - 종목/테마 추출
    - 점수 기반 추천
    - Watch List 생성
    ↓
📈 scheduler.py (매매 파이프라인)
    - 09:00~10:30 매매 시그널 실행
    - 에이전트 팀 실행
    ↓
📤 telegram_bot.py
    - 개인별 알림 발송
```

---

## 🎯 핵심 기능

| 기능                | 설명                                    |
| ------------------- | --------------------------------------- |
| **폴더별 모니터링** | 대화방 폴더 단위로 채널 그룹화          |
| **실시간 수집**     | 설정된 간격(기본 5분)으로 폴링          |
| **새 메시지만**     | 중복 수집 방지, 효율적 API 사용         |
| **자동 저장**       | `etc/telegram_texts/폴더명/` 자동 저장  |
| **테마 연동**       | 수집 후 자동으로 `theme_extractor` 실행 |
| **백그라운드**      | APScheduler로 백그라운드 작업 관리      |

---

## 📋 체크리스트

- [ ] `my.telegram.org`에서 API ID/Hash 발급
- [ ] `.env` 파일에서 Telethon 설정 입력
- [ ] `.env`에서 `TELEGRAM_MONITOR_FOLDERS` 입력
- [ ] 필요 시 `config.py`에서 `TELEGRAM_CHANNEL_GROUPS` 입력
- [ ] `pip install -r requirements.txt` 실행
- [ ] `python -m pytest` 기본 테스트
- [ ] 필요 시 `RUN_INTEGRATION_TESTS=true`와 함께 `python -m pytest -m integration` 통합 테스트
- [ ] `TELEGRAM_MONITOR_ENABLED=true` 활성화
- [ ] `python main.py` 실행

---

## 🔧 주요 설정 파라미터

### 폴링 주기 (TELEGRAM_POLL_INTERVAL)

```python
60          # 1분 (개발/테스트) - API 호출 많음
300         # 5분 (권장) - 균형잡힌 설정
600         # 10분 (경량 모드) - API 호출 적음
```

### 메시지 수집 개수 (TELEGRAM_MESSAGE_FETCH_LIMIT)

```python
50          # 가볍게
100         # 기본값 (권장)
200         # 상세히
```

---

## ⚠️ 주의사항

1. **API 자격증명 보호**
   - `.env` 파일을 절대 git에 커밋하지 마세요
   - `.gitignore`에 `.env` 등록됨 (확인 필수)

2. **동시 로그인**
   - 같은 계정을 여러 기기에서 동시 로그인하면 세션 끊김
   - 기존 세션 제거: `rm .telegram_session*`

3. **API 속도 제한**
   - Telethon은 Telegram의 속도 제한 정책을 준수
   - 너무 짧은 폴링 주기(예: 10초)는 차단될 수 있음
   - 권장: 300초(5분) 이상

---

## 📚 상세 가이드

[📖 텔레그램 모니터링 가이드](docs/TELEGRAM_MONITORING_GUIDE.md)에서 다음을 확인하세요:

- API 자격증명 발급 상세 방법
- 모니터링 폴더 이름과 채널 그룹 설정
- 문제 해결
- 성능 최적화

---

## 🎓 다음 단계

1. **기본 운영**
   - 텔레그램 모니터링 활성화
   - 매매 파이프라인 테스트

2. **고급 설정**
   - 채널별 가중치 조정
   - 필터 조건 커스터마이징

3. **모니터링**
   - 로그 분석
   - 수집 메시지 품질 확인

---

## 📞 문제 발생 시

### "Telethon이 설치되지 않았습니다"

```bash
pip install -r requirements.txt
```

### "인증 코드 오류"

```bash
# 기존 세션 제거
rm .telegram_session*
# 다시 실행
$env:RUN_INTEGRATION_TESTS="true"
.\venv\Scripts\python.exe -m pytest -m integration
```

### "메시지가 수집되지 않음"

1. 폴더 이름 확인: `.env`의 `TELEGRAM_MONITOR_FOLDERS`
2. 권한 확인: 채널에 bot 추가 필요
3. 폴링 주기 확인: 너무 짧으면 API 제한

---

**✅ 모든 파일이 준비되었습니다. 위 단계를 따라 실행하세요!**
