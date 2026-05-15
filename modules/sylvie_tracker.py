"""
Sylvie 動態追蹤（Phase 34.1）

偵測 Sylvie 對帳單變化 → 推 LINE「太太動態」卡
比對：當前 sylvie_portfolio.json vs 上次 snapshot

偵測 5 種變化：
  ① 新增持股（買新標的）
  ② 已清倉（完全賣出）
  ③ 加碼（股數增加）
  ④ 減碼（股數減少）
  ⑤ 新已實現（新賣出紀錄）

對你的價值：
  - Sylvie 跟 ARK 系統，她的動作 = ARK 訊號間接
  - 你 + 她共識 = 強訊號
  - 她賣的若你也有 → 警示
  - 她買的若你也想 → 確認
"""
import json
from datetime import datetime
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
sylvie路徑 = 專案根 / "數據" / "sylvie_portfolio.json"
snapshot路徑 = 專案根 / "數據" / "sylvie_snapshot.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def 偵測變化() -> dict:
    """
    比對當前 vs snapshot，回傳變化清單。
    格式：{
      新增持股: [], 已清倉: [], 加碼: [], 減碼: [],
      新已實現: [], snapshot_existed: bool
    }
    """
    current = _load_json(sylvie路徑)
    snapshot = _load_json(snapshot路徑)

    if not snapshot:
        # 第一次跑，沒 snapshot，把當前存起來當基準
        return {
            "新增持股": [], "已清倉": [], "加碼": [], "減碼": [],
            "新已實現": [],
            "snapshot_existed": False,
            "說明": "首次執行，已建立 baseline snapshot",
        }

    cur持股 = {p["symbol"]: p for p in current.get("持股", [])}
    snap持股 = {p["symbol"]: p for p in snapshot.get("持股", [])}

    新增 = [cur持股[s] for s in cur持股 if s not in snap持股]
    已清倉 = [snap持股[s] for s in snap持股 if s not in cur持股]

    加碼 = []
    減碼 = []
    for sym in cur持股:
        if sym not in snap持股:
            continue
        舊 = snap持股[sym]
        新 = cur持股[sym]
        if 新["股數"] > 舊["股數"]:
            加碼.append({**新, "舊股數": 舊["股數"], "增加": 新["股數"] - 舊["股數"]})
        elif 新["股數"] < 舊["股數"]:
            減碼.append({**新, "舊股數": 舊["股數"], "減少": 舊["股數"] - 新["股數"]})

    # 新已實現（snapshot 沒有的賣出紀錄）
    cur已 = current.get("已實現", [])
    snap已 = snapshot.get("已實現", [])
    snap已key = {(e.get("symbol"), e.get("賣出日")) for e in snap已}
    新已實現 = [e for e in cur已
                  if (e.get("symbol"), e.get("賣出日")) not in snap已key]

    return {
        "新增持股": 新增,
        "已清倉": 已清倉,
        "加碼": 加碼,
        "減碼": 減碼,
        "新已實現": 新已實現,
        "snapshot_existed": True,
        "有變化": bool(新增 or 已清倉 or 加碼 or 減碼 or 新已實現),
    }


def 存snapshot():
    """把當前 sylvie 持股存成 snapshot，下次比對基準"""
    current = _load_json(sylvie路徑)
    if not current:
        return False
    current["_snapshot_at"] = datetime.now().isoformat(timespec="seconds")
    snapshot路徑.write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return True


def 對你的影響(變化: dict) -> dict:
    """
    分析 Sylvie 的變化對 user 的影響。
    讀 portfolio.json 對比共識 + 警示
    """
    you_path = 專案根 / "API" / "portfolio.json"
    you_cfg = _load_json(you_path)
    你持股代號 = {p["symbol"] for p in you_cfg.get("current_positions", [])
                   if p.get("symbol") != "AGGREGATE"}

    警示 = []
    # 她賣的，你也有
    for e in 變化.get("新已實現", []):
        if e.get("symbol") in 你持股代號:
            警示.append({
                "類型": "她賣你也有",
                "symbol": e["symbol"],
                "name": e.get("name", ""),
                "報酬率_pct": e.get("報酬率_pct"),
                "建議": "對照 LIS 訊號 — 你要跟著動嗎？",
            })
    for c in 變化.get("已清倉", []):
        if c.get("symbol") in 你持股代號:
            警示.append({
                "類型": "她清倉你還有",
                "symbol": c["symbol"],
                "name": c.get("name", ""),
                "建議": "她全清你還抱，要不要查 LIS 位階？",
            })
    # 她減碼的，你有
    for d in 變化.get("減碼", []):
        if d.get("symbol") in 你持股代號:
            警示.append({
                "類型": "她減碼你還有",
                "symbol": d["symbol"],
                "name": d.get("name", ""),
                "減少股數": d["減少"],
                "建議": "她降部位，你要參考嗎？",
            })

    # 她加碼的，你有 → 共識強訊號
    for a in 變化.get("加碼", []):
        if a.get("symbol") in 你持股代號:
            警示.append({
                "類型": "她加碼你也有（共識買進）",
                "symbol": a["symbol"],
                "name": a.get("name", ""),
                "增加股數": a["增加"],
                "建議": "雙方共識，繼續抱 or 跟著加",
            })

    return {"警示": 警示}


