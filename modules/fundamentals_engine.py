"""
基本面引擎（Phase 23）— yfinance 抓 PE/ROE/EPS

對標 ARK 大俠：他們不是只看技術，也看基本面。

抓的維度：
  - trailingPE      本益比
  - forwardPE       預估本益比
  - returnOnEquity  ROE
  - trailingEps     每股盈餘
  - revenueGrowth   營收成長率
  - dividendYield   殖利率
  - marketCap       市值

評分（0-100）：
  基本面分數 = ROE(30) + EPS成長(25) + 估值合理(20) + 殖利率(15) + 規模(10)

整合到 strategy_pool：新策略「基本面健康」
資料快取在 數據/基本面/{symbol}.json（每月更新一次）
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf


專案根 = Path(__file__).resolve().parent.parent.parent
快取目錄 = 專案根 / "數據" / "基本面"


def 抓基本面(symbol: str, 強制重抓: bool = False) -> Optional[dict]:
    """
    yfinance 抓基本面資料。
    台股要加 .TW，美股直接代號。
    """
    快取目錄.mkdir(parents=True, exist_ok=True)
    cache_path = 快取目錄 / f"{symbol}.json"

    # 快取 30 天
    if cache_path.exists() and not 強制重抓:
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data["_cached_at"])
            if datetime.now() - cached_at < timedelta(days=30):
                return data
        except Exception:
            pass

    try:
        t = yf.Ticker(symbol)
        info = t.info
        if not info:
            return None
    except Exception as e:
        return None

    rec = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or "",
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "returnOnEquity": info.get("returnOnEquity"),
        "trailingEps": info.get("trailingEps"),
        "forwardEps": info.get("forwardEps"),
        "revenueGrowth": info.get("revenueGrowth"),
        "earningsGrowth": info.get("earningsGrowth"),
        "dividendYield": info.get("dividendYield"),
        "marketCap": info.get("marketCap"),
        "priceToBook": info.get("priceToBook"),
        "profitMargins": info.get("profitMargins"),
        "_cached_at": datetime.now().isoformat(timespec="seconds"),
    }

    cache_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return rec


def 算基本面分數(基本面: dict) -> dict:
    """
    回傳：
      {
        "總分": 0-100,
        "ROE_分": ..., "EPS成長_分": ..., "估值_分": ...,
        "理由": [...]
      }
    """
    if not 基本面:
        return {"總分": None, "理由": ["無資料"]}

    分 = 0
    理由 = []

    # ROE（30 分）
    roe = 基本面.get("returnOnEquity")
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct >= 20:
            分 += 30
            理由.append(f"ROE {roe_pct:.1f}% 優秀 +30")
        elif roe_pct >= 15:
            分 += 24
            理由.append(f"ROE {roe_pct:.1f}% 良好 +24")
        elif roe_pct >= 10:
            分 += 18
            理由.append(f"ROE {roe_pct:.1f}% 中等 +18")
        elif roe_pct >= 5:
            分 += 10
            理由.append(f"ROE {roe_pct:.1f}% 偏低 +10")
        else:
            理由.append(f"ROE {roe_pct:.1f}% 差 +0")

    # 盈餘成長（25 分）
    eg = 基本面.get("earningsGrowth")
    if eg is not None:
        eg_pct = eg * 100
        if eg_pct >= 50:
            分 += 25
            理由.append(f"EPS 成長 {eg_pct:.0f}% 爆發 +25")
        elif eg_pct >= 25:
            分 += 20
            理由.append(f"EPS 成長 {eg_pct:.0f}% 強勁 +20")
        elif eg_pct >= 10:
            分 += 13
            理由.append(f"EPS 成長 {eg_pct:.0f}% +13")
        elif eg_pct >= 0:
            分 += 5
            理由.append(f"EPS 成長 {eg_pct:.0f}% 平穩 +5")
        else:
            理由.append(f"EPS 成長 {eg_pct:.0f}% 衰退 +0")

    # 估值合理性（20 分）— PE 越低分越高（不算過低）
    pe = 基本面.get("trailingPE") or 基本面.get("forwardPE")
    if pe is not None and pe > 0:
        if 8 <= pe <= 15:
            分 += 20
            理由.append(f"PE {pe:.1f} 合理 +20")
        elif 15 < pe <= 25:
            分 += 15
            理由.append(f"PE {pe:.1f} 偏高 +15")
        elif 25 < pe <= 40:
            分 += 8
            理由.append(f"PE {pe:.1f} 高 +8")
        elif pe > 40:
            分 += 0
            理由.append(f"PE {pe:.1f} 過高 +0")
        else:
            分 += 10
            理由.append(f"PE {pe:.1f} 低 +10")

    # 殖利率（15 分）
    dy = 基本面.get("dividendYield")
    if dy is not None:
        dy_pct = dy * 100 if dy < 1 else dy  # yfinance 有時是小數
        if dy_pct >= 5:
            分 += 15
            理由.append(f"殖利率 {dy_pct:.1f}% 優 +15")
        elif dy_pct >= 3:
            分 += 12
            理由.append(f"殖利率 {dy_pct:.1f}% 良 +12")
        elif dy_pct >= 1:
            分 += 6
            理由.append(f"殖利率 {dy_pct:.1f}% +6")

    # 市值（10 分 — 規模溢價）
    mc = 基本面.get("marketCap")
    if mc is not None:
        if mc >= 1_000_000_000_000:  # > 1 兆 (台幣或美元)
            分 += 10
            理由.append(f"大市值 +10")
        elif mc >= 100_000_000_000:
            分 += 6
            理由.append(f"中大市值 +6")
        elif mc >= 10_000_000_000:
            分 += 3
            理由.append(f"中型 +3")

    return {
        "總分": round(分, 1),
        "理由": 理由,
        "細項": {
            "ROE": 基本面.get("returnOnEquity"),
            "EPS_成長": 基本面.get("earningsGrowth"),
            "PE": pe,
            "殖利率": 基本面.get("dividendYield"),
            "市值": 基本面.get("marketCap"),
        },
    }


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys, time
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 23 基本面引擎測試 ===\n")
    標的 = [
        ("2330.TW", "台積電"), ("2317.TW", "鴻海"), ("2382.TW", "廣達"),
        ("2327.TW", "國巨"), ("2492.TW", "華新科"),
        ("NVDA", "輝達"), ("AVGO", "Broadcom"), ("MU", "Micron"),
        ("AMD", "AMD"), ("META", "Meta"),
    ]
    for sym, name in 標的:
        try:
            r = 抓基本面(sym)
            if r:
                s = 算基本面分數(r)
                pe = (r.get("trailingPE") or 0)
                roe = (r.get("returnOnEquity") or 0) * 100
                eg = (r.get("earningsGrowth") or 0) * 100
                dy = (r.get("dividendYield") or 0)
                if dy < 1:
                    dy = dy * 100
                print(f"  {sym:<10} {name:<8} 分數 {s['總分']:>5} "
                      f"PE={pe:>5.1f} ROE={roe:>4.1f}% "
                      f"EPS成長={eg:>+5.1f}% 殖利={dy:>4.1f}%")
            else:
                print(f"  {sym:<10} {name:<8} 無資料")
        except Exception as e:
            print(f"  {sym:<10} ERR: {e}")
        time.sleep(0.5)
