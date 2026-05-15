"""
即時決策（Phase 15.2 + 16）— 訊號 + 持股 + 現價，一鍵告訴你買啥/賣啥/PASS

執行：
  雙擊 即時查決策.bat
  或 .venv\\Scripts\\python.exe instant_decision.py

設計理念：
  「不用問第二次」— 把 4 個資料源綜合成一張決策卡：
    1. positional_state.json    → 訊號分數 + 順勢分 + 型態
    2. signal_entry_dates.json  → 今天進入價值區的標的
    3. portfolio.json           → 你的持股 + 現金
    4. FUGLE 即時報價           → 現價

  輸出（Phase 16 新增順勢 ETF 分類）：
    ✅ 抄底買（進入價值區，跌深可進）
    🚀 順勢加碼（ETF 多頭軌道內）← 修正 LIS 對 ETF 過保守
    🔴 真過熱（RSI>80 或位階>85，PASS）
    🎯 持股警示
    💰 現金水位
"""
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (capital_planner, fugle_market, forex,
                     line_push, flex_builder, position_sizer,
                     win_rate_engine, money_manager, fear_greed,
                     technical, lis_track_record, portfolio_tracker,
                     ai_explain)

# 取顏色（沿用 flex_builder 主題）
C = flex_builder.C


# ─────────────────────────────────────────────
# 訊號分數 → 狀態
# ─────────────────────────────────────────────
def 分數_狀態(score: float) -> tuple[str, str, str]:
    """回傳 (emoji, 標籤, 顏色) — 給 LINE 卡用"""
    if score is None:
        return ("⚫", "無數據", C["text_dim"])
    if score < 25:
        return ("🟢", "深度價值", C["bull"])
    if score < 45:
        return ("✅", "進入價值區", C["bull"])
    if score < 65:
        return ("🟡", "中性區", C["wait"])
    if score < 85:
        return ("⚠️", "脫離價值區", C["wait"])
    return ("🔴", "過熱", C["bear"])


# ─────────────────────────────────────────────
# 建議金額計算（依現金水位 + 訊號強度）
# ─────────────────────────────────────────────
def 算建議金額(score: float, 現金: float) -> int:
    """
    分數越低（越深價值）→ 給越多錢
      <25 深度價值：現金 2%
      25-45 進入價值區：現金 1%
      45-65 中性：現金 0.5%
      >=65：0（不買）
    """
    if score is None or score >= 65:
        return 0
    if score < 25:
        return int(現金 * 0.02)
    if score < 45:
        return int(現金 * 0.01)
    return int(現金 * 0.005)


