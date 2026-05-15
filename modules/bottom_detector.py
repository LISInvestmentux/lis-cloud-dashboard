"""
市場底部判斷 SOP 模型（Phase 32）— 整合 Sylvie 太太 ARK 系統的 5 大指標

這是 LIS 之前最大盲點：「黑天鵝什麼時候真的來」沒有客觀判定。
Sylvie 系統用 5 個獨立訊號交叉確認，5 次重大崩盤都抓到底部。

5 大指標（歷史驗證）：
  1. VIX 恐慌指數：飆升至 40+ 並見頂回落
  2. Put/Call 比率：飆破 1.2-1.5 區間
  3. 台股融資餘額：較高峰減 30-40% 以上
  4. 外資期貨未平倉：轉為淨空單且負值破萬口
  5. 技術與輔助訊號：長下影 K、成交量萎縮、技術指標背離

歷史底部案例（5 次 100% 命中）：
  2008 金融海嘯：VIX 80.9、Put/Call 1.5、融資 -70%
  2015 中國股災：VIX 40.7、Put/Call 1.2、融資 -38%、外資淨空
  2018 貿易戰：VIX 37.3、Put/Call 1.1、融資 -33%
  2020 疫情崩盤：VIX 82.7、Put/Call 1.28、融資 -36.8%、淨空 2 萬+
  2022 通膨熊市：VIX 36.5、Put/Call 1.4、融資 -43%、淨空 1.5 萬

底部命中規則：
  5 指標命中 4+ = 🚨 確認底部（重押訊號）
  5 指標命中 3 = ⚠️ 接近底部（試單）
  5 指標命中 2 = 🟡 警戒區
  5 指標命中 <2 = ⚪ 正常市場

整合：當底部訊號 ≥3 → position_sizer 倍率 ×3-5
"""
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快取目錄 = 專案根 / "數據" / "底部偵測"


# 歷史底部案例（給用戶參考）
歷史底部 = [
    {"年份": 2008, "事件": "金融海嘯",
     "VIX": 80.9, "PutCall": 1.6, "融資降幅_pct": 70,
     "外資淨空_口": None, "結果": "後續見底反彈"},
    {"年份": 2015, "事件": "中國股災",
     "VIX": 40.7, "PutCall": 1.2, "融資降幅_pct": 38,
     "外資淨空_口": 5000, "結果": "落底時間吻合"},
    {"年份": 2018, "事件": "貿易戰",
     "VIX": 37.3, "PutCall": 1.2, "融資降幅_pct": 33,
     "外資淨空_口": None, "結果": "熊市邊緣回升"},
    {"年份": 2020, "事件": "疫情崩盤",
     "VIX": 82.7, "PutCall": 1.28, "融資降幅_pct": 36.8,
     "外資淨空_口": 20000, "結果": "十天後見底，V 型反彈"},
    {"年份": 2022, "事件": "通膨熊市",
     "VIX": 36.5, "PutCall": 1.45, "融資降幅_pct": 43,
     "外資淨空_口": 15000, "結果": "年底轉淨多後強勢反彈"},
    {"年份": 2025, "事件": "川普關稅風暴",
     "VIX": None, "PutCall": None, "融資降幅_pct": None,
     "兩日融資減": 420, "外資淨空_口": None,
     "結果": "歷史單日爆量斷頭"},
]


# ─────────────────────────────────────────────
# 指標抓取
# ─────────────────────────────────────────────
def 抓VIX() -> Optional[float]:
    """從 yfinance 抓即時 VIX"""
    try:
        from . import technical
        歷史, _ = technical.取得每日股價("^VIX", period="5d")
        if 歷史:
            return float(歷史[0]["close"])
    except Exception:
        pass
    return None


