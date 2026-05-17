import logging
import json
import threading
import time
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ModuleNotFoundError:  # 테스트/시뮬레이션 환경에서 선택 의존성 미설치 대비
    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self, timezone=None):
            self.timezone = timezone
            self.running = False

        def start(self):
            self.running = True

        def add_job(self, *args, **kwargs):
            return None

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Seoul")
telegram_listener_thread = None
naver_research_thread = None


def _resolve_weighted_codes_from_channel_report() -> list[str]:
    """
    채널 비교 리포트 + 채널 가중치 파일 기반으로 통합 추천 종목 생성.
    """
    import config

    report_path = Path(config.CHANNEL_COMPARISON_REPORT_PATH)
    if not report_path.exists():
        return []

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"[채널 가중치] 리포트 로드 실패: {exc}")
        return []

    channels = payload.get("channels", {})
    if not isinstance(channels, dict) or not channels:
        return []

    weights = {}
    weights_path = Path(config.CHANNEL_WEIGHTS_FILE)
    if weights_path.exists():
        try:
            raw = json.loads(weights_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                weights = {str(k): float(v) for k, v in raw.items()}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error(f"[채널 가중치] 가중치 파일 로드 실패: {exc}")

    weighted_scores: dict[str, float] = {}
    for channel_name, info in channels.items():
        if not isinstance(info, dict):
            continue
        channel_weight = weights.get(channel_name, 1.0)
        top_code_scores = info.get("top_code_scores", {})
        if not isinstance(top_code_scores, dict):
            continue
        for code, score in top_code_scores.items():
            try:
                weighted_scores[code] = weighted_scores.get(code, 0.0) + float(score) * channel_weight
            except (TypeError, ValueError):
                continue

    top_n = max(config.CHANNEL_WEIGHTED_TOP_N, 1)
    ranked = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    resolved = [code for code, _ in ranked]
    if resolved:
        logger.info(f"[채널 가중치] 통합 추천 종목 {len(resolved)}개 생성")
    return resolved


def resolve_stock_codes(initial_codes: list | None = None) -> list:
    """WATCH_LIST 또는 자연어 추출 기반 추천 종목 코드 결정."""
    import config

    resolved = list(initial_codes or [])
    if resolved:
        return resolved

    if not config.AUTO_BUILD_WATCH_LIST:
        return resolved

    try:
        if config.USE_CHANNEL_WEIGHTED_WATCHLIST:
            weighted = _resolve_weighted_codes_from_channel_report()
            if weighted:
                return weighted

        import theme_extractor

        # 텔레그램 텍스트를 채널 폴더 단위로 그룹 로드 (C: 채널 정규화용)
        text_groups = theme_extractor.load_texts_grouped_by_subdir(config.TEXT_SIGNAL_SOURCE_DIR)

        # 네이버 리서치 텍스트를 카테고리 그룹으로 로드 후 합산
        if config.NAVER_RESEARCH_ENABLED:
            research_groups = theme_extractor.load_texts_grouped_by_subdir(config.NAVER_RESEARCH_SOURCE_DIR)
            text_groups.update({f"naver_{k}": v for k, v in research_groups.items()})

        if not text_groups:
            return []

        # update_theme_mapping_from_texts 는 flat list 필요
        all_texts = [t for grp in text_groups.values() for t in grp]
        updated = theme_extractor.update_theme_mapping_from_texts(all_texts)

        # A+C 통합 추출 (SHA256 중복 제거 + sqrt 채널 정규화)
        aggregated = theme_extractor.extract_from_grouped_texts(
            text_groups, min_score=config.THEME_EXTRACTION_MIN_SCORE
        )
        resolved = aggregated.get("recommended_codes", [])

        # auto_watchlist_report.json 저장 (대시보드 /api/watchlist-report 에서 읽음)
        try:
            from datetime import datetime as _dt
            aggregated["generated_at"] = _dt.now().isoformat()
            report_path = Path(config.AUTO_WATCHLIST_REPORT_PATH)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(aggregated, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning(f"[테마 추출] watchlist 리포트 저장 실패: {exc}")

        dedup = aggregated.get("dedup_stats", {})
        logger.info(
            f"[테마 추출] 입력 {dedup.get('total_before', 0)}건 → "
            f"중복제거 후 {dedup.get('unique_after', 0)}건 ({dedup.get('removed', 0)}건 제거), "
            f"themes.json 갱신 {updated}종목, 추천 종목 {len(resolved)}개"
        )
    except Exception as exc:
        logger.error(f"[테마 추출] 자동 watch list 생성 실패: {exc}")
        return []

    return resolved


def refresh_all_tokens():
    """모든 사용자의 토큰 갱신"""
    import config
    from kis_api import KISAPIClient

    for user in config.USERS:
        kis_client = KISAPIClient(user)
        if kis_client.get_access_token():
            logger.info(f"토큰 갱신 성공: {user['name']}")
        else:
            logger.error(f"토큰 갱신 실패: {user['name']}")


def run_signal_pipeline(stock_codes: list = None, simulate_only: bool = False):
    # 새 사이클마다 텔레그램 텍스트 캐시 초기화 (최신 수집 데이터 반영)
    try:
        from agents.sentiment_analyst import clear_telegram_cache
        clear_telegram_cache()
    except Exception:
        pass
    """
    매매 시그널 파이프라인 실행 (AgentOrchestrator 사용)

    - 감정/기술/리서치/리스크/매매/포트폴리오 에이전트 순서로 실행
    - 각 사용자(계좌)별로 독립 실행
    - 거래 시간(09:00~10:30) 내에서만 실제 주문 발생
    - simulate_only=True면 API 호출 없이 대상 종목만 검증
    """
    import config

    stock_codes = resolve_stock_codes(stock_codes)

    if not stock_codes:
        logger.debug("모니터링 종목 없음 — 파이프라인 스킵")
        return {"stock_codes": [], "simulated": simulate_only, "processed": 0}

    if simulate_only:
        logger.info(f"[시뮬레이션] 파이프라인 대상 종목: {stock_codes}")
        return {
            "stock_codes": stock_codes,
            "simulated": True,
            "processed": len(stock_codes),
        }

    import stock_data
    from agents.agent_orchestrator import AgentOrchestrator
    from kis_api import KISAPIClient

    orchestrator = AgentOrchestrator()

    processed = 0
    for user in config.USERS:
        # 토큰 확보
        kis_client = KISAPIClient(user)
        if not kis_client.get_access_token():
            logger.error(f"[파이프라인] 토큰 발급 실패: {user['name']}")
            continue

        token = kis_client.access_token

        for i, code in enumerate(stock_codes):
            if i > 0:
                time.sleep(0.3)  # 종목당 KIS API 3회 호출 → 0.3s 간격으로 ~10 req/sec 유지
            try:
                # 필요 데이터 수집
                ohlcv = stock_data.fetch_daily_ohlcv(code, user, count=100)
                prices = ohlcv.get("closes", [])
                opens = ohlcv.get("opens", [])
                closes = ohlcv.get("closes", [])
                volumes = ohlcv.get("volumes", [])

                asking = stock_data.fetch_asking_price(code, user)
                current_price = asking.get("current_price", 0)
                if current_price <= 0:
                    logger.warning(f"[{code}] 현재가 조회 실패")
                    continue

                prev_close = stock_data.fetch_previous_close(code, user)
                open_price = opens[-1] if opens else current_price
                high_price = max(closes[-1], current_price) if closes else current_price

                # 전달 데이터 구성
                input_data = {
                    "stock_code": code,
                    "stock": {
                        "code": code,
                        "price": current_price,
                        "change_rate": (
                            (current_price - prev_close) / prev_close * 100
                            if prev_close > 0 else 0.0
                        ),
                    },
                    "open_price": open_price,
                    "high_price": high_price,
                    "prev_close": prev_close,
                    "daily_prices": prices,
                    "daily_opens": opens,
                    "daily_closes": closes,
                    "daily_volumes": volumes,
                    "minute_vols": volumes[-11:] if len(volumes) >= 11 else volumes,
                    "user": user,
                    "token": token,
                    "current_price": current_price,
                    "portfolio_value": user.get("budget", 1_000_000),
                }

                result = orchestrator.run_flow(input_data)
                processed += 1
                # 민감 정보(자격증명, 토큰)를 제외한 요약만 로깅
                safe_summary = {
                    k: v for k, v in result.items()
                    if k not in ("user", "token", "app_key", "app_secret", "bot_token")
                    and not isinstance(v, dict)  # user 딕셔너리 내 중첩 노출 방지
                }
                logger.info(
                    f"[파이프라인] {user['name']} | {code} → "
                    f"승인={result.get('final_approval')} | {safe_summary}"
                )

            except Exception as e:
                logger.error(f"[파이프라인] {user['name']} | {code} 처리 오류: {e}")

    return {"stock_codes": stock_codes, "simulated": False, "processed": processed}


def monitor_positions():
    """보유 종목의 수익률을 확인하여 손절/익절 조건 도달 시 자동 매도 실행"""
    import config
    import stock_data
    import position_tracker
    import telegram_bot as bot
    from kis_api import KISAPIClient

    open_positions = position_tracker.get_open_positions()
    if not open_positions:
        return

    for pos in open_positions:
        account_no = pos["account_no"]
        stock_code = pos["stock_code"]
        buy_price = pos["buy_price"]
        qty = pos["qty"]
        stop_loss = pos["stop_loss"]
        take_profit = pos["take_profit"]

        # 계좌 정보 찾기
        user = next((u for u in config.USERS if u["account_no"] == account_no), None)
        if not user:
            logger.error(f"[모니터링] 계좌 정보를 찾을 수 없음: {account_no}")
            continue

        kis_client = KISAPIClient(user)
        if not kis_client.get_access_token():
            logger.error(f"[모니터링] 토큰 발급 실패: {user['name']}")
            continue

        # 현재가 조회
        asking = stock_data.fetch_asking_price(stock_code, user)
        current_price = asking.get("current_price", 0)
        
        if current_price <= 0:
            logger.warning(f"[모니터링] {stock_code} 현재가 조회 실패")
            continue

        pnl_rate = (current_price - buy_price) / buy_price * 100
        
        reason = ""
        if current_price <= stop_loss:
            reason = "손절 조건 도달"
        elif current_price >= take_profit:
            reason = "익절 조건 도달"

        if reason:
            logger.info(f"[{reason}] {user['name']} | {stock_code} | 매수가:{buy_price:,.0f} 현재가:{current_price:,.0f} ({pnl_rate:+.2f}%)")
            
            # 매도 주문 실행 (시장가)
            res = kis_client.order_sell(stock_code, qty, price=0, order_type="01")
            
            if res.get("rt_cd") == "0":
                logger.info(f"[매도 성공] {user['name']} | {stock_code}")
                # 포지션 제거
                position_tracker.remove_position(account_no, stock_code)
                # 알림 전송
                bot.send_personal_sell_signal(
                    user=user,
                    stock_name=pos.get("stock_name", stock_code),
                    stock_code=stock_code,
                    sell_price=current_price,
                    reason=reason,
                    pnl_rate=pnl_rate
                )
            else:
                logger.error(f"[매도 실패] {user['name']} | {stock_code} - {res.get('msg_text', '')}")


def start_telegram_listener():
    """텔레그램 폴더별 채널 모니터링 시작 (별도 스레드)"""
    global telegram_listener_thread
    import config
    
    if not config.TELEGRAM_MONITOR_ENABLED:
        logger.debug("텔레그램 모니터링 비활성화됨 (TELEGRAM_MONITOR_ENABLED=false)")
        return
    
    # API ID는 0이 아니어야 함
    if not (config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH and config.TELEGRAM_PHONE):
        logger.warning("❌ 텔레그램 모니터링을 위해 .env에서 다음을 설정하세요:")
        logger.warning("   - TELEGRAM_API_ID: my.telegram.org에서 발급 (0이 아닌 값)")
        logger.warning("   - TELEGRAM_API_HASH: my.telegram.org에서 발급")
        logger.warning("   - TELEGRAM_PHONE: 로그인할 전화번호 (예: +82...)")
        return
    
    if telegram_listener_thread is not None and telegram_listener_thread.is_alive():
        logger.debug("텔레그램 리스너가 이미 실행 중입니다.")
        return
    
    try:
        from telegram_listener import TelegramListener, run_telegram_listener_async
        
        def run_listener():
            """스레드에서 실행할 함수"""
            try:
                listener = TelegramListener(
                    api_id=config.TELEGRAM_API_ID,
                    api_hash=config.TELEGRAM_API_HASH,
                    phone_number=config.TELEGRAM_PHONE,
                    channel_groups=config.TELEGRAM_CHANNEL_GROUPS,
                    folder_names=config.TELEGRAM_MONITOR_FOLDERS,
                    session_file=config.TELEGRAM_SESSION_FILE,
                    state_file=config.TELEGRAM_LISTENER_STATE_FILE,
                )
                
                # 비동기 리스너 실행 (무한 루프)
                run_telegram_listener_async(
                    listener, 
                    config.TELEGRAM_POLL_INTERVAL
                )
            except Exception as e:
                logger.error(f"❌ 텔레그램 리스너 실행 중 오류: {e}")
                import traceback
                traceback.print_exc()
        
        # 스레드 시작 (데몬 스레드로 설정해서 메인 프로세스 종료 시 자동 종료)
        telegram_listener_thread = threading.Thread(
            target=run_listener,
            name="TelegramListener",
            daemon=True,
        )
        telegram_listener_thread.start()
        logger.info("✅ 텔레그램 폴더별 모니터링 스레드 시작됨")
        
    except ImportError:
        logger.error("❌ Telethon 라이브러리가 설치되지 않았습니다. pip install -r requirements.txt 실행하세요.")
    except Exception as e:
        logger.error(f"❌ 텔레그램 리스너 초기화 실패: {e}")


def start_naver_research_collector():
    """네이버 리서치 수집 시작 (별도 스레드)"""
    global naver_research_thread
    import config
    
    if not config.NAVER_RESEARCH_ENABLED:
        logger.debug("네이버 리서치 수집 비활성화됨")
        return
        
    if naver_research_thread is not None and naver_research_thread.is_alive():
        return
        
    def run_collector():
        from naver_research_scraper import NaverResearchScraper
        scraper = NaverResearchScraper()
        
        while True:
            try:
                scraper.scrape_all()
            except Exception as e:
                logger.error(f"❌ 네이버 리서치 수집 중 오류: {e}")
            
            time_to_wait = config.NAVER_RESEARCH_POLL_INTERVAL
            logger.info(f"⏳ 다음 네이버 리서치 수집까지 {time_to_wait}초 대기...")
            time.sleep(time_to_wait)
            
    naver_research_thread = threading.Thread(
        target=run_collector,
        name="NaverResearchCollector",
        daemon=True
    )
    naver_research_thread.start()
    logger.info("✅ 네이버 리서치 수집 스레드 시작됨")


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()

        # ── Job 1: 매일 08:50 토큰 갱신 (시장 개장 전) ──────────────────
        scheduler.add_job(
            refresh_all_tokens,
            trigger="cron",
            hour=8,
            minute=50,
            id="token_refresh",
            replace_existing=True,
        )

        # ── Job 2: 09:00~10:30 동안 1분 주기로 매매 시그널 파이프라인 실행 ──
        # 모니터링 종목은 run_signal_pipeline(stock_codes=[...]) 호출 시 직접 전달하거나
        # theme_db / 외부 설정으로 관리
        import config
        scheduler.add_job(
            run_signal_pipeline,
            trigger="cron",
            hour="9-10",          # 09:xx ~ 10:xx
            minute="0-30",        # :00 ~ :30 → 09:00~10:30 커버
            id="signal_pipeline",
            args=[config.WATCH_LIST],
            replace_existing=True,
        )

        # ── Job 3: 09:00~15:30 동안 1분 주기로 보유 종목 손절/익절 모니터링 ──
        scheduler.add_job(
            monitor_positions,
            trigger="cron",
            hour="9-15",          # 09:xx ~ 15:xx
            minute="*",           # 매분
            id="monitor_positions",
            replace_existing=True,
        )

        # ── Job 4: 텔레그램 채널 그룹 자동 동기화 ───────────────────────
        # 시작 시 1회 즉시 실행 후, 1시간마다 반복 (앱에서 폴더 변경 자동 반영)
        if config.TELEGRAM_MONITOR_ENABLED:
            from sync_channel_groups import sync_channel_groups
            sync_channel_groups()
            scheduler.add_job(
                sync_channel_groups,
                trigger="interval",
                hours=1,
                id="sync_channel_groups",
                replace_existing=True,
            )

        # ── Job 5: AI 종목 추출 리포트 주기 갱신 (1시간 간격, 24시간 운영) ──
        # run_signal_pipeline 과 별도로 watchlist 리포트만 갱신
        # 시작 시 1회 즉시 실행하여 최신 리포트 생성
        if config.AUTO_BUILD_WATCH_LIST:
            resolve_stock_codes()  # 시작 시 즉시 1회
            scheduler.add_job(
                resolve_stock_codes,
                trigger="interval",
                hours=1,
                id="watchlist_refresh",
                replace_existing=True,
            )

        # ── Job 6: 텔레그램 폴더별 채널 모니터링 (선택 사항) ────────────
        start_telegram_listener()

        # ── Job 7: 네이버 리서치 자동 수집 ───────────────────────────
        start_naver_research_collector()

        logger.info("✅ 스케줄러 시작됨")
        logger.info("   └─ 토큰 갱신: 매일 08:50")
        logger.info("   └─ 매매 파이프라인: 09:00~10:30 (1분 주기)")
        logger.info("   └─ 손절/익절 모니터링: 09:00~15:30 (1분 주기)")
        if config.TELEGRAM_MONITOR_ENABLED:
            logger.info("   └─ 채널 그룹 동기화: 시작 시 + 1시간 주기")
            logger.info(f"   └─ 텔레그램 모니터링: {config.TELEGRAM_POLL_INTERVAL}초 주기")