# ─────────────────────────────────────────────
# 抓即時報價（含 fallback）
# ─────────────────────────────────────────────
def 取得現價(sym: str) -> float:
    q = fugle_market.即時報價_fallback(sym)
    if q and q.get("close"):
        return float(q["close"])
    return None


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def 主流程() -> int:
    開始 = datetime.now()
    print(f"=== 即時決策 [{開始:%Y-%m-%d %H:%M:%S}] ===")

    # 讀資料
    cfg = capital_planner.載入資金設定()
    現金 = cfg.get("current_cash_twd", 0)
    總資金 = cfg.get("total_capital_twd", 400000)
    持股清單 = [p for p in cfg.get("current_positions", [])
                if p.get("symbol") != "AGGREGATE"]
    持股代號集 = {p["symbol"] for p in 持股清單}

    # Phase 17.5/19：大盤情緒即時抓
    大盤資訊 = {"VIX": None, "fear_greed_score": None}
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        if fg:
            大盤資訊["fear_greed_score"] = fg["score"]
            print(f"😱 Fear-Greed: {fg['score']} ({fg.get('label_zh','')})")
    except Exception as e:
        print(f"Fear-Greed 抓取失敗: {e}")
    try:
        # VIX 從 watchlist 抓 (^VIX)
        vix_data, _ = technical.取得每日股價("^VIX", period="5d")
        if vix_data:
            大盤資訊["VIX"] = round(vix_data[0]["close"], 2)
            print(f"📊 VIX: {大盤資訊['VIX']}")
    except Exception as e:
        print(f"VIX 抓取失敗: {e}")

    黑天鵝資訊 = None
    # 簡化版黑天鵝判斷：VIX>25 或 F-G<20 算 1 條
    if 大盤資訊.get("VIX") and 大盤資訊["VIX"] > 25:
        黑天鵝資訊 = {"命中數": 1}
    if 大盤資訊.get("fear_greed_score") and 大盤資訊["fear_greed_score"] < 25:
        黑天鵝資訊 = {"命中數": (黑天鵝資訊["命中數"] if 黑天鵝資訊 else 0) + 1}

    # Phase 18：載入勝率資料庫（給 Kelly 用）
    勝率DB = win_rate_engine.載入勝率資料庫()
    if 勝率DB:
        print(f"📊 勝率資料庫已載入：{len(勝率DB)} 檔有歷史回測")

    # Phase 32.5：用 portfolio_tracker.追蹤真倉() 取得**即時市值**
    # （之前 bug：用 avg_cost*shares 把成本當市值，導致總資產少算 +報酬率沒呈現）
    匯率資訊 = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))
    USD_TWD = 匯率資訊["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    持股市值總 = 真倉["總計"]["市值_twd"]
    持股成本總 = 真倉["總計"]["成本_twd"]
    投資損益_twd = 真倉["總計"]["損益_twd"]
    投資損益率 = 真倉["總計"]["損益率_pct"]
    實際總資產 = 持股市值總 + 現金

    # 持股市值表（給集中度算）— 改用 真倉 的即時市值
    持股市值表 = {p["symbol"]: {"市值_twd": p.get("market_value_twd", 0)}
                   for p in 真倉["持股"] if not p.get("error")}

    目標閒錢比 = cfg.get("cash_management", {}).get("閒錢比例目標_pct", 35)
    彈藥資訊 = money_manager.計算可用彈藥(
        總資金=實際總資產,
        現金=現金,
        持股成本_twd=持股市值總,  # 用市值算水位（成本算會把獲利忽略掉）
        目標閒錢比_pct=目標閒錢比,
    )
    print(f"📐 實際總資產 NT$ {實際總資產:,.0f} "
          f"(持股市值 {持股市值總:,.0f} + 現金 {現金:,.0f})")
    print(f"   投資損益: NT$ {投資損益_twd:+,.0f} ({投資損益率:+.2f}%) "
          f"vs 成本 {持股成本總:,.0f}")
    print(f"💰 彈藥狀態：{彈藥資訊['模式emoji']} {彈藥資訊['模式']} "
          f"— 可動用 NT$ {彈藥資訊['可動用彈藥_twd']:,.0f}")
    print(f"   建議今日總彈藥 NT$ {彈藥資訊['建議單日總彈藥_twd']:,.0f} / "
          f"單筆上限 NT$ {彈藥資訊['建議單筆上限_twd']:,.0f}")
    print(f"   黑天鵝預備 NT$ {彈藥資訊['黑天鵝預備金_twd']:,.0f}")
    print(f"   水位：{彈藥資訊['水位']['持股_pct']:.1f}% 持股 / "
          f"{彈藥資訊['水位']['現金_pct']:.1f}% 現金 "
          f"(差 {彈藥資訊['水位']['差距_pct']:+.1f}%)")

    state_path = 專案根.parent / "數據" / "positional_state.json"
    entry_path = 專案根.parent / "數據" / "signal_entry_dates.json"
    if not state_path.exists():
        print("❌ 找不到 positional_state.json，先跑 main.py 產資料")
        return 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    scores = state["scores"]
    details = state.get("details", {})  # Phase 16: 順勢分 + 型態
    entries = {}
    if entry_path.exists():
        entries = json.loads(entry_path.read_text(encoding="utf-8"))["entries"]
    今日 = 開始.strftime("%Y-%m-%d")
    今日進場 = [s for s, d in entries.items() if d == 今日]

    print(f"💰 現金 NT$ {現金:,.0f}")
    print(f"📊 持股 {len(持股清單)} 檔，今日進入價值區 {len(今日進場)} 檔")
    print()

    # ─── 1. 今日「抄底買」候選（進入價值區）+ Phase 17 智能部位 ───
    抄底訊號 = []
    for sym in 今日進場:
        score = scores.get(sym)
        if score is None or score >= 65:
            continue
        現價 = 取得現價(sym)
        if 現價 is None:
            continue
        d = details.get(sym, {})
        持股名 = next((p["name"] for p in 持股清單 if p["symbol"] == sym), "")
        抄底訊號.append({
            "symbol": sym,
            "name": 持股名,
            "位階分數": score,
            "順勢分": d.get("順勢分"),
            "型態": d.get("型態", "抄底"),
            "是ETF": d.get("是ETF", False),
            "close": 現價,
        })

    抄底建議_原 = position_sizer.批次建議(
        抄底訊號, 大盤資訊, 黑天鵝資訊, 持股市值表, 總資金,
        個股勝率=勝率DB,
    )
    # 套用彈藥限制
    抄底限制 = money_manager.套用彈藥限制(抄底建議_原, 彈藥資訊)
    抄底建議 = 抄底限制["調整後清單"]
    print(f"   抄底彈藥控管：{抄底限制['說明']}")

    # Phase 32.7：ARK 美股戰法設定（A=stepped / B=off / C=strict）
    us_cfg = cfg.get("us_strategy", {})
    us_mode = us_cfg.get("mode", "stepped")
    us_tier = us_cfg.get("tier_limits_usd", {})
    us_strict_max = us_cfg.get("max_per_signal_usd", 100)
    print(f"🇺🇸 ARK 美股戰法 mode={us_mode}")

    def _套用ARK美股戰法(b: dict) -> dict:
        """
        依 us_strategy.mode 處理美股訊號：
          stepped (A) — 依訊號等級給上限，取 min(LIS 算的, ARK 等級 cap)
          off     (B) — 不套 ARK 限制，但仍要修 USD/TWD 換算 bug
          strict  (C) — 固定 max_per_signal_usd（$100）
        """
        sym = b["symbol"]
        if not sym or sym.endswith(".TW") or sym.endswith(".TWO"):
            return b  # 台股不動
        現價_usd = b["現價"]
        if 現價_usd <= 0:
            return b

        # LIS 原算法給的 USD 金額（修原 bug：原本用 USD 現價除 TWD 金額）
        lis_usd = (b["建議金額_twd"] / USD_TWD) if USD_TWD else 0

        if us_mode == "off":
            # B: 不套限制，照 LIS 原算法
            建議USD = lis_usd
            tag = "LIS 原算法（無 ARK 限額）"
        elif us_mode == "strict":
            # C: 固定 $100 上限
            建議USD = min(lis_usd, us_strict_max) if lis_usd > 0 else us_strict_max
            建議USD = max(建議USD, 現價_usd)  # 至少 1 股
            tag = f"ARK 嚴格 ${us_strict_max}"
        else:  # stepped (A) — 預設
            等級 = b.get("等級", "紀律")
            cap = us_tier.get(等級, 100)
            建議USD = min(lis_usd, cap) if lis_usd > 0 else cap
            建議USD = max(建議USD, 現價_usd)  # 至少 1 股
            tag = f"ARK 分級 {等級} ≤ ${cap}"

        # 換成股數 + 重算金額
        建議股數 = max(1, int(建議USD / 現價_usd)) if 現價_usd > 0 else 1
        建議USD = round(建議股數 * 現價_usd, 2)
        建議TWD = int(建議USD * USD_TWD)
        b["建議股數"] = 建議股數
        b["建議金額_twd"] = 建議TWD
        b["建議金額"] = 建議TWD
        b["建議金額_usd"] = 建議USD
        b.setdefault("理由", []).append(f"🇺🇸 {tag}")
        return b

    抄底清單 = []
    抄底PASS = []
    for b in 抄底建議:
        sym = b["symbol"]
        現價 = b["現價"]
        b["在持股"] = sym in 持股代號集
        b["score"] = b["位階分數"]
        b["建議金額"] = b["建議金額_twd"]
        if b["建議金額_twd"] <= 0:
            抄底PASS.append(b)
            continue
        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        if is_us:
            # ARK 美股戰法：強制 1 股 / 100 美限制（覆寫原 position_sizer 算的金額）
            _套用ARK美股戰法(b)
        else:
            b["建議股數"] = max(1, int(b["建議金額_twd"] / 現價)) if 現價 > 0 else 0
        抄底清單.append(b)

    print(f"✅ 抄底買進候選（{len(抄底清單)} 檔）")
    for r in 抄底清單:
        標記 = "（持股加碼）" if r["在持股"] else "（新進場）"
        k = r.get("Kelly資訊") or {}
        kelly_str = (f" Kelly={k.get('Kelly_pct'):.1f}%(n={k.get('交易數')})"
                     if k else "")
        print(f"  {r['symbol']:<12} {r['等級_emoji']} {r['等級_標籤']:<12} "
              f"位階={r['score']:.1f} 倍率={r['倍率']:.1f}x "
              f"建議={r['建議金額']:,} ({r['建議股數']} 股){kelly_str} {標記}")
        print(f"    理由: {' / '.join(r['理由'])}")

    # ─── Phase 16/17: 順勢加碼 ETF + 智能部位 ───
    順勢訊號 = []
    for sym, d in details.items():
        if not d.get("是ETF") or d.get("型態") != "順勢":
            continue
        score = scores.get(sym)
        if score is None:
            continue
        順勢分 = d.get("順勢分") or 0
        if 順勢分 < 60:
            continue
        現價 = 取得現價(sym)
        if 現價 is None:
            continue
        持股名 = next((p["name"] for p in 持股清單 if p["symbol"] == sym), "")
        順勢訊號.append({
            "symbol": sym,
            "name": 持股名,
            "位階分數": score,
            "順勢分": 順勢分,
            "型態": "順勢",
            "是ETF": True,
            "close": 現價,
        })

    順勢建議_原 = position_sizer.批次建議(
        順勢訊號, 大盤資訊, 黑天鵝資訊, 持股市值表, 總資金,
        個股勝率=勝率DB,
    )
    # 套用彈藥限制（用剩下的彈藥）
    剩餘彈藥 = max(0, 彈藥資訊["建議單日總彈藥_twd"] -
                    抄底限制["調整後總額_twd"])
    順勢彈藥 = {**彈藥資訊,
                "建議單日總彈藥_twd": 剩餘彈藥,
                "建議單筆上限_twd": min(彈藥資訊["建議單筆上限_twd"], 剩餘彈藥)}
    順勢限制 = money_manager.套用彈藥限制(順勢建議_原, 順勢彈藥)
    順勢建議 = 順勢限制["調整後清單"]
    print(f"   順勢彈藥控管（剩 NT$ {剩餘彈藥:,.0f}）：{順勢限制['說明']}")

    順勢清單 = []
    順勢PASS = []
    for b in 順勢建議:
        sym = b["symbol"]
        現價 = b["現價"]
        b["在持股"] = sym in 持股代號集
        b["score"] = b["位階分數"]
        b["建議金額"] = b["建議金額_twd"]
        if b["建議金額_twd"] <= 0:
            順勢PASS.append(b)
            continue
        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        if is_us:
            _套用ARK美股戰法(b)
        else:
            b["建議股數"] = max(1, int(b["建議金額_twd"] / 現價)) if 現價 > 0 else 0
        順勢清單.append(b)

    print(f"\n🚀 順勢加碼 ETF（{len(順勢清單)} 檔）")
    for r in 順勢清單[:8]:
        標記 = "（持股加碼）" if r["在持股"] else "（新進場）"
        print(f"  {r['symbol']:<12} {r['等級_emoji']} {r['等級_標籤']:<12} "
              f"順 {r['順勢分']:.0f} 倍 {r['倍率']:.1f}x "
              f"建議={r['建議金額']:,} ({r['建議股數']} 股) {標記}")

    # 合併「可買」for 卡片用
    可買清單 = 抄底清單 + 順勢清單

    # Phase 32.5：AI 解釋層 — 一次批次叫 Gemini，每檔 25 字內人話解釋
    if 可買清單:
        try:
            ai解釋 = ai_explain.批次解釋(可買清單, 大盤資訊)
            print(f"\n📝 AI 解釋層（共 {len(ai解釋)} 檔）：")
            for r in 可買清單:
                sym = r.get("symbol", "")
                exp = ai解釋.get(sym, "")
                if exp:
                    r["AI解釋"] = exp
                    print(f"   {sym}: {exp}")
        except Exception as e:
            print(f"AI 解釋呼叫失敗: {e}")

    # ─── 2. 持股「真過熱」警示（Phase 16 重新定義）───
    # 只警示「真過熱」（型態 = 過熱_別追 或 RSI > 80）
    # 不再把所有「脫離價值區」的 ETF 都警示
    持股警示 = []
    for p in 持股清單:
        sym = p["symbol"]
        score = scores.get(sym)
        if score is None:
            continue
        d = details.get(sym, {})
        是ETF = d.get("是ETF", False)
        型態 = d.get("型態", "")

        # ETF：只警示「過熱_別追」「轉弱」
        # 個股：仍用原邏輯（>=65 都警示）
        if 是ETF:
            if 型態 not in ("過熱_別追", "轉弱"):
                continue
        else:
            if score < 65:
                continue

        現價 = 取得現價(sym)
        if 現價 is None:
            continue
        漲幅 = (現價 / p["avg_cost"] - 1) * 100
        持股警示.append({
            "symbol": sym,
            "name": p.get("name", ""),
            "score": score,
            "現價": 現價,
            "漲幅": 漲幅,
            "shares": p["shares"],
            "型態": 型態 or ("過熱" if score > 85 else "脫離"),
            "是ETF": 是ETF,
        })
    持股警示.sort(key=lambda r: -r["score"])

    print(f"\n⚠️ 持股過熱別追（{len(持股警示)} 檔）")
    for r in 持股警示[:8]:
        print(f"  {r['symbol']:<12} 分數={r['score']:.1f} "
              f"漲幅={r['漲幅']:+.2f}% 現價={r['現價']:.2f}")

    # Phase 26: 自動記錄訊號到 track_record（給未來 30/60/90 天驗證）
    今日記錄id = set()  # 避免同檔重複記錄
    記錄筆數 = 0
    for r in 抄底清單:
        sym = r["symbol"]
        if sym in 今日記錄id:
            continue
        type_ = ("BUY_DEEP_VALUE" if r["score"] < 25
                 else "BUY_VALUE_ZONE")
        try:
            lis_track_record.記錄訊號(
                訊號類型=type_, symbol=sym, 進場價=r["現價"],
                位階=r["score"],
                Kelly_pct=(r.get("Kelly資訊") or {}).get("Kelly_pct"),
                預期報酬_pct=15.0,
                建議金額_twd=r["建議金額"],
                說明=f"抄底 {r['等級_標籤']} 倍率 {r['倍率']:.1f}x",
            )
            今日記錄id.add(sym)
            記錄筆數 += 1
        except Exception:
            pass
    for r in 順勢清單:
        sym = r["symbol"]
        if sym in 今日記錄id:
            continue
        try:
            lis_track_record.記錄訊號(
                訊號類型="BUY_MOMENTUM", symbol=sym, 進場價=r["現價"],
                位階=r["score"], 順勢分=r.get("順勢分"),
                Kelly_pct=(r.get("Kelly資訊") or {}).get("Kelly_pct"),
                預期報酬_pct=10.0,
                建議金額_twd=r["建議金額"],
                說明=f"順勢 {r['等級_標籤']} 倍率 {r['倍率']:.1f}x",
            )
            今日記錄id.add(sym)
            記錄筆數 += 1
        except Exception:
            pass
    if 記錄筆數 > 0:
        print(f"📝 已自動記錄 {記錄筆數} 筆訊號到 track_record（30d 後驗證）")

    # 同步驗證舊訊號（如果 30/60/90 天到了）
    try:
        驗證結果 = lis_track_record.驗證所有舊訊號(取得現價=取得現價)
        if 驗證結果["更新數"] > 0:
            print(f"📊 驗證 {驗證結果['更新數']} 筆舊訊號 / "
                  f"當前信任分 {驗證結果['信任分']}")
    except Exception as e:
        print(f"驗證舊訊號失敗：{e}")

    # ─── 3. 建 Flex 卡 ───
    卡 = 建構即時決策卡(抄底清單, 順勢清單, 持股警示, 現金, 開始,
                         彈藥資訊=彈藥資訊)

    if not 卡:
        print("\n⚠️ 沒有可顯示內容")
        return 0

    alt = (f"🎯 即時決策 — 抄底 {len(抄底清單)} / "
           f"順勢 {len(順勢清單)} / 警示 {len(持股警示)} 檔")
    print(f"\n推送到 LINE...")
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=卡)
        print("✅ 推播成功！打開 LINE 看 📱")
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
        traceback.print_exc()
        return 1

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"\n=== 完成（耗時 {耗時:.0f} 秒）===")
    return 0


