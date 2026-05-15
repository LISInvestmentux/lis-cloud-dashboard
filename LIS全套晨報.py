"""
LIS 全套晨報（Phase 33.1）— 每天 8AM 自動跑全套

依序執行所有 push 腳本，組成完整每日早報：
  1. 全息儀表板（Phase 33）— 部位 + 底部 SOP + 供需 + 策略池 + 信任分
  2. 即時決策（Phase 17-26）— 訊號 + Kelly + 彈藥
  3. 主情報中心（Phase 22-25）— 台美連動 + 法人 + 基本面 + 新聞
  4. 跨來源共識（Phase 27 + 30）— 多社群共識排行
  5. 集中模式計畫（Phase 20）— ARK 9 檔行動

預估 LINE 卡數：4-6 張 carousel
時間：約 30-60 秒

排程設定：
  Windows Task Scheduler → 每天 08:00 → 跑此腳本
"""
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent


def 跑(腳本: str, 描述: str, 必跑: bool = False) -> bool:
    """跑一個 push 腳本，回傳是否成功"""
    print(f"\n{'='*50}")
    print(f"📡 [{datetime.now():%H:%M:%S}] {描述}")
    print(f"{'='*50}")

    try:
        r = subprocess.run(
            [str(專案根 / ".venv/Scripts/python.exe"), 腳本],
            cwd=str(專案根),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        if r.returncode == 0:
            # 印重要 line
            for line in r.stdout.split("\n")[-15:]:
                if line.strip():
                    print(f"  {line}")
            print(f"  ✅ 完成")
            return True
        else:
            print(f"  ❌ 失敗 (code {r.returncode})")
            print(f"  stderr: {r.stderr[:300]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ⏱️ 超時")
        return False
    except Exception as e:
        print(f"  💥 異常：{e}")
        return False


def 主流程() -> int:
    開始 = datetime.now()
    print(f"\n{'#'*60}")
    print(f"# 🌅 LIS 全套晨報 [{開始:%Y-%m-%d %H:%M:%S}]")
    print(f"{'#'*60}")

    結果 = {}

    # 0. 今日行動卡（Phase 33.2 — 最先推，user 一打開最先看到）
    結果["今日行動"] = 跑("push_今日行動.py",
                            "今日行動卡（Phase 33.2 — 最重要的一張）")
    time.sleep(2)

    # 1. 全息儀表板（一張看全部）
    結果["全息儀表板"] = 跑("push_holistic.py",
                              "全息儀表板（Phase 33）")
    time.sleep(2)

    # 2. 即時決策（含自動記錄訊號）
    結果["即時決策"] = 跑("instant_decision.py",
                            "即時決策（Phase 17-26）")
    time.sleep(2)

    # 3. 主情報中心（台美連動 + 法人 + 基本面 + 新聞）
    結果["主情報中心"] = 跑("push_master_intelligence.py",
                              "主情報中心（Phase 22-25）")
    time.sleep(2)

    # 4. 跨來源共識（社群+KOL+ARK 共識排行）
    結果["跨來源共識"] = 跑("push_社群共識.py",
                              "跨來源共識（Phase 27 + 30）")
    time.sleep(2)

    # 5. 策略池入選
    結果["策略池"] = 跑("push_strategy_pool.py",
                          "策略池入選（Phase 25）")

    # 總結
    耗時 = (datetime.now() - 開始).total_seconds()
    成功 = sum(1 for v in 結果.values() if v)
    print(f"\n{'#'*60}")
    print(f"# ✅ 晨報完成 — 成功 {成功}/{len(結果)} / 耗時 {耗時:.0f} 秒")
    print(f"{'#'*60}")
    for 名, ok in 結果.items():
        print(f"  {'✅' if ok else '❌'} {名}")

    return 0 if 成功 == len(結果) else 1


if __name__ == "__main__":
    sys.exit(主流程())
