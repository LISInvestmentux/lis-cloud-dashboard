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

    # ⭐ Phase 49 (5/17) — 每日 KOL YouTube 掃描（放最前，慢但失敗不影響後續）
    結果["KOL掃描"] = 跑("push_kol_scan.py",
                          "KOL YouTube 掃描（Terry 等）")

    # ⭐ Phase 51 (5/17) — 綜合勝率評分（每檔台股 0-100 該賣分 + 整體勝率）
    結果["勝率評分"] = 跑("push_comprehensive_score.py",
                          "Phase 51 綜合勝率評分（19 檔台股）")

    # ⭐ Phase 52 (5/17) — 目的反推配置（每週一推一次，其他天 silent）
    結果["目的反推"] = 跑("push_goal_backsolve.py",
                          "Phase 52 目的反推配置（週一一次）")

    # ⭐ Phase 53 (5/17) — 獨立成長軌跡（每天更新進度條）
    結果["成長軌跡"] = 跑("push_growth_trajectory.py",
                          "Phase 53 獨立成長軌跡")

    # ⭐ Phase 54 (5/17) — Sylvie 雙向反推 + 軌跡追蹤（每週一）
    結果["Sylvie追蹤"] = 跑("push_sylvie_tracking.py",
                            "Phase 54 Sylvie 反推+軌跡（週一）")

    # ⭐ Phase 60 (5/17) — LIS 教練建議（整合 55-59 新聞/籌碼/期貨/融資/技術）
    # 包含 Phase 55-59 全部內部呼叫一次
    結果["教練建議"] = 跑("push_coach_advisor.py",
                          "Phase 60 LIS 教練（減碼/加碼/守著）")

    # ⭐ Phase 61 (5/17) — 宏觀訊號（油價/殖利率/DXY/黃金/BTC）
    結果["宏觀訊號"] = 跑("push_macro_signals.py",
                          "Phase 61 宏觀訊號")

    # ⭐ Phase 62 (5/17) — 動態支撐阻力（Fib + 歷史 + 整數 + MA）
    結果["支撐阻力"] = 跑("push_support_resistance.py",
                          "Phase 62 動態支撐阻力")

    # ⭐ Phase 63 (5/17) — 事件月曆 + 主動推播
    結果["事件月曆"] = 跑("push_event_calendar.py",
                          "Phase 63 事件月曆")

    # ⭐ Phase 64 (5/17) — 事件後主動觸發（NVDA 5/20 財報後自動推買單卡）
    結果["事件觸發"] = 跑("push_event_trigger.py",
                          "Phase 64 事件觸發（昨日重大事件自動分析）")

    # ⭐ Phase 65 (5/17) — 達標機率分析（主動告訴你年化期望 + 各目標機率）
    結果["達標機率"] = 跑("push_return_target.py",
                          "Phase 65 達標機率（不問也告訴你）")

    # ⭐ Phase 66 (5/17) — 預掛單建議（兩段式：A 試反彈 / B 保底）
    結果["預掛單"] = 跑("push_pre_market_orders.py",
                        "Phase 66 預掛單建議（新手友好）")

    # ⭐ Phase 67 (5/18 凌晨) — 多 AI 神諭（每週一、4 AI 並行 + Claude 整合）
    結果["多AI神諭"] = 跑("push_multi_ai_oracle.py",
                          "Phase 67 多 AI 神諭（週一、OpenRouter）")

    # ⭐ Phase 68 (5/18 凌晨) — Gmail 備援（廣州牆內可用）
    結果["Gmail備援"] = 跑("push_daily_email.py",
                          "Phase 68 Gmail 報告（廣州牆內備援）")

    # ⭐ Phase 70+71+73 (5/18 凌晨) — 量化回測 + 歷史佐證 + KOL 追蹤（週一深度）
    結果["量化驗證"] = 跑("push_phase70_71_72_73.py",
                          "Phase 70-73 量化深度（週一）")

    # ⭐ Phase 79 (5/18 10:30) — 截圖自動內化（user 丟資料夾、自動 sync）
    # 必須在「最終共識」前跑、確保 portfolio.json 是最新
    結果["截圖內化"] = 跑("push_screenshot_intake.py",
                          "Phase 79 截圖自動 OCR + sync")

    # ⭐ Phase 78 (5/18 凌晨 03:15) — 最終共識卡（整合內部+4 AI、最後跑）
    # 必須最後！等所有 cache 寫入後再整合
    結果["最終共識"] = 跑("push_unified_consensus.py",
                          "Phase 78 最終共識（內部+4 AI 整合、LINE+Gmail）")

    # ⭐ Phase 37 (5/16) — 5 張主卡整合替代 30+ 舊卡
    # 一張 carousel 含 5 個 bubble：今日行動 / 持股&大盤 / 訊號&機會 / Sylvie&KOL / 美股&新聞
    # 每張帶 LIFF 按鈕展開細節（Phase 2b 完成 view 切換）
    結果["5張主卡"] = 跑("push_5cards.py",
                          "Phase 37 5 張主卡（取代舊 30+ 卡）")
    # 舊邏輯保留註解，待 user 確認新版穩定後刪除：
    # 結果["今日行動"] = 跑("push_今日行動.py", ...)
    # 結果["全息儀表板"] = 跑("push_holistic.py", ...)
    # 結果["即時決策"] = 跑("instant_decision.py", ...)
    # 結果["跨來源共識"] = 跑("push_社群共識.py", ...)

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