# ─────────────────────────────────────────────
# Flex 卡建構
# ─────────────────────────────────────────────
def _候選列(r: dict, 顯示順勢: bool = False) -> dict:
    """單列：標的 + 等級 + 倍率 + 現價 + 建議金額/股數（Phase 17/18 升級）"""
    文字 = flex_builder.文字
    等級色映射 = {
        "ALL_IN": C["bear"],   # 紅
        "重押":   C["bull"],   # 亮黃
        "加碼":   C["bull"],
        "順勢":   C["bull"],
        "紀律":   C["text_main"],
        "PASS":   C["wait"],
    }
    等級色 = 等級色映射.get(r.get("等級", "紀律"), C["text_main"])
    等級emoji = r.get("等級_emoji", "📌")
    等級標 = r.get("等級_標籤", "紀律")
    倍率 = r.get("倍率", 1.0)
    標記 = "🔄 加碼" if r.get("在持股") else "🆕 新進場"

    # Phase 18：Kelly 資訊（若有）
    kelly_info = r.get("Kelly資訊") or {}
    kelly_pct = kelly_info.get("Kelly_pct")
    勝率 = kelly_info.get("勝率")
    交易數 = kelly_info.get("交易數")
    has_kelly = kelly_pct is not None and 交易數 and 交易數 >= 5

    contents = [
        # 第 1 行：等級徽章 + 標的 + 現價
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"{等級emoji} {r['symbol']}", size="sm",
                     color=等級色, weight="bold", flex=4),
                文字(等級標, size="xxs", color=等級色,
                     align="center", flex=3),
                文字(f"{r['現價']:.2f}", size="sm",
                     color=C["text_main"], align="end",
                     weight="bold", flex=3),
            ],
        },
        # 第 2 行：倍率 + 建議
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"倍 {倍率:.1f}x", size="xxs",
                     color=C["text_dim"], flex=3),
                文字(標記, size="xxs", color=C["text_dim"],
                     align="center", flex=2),
                文字(f"NT$ {r['建議金額']:,} ({r['建議股數']} 股)",
                     size="xs", color=C["accent"],
                     align="end", flex=5),
            ],
        },
    ]

    # 第 3 行（如有 Kelly）：歷史勝率
    if has_kelly:
        contents.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"📊 8 年勝率 {勝率*100:.0f}% · Kelly {kelly_pct:.1f}% (n={交易數})",
                     size="xxs", color=C["accent"], flex=1),
            ],
        })

    # Phase 32.5：AI 解釋層（25 字內人話）
    ai_exp = r.get("AI解釋")
    if ai_exp:
        contents.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"📝 {ai_exp}", size="xxs",
                     color=C["text_subtle"], wrap=True, flex=1),
            ],
        })

    return {
        "type": "box", "layout": "vertical", "spacing": "xs",
        "paddingTop": "sm",
        "contents": contents,
    }


