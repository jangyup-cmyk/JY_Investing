import glob
import logging
import os
import pathlib
from datetime import datetime

from flask import Flask, jsonify, render_template

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

            balances.append({
                "name": user["name"],
                "account": user["account_no"],
                "total_eval_amount": int(summary.get("tot_evlu_amt", 0)),
                "total_buy_amount": int(summary.get("tot_puchsamt", 0)),
                "available_balance": int(summary.get("prvs_rcdl_excc_amt", 0)),
                "holdings_count": len(holdings),
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
        # 수익률 등을 서버에서 실시간 조회해서 줄 수도 있으나,
        # API 부하가 심할 수 있으므로 저장된 매수가 기준으로 클라이언트에 전달.
        # 최신가는 별도 API나 스케줄러 로그에서 갱신됨을 가정.
        return jsonify({"success": True, "data": positions})
    except Exception as e:
        logger.error(f"포지션 조회 오류: {e}", exc_info=True)
        detail = str(e) if _FLASK_DEBUG else "서버 내부 오류"
        return jsonify({"success": False, "error": detail})

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
    """로그 파일 최신 엔트리가 2분 이내면 스케줄러가 가동 중으로 판단"""
    try:
        log_files = glob.glob(os.path.join("logs", "trading_*.log"))
        if not log_files:
            return False
        latest = max(log_files, key=os.path.getmtime)
        age = datetime.now().timestamp() - os.path.getmtime(latest)
        return age < 120
    except Exception:
        return False


@app.route("/api/system-status")
def get_system_status():
    """스케줄러 가동 상태 및 설정 요약 반환"""
    try:
        return jsonify({
            "success": True,
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


if __name__ == "__main__":
    app.run(host=_FLASK_HOST, port=_FLASK_PORT, debug=_FLASK_DEBUG)
