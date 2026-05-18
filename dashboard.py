import glob
import logging
import os
import pathlib
import subprocess
import sys
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config
import position_tracker
from kis_api import KISAPIClient

_BASE_DIR = pathlib.Path(__file__).resolve().parent
app = Flask(__name__,
            template_folder=str(_BASE_DIR / "templates"),
            static_folder=str(_BASE_DIR / "static"))
logger = logging.getLogger(__name__)

_FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
_FLASK_HOST  = os.getenv("FLASK_HOST", "127.0.0.1")
_FLASK_PORT  = int(os.getenv("FLASK_PORT", "5000"))

# ── main.py 프로세스 관리 ──────────────────────────────────────
_main_proc: "subprocess.Popen | None" = None
_MAIN_PID_FILE = _BASE_DIR / "main.pid"


def _pid_alive(pid: int) -> bool:
    """PID 가 살아있는지 확인 (Windows 호환)"""
    try:
        if os.name == "nt":
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle == 0:
                return False
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
            return result != 0   # 0 = WAIT_OBJECT_0 (종료됨)
        else:
            os.kill(pid, 0)
            return True
    except (OSError, PermissionError):
        return False


def _main_is_running() -> bool:
    """main.py 프로세스 실행 여부 확인"""
    global _main_proc
    if _main_proc is not None and _main_proc.poll() is None:
        return True
    if _MAIN_PID_FILE.exists():
        try:
            pid = int(_MAIN_PID_FILE.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                return True
        except (ValueError, OSError):
            pass
        try:
            _MAIN_PID_FILE.unlink()
        except OSError:
            pass
    return False


def _kill_pid(pid: int) -> None:
    """PID 강제 종료 (Windows/Unix 공통)"""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                       capture_output=True)
    else:
        os.kill(pid, 15)  # SIGTERM

@app.route("/")
def index():
    """메인 대시보드 화면"""
    return render_template("index.html")

@app.route("/api/config")
def get_config():
    """시스템 설정 정보 반환"""
    return jsonify({
        "channel_name": config.CHANNEL_NAME,
        "watch_list": config.WATCH_LIST,
        "stop_loss_rate": config.STOP_LOSS_RATE,
        "take_profit_rate": config.TAKE_PROFIT_RATE,
        "users": [{"name": u["name"], "account": u["account_no"]} for u in config.USERS]
    })

_STOCK_NAMES_CACHE = _BASE_DIR / "etc" / "stock_names.json"


