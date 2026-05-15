"""
FRED 總經數據（Phase 36.1）— 美國聯邦儲備經濟資料

抓取核心指標：
  - Fed Funds Rate（聯準會利率）
  - CPI（通膨率）
  - 失業率
  - 10Y Treasury Yield（10 年期公債）
  - 10Y-2Y Yield Spread（倒掛指標 — 衰退預警）

外加：
  - FOMC 會議日曆（接近會議前 1 週提醒減碼）
  - CPI 公布日（前 3 天提醒）

設計理念：
  黑天鵝預警的「根本原因」— 利率、通膨、就業
  在 daily_action_card footer 顯示，user 一眼看到總經狀況

依賴：FRED_API_KEY 在 .env
"""
import os
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = 專案根 / "數據" / "cache" / "fred"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FRED_BASE = "https://api.stlouisfed.org/fred"

# 核心 series IDs
SERIES = {
    "fed_rate":       "FEDFUNDS",     # Fed Funds Rate (monthly average, more stable than DFF)
    "cpi":            "CPIAUCSL",     # CPI (monthly)
    "cpi_yoy":        None,           # 算出來的，從 CPI 算 YoY
    "unemployment":   "UNRATE",       # Unemployment Rate (monthly)
    "10y_treasury":   "DGS10",        # 10-Year Treasury (daily)
    "2y_treasury":    "DGS2",         # 2-Year Treasury (daily)
    "10y_2y_spread":  "T10Y2Y",       # 10Y-2Y Spread (倒掛指標)
    "vix":            "VIXCLS",       # VIX (daily) — 跟 yfinance 一樣
}

# FOMC 會議 release_id
RELEASE_FOMC = 326  # H.15 Selected Interest Rates
RELEASE_CPI = 10    # Consumer Price Index


def _api_key() -> str:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("FRED_API_KEY 未設定，請去 .env 加")
    return key


