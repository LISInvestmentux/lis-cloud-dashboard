"""
每月使命卡（Phase 47 — Octalysis 核心 1 重大使命召喚）

每月 1 號 8AM 主推時，daily_5cards 多推一張「給兒子的禮物」使命卡。
不要太頻繁（否則疲乏）— 一個月只有一次 = 稀缺感（核心 6）+ 使命感（核心 1）。

內容:
  - 本月已實現獲利
  - 累計給兒子家族池
  - LIS 進化記錄（這個月做了哪些 Phase）
  - 「兒子 20 歲時會看到」這個 framing
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 應該出使命卡() -> bool:
    """判斷今天是否應該出使命卡：每月 1-3 號出（給用戶 3 天緩衝看到）"""
    today = datetime.now()
    return today.day <= 3


def 算本月已實現(realized_history: list, USD_TWD: float = 32.0) -> dict:
    """算本月 realized history"""
    今日 = datetime.now()
    本月_start = 今日.replace(day=1).date()
    上月_start = (今日.replace(day=1) - timedelta(days=1)).replace(day=1).date()
    上月_end = 今日.replace(day=1).date() - timedelta(days=1)

    本月 = []
    上月 = []
    for r in realized_history or []:
        try:
            d = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if 本月_start <= d:
            本月.append(r)
        elif 上月_start <= d <= 上月_end:
            上月.append(r)

    def total(records):
        台股 = sum(r.get("pnl_twd") or 0 for r in records
                  if (r.get("symbol", "").endswith(".TW") or r.get("symbol", "").endswith(".TWO")))
        美股_usd = sum(r.get("pnl_usd") or 0 for r in records
                      if not (r.get("symbol", "").endswith(".TW") or r.get("symbol", "").endswith(".TWO")))
        return round(台股 + 美股_usd * USD_TWD, 0)

    return {
        "本月_twd": total(本月),
        "上月_twd": total(上月),
        "本月筆數": len(本月),
        "上月筆數": len(上月),
    }


def 卡_月度使命(cfg: dict, USD_TWD: float = 32.0) -> dict:
    """組「每月使命」Flex 卡"""
    try:
        from . import flex_builder, discipline_progress
    except ImportError:
        import flex_builder, discipline_progress

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    今日 = datetime.now()
    上月 = (今日.replace(day=1) - timedelta(days=1))

    realized = cfg.get("realized_history", []) or []
    本月資料 = 算本月已實現(realized, USD_TWD)
    prog = discipline_progress.取得footer資料(cfg, USD_TWD)

    body = []

    # ─── Header ───
    body.append(文字(f"🌱 {上月.month} 月家族 LIS 報告",
                     size="xl", color=C["accent"], weight="bold"))
    body.append(文字(f"給兒子 20 歲時的禮物 · 第 {prog['連續紀律天數']} 天",
                     size="xs", color=C["text_dim"], wrap=True))
    body.append(分隔線())

    # ─── 上月成績 ───
    body.append(文字(f"📊 {上月.month} 月已實現獲利",
                     size="md", color=C["bull"], weight="bold"))
    上月_twd = 本月資料["上月_twd"]
    上月色 = C["bull"] if 上月_twd >= 0 else C["bear"]
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("獲利", size="sm", color=C["text_dim"], flex=3),
            文字(f"NT$ {上月_twd:+,.0f}",
                 size="lg", color=上月色, weight="bold", align="end", flex=5),
        ],
    })
    body.append(文字(f"  {本月資料['上月筆數']} 筆已實現交易",
                    size="xxs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 累計（從開始到上月底）───
    body.append(文字("💎 累計成績單", size="md",
                     color=C["accent"], weight="bold"))
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總已實現", size="sm", color=C["text_dim"], flex=3),
            文字(f"NT$ {prog['累計已實現_twd']:,.0f}",
                 size="md", color=C["bull"], weight="bold", align="end", flex=5),
        ],
    })
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("勝率", size="sm", color=C["text_dim"], flex=3),
            文字(f"{prog['勝率_pct']:.1f}% ({prog['累計筆數']} 筆)",
                 size="sm", color=C["text_main"], align="end", flex=5),
        ],
    })
    body.append(分隔線())

    # ─── 兒子的禮物（核心 1 使命）───
    body.append(文字("🌱 給兒子的家族池", size="md",
                     color=C["accent"], weight="bold"))
    兒子_twd = prog["兒子家族池_twd"]
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("累積禮物（20%）", size="sm",
                 color=C["text_dim"], flex=3),
            文字(f"NT$ {兒子_twd:,.0f}",
                 size="md", color=C["accent"],
                 weight="bold", align="end", flex=5),
        ],
    })
    body.append(文字("假設未來給兒子的家族投資池 = 累計已實現 × 20%",
                    size="xxs", color=C["text_dim"], wrap=True))
    body.append(分隔線())

    # ─── 結語（核心 1 使命）───
    body.append(文字("兒子 20 歲時會看到 LIS 演進史",
                    size="sm", color=C["text_main"],
                    weight="bold", wrap=True))
    body.append(文字(
        f"  上個月你又寫了 {本月資料['上月筆數']} 筆紀律執行",
        size="xs", color=C["text_dim"], wrap=True))
    body.append(文字(
        f"  + 累計 {prog['連續紀律天數']} 天連續系統運作",
        size="xs", color=C["text_dim"], wrap=True))
    body.append(文字(
        "  LIS 不只是賺錢工具，是傳承給家族的紀律 OS",
        size="xs", color=C["accent"], wrap=True, weight="bold"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


# CLI 測試
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cfg = json.loads((專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))
    print(f"今天: {datetime.now():%Y-%m-%d}")
    print(f"應該出使命卡: {應該出使命卡()}")
    print()

    flex = 卡_月度使命(cfg)
    # 抓 body 文字看內容
    def extract(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                t = node.get("text", "")
                if t.strip():
                    print(f"  {t}")
            else:
                for c in node.get("contents", []):
                    extract(c)
    extract(flex["body"])
