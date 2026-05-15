"""
盤中 / 盤前盤後推播邏輯（Phase 4 + 5）

三種時段：
- 台股盤中（11:00 / 13:00）
- 美股盤前（22:30）
- 美股盤中（00:00 / 03:00）

每個時段推不一樣的東西，比 8:00 完整版精簡。
"""
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

專案根 = Path(__file__).resolve().parent.parent.parent
load_dotenv(專案根 / "API" / ".env")
LIFF_URL = os.getenv("LIFF_URL", "")

# 支援 import 兩種路徑
try:
    from . import (fear_greed, technical, news_ai, enjoy_index,
                   capital_planner, flex_builder, line_push, etf_navigator,
                   signal_diff, portfolio_tracker, forex)
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from modules import (fear_greed, technical, news_ai, enjoy_index,
                         capital_planner, flex_builder, line_push,
                         etf_navigator, signal_diff,
                         portfolio_tracker, forex)


# ─────────────────────────────────────────────
# 共用：建立「美股焦點」卡片組
# ─────────────────────────────────────────────
def _美股焦點卡片(時段標籤: str) -> list[dict]:
    """
    回傳美股相關的 Flex 卡片：
      - 💼 美股持股總覽（只看美股）
      - ⚡ 美股紀律警示（A/D 雙策略）
    """
    cfg = capital_planner.載入資金設定()
    固定 = cfg.get("currency_rates", {}).get("USD_TWD", 32.0)
    USD_TWD = forex.取得匯率_純數字(fallback=固定)
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    # 過濾出美股
    美股持股 = [r for r in 真倉["持股"] if r.get("is_us")]
    if not 美股持股:
        return []

    # 建一個「只有美股」的真倉物件
    美 = 真倉["美股小計"]
    美股真倉 = {
        "持股": 美股持股,
        "總計": {
            "成本_twd": 美["成本_twd"],
            "市值_twd": 美["市值_twd"],
            "損益_twd": 美["市值_twd"] - 美["成本_twd"],
            "損益率_pct": 美["損益率_pct"],
            "賺檔數": sum(1 for r in 美股持股 if r.get("pnl_twd", 0) >= 0),
            "賠檔數": sum(1 for r in 美股持股 if r.get("pnl_twd", 0) < 0),
            "總檔數": 美["檔數"],
        },
        "台股小計": {"檔數": 0},
        "美股小計": 美,
        "警示": {
            "達停利": [r for r in 真倉["警示"]["達停利"] if r.get("is_us")],
            "破停損": [r for r in 真倉["警示"]["破停損"] if r.get("is_us")],
            "接近停利": [r for r in 真倉["警示"]["接近停利"] if r.get("is_us")],
            "接近停損": [r for r in 真倉["警示"]["接近停損"] if r.get("is_us")],
        },
    }
    美股真倉["有警示"] = any(美股真倉["警示"].values())

    卡片 = []
    總覽卡 = flex_builder.建構持股總覽卡(美股真倉)
    if 總覽卡:
        卡片.append(總覽卡)
    警示卡 = flex_builder.建構真倉警示卡(美股真倉)
    if 警示卡:
        卡片.append(警示卡)
    return 卡片


# ─────────────────────────────────────────────
# 共用：讀今日 Enjoy Index + 預算
# ─────────────────────────────────────────────
def _今日預算():
    """從 portfolio.json + 最新 enjoy 估算今日每檔預算。"""
    import json
    snapshot = 專案根 / "數據" / "daily" / f"{datetime.now():%Y-%m-%d}.json"
    enjoy分 = 50  # default WAIT
    if snapshot.exists():
        try:
            with open(snapshot, "r", encoding="utf-8") as f:
                enjoy分 = json.load(f)["enjoy_index"]["總分"]
        except Exception:
            pass
    資金 = capital_planner.載入資金設定()
    規劃 = capital_planner.計算今日資金規劃(enjoy分, 資金)
    return 規劃, enjoy分