def _抓url(url: str, timeout: int = 15) -> Optional[str]:
    """共用 fetch 函式"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def 抓融資餘額_TWSE() -> Optional[dict]:
    """抓台股融資餘額（TWSE）。Phase 32.2 修正解析"""
    url = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?selectType=MS&response=json"
    body = _抓url(url)
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None

    # 找「融資金額(仟元)」這列（不是「融資(交易單位)」）
    今日餘額 = None
    昨日餘額 = None
    for t in data.get("tables", []):
        for row in t.get("data", []):
            if not row or len(row) < 6:
                continue
            label = str(row[0])
            if "融資金額" in label and "仟元" in label:
                # 欄位：[標籤, 買進, 賣出, 現金償還, 前日餘額, 今日餘額]
                try:
                    昨日餘額 = int(row[4].replace(",", ""))
                    今日餘額 = int(row[5].replace(",", ""))
                except Exception:
                    pass
                break

    return {
        "今日_千元": 今日餘額,
        "昨日_千元": 昨日餘額,
        "_說明": "TWSE 融資金額（仟元）",
    }


def 抓外資期貨淨空() -> Optional[dict]:
    """
    Phase 32.4：改用 TAIFEX OpenAPI 抓 外資及陸資 在臺股期貨的 OI 淨額。
    淨空 = 負值的絕對值（外資 net short）。
    舊版 HTML regex 不穩，新版 JSON 直接打 endpoint。
    """
    url = ("https://openapi.taifex.com.tw/v1/"
           "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate")
    body = _抓url(url)
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    for d in data:
        if d.get("ContractCode") == "臺股期貨" and "外資" in str(d.get("Item", "")):
            try:
                oi_net = int(str(d.get("OpenInterest(Net)", "0")).replace(",", ""))
                return {
                    "日期": d.get("Date"),
                    "外資淨額_口": oi_net,
                    "外資淨空_口": abs(oi_net) if oi_net < 0 else 0,
                    "_說明": "TAIFEX OpenAPI 臺股期貨外資 OI 淨額（負=淨空）",
                }
            except Exception:
                pass
    return None


def 算融資峰值降幅(今日餘_千元: int) -> Optional[dict]:
    """
    Phase 32.3：從快取讀過去 30 天的融資餘額，算今日 vs 峰值降幅。
    Sylvie 5 指標的「融資餘額」要的是「相對峰值 30-40% 以上的降幅」。

    回傳 {峰值_千元, 降幅_pct, 樣本數}；樣本不足 5 天回 None。
    """
    if not 快取目錄.exists():
        return None
    cutoff = datetime.now() - timedelta(days=30)
    歷史餘額 = [今日餘_千元]  # 含今日（還沒寫進 cache）
    for f in 快取目錄.glob("*.json"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d")
            if day < cutoff:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            融 = (d.get("原始資料") or {}).get("融資") or {}
            餘 = 融.get("今日_千元")
            if 餘 and 餘 != 今日餘_千元:  # 避免今日重複
                歷史餘額.append(餘)
        except Exception:
            continue
    if len(歷史餘額) < 5:
        return None
    峰值 = max(歷史餘額)
    if 峰值 <= 0:
        return None
    return {
        "峰值_千元": 峰值,
        "降幅_pct": round((1 - 今日餘_千元 / 峰值) * 100, 2),
        "樣本數": len(歷史餘額),
    }


def 算PutCall偏離(今日_vol_PC: float) -> Optional[dict]:
    """
    Phase 32.5 智慧版：從 cache 讀過去 30 天的 Put/Call Volume，算今日 vs 中位偏離%。
    比絕對 threshold (1.15/1.3) 更穩 — 自適應市場結構。

    回傳 {中位, 偏離_pct, 樣本數}；樣本不足 10 天回 None。
    """
    if not 快取目錄.exists():
        return None
    cutoff = datetime.now() - timedelta(days=30)
    歷史 = [今日_vol_PC]
    for f in 快取目錄.glob("*.json"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d")
            if day < cutoff:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            pc = (d.get("原始資料") or {}).get("PutCall") or {}
            v = pc.get("Put_Call_Volume")
            if v and v != 今日_vol_PC:
                歷史.append(float(v))
        except Exception:
            continue
    if len(歷史) < 10:
        return None
    歷史.sort()
    中位 = 歷史[len(歷史) // 2]
    if 中位 <= 0:
        return None
    return {
        "中位": round(中位, 2),
        "偏離_pct": round((今日_vol_PC - 中位) / 中位 * 100, 1),
        "樣本數": len(歷史),
    }


def 算外資期貨偏離(今日淨空_口: int) -> Optional[dict]:
    """
    Phase 32.4 智慧版：從 cache 讀過去 60 天的外資淨空，算今日 vs 中位數偏離%。
    台灣外資結構性淨空 30-50K 是常態（不是訊號），需要看「相對偏離」才能抓到真實壓力。

    回傳 {中位_口, 偏離_pct, 樣本數}；樣本不足 10 天回 None（觸發 fallback 絕對 threshold）。
    """
    if not 快取目錄.exists():
        return None
    cutoff = datetime.now() - timedelta(days=60)
    歷史 = [今日淨空_口]
    for f in 快取目錄.glob("*.json"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d")
            if day < cutoff:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            外 = (d.get("原始資料") or {}).get("外資期貨") or {}
            x = 外.get("外資淨空_口")
            if x is not None and x != 今日淨空_口:
                歷史.append(x)
        except Exception:
            continue
    if len(歷史) < 10:
        return None
    歷史.sort()
    中位 = 歷史[len(歷史) // 2]
    if 中位 <= 0:
        return None  # 沒有真實「淨空」基線時不算偏離
    return {
        "中位_口": 中位,
        "偏離_pct": round((今日淨空_口 - 中位) / 中位 * 100, 1),
        "樣本數": len(歷史),
    }


def 計算技術背離(symbol: str = "^TWII") -> dict:
    """
    Phase 32.3：技術背離判定。
    定義（簡化版）：
      - 量縮：今日量 < 近 5 日均量 × 0.7
      - 長下影：(min(O,C) - L) / |C - O| > 2  → 殺尾被買回
    兩者同時成立 = 背離（盤中曾跌深但收回，量縮代表賣壓衰竭）

    回傳：{背離: bool, 量比, 下影比, 說明}
    """
    try:
        from . import technical
        歷史, _ = technical.取得每日股價(symbol, period="20d")
        if len(歷史) < 6:
            return {"背離": False, "說明": "歷史 K 線不足"}
        最新 = 歷史[0]
        近5日 = 歷史[1:6]

        # 量比（^TWII 在 yfinance 的 volume 經常為 0，fallback 到 0050.TW）
        今日量 = 最新.get("volume", 0) or 0
        近5均量 = sum((d.get("volume", 0) or 0) for d in 近5日) / 5
        量來源 = symbol
        if 今日量 == 0 or 近5均量 == 0:
            try:
                proxy歷史, _ = technical.取得每日股價("0050.TW", period="10d")
                if len(proxy歷史) >= 6:
                    今日量 = proxy歷史[0].get("volume", 0) or 0
                    近5均量 = sum((d.get("volume", 0) or 0) for d in proxy歷史[1:6]) / 5
                    量來源 = "0050.TW(proxy)"
            except Exception:
                pass
        量比 = round(今日量 / 近5均量, 2) if 近5均量 > 0 else 1.0
        量縮 = 量比 < 0.7

        # 下影比
        o = 最新.get("open", 0)
        c = 最新.get("close", 0)
        l = 最新.get("low", 0)
        實體 = abs(c - o)
        if 實體 <= 0.01:
            return {"背離": False, "量比": 量比, "下影比": 0,
                    "說明": "實體過小，無法判定"}
        下影 = min(o, c) - l
        下影比 = round(下影 / 實體, 2)
        長下影 = 下影比 > 2.0

        背離 = bool(量縮 and 長下影)
        說明 = (f"量比 {量比}（{'縮' if 量縮 else '正常'}, 源={量來源}）、"
                 f"下影/實體 {下影比}x（{'長' if 長下影 else '正常'}）")
        return {"背離": 背離, "量比": 量比, "下影比": 下影比,
                "量來源": 量來源, "說明": 說明}
    except Exception as e:
        return {"背離": False, "說明": f"計算失敗: {e}"}


def 計算技術背離_多ETF() -> dict:
    """
    Phase 32.5：多 ETF 投票版技術背離。
    觀察 0050.TW (台股 50)、0056.TW (高股息)、2330.TW (龍頭)
    每檔獨立算量縮+長下影，2/3+ 同意才算背離（避免單檔誤判）。

    回傳：{背離, 投票, 細節[], 說明}
    """
    symbols = [
        ("0050.TW", "台 50 ETF"),
        ("0056.TW", "高股息"),
        ("2330.TW", "台積電"),
    ]
    細節 = []
    背離數 = 0
    for sym, label in symbols:
        r = 計算技術背離(sym)
        細節.append({
            "symbol": sym,
            "label": label,
            "背離": r.get("背離", False),
            "量比": r.get("量比"),
            "下影比": r.get("下影比"),
        })
        if r.get("背離"):
            背離數 += 1
    背離 = 背離數 >= 2  # 2/3 投票通過
    說明 = f"多 ETF 投票 {背離數}/{len(symbols)} 背離"
    return {"背離": 背離, "投票": f"{背離數}/{len(symbols)}",
            "細節": 細節, "說明": 說明}


def 抓PutCall比率() -> Optional[dict]:
    """
    台指選擇權 Put/Call 比率（期交所 OpenAPI）
    Phase 32.2 用對的 API
    """
    url = "https://openapi.taifex.com.tw/v1/PutCallRatio"
    body = _抓url(url)
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    # 最新一筆（第 0 個）
    latest = data[0]
    try:
        pc_oi = float(latest.get("PutCallOIRatio%", 0)) / 100  # 169.31 → 1.69
        pc_vol = float(latest.get("PutCallVolumeRatio%", 0)) / 100
        return {
            "Put_Call_OI": round(pc_oi, 2),
            "Put_Call_Volume": round(pc_vol, 2),
            "日期": latest.get("Date"),
            "_說明": "Put/Call 比率（Volume=當日成交比，Sylvie 主指標；OI=累積部位比，台灣結構性偏高 1.5-1.8）",
        }
    except Exception:
        return None


# ─────────────────────────────────────────────
# 主判定
# ─────────────────────────────────────────────
def 底部判定(VIX: Optional[float] = None,
              PutCall: Optional[float] = None,
              PutCall_偏離_pct: Optional[float] = None,
              融資降幅_pct: Optional[float] = None,
              外資淨空_口: Optional[float] = None,
              外資偏離_pct: Optional[float] = None,
              技術背離: bool = False) -> dict:
    """
    輸入 5 大指標，回傳底部命中數 + 建議
    """
    命中 = []
    詳情 = []

    # 1. VIX
    if VIX is not None:
        if VIX >= 40:
            命中.append("VIX_極端")
            詳情.append(f"🚨 VIX {VIX:.1f} 極端（≥40）")
        elif VIX >= 30:
            命中.append("VIX_警戒")
            詳情.append(f"⚠️ VIX {VIX:.1f} 警戒（30-40）")
        else:
            詳情.append(f"⚪ VIX {VIX:.1f} 正常")
    else:
        詳情.append("⚫ VIX 無資料")

    # 2. Put/Call (Phase 32.5 智慧版)
    # 優先用「相對 30 日中位偏離」(自適應市場結構)；
    # 歷史 <10 天時 fallback 用絕對 threshold (1.15/1.3)。
    if PutCall_偏離_pct is not None:
        # 智慧版：偏離率越大代表越悲觀
        if PutCall_偏離_pct >= 30:
            命中.append("PutCall_極端")
            詳情.append(f"🚨 Put/Call {PutCall:.2f} (偏離中位 +{PutCall_偏離_pct:.0f}%)")
        elif PutCall_偏離_pct >= 15:
            命中.append("PutCall_警戒")
            詳情.append(f"⚠️ Put/Call {PutCall:.2f} (偏離中位 +{PutCall_偏離_pct:.0f}%)")
        else:
            詳情.append(f"⚪ Put/Call {PutCall:.2f} (偏離 {PutCall_偏離_pct:+.0f}%)")
    elif PutCall is not None:
        # Fallback：絕對 threshold (1.15/1.3，台灣現況校準)
        if PutCall >= 1.3:
            命中.append("PutCall_極端")
            詳情.append(f"🚨 Put/Call {PutCall:.2f} 極端悲觀（≥1.3）")
        elif PutCall >= 1.15:
            命中.append("PutCall_警戒")
            詳情.append(f"⚠️ Put/Call {PutCall:.2f} 偏空（≥1.15）")
        else:
            詳情.append(f"⚪ Put/Call {PutCall:.2f} 正常")
    else:
        詳情.append("⚫ Put/Call 無資料")

    # 3. 融資餘額降幅
    if 融資降幅_pct is not None:
        if 融資降幅_pct >= 30:
            命中.append("融資_大減")
            詳情.append(f"🚨 融資減 {融資降幅_pct:.0f}% 散戶斷頭")
        elif 融資降幅_pct >= 15:
            命中.append("融資_減少")
            詳情.append(f"⚠️ 融資減 {融資降幅_pct:.0f}% 警戒")
        else:
            詳情.append(f"⚪ 融資減 {融資降幅_pct:.0f}% 正常")
    else:
        詳情.append("⚫ 融資 無資料")

    # 4. 外資期貨淨空（Phase 32.4 智慧版）
    # 優先用「相對 60 天中位偏離」(自適應台灣結構基線變化)；
    # 歷史 <10 天時 fallback 用絕對 threshold (60K/90K)。
    if 外資偏離_pct is not None:
        # 智慧版：相對中位偏離 (越大代表今日空壓越強)
        if 外資偏離_pct >= 100:  # 今日比常態空 2 倍以上
            命中.append("外資淨空_極端")
            詳情.append(f"🚨 外資淨空 {外資淨空_口:,.0f} 口 (偏離中位 +{外資偏離_pct:.0f}%)")
        elif 外資偏離_pct >= 50:  # 1.5 倍空
            命中.append("外資淨空_警戒")
            詳情.append(f"⚠️ 外資淨空 {外資淨空_口:,.0f} 口 (偏離中位 +{外資偏離_pct:.0f}%)")
        else:
            詳情.append(f"⚪ 外資淨空 {外資淨空_口:,.0f} 口 (偏離 {外資偏離_pct:+.0f}%)")
    elif 外資淨空_口 is not None:
        # Fallback：絕對 threshold（歷史 <10 天時用）
        if 外資淨空_口 >= 90000:
            命中.append("外資淨空_極端")
            詳情.append(f"🚨 外資淨空 {外資淨空_口:,.0f} 口 極端空壓")
        elif 外資淨空_口 >= 60000:
            命中.append("外資淨空_警戒")
            詳情.append(f"⚠️ 外資淨空 {外資淨空_口:,.0f} 口 偏空")
        else:
            詳情.append(f"⚪ 外資淨空 {外資淨空_口:,.0f} 口 常態")
    else:
        詳情.append("⚫ 外資淨空 無資料")

    # 5. 技術背離
    if 技術背離:
        命中.append("技術_背離")
        詳情.append("🚨 技術背離（量縮 + 長下影）")
    else:
        詳情.append("⚪ 技術 無背離")

    # 結論
    n = len(命中)
    if n >= 4:
        等級 = "🚨 確認底部"
        建議 = "重押訊號！用避險預備金 ALL IN"
        部位倍率 = 5.0
    elif n >= 3:
        等級 = "⚠️ 接近底部"
        建議 = "試單訊號，分批進場"
        部位倍率 = 3.0
    elif n >= 2:
        等級 = "🟡 警戒區"
        建議 = "提高觀察頻率，準備彈藥"
        部位倍率 = 1.5
    else:
        等級 = "⚪ 正常市場"
        建議 = "繼續紀律執行，無底部訊號"
        部位倍率 = 1.0

    return {
        "命中數": n,
        "命中清單": 命中,
        "詳情": 詳情,
        "等級": 等級,
        "建議": 建議,
        "部位倍率": 部位倍率,
        "資料完整度": sum(1 for d in 詳情 if not d.startswith("⚫")),
        "時間": datetime.now().isoformat(timespec="seconds"),
    }


def 即時底部判定() -> dict:
    """抓即時資料 + 跑判定（Phase 32.2 整合 OpenAPI）"""
    print("🔍 抓 VIX...")
    vix = 抓VIX()
    print(f"   VIX: {vix}")

    print("🔍 抓融資餘額...")
    融 = 抓融資餘額_TWSE()
    融資降幅 = None
    融資峰值資訊 = None
    今日餘 = None
    if 融:
        今日餘 = 融.get("今日_千元")
        昨日餘 = 融.get("昨日_千元")
        if 今日餘:
            # Phase 32.3：算 30 天峰值降幅（Sylvie 指標真正要的）
            融資峰值資訊 = 算融資峰值降幅(今日餘)
            if 融資峰值資訊:
                融資降幅 = 融資峰值資訊["降幅_pct"]
                print(f"   融資餘額: {今日餘/1e6:.1f} 億 "
                      f"(30日峰值 {融資峰值資訊['峰值_千元']/1e6:.1f}億, "
                      f"降幅 {融資降幅:+.1f}%, n={融資峰值資訊['樣本數']})")
            else:
                if 昨日餘:
                    日降幅 = (1 - 今日餘 / 昨日餘) * 100
                    print(f"   融資餘額: {今日餘/1e6:.1f} 億 "
                          f"(日變 {日降幅:+.2f}%；歷史 <5 天，無峰值降幅)")
                else:
                    print(f"   融資餘額: {今日餘/1e6:.1f} 億（首次記錄）")

    print("🔍 抓 Put/Call...")
    pc = 抓PutCall比率()
    pc_val = None
    pc_偏離資訊 = None
    if pc:
        # Phase 32.4：用 Volume P/C（Sylvie 主指標，OI 在台灣結構偏高 1.5-1.8 不準）
        pc_val = pc.get("Put_Call_Volume")
        # Phase 32.5：智慧偏離（10 天 cache 後生效）
        if pc_val:
            pc_偏離資訊 = 算PutCall偏離(pc_val)
        if pc_偏離資訊:
            print(f"   Put/Call Volume: {pc_val} "
                  f"(30 日中位 {pc_偏離資訊['中位']:.2f}, "
                  f"偏離 {pc_偏離資訊['偏離_pct']:+.1f}%, n={pc_偏離資訊['樣本數']})")
        else:
            print(f"   Put/Call Volume: {pc_val} "
                  f"(OI: {pc.get('Put_Call_OI')}; 歷史 <10 天用絕對 threshold)")

    # Phase 32.4：外資期貨 OI 淨空（TAIFEX OpenAPI + 智慧偏離）
    print("🔍 抓外資期貨淨空（臺股期貨 OI）...")
    外資期貨 = 抓外資期貨淨空()
    外資淨空_口 = None
    外資偏離資訊 = None
    if 外資期貨:
        外資淨空_口 = 外資期貨.get("外資淨空_口", 0)
        oi淨額 = 外資期貨.get("外資淨額_口", 0)
        # 智慧版：算 60 天偏離（樣本 <10 天時回 None，會 fallback 到絕對 threshold）
        if 外資淨空_口 > 0:
            外資偏離資訊 = 算外資期貨偏離(外資淨空_口)
        if 外資偏離資訊:
            print(f"   外資 臺股期貨 OI 淨額: {oi淨額:+,} 口 "
                  f"(淨空 {外資淨空_口:,}，60 日中位 {外資偏離資訊['中位_口']:,}，"
                  f"偏離 {外資偏離資訊['偏離_pct']:+.1f}%, n={外資偏離資訊['樣本數']})")
        else:
            print(f"   外資 臺股期貨 OI 淨額: {oi淨額:+,} 口 "
                  f"(淨空 {外資淨空_口:,}，歷史 <10 天用絕對 threshold)")
    else:
        print("   外資期貨抓取失敗")

    # 0050 買賣超：當輔助參考（不參與底部判定）
    print("🔍 抓外資 0050 買賣超（輔助參考）...")
    外資_0050 = None
    try:
        from . import institutional_tracker as it
        from datetime import timedelta as _td
        for i in range(0, 5):
            d = (datetime.now() - _td(days=i)).strftime("%Y%m%d")
            r = it.抓今日法人籌碼(d)
            if r and r.get("資料"):
                d_0050 = r["資料"].get("0050")
                if d_0050:
                    外資_0050 = d_0050.get("外資", 0)
                    print(f"   外資 0050 買賣超: {外資_0050/1000:+.0f} 張")
                    break
    except Exception:
        pass
    外資警示 = (外資_0050 / 1000) if (外資_0050 and 外資_0050 < -15_000_000) else None

    # Phase 32.5：技術背離（多 ETF 投票，2/3+ 同意才算）
    print("🔍 算技術背離（多 ETF 投票）...")
    背離資訊 = 計算技術背離_多ETF()
    print(f"   {背離資訊['說明']} → {'背離' if 背離資訊['背離'] else '無背離'}")
    for d in 背離資訊.get("細節", []):
        flag = "✓" if d["背離"] else " "
        print(f"     [{flag}] {d['label']:<10} 量比 {d['量比']} / 下影 {d['下影比']}x")

    結果 = 底部判定(
        VIX=vix,
        PutCall=pc_val,
        PutCall_偏離_pct=pc_偏離資訊.get("偏離_pct") if pc_偏離資訊 else None,
        融資降幅_pct=融資降幅,
        外資淨空_口=外資淨空_口,
        外資偏離_pct=外資偏離資訊.get("偏離_pct") if 外資偏離資訊 else None,
        技術背離=背離資訊["背離"],
    )
    # 加上原始資料
    結果["原始資料"] = {
        "VIX": vix,
        "PutCall": pc,
        "PutCall_偏離": pc_偏離資訊,
        "融資": 融,
        "融資峰值": 融資峰值資訊,
        "外資期貨": 外資期貨,
        "外資偏離": 外資偏離資訊,
        "外資_0050_張": (外資_0050 / 1000) if 外資_0050 else None,
        "外資警示": 外資警示,
        "技術背離": 背離資訊,
    }

    # Phase 32.4 UX：融資若是「歷史不足」狀態，把「無資料」改成「累積中 (N/5)」
    if 融 and 融.get("今日_千元") and 融資降幅 is None:
        n = (融資峰值資訊 or {}).get("樣本數", 1)
        今日_億 = 融.get("今日_千元") / 1e6
        for i, d in enumerate(結果["詳情"]):
            if "融資 無資料" in d:
                結果["詳情"][i] = f"⚪ 融資 累積中 ({n}/5 天, {今日_億:.0f}億)"
                break

    # 存快取
    快取目錄.mkdir(parents=True, exist_ok=True)
    cache_path = 快取目錄 / f"{datetime.now():%Y-%m-%d}.json"
    cache_path.write_text(json.dumps(結果, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    return 結果


# ─────────────────────────────────────────────
# 對照歷史
# ─────────────────────────────────────────────
def 對比歷史底部(VIX: float = None, PutCall: float = None,
                  融資降幅: float = None) -> dict:
    """看當前數字跟哪次歷史底部最像"""
    距離 = []
    for case in 歷史底部:
        if case.get("VIX") is None:
            continue
        差距 = 0
        if VIX is not None:
            差距 += abs(VIX - case["VIX"]) / case["VIX"]
        if PutCall is not None and case.get("PutCall"):
            差距 += abs(PutCall - case["PutCall"]) / case["PutCall"]
        if 融資降幅 is not None and case.get("融資降幅_pct"):
            差距 += abs(融資降幅 - case["融資降幅_pct"]) / case["融資降幅_pct"]
        距離.append((case, 差距))
    距離.sort(key=lambda x: x[1])
    return {
        "最像": 距離[0][0] if 距離 else None,
        "排序": [c["年份"] for c, _ in 距離[:3]],
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

    print("=== Phase 32 市場底部判斷 SOP ===\n")

    # 跑即時
    r = 即時底部判定()
    print(f"\n📊 底部命中：{r['命中數']}/5")
    print(f"   等級：{r['等級']}")
    print(f"   建議：{r['建議']}")
    print(f"   部位倍率：×{r['部位倍率']}")
    print(f"\n🔍 詳情：")
    for d in r["詳情"]:
        print(f"   {d}")

    # 模擬 2020 疫情底部
    print("\n\n=== 模擬：2020 疫情底部 ===")
    sim = 底部判定(VIX=82.7, PutCall=1.28, 融資降幅_pct=36.8,
                    外資淨空_口=20000, 技術背離=True)
    print(f"命中：{sim['命中數']}/5")
    print(f"等級：{sim['等級']} 倍率 ×{sim['部位倍率']}")

    # 模擬今天市場（多頭）
    print("\n=== 模擬：今天多頭 ===")
    sim = 底部判定(VIX=15, PutCall=0.8, 融資降幅_pct=5,
                    外資淨空_口=0, 技術背離=False)
    print(f"命中：{sim['命中數']}/5 → {sim['等級']}")
