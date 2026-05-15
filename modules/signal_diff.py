"""
事件警示模組（Phase 4.5）
比較「目前掃描結果」vs「上次掃描快照」，找出**新增**的觸發訊號。

只有「新觸發」才推播，避免每小時推同樣的訊號。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快照路徑 = 專案根 / "數據" / "signal_state.json"


def 讀上次狀態() -> dict:
    """讀上次的訊號狀態。第一次跑時回傳空。"""
    if not 快照路徑.exists():
        return {"shakeout": [], "bull": [], "shit": [], "last_update": None}
    try:
        with open(快照路徑, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"shakeout": [], "bull": [], "shit": [], "last_update": None}


def 寫入狀態(掃描結果: list[dict]) -> None:
    """寫入當前的訊號狀態。"""
    state = {
        "last_update": datetime.now().isoformat(timespec="seconds"),
        "shakeout": sorted([
            r["symbol"] for r in 掃描結果
            if r.get("shakeout_low")
        ]),
        "bull": sorted([
            r["symbol"] for r in 掃描結果
            if r.get("bull_signal")
        ]),
        "shit": sorted([
            r["symbol"] for r in 掃描結果
            if r.get("shit_signal")
        ]),
    }
    快照路徑.parent.mkdir(parents=True, exist_ok=True)
    with open(快照路徑, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def 比較取得新訊號(掃描結果: list[dict]) -> dict:
    """
    比較這次掃描跟上次，回傳：
    {
        "new_shakeout": [新出現的震盪低點 stocks],
        "new_bull":     [新出現的金叉 stocks],
        "new_shit":     [新出現的錯殺 stocks],
        "has_new":      bool（是否有任何新訊號）,
    }
    """
    上次 = 讀上次狀態()
    上次shakeout = set(上次.get("shakeout", []))
    上次bull = set(上次.get("bull", []))
    上次shit = set(上次.get("shit", []))

    新shakeout = []
    新bull = []
    新shit = []
    for r in 掃描結果:
        sym = r["symbol"]
        if r.get("shakeout_low") and sym not in 上次shakeout:
            新shakeout.append(r)
        if r.get("bull_signal") and sym not in 上次bull:
            新bull.append(r)
        if r.get("shit_signal") and sym not in 上次shit:
            新shit.append(r)

    return {
        "new_shakeout": 新shakeout,
        "new_bull": 新bull,
        "new_shit": 新shit,
        "has_new": bool(新shakeout or 新bull or 新shit),
        "last_update": 上次.get("last_update"),
    }
