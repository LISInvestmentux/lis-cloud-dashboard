"""
Sylvie CSV 自動匯入（Phase 33.2）

把券商匯出的 CSV 對帳單 → 自動轉成 sylvie_portfolio.json

支援券商格式（自動偵測）：
  - 國泰證券「未實現損益」CSV
  - 元大證券對帳單
  - 永豐證券對帳單

通用欄位偵測：
  symbol/股票代號/Symbol
  shares/股數/Shares
  cost/成本/平均成本/Cost
  name/股票名稱/Name

使用：
  python -m modules.sylvie_csv_importer 對帳單.csv
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
SYLVIE_PATH = 專案根 / "數據" / "sylvie_portfolio.json"
SYLVIE_BAK = 專案根 / "數據" / "sylvie_portfolio.bak.json"


# 欄位別名（不同券商命名）
# 順序很重要：越精確的放越前面（避免「證券」誤匹配「證券名稱」）
欄位別名 = {
    "symbol":   ["股票代號", "證券代號", "stock_code", "代碼", "代號",
                  "symbol", "Code"],
    "name":     ["股票名稱", "證券名稱", "stock_name", "名稱",
                  "name", "Name"],
    "shares":   ["庫存股數", "現股股數", "持有股數", "股數",
                  "shares", "Shares", "Quantity", "數量"],
    "cost":     ["平均成本", "成交均價", "成本價", "avg_cost",
                  "成本", "cost", "Cost"],
    "current_price": ["最新價", "收盤價", "市價", "現價",
                      "current_price", "Price"],
    "pnl_pct":  ["未實現損益率", "報酬率_pct", "報酬率", "獲利率",
                  "pnl_pct", "PnL%"],
}


def _正規化symbol(s: str) -> str:
    """把 '2330' 變 '2330.TW'，'2330台積電' → '2330.TW'"""
    s = str(s).strip()
    # 抽出數字代號
    m = re.match(r"(\d{4,6}[A-Z]?)", s)
    if m:
        代號 = m.group(1)
        # 4 位 + 可能後綴 = 台股 / 5 位開頭 0 = ETF / 6 位 = OTC
        if len(代號) >= 4 and 代號.isdigit() or 代號[-1].isalpha():
            if not (代號.endswith(".TW") or 代號.endswith(".TWO")):
                return f"{代號}.TW"
    # 英文代號 = 美股
    if re.match(r"^[A-Z]{1,5}$", s):
        return s
    return s


def _找欄位(headers: list, 別名: list,
            已用: set = None) -> Optional[str]:
    """
    在 CSV header 裡找欄位 — 兩階段：
      1. 完全相等優先（避免「證券」誤抓「證券名稱」）
      2. 沒精確才退回包含匹配
      3. 已用過的欄位跳過（避免同一個 CSV col 被兩個 standard 用）
    """
    已用 = 已用 or set()
    # 階段 1：完全相等
    for 別 in 別名:
        for h in headers:
            if h in 已用:
                continue
            if 別.lower().strip() == h.lower().strip():
                return h
    # 階段 2：包含匹配
    for 別 in 別名:
        for h in headers:
            if h in 已用:
                continue
            if 別.lower() in h.lower():
                return h
    return None


def 讀CSV(csv_path: Path) -> list[dict]:
    """讀 CSV 並映射成標準格式"""
    # 試 UTF-8 BOM、UTF-8、Big5
    內容 = None
    for enc in ["utf-8-sig", "utf-8", "big5", "cp950", "gbk"]:
        try:
            內容 = csv_path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if not 內容:
        raise ValueError(f"無法解碼 CSV：{csv_path}")

    # 嘗試 sniff
    try:
        dialect = csv.Sniffer().sniff(內容[:2048])
    except Exception:
        dialect = csv.excel

    rows = list(csv.DictReader(內容.splitlines(), dialect=dialect))
    if not rows:
        return []

    headers = list(rows[0].keys())
    print(f"  CSV 欄位偵測：{headers}")

    # 找對應欄位（已用過的不再分配，避免一欄被兩個 standard 用）
    映射 = {}
    已用 = set()
    for 標準名, 別名 in 欄位別名.items():
        欄 = _找欄位(headers, 別名, 已用)
        if 欄:
            映射[標準名] = 欄
            已用.add(欄)

    print(f"  映射結果：{映射}")
    if "symbol" not in 映射 or "shares" not in 映射:
        raise ValueError(
            f"CSV 缺少必要欄位（symbol/shares），已偵測：{list(映射.keys())}")

    結果 = []
    for r in rows:
        try:
            symbol_raw = r.get(映射["symbol"], "").strip()
            if not symbol_raw:
                continue
            shares = float(str(r.get(映射["shares"], 0)).replace(",", ""))
            if shares <= 0:
                continue
            symbol = _正規化symbol(symbol_raw)

            cost = None
            if "cost" in 映射:
                try:
                    cost = float(str(r.get(映射["cost"], 0)).replace(",", ""))
                except Exception:
                    pass

            current = None
            if "current_price" in 映射:
                try:
                    current = float(str(r.get(映射["current_price"], 0)).replace(",", ""))
                except Exception:
                    pass

            pnl_pct = None
            if "pnl_pct" in 映射:
                try:
                    s = str(r.get(映射["pnl_pct"], "")).replace("%", "").strip()
                    pnl_pct = float(s)
                except Exception:
                    pass
            # 沒有報酬率但有 cost + current → 算
            if pnl_pct is None and cost and current and cost > 0:
                pnl_pct = round((current / cost - 1) * 100, 2)

            name = ""
            if "name" in 映射:
                name = str(r.get(映射["name"], "")).strip()
                # 去掉名稱中混進的數字代號
                name = re.sub(r"\d{4,6}[A-Z]?", "", name).strip()

            rec = {
                "symbol": symbol,
                "name": name,
                "股數": int(shares),
                "成本": round(cost, 4) if cost else None,
                "報酬率_pct": pnl_pct,
            }
            結果.append(rec)
        except Exception as e:
            print(f"  ⚠️ 跳過列：{r} ({e})")
            continue
    return 結果


def 匯入(csv_path: str, dry_run: bool = False,
         備份: bool = True) -> dict:
    """主入口：CSV → sylvie_portfolio.json"""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(csv_path)

    print(f"📂 讀 CSV：{path.name}")
    持股 = 讀CSV(path)
    print(f"✅ 解析 {len(持股)} 檔持股")

    # 算總值
    總成本_twd = sum((p["股數"] * (p["成本"] or 0)) for p in 持股)
    總現值_twd = 總成本_twd  # 若有 current_price 才能算，這裡保守用成本
    報酬合計 = sum((p["股數"] * (p["成本"] or 0) * (p["報酬率_pct"] or 0) / 100)
                    for p in 持股)
    if 總成本_twd > 0:
        總報酬率_pct = round(報酬合計 / 總成本_twd * 100, 2)
        總現值_twd = 總成本_twd + 報酬合計
    else:
        總報酬率_pct = 0

    data = {
        "_說明": f"Sylvie 太太持股資料（CSV 匯入：{path.name}）",
        "_更新提醒": "下次再用 sylvie_csv_importer 覆蓋",
        "更新日": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "總現值_twd": round(總現值_twd, 0),
        "總成本_twd": round(總成本_twd, 0),
        "總報酬率_pct": 總報酬率_pct,
        "持股": 持股,
        "已實現": [],  # CSV 通常只有持股，已實現需另一個 CSV
    }

    if dry_run:
        print("\n[DRY RUN] 不寫檔，預覽：")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:600])
        return data

    if 備份 and SYLVIE_PATH.exists():
        SYLVIE_BAK.write_bytes(SYLVIE_PATH.read_bytes())
        print(f"📦 備份舊檔：{SYLVIE_BAK.name}")

    SYLVIE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 寫入：{SYLVIE_PATH}")

    return data


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("使用方法：")
        print("  python -m modules.sylvie_csv_importer <CSV 路徑>")
        print("  python -m modules.sylvie_csv_importer <CSV 路徑> --dry")
        sys.exit(1)

    csv_path = sys.argv[1]
    dry_run = "--dry" in sys.argv
    data = 匯入(csv_path, dry_run=dry_run)
    print(f"\n📊 總覽：")
    print(f"  持股 {len(data['持股'])} 檔")
    print(f"  總成本 NT$ {data['總成本_twd']:,.0f}")
    print(f"  總現值 NT$ {data['總現值_twd']:,.0f}")
    print(f"  總報酬 {data['總報酬率_pct']:+.2f}%")
