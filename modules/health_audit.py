"""
Phase 36 — LIS 反 CC 自動健康掃描

Claude 的「自我審查機制」— 每次跑都會檢查整個系統有沒有：
  1. 排程任務漏掉 / 過期
  2. 推播失敗 / API 錯誤
  3. portfolio.json schema 異常
  4. pending_orders / pending_settlement 過期未清
  5. 重要檔案缺失
  6. logs 中的 ERROR 數量異常

設計理念：
  user 早上看到 health_audit 報告 = 提早發現問題
  不要等 user 抱怨「為什麼今天沒收到推播」才查

每天 9:00 跑 LIS_Health_Check 時呼叫。
"""
import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 檢查排程任務() -> dict:
    """檢查 Windows Task Scheduler 裡的 LIS_* 任務"""
    import subprocess
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-ScheduledTask -TaskName 'LIS*' | "
             "ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
             "[PSCustomObject]@{Name=$_.TaskName; State=$_.State; "
             "Next=$i.NextRunTime; Last=$i.LastRunTime; "
             "LastResult=$i.LastTaskResult} } | "
             "ConvertTo-Json"],
            capture_output=True, text=True, encoding="utf-8", timeout=10)
        tasks = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(tasks, dict):
            tasks = [tasks]
    except Exception as e:
        return {"錯誤": f"無法查排程：{e}", "任務數": 0,
                "異常任務": [], "正常": False}

    異常 = []
    for t in tasks:
        try:
            next_run = t.get("Next", "")
            if not next_run or next_run == "":
                異常.append({
                    "name": t["Name"],
                    "問題": "沒有下次執行時間（可能停用）",
                })
                continue
            # LastResult 判定：
            #   0 = 成功
            #   1 = PowerShell stderr 輸出 false-positive（不算 fail，要看 log）
            #   267011 = Task has not yet run
            #   267009 = Task is currently running
            # → 1 也忽略（避免 yfinance/Gemini 偶爾警告就警報）
            # → 真正要關心的是 >= 2 的錯誤碼
            lr = t.get("LastResult", 0)
            容忍清單 = (0, 1, 267011, 267009)
            if lr not in 容忍清單:
                異常.append({
                    "name": t["Name"],
                    "問題": f"上次執行失敗 (code {lr})",
                })
        except Exception:
            continue

    return {
        "任務數": len(tasks),
        "異常任務": 異常,
        "正常": len(異常) == 0,
    }


def 檢查portfolio_schema() -> dict:
    """檢查 portfolio.json 結構完整性"""
    path = 專案根 / "API" / "portfolio.json"
    if not path.exists():
        return {"錯誤": "portfolio.json 不存在", "正常": False}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"錯誤": f"JSON 解析失敗：{e}", "正常": False}

    必要欄位 = ["current_cash_twd", "current_positions",
                "risk_rules", "deployment_by_enjoy_index"]
    缺失 = [f for f in 必要欄位 if f not in data]
    問題 = []
    if 缺失:
        問題.append(f"缺欄位：{缺失}")

    # 持股 sanity check
    持股 = data.get("current_positions", [])
    for p in 持股:
        if p.get("symbol") == "AGGREGATE":
            continue
        if not p.get("symbol"):
            問題.append(f"持股缺 symbol: {p}")
        if p.get("shares", 0) <= 0:
            問題.append(f"{p.get('symbol')} 股數 ≤ 0")
        if p.get("avg_cost", 0) <= 0:
            問題.append(f"{p.get('symbol')} avg_cost ≤ 0")

    return {
        "持股檔數": len([p for p in 持股 if p.get("symbol") != "AGGREGATE"]),
        "現金_twd": data.get("current_cash_twd", 0),
        "問題": 問題,
        "正常": len(問題) == 0,
    }


def 檢查pending_過期() -> dict:
    """檢查 pending_orders / pending_settlement 有沒有過期"""
    path = 專案根 / "API" / "portfolio.json"
    if not path.exists():
        return {"正常": True, "過期": []}
    data = json.loads(path.read_text(encoding="utf-8"))

    今天 = date.today()
    過期 = []

    # pending_orders 太老（>14 天沒掛到單）
    for o in data.get("pending_orders", []):
        ca = o.get("created_at", "")
        try:
            d = datetime.strptime(ca[:10], "%Y-%m-%d").date()
            天數 = (今天 - d).days
            if 天數 > 14:
                過期.append({
                    "類型": "pending_order 太老",
                    "symbol": o.get("symbol"),
                    "建立": ca,
                    "天數": 天數,
                    "建議": "確認是否要清掉或更新",
                })
        except Exception:
            continue

    # pending_settlement 早就過了入帳日
    for p in data.get("pending_settlement", []):
        sd = p.get("settlement_date", "")
        try:
            d = datetime.strptime(sd[:10], "%Y-%m-%d").date()
            if (今天 - d).days > 2:  # 過了 2 天還沒清
                過期.append({
                    "類型": "settlement 已過期未清",
                    "symbol": p.get("symbol"),
                    "settlement_date": sd,
                    "建議": "用 settlement_auto 清掉並把錢加進現金",
                })
        except Exception:
            continue

    return {
        "過期項目": 過期,
        "正常": len(過期) == 0,
    }