def 跑追蹤(推LINE: bool = True, 強制更新snapshot: bool = False) -> dict:
    """主入口：偵測 + 對你影響 + 推 LINE"""
    變化 = 偵測變化()
    影響 = 對你的影響(變化) if 變化.get("snapshot_existed") else {"警示": []}

    if 強制更新snapshot or not 變化.get("snapshot_existed"):
        存snapshot()

    結果 = {**變化, "對你影響": 影響.get("警示", [])}

    if 推LINE and 變化.get("有變化") and 推LINE通知(結果):
        # 推完後更新 snapshot
        存snapshot()

    return 結果


def 推LINE通知(結果: dict) -> bool:
    """組訊息推 LINE"""
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return False

    片段 = ["👩 Sylvie 動態追蹤"]

    新已 = 結果.get("新已實現", [])
    if 新已:
        片段.append(f"\n💰 新已實現 {len(新已)} 筆:")
        for e in 新已[:5]:
            sign = "+" if e.get("報酬率_pct", 0) >= 0 else ""
            片段.append(f"  {e['symbol']} {e.get('name','')[:8]} "
                          f"{sign}{e.get('報酬率_pct',0):.2f}%")

    if 結果.get("新增持股"):
        片段.append(f"\n🆕 新買 {len(結果['新增持股'])} 檔:")
        for n in 結果["新增持股"][:5]:
            片段.append(f"  {n['symbol']} {n.get('name','')[:8]} {n['股數']} 股")

    if 結果.get("已清倉"):
        片段.append(f"\n🚪 全清 {len(結果['已清倉'])} 檔:")
        for c in 結果["已清倉"][:5]:
            片段.append(f"  {c['symbol']} {c.get('name','')[:8]}")

    if 結果.get("加碼"):
        片段.append(f"\n📈 加碼 {len(結果['加碼'])} 檔:")
        for a in 結果["加碼"][:5]:
            片段.append(f"  {a['symbol']} +{a['增加']} 股")

    if 結果.get("減碼"):
        片段.append(f"\n📉 減碼 {len(結果['減碼'])} 檔:")
        for d in 結果["減碼"][:5]:
            片段.append(f"  {d['symbol']} -{d['減少']} 股")

    if 結果.get("對你影響"):
        片段.append(f"\n⚠️ 對你影響 {len(結果['對你影響'])} 筆:")
        for w in 結果["對你影響"][:5]:
            片段.append(f"  {w['symbol']} {w['類型']}")
            片段.append(f"    → {w['建議']}")

    if len(片段) == 1:
        return False

    訊息 = "\n".join(片段)
    try:
        line_push.推播文字訊息(訊息)
        return True
    except Exception:
        return False


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

    print(f"=== Sylvie 動態追蹤（{datetime.now():%Y-%m-%d %H:%M}）===\n")
    r = 跑追蹤(推LINE=False)

    if not r.get("snapshot_existed"):
        print("📌 首次執行，已建立 baseline snapshot")
        print(f"   下次跑時會比對變化")
    else:
        if r.get("有變化"):
            print("✅ 偵測到變化：")
            for k in ["新增持股", "已清倉", "加碼", "減碼", "新已實現"]:
                if r.get(k):
                    print(f"  {k}: {len(r[k])} 筆")
                    for x in r[k][:3]:
                        print(f"    {x}")
            if r.get("對你影響"):
                print(f"\n⚠️ 對你影響:")
                for w in r["對你影響"]:
                    print(f"  {w['symbol']} {w['類型']}: {w['建議']}")
        else:
            print("（無變化）")