# ─────────────────────────────────────────────
# 台股盤中推播（11:00 / 13:00）
# ─────────────────────────────────────────────
def 推播台股盤中(時段標籤: str = "盤中") -> int:
    """掃台股觸發 + ETF 五檔布局 + LIFF 入口。"""
    開始 = datetime.now()
    print(f"=== 台股{時段標籤}推播 [{開始:%H:%M:%S}] ===")

    # 1. 算今日預算
    規劃, enjoy分 = _今日預算()
    每檔預算 = min(規劃["單檔上限_twd"],
                   規劃["今日可動用子彈_twd"] / 5)
    print(f"  Enjoy={enjoy分} 子彈={規劃['今日可動用子彈_twd']:,.0f} 每檔={每檔預算:,.0f}")

    # 2. 掃台股個股 + ETF 觸發訊號
    print("  掃描台股觀察清單...")
    cfg = technical.載入觀察清單()
    台股items = next(r for r in cfg["regions"] if r["id"] == "tw_stocks")["stocks"]
    etfitems = next(r for r in cfg["regions"] if r["id"] == "tw_etfs")["stocks"]
    台股結果 = technical.掃描清單(台股items, 延遲秒=0.5)
    etf結果 = technical.掃描清單(etfitems, 延遲秒=0.5)

    # 2b. 比較跟上次掃描，找新訊號（Phase 4.5）
    全部結果 = 台股結果 + etf結果
    diff = signal_diff.比較取得新訊號(全部結果)
    print(f"  新訊號：{len(diff['new_shakeout'])} 震盪低點 / "
          f"{len(diff['new_bull'])} 金叉 / {len(diff['new_shit'])} 錯殺")

    # 3. 抓 ETF 即時五檔
    print("  抓 ETF 即時五檔報價...")
    etf布局 = etf_navigator.取得今日ETF布局建議(每檔預算_twd=每檔預算)

    # 4. 組 carousel
    日期 = datetime.now().strftime("%Y/%m/%d %H:%M")
    預算文字 = (f"{日期} · Enjoy {enjoy分} · "
                 f"子彈 NT$ {規劃['今日可動用子彈_twd']:,.0f} · "
                 f"每檔 NT$ {每檔預算:,.0f}")

    # Carousel 1: 事件警示 +個股觸發 + LIFF
    台股區 = {"label": f"📋 台股{時段標籤}", "items": 台股結果}
    etf區 = {"label": f"📋 ETF {時段標籤}", "items": etf結果}

    carousel1_contents = []
    # 有新訊號才加事件警示卡（放最前面）
    if diff["has_new"]:
        carousel1_contents.append(
            flex_builder.建構事件警示卡(diff, f"台股{時段標籤} {日期}")
        )
    carousel1_contents.extend([
        flex_builder.建構區域卡(
            台股區, f"📋 台股{時段標籤}觸發", 日期,
            預算_twd=每檔預算, USD_TWD=規劃["USD_TWD"]),
        flex_builder.建構區域卡(
            etf區, f"📋 ETF {時段標籤}觸發", 日期,
            預算_twd=每檔預算, USD_TWD=規劃["USD_TWD"]),
    ])
    if LIFF_URL:
        carousel1_contents.append(flex_builder.建構LIFF入口卡(LIFF_URL))
    carousel1 = {"type": "carousel", "contents": carousel1_contents}

    # Carousel 2: ETF 即時五檔布局
    carousel2 = flex_builder.建構ETF布局Carousel(etf布局, 預算文字=預算文字)

    # 5. 推播
    print("  推播...")
    line_push.推播Flex訊息(替代文字=f"台股{時段標籤} · 觸發訊號", flex內容=carousel1)
    print(f"    ✅ 第 1 輪（{len(carousel1['contents'])} 卡）")
    line_push.推播Flex訊息(替代文字=f"台股{時段標籤} · ETF 五檔", flex內容=carousel2)
    print(f"    ✅ 第 2 輪（{len(carousel2['contents'])} 卡）")

    # 6. 記錄狀態（給下次比較）
    signal_diff.寫入狀態(全部結果)

    print(f"=== 完成（{(datetime.now() - 開始).seconds}s）===")
    return 0