def 建構即時決策卡(抄底清單: list, 順勢清單: list, 持股警示: list,
                    現金: float, 時間: datetime,
                    彈藥資訊: dict = None) -> dict:
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    內容 = []

    # Header
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🎯 即時決策", size="xl", color=C["text_main"],
                 weight="bold"),
            文字(f"{時間:%Y-%m-%d %H:%M} · 訊號+順勢+Kelly+彈藥",
                 size="xs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    # 現金水位 + 彈藥狀態（Phase 17.5）
    if 彈藥資訊:
        w = 彈藥資訊["水位"]
        模式色 = (C["bull"] if 彈藥資訊["模式"] == "充足"
                  else C["text_main"] if 彈藥資訊["模式"] == "平衡"
                  else C["wait"] if 彈藥資訊["模式"] == "接近底線"
                  else C["bear"])
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"💰 彈藥狀態 {彈藥資訊['模式emoji']}",
                             size="sm", color=C["text_dim"], flex=3),
                        文字(彈藥資訊["模式"], size="sm",
                             color=模式色, weight="bold",
                             align="end", flex=4),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"持 {w['持股_pct']:.0f}% / 現 {w['現金_pct']:.0f}%",
                             size="xxs", color=C["text_dim"], flex=4),
                        文字(f"差 {w['差距_pct']:+.1f}%",
                             size="xxs", color=模式色,
                             align="end", flex=3),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字("今日總彈藥", size="xxs",
                             color=C["text_dim"], flex=3),
                        文字(f"NT$ {彈藥資訊['建議單日總彈藥_twd']:,.0f}",
                             size="xs", color=C["accent"],
                             weight="bold", align="end", flex=4),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字("黑天鵝預備", size="xxs",
                             color=C["text_dim"], flex=3),
                        文字(f"NT$ {彈藥資訊['黑天鵝預備金_twd']:,.0f}",
                             size="xxs", color=C["wait"],
                             align="end", flex=4),
                    ],
                },
            ],
        })
    else:
        內容.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                文字("💰 可用現金", size="sm", color=C["text_dim"], flex=3),
                文字(f"NT$ {現金:,.0f}", size="sm", color=C["bull"],
                     weight="bold", align="end", flex=4),
            ],
        })
    內容.append(分隔線())

    # ─── 抄底買進 ───
    內容.append(文字(f"✅ 抄底買進 ({len(抄底清單)} 檔)",
                     size="md", color=C["bull"], weight="bold"))
    if not 抄底清單:
        內容.append(文字("（今天沒有進入價值區的標的）",
                         size="xs", color=C["text_subtle"]))
    else:
        for r in 抄底清單[:5]:
            內容.append(_候選列(r, 顯示順勢=False))

    內容.append(分隔線())

    # ─── 順勢加碼 ETF（Phase 16）───
    內容.append(文字(f"🚀 順勢加碼 ETF ({len(順勢清單)} 檔)",
                     size="md", color=C["bull"], weight="bold"))
    內容.append(文字("ETF 多頭軌道內，順勢可加（不算追高）",
                     size="xxs", color=C["text_subtle"]))
    if not 順勢清單:
        內容.append(文字("（沒有 ETF 在順勢加碼區）",
                         size="xs", color=C["text_subtle"]))
    else:
        for r in 順勢清單[:5]:
            內容.append(_候選列(r, 顯示順勢=True))

    內容.append(分隔線())

    # ─── 持股真過熱警示 ───
    內容.append(文字(f"🔴 真過熱別追 ({len(持股警示)} 檔)",
                     size="md", color=C["bear"], weight="bold"))
    if not 持股警示:
        內容.append(文字("（持股目前無真過熱）",
                         size="xs", color=C["text_subtle"]))
    else:
        for r in 持股警示[:5]:
            emoji, 狀態, 色 = 分數_狀態(r["score"])
            漲幅色 = C["bull"] if r["漲幅"] >= 0 else C["bear"]
            內容.append({
                "type": "box", "layout": "horizontal", "spacing": "xs",
                "paddingTop": "xs",
                "contents": [
                    文字(f"{emoji} {r['symbol']}", size="sm",
                         color=C["text_main"], flex=4),
                    文字(f"分 {r['score']:.0f}", size="xs",
                         color=色, align="center", flex=2),
                    文字(f"{r['漲幅']:+.1f}%", size="sm",
                         color=漲幅色, align="end", weight="bold",
                         flex=3),
                ],
            })

    內容.append(分隔線())

    # 紀律提醒
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "paddingTop": "sm",
        "contents": [
            文字("🧠 紀律提醒（Phase 16）", size="xs", color=C["text_dim"],
                 weight="bold"),
            文字("• ✅ 抄底 = 跌深進場（個股優先）",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字("• 🚀 順勢 = ETF 多頭軌道內可加（非追高）",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字("• 🔴 真過熱（RSI>80）→ PASS",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字("• DCA 0050 + 00646 月月買，不看訊號",
                 size="xxs", color=C["text_subtle"], wrap=True),
        ],
    })

    return {
        "type": "bubble",
        "size": "giga",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": 內容,
        },
    }


if __name__ == "__main__":
    sys.exit(主流程())
