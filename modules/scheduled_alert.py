"""
排程任務健康監控（Phase 32.5）

兩個用途：
  1. **即時警示**：排程腳本失敗時 call `推送失敗警示()` 推 LINE
  2. **每日健診**：每天 09:00 跑 `每日健診()` 掃過去 24h 所有 log

用法 1（即時）：
  python -m modules.scheduled_alert ALERT "LIS_Daily_Report" 1 "D:\\...\\run_2026-05-14.log"

用法 2（每日健診，預設）：
  python -m modules.scheduled_alert
"""
import os
import re
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
LOG目錄 = 專案根 / "數據" / "logs"


def 推送失敗警示(任務名: str, exit_code: int, log_file: str = "") -> int:
    """單次失敗即時推 LINE"""
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception as e:
        print(f"無法 import line_push: {e}")
        return 1

    log_tail = ""
    if log_file and Path(log_file).exists():
        try:
            content = Path(log_file).read_text(encoding="utf-8", errors="replace")
            log_tail = "\n".join(content.splitlines()[-10:])
        except Exception:
            pass

    訊息 = (
        f"⚠️ LIS 排程任務失敗\n"
        f"任務：{任務名}\n"
        f"ExitCode：{exit_code}\n"
        f"時間：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"———\n"
        f"Log tail：\n{log_tail[-500:]}"
    )

    try:
        line_push.推播文字訊息(訊息)
        print(f"✅ 已推送失敗警示：{任務名}")
        return 0
    except Exception as e:
        print(f"❌ 推送失敗：{e}")
        traceback.print_exc()
        return 1


def 掃近期log(小時數: int = 24) -> dict:
    """掃過去 N 小時的 .log，找 ExitCode != 0 的任務"""
    if not LOG目錄.exists():
        return {"檢查到": 0, "失敗清單": [], "說明": "log 目錄不存在"}

    cutoff = datetime.now() - timedelta(hours=小時數)
    失敗清單 = []
    檢查到 = 0

    for log_path in LOG目錄.glob("*.log"):
        try:
            stat = log_path.stat()
            修改時間 = datetime.fromtimestamp(stat.st_mtime)
            if 修改時間 < cutoff:
                continue
            檢查到 += 1
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # 抓 "ExitCode=N" 結尾，N != 0 表示失敗
            matches = re.findall(r"ExitCode=(\d+)", content)
            if not matches:
                continue
            最後exit = int(matches[-1])
            if 最後exit != 0:
                # 抓最後幾行錯誤訊息
                tail = "\n".join(content.splitlines()[-8:])
                失敗清單.append({
                    "檔案": log_path.name,
                    "exit_code": 最後exit,
                    "修改時間": 修改時間.strftime("%m-%d %H:%M"),
                    "tail": tail[-400:],
                })
        except Exception:
            continue

    return {"檢查到": 檢查到, "失敗清單": 失敗清單}


def 每日健診(只在失敗時推: bool = True) -> int:
    """掃過去 48h log（cover 昨天+今天），有失敗才推 LINE"""
    結果 = 掃近期log(小時數=48)
    print(f"=== 排程健診 [{datetime.now():%H:%M:%S}] ===")
    print(f"檢查 log 數: {結果['檢查到']}")
    print(f"失敗任務數: {len(結果['失敗清單'])}")

    if not 結果["失敗清單"]:
        if 只在失敗時推:
            print("✅ 全部正常，無需推播")
            return 0

    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception as e:
        print(f"無法 import line_push: {e}")
        return 1

    if 結果["失敗清單"]:
        失敗列 = "\n".join(
            f"❌ {r['檔案']} ({r['修改時間']}, exit={r['exit_code']})"
            for r in 結果["失敗清單"][:5]
        )
        訊息 = (
            f"⚠️ LIS 排程每日健診（48h 內）\n"
            f"檢查 {結果['檢查到']} 份 log，{len(結果['失敗清單'])} 份失敗：\n"
            f"———\n"
            f"{失敗列}\n"
            f"———\n"
            f"請查 D:\\LIS股票投資系統\\數據\\logs\\"
        )
    else:
        訊息 = (
            f"✅ LIS 排程每日健診（48h 全綠）\n"
            f"檢查 {結果['檢查到']} 份 log，全部 ExitCode=0\n"
            f"系統穩定運作中"
        )

    try:
        line_push.推播文字訊息(訊息)
        print("✅ 已推送健診結果")
        return 0
    except Exception as e:
        print(f"❌ 推送失敗：{e}")
        return 1


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    if len(sys.argv) >= 2 and sys.argv[1] == "ALERT":
        # 即時警示模式：ALERT 任務名 exit_code [log_file]
        任務名 = sys.argv[2] if len(sys.argv) > 2 else "未知任務"
        exit_code = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        log_file = sys.argv[4] if len(sys.argv) > 4 else ""
        sys.exit(推送失敗警示(任務名, exit_code, log_file))
    else:
        # 預設：每日健診模式
        sys.exit(每日健診())