# ─────────────────────────────────────────────
# 美股盤前推播（22:30）
# ─────────────────────────────────────────────
def 推播美股盤前() -> int:
    開始 = datetime.now()
    print(f"=== 美股盤前推播 [{開始:%H:%M:%S}] ===")

    規劃, enjoy分 = _今日預算()
    每檔預算 = min(規劃["單檔上限_twd"],
                   規劃["今日可動用子彈_twd"] / 5)

    # 抓 Fear & Greed + 大盤指標
    print("  抓 F&G + 大盤指標...")
    情緒 = fear_greed.取得恐慌貪婪指數()
    cfg = technical.載入觀察清單()
    指數結果 = technical.掃描清單(cfg["indices"]["items"])

    # 掃美股
    print("  掃描美股觀察清單...")
    美股items = next(r for r in cfg["regions"] if r["id"] == "us")["stocks"]
    美股結果 = technical.掃描清單(美股items, 延遲秒=0.5)

    # 找 VIX
    vix項 = next((r for r in 指數結果
                   if (r.get("original_symbol") or r.get("symbol")) == "^VIX"
                   and "error" not in r), None)
    vix值 = vix項["close"] if vix項 else None

    日期 = datetime.now().strftime("%Y/%m/%d %H:%M")
    美股區 = {"label": "🌙 美股盤前", "items": 美股結果}

    # 美股焦點卡片（持股總覽 + 紀律警示）
    print("  建立美股焦點卡...")
    美股焦點 = _美股焦點卡片("盤前")

    carousel = {
        "type": "carousel",
        "contents": [
            flex_builder.建構風險指針卡(vix值),
            flex_builder.建構大盤指標卡(指數結果),
        ] + 美股焦點 + [
            flex_builder.建構區域卡(
                美股區, "🌙 美股盤前", 日期,
                預算_twd=每檔預算, USD_TWD=規劃["USD_TWD"]),
        ] + ([flex_builder.建構LIFF入口卡(LIFF_URL)] if LIFF_URL else []),
    }

    print("  推播...")
    line_push.推播Flex訊息(替代文字="美股盤前 · 持股 + 觸發",
                            flex內容=carousel)
    print(f"    [OK] 推播完成（{len(carousel['contents'])} 卡，"
          f"含 {len(美股焦點)} 張美股焦點）")

    print(f"=== 完成（{(datetime.now() - 開始).seconds}s）===")
    return 0


# ─────────────────────────────────────────────
# 美股盤中推播（00:00 / 03:00）
# ─────────────────────────────────────────────
def 推播美股盤中(時段標籤: str = "盤中") -> int:
    開始 = datetime.now()
    print(f"=== 美股{時段標籤}推播 [{開始:%H:%M:%S}] ===")

    規劃, enjoy分 = _今日預算()
    每檔預算 = min(規劃["單檔上限_twd"],
                   規劃["今日可動用子彈_twd"] / 5)

    cfg = technical.載入觀察清單()
    # 只抓 VIX 跟主要美股指數
    print("  抓 VIX + 美股指數...")
    指數結果 = technical.掃描清單([
        {"symbol": "^VIX", "name": "VIX"},
        {"symbol": "^GSPC", "name": "S&P 500"},
        {"symbol": "^IXIC", "name": "那斯達克"},
        {"symbol": "^SOX", "name": "費城半導體"},
    ])
    vix項 = next((r for r in 指數結果 if "VIX" in r.get("symbol", "")
                   and "error" not in r), None)
    vix值 = vix項["close"] if vix項 else None

    # 掃美股觸發
    print("  掃描美股觀察清單...")
    美股items = next(r for r in cfg["regions"] if r["id"] == "us")["stocks"]
    美股結果 = technical.掃描清單(美股items, 延遲秒=0.5)

    日期 = datetime.now().strftime("%Y/%m/%d %H:%M")
    美股區 = {"label": f"🌙 美股{時段標籤}", "items": 美股結果}

    # 美股焦點卡片
    print("  建立美股焦點卡...")
    美股焦點 = _美股焦點卡片(時段標籤)

    carousel = {
        "type": "carousel",
        "contents": [
            flex_builder.建構風險指針卡(vix值),
        ] + 美股焦點 + [
            flex_builder.建構區域卡(
                美股區, f"🌙 美股{時段標籤}", 日期,
                預算_twd=每檔預算, USD_TWD=規劃["USD_TWD"]),
        ] + ([flex_builder.建構LIFF入口卡(LIFF_URL)] if LIFF_URL else []),
    }

    print("  推播...")
    line_push.推播Flex訊息(替代文字=f"美股{時段標籤} · 觸發訊號", flex內容=carousel)
    print(f"    ✅ 推播完成（{len(carousel['contents'])} 卡）")

    print(f"=== 完成（{(datetime.now() - 開始).seconds}s）===")
    return 0


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    模式 = sys.argv[1] if len(sys.argv) > 1 else "tw_morning"
    if 模式 == "tw_morning":
        sys.exit(推播台股盤中("盤中"))
    elif 模式 == "tw_close":
        sys.exit(推播台股盤中("收盤前"))
    elif 模式 == "us_premarket":
        sys.exit(推播美股盤前())
    elif 模式 == "us_intraday":
        sys.exit(推播美股盤中("盤中"))
    else:
        print(f"未知模式：{模式}")
        print("用法：python intraday.py [tw_morning|tw_close|us_premarket|us_intraday]")
        sys.exit(1)
