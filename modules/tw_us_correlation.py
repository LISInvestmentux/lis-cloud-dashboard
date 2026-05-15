"""
台美連動分析（Phase 25.5）— 對標 AI 供應鏈傳導

關鍵觀察：
  美股 NVDA 漲 → 隔天台積電 2330 漲（AI 訂單傳導）
  美股 SMH 跌 → 隔天 00911 跌（半導體 ETF 連動）

本模組：
  1. 抓昨夜美股表現
  2. 用歷史相關性找台股對應
  3. 預測今日台股可能走勢

供應鏈對照表（AI 主軸）：
  NVDA      → 台積電 2330 / 鴻海 2317 / 廣達 2382 / 緯穎 6669
  AVGO      → 台積電 2330 / 創意 3443
  AMD       → 台積電 2330 / 矽力 6415
  MU        → 南亞科 2408 / 華邦電 2344
  TSM       → 台積電 2330（直接）
  META      → 鴻海 2317（伺服器）
  GOOGL     → 廣達 2382 / 廣達 2382
  SMH       → 00911 / 00935 (ETF 鏡像)
  QQQ       → 00662 (NASDAQ ETF)
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


# AI 供應鏈傳導對照
傳導表 = {
    "NVDA": [("2330.TW", "台積電", "晶圓代工"),
             ("2317.TW", "鴻海", "AI 伺服器"),
             ("2382.TW", "廣達", "AI 伺服器"),
             ("6669.TW", "緯穎", "純 AI"),
             ("00911.TW", "兆豐洲際半導體", "ETF")],
    "AVGO": [("2330.TW", "台積電", "晶圓代工"),
             ("3443.TW", "創意", "ASIC"),
             ("00911.TW", "兆豐洲際半導體", "ETF")],
    "AMD":  [("2330.TW", "台積電", "晶圓代工"),
             ("00911.TW", "兆豐洲際半導體", "ETF")],
    "MU":   [("2408.TW", "南亞科", "DRAM"),
             ("2344.TW", "華邦電", "成熟記憶體")],
    "TSM":  [("2330.TW", "台積電", "ADR 直連")],
    "META": [("2317.TW", "鴻海", "AI 伺服器"),
             ("2382.TW", "廣達", "AI 伺服器")],
    "GOOGL": [("2382.TW", "廣達", "AI 伺服器")],
    "SMH":  [("00911.TW", "兆豐洲際半導體", "鏡像 ETF"),
             ("00935.TW", "野村新科技 50", "半導體")],
    "QQQ":  [("00662.TW", "富邦NASDAQ", "鏡像 ETF")],
}


def 抓昨夜美股表現() -> dict:
    """從 win_rate_db 或即時抓"""
    from . import technical

    結果 = {}
    for 美股, _ in 傳導表.items():
        try:
            歷史, _ = technical.取得每日股價(美股, period="5d")
            if 歷史 and len(歷史) >= 2:
                今 = 歷史[0]["close"]
                昨 = 歷史[1]["close"]
                漲幅 = (今 / 昨 - 1) * 100
                結果[美股] = {
                    "close": 今,
                    "prev": 昨,
                    "漲幅_pct": round(漲幅, 2),
                    "強度": ("🔥強漲" if 漲幅 >= 3 else
                              "📈漲" if 漲幅 >= 1 else
                              "🟡盤整" if -1 <= 漲幅 <= 1 else
                              "📉跌" if 漲幅 > -3 else
                              "💀大跌"),
                }
        except Exception:
            pass
    return 結果


def 台股傳導預測() -> dict:
    """
    回傳台股受美股影響的預測。
    {
      美股: {漲跌, 強度, 影響的台股: [...]}
    }
    """
    美股表現 = 抓昨夜美股表現()
    傳導預測 = {}

    for 美股, perf in 美股表現.items():
        台股對應 = 傳導表.get(美股, [])
        傳導預測[美股] = {
            **perf,
            "影響的台股": [
                {"symbol": s, "name": n, "關係": r}
                for s, n, r in 台股對應
            ],
        }

    # 整體傾向
    平均漲幅 = (sum(p["漲幅_pct"] for p in 美股表現.values())
                / len(美股表現) if 美股表現 else 0)
    if 平均漲幅 >= 2:
        傾向 = "🔥 美股大漲 → 台股 AI 鏈早盤偏多"
    elif 平均漲幅 >= 0.5:
        傾向 = "📈 美股偏多 → 台股 AI 鏈正向"
    elif 平均漲幅 <= -2:
        傾向 = "💀 美股大跌 → 台股 AI 鏈早盤偏空"
    elif 平均漲幅 <= -0.5:
        傾向 = "📉 美股偏空 → 台股 AI 鏈承壓"
    else:
        傾向 = "🟡 美股盤整 → 台股自走"

    # 找最強傳導訊號
    最強漲 = max(美股表現.items(),
                key=lambda x: x[1]["漲幅_pct"], default=None)
    最強跌 = min(美股表現.items(),
                key=lambda x: x[1]["漲幅_pct"], default=None)

    return {
        "美股表現": 美股表現,
        "傳導預測": 傳導預測,
        "平均漲幅_pct": round(平均漲幅, 2),
        "整體傾向": 傾向,
        "最強上漲": 最強漲[0] if 最強漲 else None,
        "最強下跌": 最強跌[0] if 最強跌 else None,
    }


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 25.5 台美連動分析 ===\n")
    r = 台股傳導預測()

    print(f"🌙 昨夜美股 ({len(r['美股表現'])} 檔)")
    for sym, p in sorted(r["美股表現"].items(),
                         key=lambda x: -x[1]["漲幅_pct"]):
        print(f"  {sym:<6} {p['close']:>8.2f} {p['漲幅_pct']:>+6.2f}% {p['強度']}")

    print(f"\n📊 整體傾向：{r['整體傾向']}")
    print(f"   平均漲幅：{r['平均漲幅_pct']:+.2f}%")

    print(f"\n🔥 最強傳導（{r['最強上漲']} 漲）→ 影響台股：")
    if r['最強上漲']:
        for ts in r["傳導預測"][r['最強上漲']]["影響的台股"]:
            print(f"  {ts['symbol']:<10} {ts['name']:<12} 關係：{ts['關係']}")

    print(f"\n💀 最強跌幅（{r['最強下跌']} 跌）→ 警告台股：")
    if r['最強下跌']:
        for ts in r["傳導預測"][r['最強下跌']]["影響的台股"]:
            print(f"  {ts['symbol']:<10} {ts['name']:<12} 關係：{ts['關係']}")