def _load_stock_names_cache() -> dict:
    """etc/stock_names.json 로드 (없으면 빈 dict)"""
    try:
        if _STOCK_NAMES_CACHE.exists():
            import json as _j
            return _j.loads(_STOCK_NAMES_CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _update_stock_names_cache(new_entries: dict) -> None:
    """새 종목명을 기존 캐시에 병합 저장 (빈 값·기존 항목 덮어쓰지 않음)"""
    if not new_entries:
        return
    try:
        import json as _j
        cache = _load_stock_names_cache()
        changed = False
        for code, name in new_entries.items():
            if name and code not in cache:
                cache[code] = name
                changed = True
        if changed:
            _STOCK_NAMES_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _STOCK_NAMES_CACHE.write_text(
                _j.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception as exc:
        logger.debug(f"stock_names 캐시 저장 실패: {exc}")


@app.route("/api/balance")
def get_balance():
    """모든 사용자의 계좌 잔고 및 평가 수익 반환"""
    balances = []
    for user in config.USERS:
        client = KISAPIClient(user)
        # 토큰 확인 (비동기 환경을 고려해 너무 빈번한 토큰 갱신은 캐시에서 처리됨)
        if not client.get_access_token():
            balances.append({
                "name": user["name"],
                "account": user["account_no"],
                "error": "토큰 발급 실패"
            })
            continue
            
        data = client.get_balance()
        if data and "output2" in data:
            summary = data["output2"][0] if data["output2"] else {}
            holdings = data.get("output1", [])

            # 잔고 종목명을 stock_names.json 캐시에 누적 저장
            _update_stock_names_cache(
                {h.get("pdno", ""): h.get("prdt_name", "")
                 for h in holdings if h.get("pdno") and h.get("prdt_name")}
            )

            balances.append({
                "name": user["name"],
                "account": user["account_no"],
                "total_eval_amount": int(summary.get("tot_evlu_amt", 0)),
                "total_buy_amount": int(summary.get("pchs_amt_smtl_amt", 0)),
                "eval_profit_loss": int(summary.get("evlu_pfls_smtl_amt", 0)),
                "available_balance": int(summary.get("prvs_rcdl_excc_amt", 0)),
                "holdings_count": len(holdings),
                "holdings": [
                    {
                        "code": h.get("pdno", ""),
                        "current_price": int(h.get("prpr", 0)),
                        "pnl_rate": float(h.get("evlu_pfls_rt", 0)),
                        "pnl_amt": int(h.get("evlu_pfls_amt", 0)),
                    }
                    for h in holdings
                ],
            })
        else:
            balances.append({
                "name": user["name"],
                "account": user["account_no"],
                "error": "잔고 조회 실패"
            })
            
    return jsonify({"success": True, "data": balances})

@app.route("/api/positions")
def get_positions():
    """현재 보유 중인 포지션 목록 반환"""
    try:
        positions = position_tracker.get_open_positions()
        return jsonify({"success": True, "data": positions})
    except Exception as e:
        logger.error(f"포지션 조회 오류: {e}", exc_info=True)
        detail = str(e) if _FLASK_DEBUG else "서버 내부 오류"
        return jsonify({"success": False, "error": detail})


@app.route("/api/positions/<path:key>", methods=["PATCH"])
def update_position(key: str):
    """손절/익절가 수동 수정 (대시보드 편집 UI)"""
    try:
        body = request.get_json(force=True) or {}
        stop_loss   = float(body.get("stop_loss", 0))
        take_profit = float(body.get("take_profit", 0))
        buy_date   = str(body.get("buy_date", "")).strip()
        if stop_loss <= 0 or take_profit <= 0:
            return jsonify({"success": False, "error": "유효하지 않은 값 (0 이하)"})
        if stop_loss >= take_profit:
            return jsonify({"success": False, "error": "손절가는 익절가보다 작아야 합니다"})
        # key 형식: "계좌번호_종목코드"
        parts = key.split("_", 1)
        if len(parts) != 2:
            return jsonify({"success": False, "error": "잘못된 키 형식"})
        ok = position_tracker.update_position_levels(parts[0], parts[1], stop_loss, take_profit, buy_date)
        return jsonify({"success": ok, "error": None if ok else "저장 실패"})
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"입력 오류: {e}"})
    except Exception as e:
        logger.error(f"포지션 수정 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})

@app.route("/api/watchlist-report")
def get_watchlist_report():
    """AI 자동 추출 현황 반환 (추천 종목·테마·채널 가중치)"""
    import json as _json
    import pathlib as _pl

    base = _pl.Path("etc")

    # 1. auto_watchlist_report.json (config 경로 기준)
    report_path = _pl.Path(config.AUTO_WATCHLIST_REPORT_PATH)
    report: dict = {}
    if report_path.exists():
        try:
            report = _json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 2. themes.json (종목 → 테마 매핑)
    themes_path = _pl.Path("themes.json")
    themes: dict = {}
    if themes_path.exists():
        try:
            themes = _json.loads(themes_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 3. channel_weights.json
    weights_path = base / "channel_weights.json"
    weights: dict = {}
    if weights_path.exists():
        try:
            weights = _json.loads(weights_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 종목명 조회: stock_names.json 캐시 → stock_aliases.json → positions → KIS API
    name_map: dict = _load_stock_names_cache()   # 1순위: 누적 캐시

    aliases_path = base / "stock_aliases.json"   # 2순위: alias 사전
    if aliases_path.exists():
        try:
            raw = _json.loads(aliases_path.read_text(encoding="utf-8"))
            for code, names in raw.items():
                if code not in name_map:
                    name_map[code] = names[0] if names else code
        except Exception:
            pass

    for pos in position_tracker.get_open_positions():  # 3순위: 보유 포지션
        code = pos.get("stock_code", "")
        if code and code not in name_map:
            name_map[code] = pos.get("stock_name", code)

    # 추천 종목별 정보 조합 + 4순위: KIS API 실시간 조회 (캐시 미스 종목만)
    code_scores: dict = report.get("code_scores", {})
    recommended: list = report.get("recommended_codes", [])
    max_score = max(code_scores.values(), default=1)

    # 캐시에 없는 종목 KIS API 일괄 조회 후 캐시 갱신
    miss_codes = [c for c in recommended if c not in name_map and c]
    if miss_codes and config.USERS:
        try:
            from kis_api import _token_cache as _tc
            _client = KISAPIClient(config.USERS[0])
            account_no = config.USERS[0].get("account_no", "")
            # 이미 캐시된 토큰이 있을 때만 API 조회 (추가 발급 불필요)
            token_ok = account_no in _tc or account_no[:8] + "01" in _tc
            if not token_ok:
                token_ok = _client.get_access_token()
            if token_ok:
                fetched: dict = {}
                for mc in miss_codes:
                    n = _client.get_stock_name(mc)
                    if n:
                        fetched[mc] = n
                if fetched:
                    name_map.update(fetched)
                    _update_stock_names_cache(fetched)
        except Exception as exc:
            logger.debug(f"종목명 API 조회 실패: {exc}")

    stocks = []
    for code in recommended:
        score = code_scores.get(code, 0)
        stocks.append({
            "code": code,
            "name": name_map.get(code, code),   # 최종 fallback: 코드 그대로
            "score": round(score, 1),
            "score_pct": round(score / max_score * 100, 1),
            "themes": themes.get(code, []),
        })

    # 테마 빈도 상위 10개
    theme_freq = report.get("theme_frequency", {})
    top_themes = sorted(theme_freq.items(), key=lambda x: x[1], reverse=True)[:12]

    return jsonify({
        "success": True,
        "generated_at": report.get("generated_at", ""),
        "text_count": report.get("text_count", 0),
        "auto_build": config.AUTO_BUILD_WATCH_LIST,
        "manual_watch_list": config.WATCH_LIST,
        "stocks": stocks,
        "top_themes": [{"name": k, "count": v} for k, v in top_themes],
        "channel_weights": weights,
    })


@app.route("/api/watchlist-report/refresh", methods=["POST"])
def refresh_watchlist_report():
    """AI 종목 추출 리포트 즉시 재생성 (대시보드 새로고침 버튼용)"""
    try:
        import scheduler as _sched
        codes = _sched.refresh_watchlist_report()
        return jsonify({
            "success": True,
            "recommended_codes": codes,
            "count": len(codes),
        })
    except Exception as exc:
        logger.error(f"watchlist refresh 실패: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc) if _FLASK_DEBUG else "재생성 실패"})


@app.route("/api/collection-stats")
def get_collection_stats():
    """정보수집 현황 통계 반환 (네이버 리서치 + 텔레그램 텍스트)"""
    import json as _json
    import pathlib as _pl

    base = _pl.Path("etc")

    def _scan_dir(path: _pl.Path):
        """디렉터리 내 파일 수와 최신 수정 시각 반환"""
        if not path.exists():
            return {"count": 0, "latest": None}
        files = [f for f in path.rglob("*") if f.is_file()]
        if not files:
            return {"count": 0, "latest": None}
        latest = max(files, key=lambda f: f.stat().st_mtime)
        return {
            "count": len(files),
            "latest": datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        }

    # 네이버 리서치 카테고리별 통계
    naver_root = base / "naver_research"
    naver_categories = {}
    NAVER_LABEL = {
        "market_info": "시황", "economy": "경제", "industry": "산업",
        "company": "기업", "invest": "투자", "debenture": "채권",
    }
    if naver_root.exists():
        for cat_dir in sorted(naver_root.iterdir()):
            if cat_dir.is_dir():
                stat = _scan_dir(cat_dir)
                naver_categories[cat_dir.name] = {
                    "label": NAVER_LABEL.get(cat_dir.name, cat_dir.name),
                    **stat,
                }

    # 텔레그램 텍스트 폴더별 통계
    # channel_groups.json 에 등록된 폴더만 표시 (삭제된 구버전 폴더 제외)
    tg_root = base / "telegram_texts"
    tg_groups = {}

    # 실제 모니터링 중인 폴더 목록 로드
    channel_groups_path = base / "channel_groups.json"
    active_tg_folders: set[str] = set()
    if channel_groups_path.exists():
        try:
            cg_data = _json.loads(channel_groups_path.read_text(encoding="utf-8"))
            if isinstance(cg_data, dict):
                active_tg_folders = set(cg_data.keys())
        except Exception:
            pass  # 파일 읽기 실패 시 빈 set → 아래에서 fallback

    if tg_root.exists():
        for grp_dir in sorted(tg_root.iterdir()):
            if not grp_dir.is_dir():
                continue
            # active_tg_folders 가 비어있으면 (channel_groups.json 없음) 전체 표시
            if active_tg_folders and grp_dir.name not in active_tg_folders:
                continue  # 등록되지 않은 구버전/테스트 폴더 제외
            stat = _scan_dir(grp_dir)
            if stat["count"] > 0:
                tg_groups[grp_dir.name] = stat

    # 텔레그램 리스너 추적 채널 수
    state_file = base / "telegram_listener_state.json"
    tracked_channels = 0
    if state_file.exists():
        try:
            tracked_channels = len(_json.loads(state_file.read_text(encoding="utf-8")))
        except Exception:
            pass

    return jsonify({
        "success": True,
        "naver": naver_categories,
        "telegram": tg_groups,
        "tracked_channels": tracked_channels,
    })


@app.route("/api/logs")
def get_logs():
    """가장 최근 로그 파일의 마지막 100줄 반환 (파싱)"""
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return jsonify({"success": True, "data": []})

        # 가장 최신 로그 파일 찾기
        log_files = glob.glob(os.path.join(log_dir, "trading_*.log"))
        if not log_files:
            return jsonify({"success": True, "data": []})

        latest_log = max(log_files, key=os.path.getctime)

        lines = []
        with open(latest_log, "r", encoding="utf-8") as f:
            # 전체 읽기 (로그가 매우 크면 tail 로직 필요)
            all_lines = f.readlines()
            # 뒤에서 100줄만
            for line in all_lines[-100:]:
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 4:
                    lines.append({
                        "timestamp": parts[0],
                        "module": parts[1],
                        "level": parts[2],
                        "message": parts[3]
                    })
                else:
                    # 파싱 실패한 줄은 통째로
                    lines.append({
                        "timestamp": "",
                        "module": "",
                        "level": "INFO",
                        "message": line.strip()
                    })

        # 최신 로그가 위에 오도록 역순 배치
        lines.reverse()
        return jsonify({"success": True, "data": lines})

    except Exception as e:
        logger.error(f"로그 조회 오류: {e}", exc_info=True)
        detail = str(e) if _FLASK_DEBUG else "서버 내부 오류"
        return jsonify({"success": False, "error": detail})

def _is_scheduler_running() -> bool:
    """main.py 프로세스 또는 로그 최신성으로 스케줄러 가동 판단"""
    if _main_is_running():
        return True
    try:
        log_files = glob.glob(os.path.join("logs", "trading_*.log"))
        if not log_files:
            return False
        latest = max(log_files, key=os.path.getmtime)
        age = datetime.now().timestamp() - os.path.getmtime(latest)
        return age < 120
    except Exception:
        return False


@app.route("/api/system/start", methods=["POST"])
def system_start():
    """main.py 시작"""
    global _main_proc
    if _main_is_running():
        return jsonify({"success": False, "error": "이미 실행 중입니다"})
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        _main_proc = subprocess.Popen(
            [sys.executable, str(_BASE_DIR / "main.py")],
            cwd=str(_BASE_DIR),
            **kwargs,
        )
        _MAIN_PID_FILE.write_text(str(_main_proc.pid), encoding="utf-8")
        logger.info(f"[Dashboard] main.py 시작 (PID={_main_proc.pid})")
        return jsonify({"success": True, "pid": _main_proc.pid})
    except Exception as e:
        logger.error(f"[Dashboard] main.py 시작 실패: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/system/stop", methods=["POST"])
def system_stop():
    """main.py 중지"""
    global _main_proc
    if not _main_is_running():
        return jsonify({"success": False, "error": "실행 중인 프로세스가 없습니다"})
    try:
        pid = None
        if _main_proc is not None and _main_proc.poll() is None:
            pid = _main_proc.pid
            _main_proc.terminate()
            try:
                _main_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _main_proc.kill()
            _main_proc = None
        elif _MAIN_PID_FILE.exists():
            pid = int(_MAIN_PID_FILE.read_text(encoding="utf-8").strip())
            _kill_pid(pid)
        try:
            _MAIN_PID_FILE.unlink()
        except OSError:
            pass
        logger.info(f"[Dashboard] main.py 중지 (PID={pid})")
        return jsonify({"success": True, "pid": pid})
    except Exception as e:
        logger.error(f"[Dashboard] main.py 중지 실패: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/system-status")
def get_system_status():
    """스케줄러 가동 상태 및 설정 요약 반환"""
    try:
        return jsonify({
            "success": True,
            "main_running": _main_is_running(),
            "scheduler_running": _is_scheduler_running(),
            "jobs": [],
            "telegram_monitor": os.getenv("TELEGRAM_MONITOR_ENABLED", "false").lower() == "true",
            "naver_research": os.getenv("NAVER_RESEARCH_ENABLED", "true").lower() == "true",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        logger.error(f"시스템 상태 조회 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})


@app.route("/api/ai-costs")
def get_ai_costs():
    """Claude Code 개발 비용 요약 (JSONL 파싱)"""
    try:
        import glob as _glob
        import json as _json
        import pathlib

        claude_projects = pathlib.Path.home() / ".claude" / "projects"
        jsonl_files = []
        if claude_projects.exists():
            for proj_dir in claude_projects.iterdir():
                if proj_dir.is_dir() and "JY" in proj_dir.name:
                    jsonl_files.extend(proj_dir.glob("*.jsonl"))

        PRICING = {
            "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0,  "cache_read": 0.30, "cache_write": 3.75},
            "claude-haiku-4-5":  {"input": 0.8,  "output": 4.0,   "cache_read": 0.08, "cache_write": 1.0},
            "claude-opus-4-7":   {"input": 15.0, "output": 75.0,  "cache_read": 1.50, "cache_write": 18.75},
        }

        model_stats = {}
        for jsonl in jsonl_files:
            try:
                with open(jsonl, encoding="utf-8") as f:
                    for line in f:
                        try:
                            obj = _json.loads(line)
                            usage = obj.get("usage") or obj.get("message", {}).get("usage") or {}
                            model = obj.get("model") or obj.get("message", {}).get("model") or ""
                            if not model or not usage or model == "<synthetic>":
                                continue
                            s = model_stats.setdefault(model, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "messages": 0})
                            s["input"]       += usage.get("input_tokens", 0)
                            s["output"]      += usage.get("output_tokens", 0)
                            s["cache_read"]  += usage.get("cache_read_input_tokens", 0)
                            s["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                            s["messages"]    += 1
                        except Exception:
                            pass
            except Exception:
                pass

        rows = []
        total_cost = 0.0
        total_tokens = 0
        for model, s in model_stats.items():
            p = PRICING.get(model, {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75})
            cost = (
                s["input"]       / 1_000_000 * p["input"] +
                s["output"]      / 1_000_000 * p["output"] +
                s["cache_read"]  / 1_000_000 * p["cache_read"] +
                s["cache_write"] / 1_000_000 * p["cache_write"]
            )
            tok = s["input"] + s["output"] + s["cache_read"] + s["cache_write"]
            total_cost   += cost
            total_tokens += tok
            rows.append({
                "model": model, "messages": s["messages"],
                "input": s["input"], "output": s["output"],
                "cache_read": s["cache_read"], "cache_write": s["cache_write"],
                "total_tokens": tok, "cost_usd": round(cost, 4),
            })

        rows.sort(key=lambda r: r["cost_usd"], reverse=True)
        return jsonify({
            "success": True,
            "rows": rows,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "scanned_files": len(jsonl_files),
        })
    except Exception as e:
        logger.error(f"AI 비용 조회 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})


def _compute_performance_stats(closed: list) -> dict:
    """closed_positions 리스트 → 누적 성과 지표 계산"""
    if not closed:
        return {
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "total_pnl_amt": 0.0,
            "avg_pnl_rate": 0.0,
            "best_pnl_rate": 0.0,
            "worst_pnl_rate": 0.0,
        }
    pnl_rates = [float(p.get("pnl_rate", 0.0)) for p in closed]
    pnl_amts  = [float(p.get("pnl_amt", 0.0))  for p in closed]
    wins      = [r for r in pnl_rates if r > 0]
    losses    = [r for r in pnl_rates if r <= 0]
    trade_count = len(closed)
    return {
        "trade_count": trade_count,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / trade_count * 100, 2) if trade_count else 0.0,
        "total_pnl_amt": round(sum(pnl_amts), 2),
        "avg_pnl_rate": round(sum(pnl_rates) / trade_count, 4) if trade_count else 0.0,
        "best_pnl_rate": round(max(pnl_rates), 4),
        "worst_pnl_rate": round(min(pnl_rates), 4),
    }


@app.route("/api/performance")
def get_performance():
    """누적 거래 성과 요약 (closed_positions.json 기반, KIS API 호출 없음)"""
    try:
        closed = position_tracker.load_closed_positions()
        account = request.args.get("account_no", "").strip()
        if account:
            closed = [p for p in closed if str(p.get("account_no", "")) == account]
        return jsonify({"success": True, "data": _compute_performance_stats(closed)})
    except Exception as e:
        logger.error(f"성과 조회 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})


@app.route("/api/performance/by-stock")
def get_performance_by_stock():
    """종목별 누적 PnL 랭킹 (closed_positions.json 기반)"""
    try:
        closed = position_tracker.load_closed_positions()
        account = request.args.get("account_no", "").strip()
        if account:
            closed = [p for p in closed if str(p.get("account_no", "")) == account]

        agg: dict = {}
        for p in closed:
            code = str(p.get("stock_code", ""))
            if not code:
                continue
            slot = agg.setdefault(code, {
                "stock_code": code,
                "stock_name": p.get("stock_name", code),
                "trade_count": 0,
                "total_pnl_amt": 0.0,
                "pnl_rates": [],
            })
            slot["trade_count"] += 1
            slot["total_pnl_amt"] += float(p.get("pnl_amt", 0.0))
            slot["pnl_rates"].append(float(p.get("pnl_rate", 0.0)))

        rows = []
        for slot in agg.values():
            rates = slot.pop("pnl_rates")
            slot["avg_pnl_rate"] = round(sum(rates) / len(rates), 4) if rates else 0.0
            slot["total_pnl_amt"] = round(slot["total_pnl_amt"], 2)
            rows.append(slot)
        rows.sort(key=lambda r: r["total_pnl_amt"], reverse=True)
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        logger.error(f"종목별 성과 조회 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})


def _mask_account(acct: str) -> str:
    """계좌번호 마지막 2자리만 노출 (예: 73918950 → '***8950')"""
    s = str(acct)
    return ("*" * max(0, len(s) - 4)) + s[-4:] if len(s) > 4 else "****"


def _check_positions_file_valid():
    """positions.json 의 raw JSON 파싱 여부 + 열린 포지션 수.
    _load() 와 달리 auto-recovery 는 트리거하지 않음.
    """
    pf = position_tracker.POSITION_FILE
    if not os.path.exists(pf):
        return True, 0
    try:
        import json as _json
        with open(pf, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if not isinstance(data, dict):
            return False, 0
        open_count = sum(
            1 for v in data.values()
            if isinstance(v, dict) and v.get("status") == "open"
        )
        return True, open_count
    except (Exception,):
        return False, 0


def _check_last_log_age_sec():
    """가장 최근 trading_*.log 파일의 수정 시각 기준 경과 초.
    로그 파일 없으면 None 반환."""
    try:
        files = glob.glob(os.path.join("logs", "trading_*.log"))
        if not files:
            return None
        latest = max(files, key=os.path.getmtime)
        return int(datetime.now().timestamp() - os.path.getmtime(latest))
    except Exception:
        return None


def _check_kis_tokens():
    """kis_api._token_cache 메타만 조회 — 절대 KIS API 호출하지 않음.
    반환: {masked_account: {"seconds_until_expiry": int, "expired": bool}}"""
    import time as _time
    try:
        from kis_api import _token_cache
    except Exception:
        return {}
    now = _time.time()
    result = {}
    for acct, info in dict(_token_cache).items():
        exp = float(info.get("expire_time", 0) or 0)
        result[_mask_account(acct)] = {
            "seconds_until_expiry": int(exp - now) if exp else None,
            "expired": (exp <= now) if exp else None,
        }
    return result


def _check_thread_alive(thread_obj) -> "bool | None":
    """스레드 객체가 살아있는지. 등록된 적 없으면 None (unknown)."""
    if thread_obj is None:
        return None
    try:
        return bool(thread_obj.is_alive())
    except Exception:
        return None


def _compute_health_status(checks: dict) -> str:
    """집계 status 산출.

    unhealthy: positions.json 파싱 실패 (실거래 보호 중단)
    degraded:  토큰 만료 / 스케줄러 미가동 / 5분 이상 로그 정체
    healthy:   그 외 (None=unknown 은 healthy 로 간주)
    """
    if checks.get("positions_json_valid") is False:
        return "unhealthy"

    degraded_signals = []
    tokens = checks.get("kis_tokens") or {}
    if any(v.get("expired") is True for v in tokens.values()):
        degraded_signals.append("kis_token_expired")
    if checks.get("scheduler_running") is False:
        degraded_signals.append("scheduler_stopped")
    last_log = checks.get("last_log_age_sec")
    if isinstance(last_log, int) and last_log > 300:
        degraded_signals.append("logs_stale")

    checks["degraded_reasons"] = degraded_signals
    return "degraded" if degraded_signals else "healthy"


@app.route("/api/rejections/summary")
def get_rejections_summary():
    """에이전트 거부 사유 요약 (관측성 — 매매 흐름과 무관)."""
    try:
        import agent_telemetry
        try:
            days = int(request.args.get("days", "7"))
        except (TypeError, ValueError):
            days = 7
        days = max(1, min(days, 90))
        try:
            top = int(request.args.get("top", "10"))
        except (TypeError, ValueError):
            top = 10
        top = max(1, min(top, 50))
        return jsonify({
            "success": True,
            "data": agent_telemetry.summarize_rejections(days=days, top_reasons=top),
        })
    except Exception as e:
        logger.error(f"거부 요약 조회 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e) if _FLASK_DEBUG else "서버 내부 오류"})


@app.route("/api/health")
def get_health():
    """시스템 헬스체크 엔드포인트 (UptimeRobot 호환: 200=healthy, 503=degraded/unhealthy).

    KIS API 호출 없음 — 캐시된 토큰 메타데이터만 확인.
    계좌번호는 마스킹되어 노출되며, 토큰 값 자체는 절대 포함하지 않음.
    """
    try:
        import scheduler as _sched
        valid, open_count = _check_positions_file_valid()
        checks = {
            "scheduler_running": _is_scheduler_running(),
            "kis_tokens": _check_kis_tokens(),
            "positions_json_valid": valid,
            "positions_open_count": open_count,
            "closed_positions_count": len(position_tracker.load_closed_positions()),
            "last_log_age_sec": _check_last_log_age_sec(),
            "telegram_listener_alive": _check_thread_alive(getattr(_sched, "telegram_listener_thread", None)),
            "naver_research_alive": _check_thread_alive(getattr(_sched, "naver_research_thread", None)),
        }
        status = _compute_health_status(checks)
        http_status = 200 if status == "healthy" else 503
        body = {
            "status": status,
            "checks": checks,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        return jsonify(body), http_status
    except Exception as e:
        logger.error(f"health 체크 오류: {e}", exc_info=True)
        # health 라우트는 절대 200/503 외 응답하지 않도록 안전망
        return jsonify({
            "status": "unhealthy",
            "error": str(e) if _FLASK_DEBUG else "internal error",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }), 503


if __name__ == "__main__":
    app.run(host=_FLASK_HOST, port=_FLASK_PORT, debug=_FLASK_DEBUG)