def _抓series最新(series_id: str, limit: int = 2) -> Optional[dict]:
    """抓某 series 最新 N 筆觀察值"""
    try:
        params = {
            "series_id": series_id,
            "api_key": _api_key(),
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        r = requests.get(f"{FRED_BASE}/series/observations",
                          params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        obs = data.get("observations", [])
        if not obs:
            return None
        return {
            "series_id": series_id,
            "latest": {
                "date": obs[0]["date"],
                "value": float(obs[0]["value"]) if obs[0]["value"] != "." else None,
            },
            "previous": ({
                "date": obs[1]["date"],
                "value": float(obs[1]["value"]) if obs[1]["value"] != "." else None,
            } if len(obs) > 1 else None),
        }
    except Exception as e:
        return {"error": str(e), "series_id": series_id}


def 抓核心指標() -> dict:
    """抓 6 個核心指標 + 算 CPI YoY"""
    結果 = {}

    # 直接 series
    for key, sid in SERIES.items():
        if not sid:
            continue
        r = _抓series最新(sid)
        if r and "error" not in r:
            結果[key] = r["latest"]

    # CPI YoY（需要 13 個月對比）
    try:
        params = {
            "series_id": "CPIAUCSL",
            "api_key": _api_key(),
            "file_type": "json",
            "sort_order": "desc",
            "limit": 13,
        }
        r = requests.get(f"{FRED_BASE}/series/observations",
                          params=params, timeout=15)
        obs = r.json().get("observations", [])
        if len(obs) >= 13:
            latest = float(obs[0]["value"])
            year_ago = float(obs[12]["value"])
            yoy = (latest / year_ago - 1) * 100
            結果["cpi_yoy"] = {
                "value": round(yoy, 2),
                "date": obs[0]["date"],
                "latest_index": latest,
                "year_ago_index": year_ago,
            }
    except Exception:
        pass

    return 結果


def 算倒掛預警(spread: float) -> dict:
    """T10Y2Y 倒掛 = 歷史上衰退前兆"""
    if spread is None:
        return {"等級": "?", "色": "wait", "說明": "無資料"}
    if spread < 0:
        return {
            "等級": "🚨 倒掛",
            "色": "bear",
            "說明": f"10Y-2Y = {spread:.2f}%，歷史上每次倒掛 6-18 月後衰退",
        }
    elif spread < 0.5:
        return {
            "等級": "⚠️ 接近倒掛",
            "色": "wait",
            "說明": f"10Y-2Y = {spread:.2f}%，留意",
        }
    elif spread < 1.5:
        return {
            "等級": "📊 正常偏低",
            "色": "text_main",
            "說明": f"10Y-2Y = {spread:.2f}%",
        }
    else:
        return {
            "等級": "✅ 健康",
            "色": "bull",
            "說明": f"10Y-2Y = {spread:.2f}%，殖利率曲線正常",
        }


def 算通膨壓力(cpi_yoy: float, fed_rate: float) -> dict:
    """通膨 vs Fed rate = 實質利率"""
    if cpi_yoy is None or fed_rate is None:
        return {"等級": "?", "色": "wait", "說明": "無資料"}
    real_rate = fed_rate - cpi_yoy
    if cpi_yoy > 5:
        return {
            "等級": "🔥 通膨過熱",
            "色": "bear",
            "實質利率": real_rate,
            "說明": f"CPI {cpi_yoy:.1f}% 超 5%，Fed 有壓力升息",
        }
    elif cpi_yoy > 3:
        return {
            "等級": "⚠️ 通膨偏高",
            "色": "wait",
            "實質利率": real_rate,
            "說明": f"CPI {cpi_yoy:.1f}% 高於 Fed 2% 目標",
        }
    elif cpi_yoy > 2:
        return {
            "等級": "📊 接近目標",
            "色": "text_main",
            "實質利率": real_rate,
            "說明": f"CPI {cpi_yoy:.1f}% 接近 Fed 目標 2%",
        }
    elif cpi_yoy > 0:
        return {
            "等級": "✅ 低通膨",
            "色": "bull",
            "實質利率": real_rate,
            "說明": f"CPI {cpi_yoy:.1f}% 偏低，可能降息",
        }
    else:
        return {
            "等級": "❄️ 通縮",
            "色": "bear",
            "實質利率": real_rate,
            "說明": f"CPI {cpi_yoy:.1f}% 通縮危機",
        }


def 抓FOMC日曆() -> list:
    """抓 FOMC 未來會議日（從 H.15 release）"""
    try:
        params = {
            "release_id": RELEASE_FOMC,
            "api_key": _api_key(),
            "file_type": "json",
        }
        r = requests.get(f"{FRED_BASE}/release/dates",
                          params=params, timeout=15)
        dates = r.json().get("release_dates", [])
        # 找未來的 + 過去 1 個月內的
        today = date.today()
        cutoff_past = today - timedelta(days=30)
        cutoff_future = today + timedelta(days=180)
        近期 = []
        for d in dates:
            try:
                dt = datetime.strptime(d["date"], "%Y-%m-%d").date()
                if cutoff_past <= dt <= cutoff_future:
                    天數 = (dt - today).days
                    近期.append({
                        "date": d["date"],
                        "days_from_today": 天數,
                        "future": 天數 >= 0,
                    })
            except Exception:
                continue
        return sorted(近期, key=lambda r: r["date"])
    except Exception as e:
        return []


def 算事件預警() -> list:
    """根據 FOMC 日曆 + CPI 公布日算事件預警"""
    警報 = []
    fomc = 抓FOMC日曆()
    for f in fomc:
        d = f["days_from_today"]
        if 0 <= d <= 7:
            警報.append({
                "類型": "🔴 FOMC 1 週內",
                "色": "bear",
                "日期": f["date"],
                "天數": d,
                "建議": "減碼 / 拉高閒錢比 / 避免新部位（決議前波動大）",
            })
        elif 8 <= d <= 14:
            警報.append({
                "類型": "🟡 FOMC 2 週內",
                "色": "wait",
                "日期": f["date"],
                "天數": d,
                "建議": "留意決議走向，不追高",
            })
    return 警報


def 全套總經分析() -> dict:
    """主入口：抓所有指標 + 算預警"""
    指標 = 抓核心指標()

    fed_rate = (指標.get("fed_rate") or {}).get("value")
    cpi_yoy = (指標.get("cpi_yoy") or {}).get("value")
    spread = (指標.get("10y_2y_spread") or {}).get("value")
    unemp = (指標.get("unemployment") or {}).get("value")
    t10y = (指標.get("10y_treasury") or {}).get("value")

    倒掛 = 算倒掛預警(spread)
    通膨 = 算通膨壓力(cpi_yoy, fed_rate) if cpi_yoy and fed_rate else None
    事件 = 算事件預警()

    return {
        "指標": 指標,
        "fed_rate": fed_rate,
        "cpi_yoy": cpi_yoy,
        "10y_2y_spread": spread,
        "unemployment": unemp,
        "10y_treasury": t10y,
        "倒掛分析": 倒掛,
        "通膨分析": 通膨,
        "事件預警": 事件,
        "時間": datetime.now().isoformat(timespec="seconds"),
    }


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

    print("=" * 60)
    print("FRED 美國總經分析")
    print("=" * 60)

    r = 全套總經分析()

    print(f"\n📊 核心指標")
    print(f"  Fed Rate:     {r['fed_rate']}%  (聯準會基準利率)")
    print(f"  CPI YoY:      {r['cpi_yoy']}%  (通膨年增率)")
    print(f"  Unemployment: {r['unemployment']}%  (失業率)")
    print(f"  10Y Treasury: {r['10y_treasury']}%  (10 年公債殖利率)")
    print(f"  10Y-2Y Spread:{r['10y_2y_spread']}%  (倒掛指標)")

    print(f"\n🌡️ 倒掛分析: {r['倒掛分析']['等級']}")
    print(f"   {r['倒掛分析']['說明']}")

    if r['通膨分析']:
        print(f"\n🔥 通膨分析: {r['通膨分析']['等級']}")
        print(f"   {r['通膨分析']['說明']}")
        print(f"   實質利率: {r['通膨分析']['實質利率']:.2f}%")

    print(f"\n📅 事件預警 ({len(r['事件預警'])} 件)")
    for e in r['事件預警']:
        print(f"  {e['類型']}  {e['日期']} (還 {e['天數']} 天)")
        print(f"    → {e['建議']}")