def 檢查logs_錯誤() -> dict:
    """掃今日 logs，數 ERROR / 400 / Traceback"""
    今天 = date.today().strftime("%Y-%m-%d")
    log_dir = 專案根 / "數據" / "logs"
    if not log_dir.exists():
        return {"正常": True, "今日logs": 0}

    今日_logs = list(log_dir.glob(f"*{今天}*"))
    錯誤總數 = 0
    嚴重 = []
    for log in 今日_logs:
        try:
            內容 = log.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # 計數
        e_count = len(re.findall(r"Traceback|HTTP 400|HTTP 500|ERROR", 內容))
        錯誤總數 += e_count
        if e_count >= 3:
            嚴重.append({"log": log.name, "錯誤數": e_count})

    return {
        "今日logs": len(今日_logs),
        "錯誤總數": 錯誤總數,
        "嚴重log": 嚴重,
        "正常": len(嚴重) == 0,
    }


def 檢查關鍵檔案() -> dict:
    """檢查必要檔案存在"""
    必要 = [
        "API/portfolio.json",
        "API/.env",
        "API/watchlist.json",
        "程式碼/.venv/Scripts/python.exe",
        "程式碼/modules/daily_action_card.py",
        "程式碼/modules/line_push.py",
        "程式碼/modules/flex_builder.py",
    ]
    缺失 = []
    for f in 必要:
        p = 專案根 / f
        if not p.exists():
            缺失.append(f)

    return {
        "檢查數": len(必要),
        "缺失": 缺失,
        "正常": len(缺失) == 0,
    }


def 跑全套(推LINE: bool = False) -> dict:
    """主入口：跑全部檢查"""
    print(f"=== Phase 36 LIS 健康掃描 [{datetime.now():%Y-%m-%d %H:%M}] ===")

    結果 = {
        "排程": 檢查排程任務(),
        "portfolio": 檢查portfolio_schema(),
        "pending": 檢查pending_過期(),
        "logs": 檢查logs_錯誤(),
        "檔案": 檢查關鍵檔案(),
        "時間": datetime.now().isoformat(timespec="seconds"),
    }

    所有正常 = all(r.get("正常", False) for r in 結果.values()
                    if isinstance(r, dict))
    結果["總體正常"] = 所有正常

    # 印報告
    for 區, r in 結果.items():
        if 區 == "時間" or 區 == "總體正常":
            continue
        if isinstance(r, dict):
            符 = "✅" if r.get("正常") else "⚠️"
            print(f"\n{符} {區}")
            for k, v in r.items():
                if k == "正常":
                    continue
                if isinstance(v, list) and v:
                    print(f"  {k}: {len(v)} 筆")
                    for item in v[:3]:
                        print(f"    {item}")
                elif not isinstance(v, list):
                    print(f"  {k}: {v}")

    print(f"\n{'✅ 全部正常' if 所有正常 else '⚠️ 有異常需處理'}")

    # 推 LINE（只在異常時推）
    if 推LINE and not 所有正常:
        推LINE通知(結果)

    return 結果


def 推LINE通知(結果: dict) -> bool:
    """組異常摘要推 LINE"""
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return False

    片段 = [f"🩺 LIS 健康掃描 — {datetime.now():%m/%d %H:%M}"]
    for 區, r in 結果.items():
        if 區 in ("時間", "總體正常") or not isinstance(r, dict):
            continue
        if r.get("正常"):
            continue
        片段.append(f"\n⚠️ {區} 異常：")
        for k, v in r.items():
            if k in ("正常",):
                continue
            if isinstance(v, list) and v:
                for item in v[:3]:
                    if isinstance(item, dict):
                        s = " / ".join(f"{ik}:{iv}" for ik, iv in
                                        list(item.items())[:3])
                        片段.append(f"  • {s}")
                    else:
                        片段.append(f"  • {item}")

    msg = "\n".join(片段)
    try:
        line_push.推播文字訊息(msg[:4500])
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    push = "--push" in sys.argv
    跑全套(推LINE=push)
