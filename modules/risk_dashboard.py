"""
風控 5 儀表彙整（Phase 6.2）
仿方舟 ARK 的 5 個情緒儀表，0-100 分（越高越「警示/過熱」）。

5 個儀表：
  1. 散戶情緒 F&G        — F&G score
  2. VIX 反向            — 100 - min(VIX×2, 100)（低 VIX = 過度自滿）
  3. 大盤位階熱度        — 平均(^TWII / ^TWOII / ^SOX RSI)
  4. 量能爆衝率          — watchlist 量爆個股數 / 總數 × 100
  5. 外資集中度          — watchlist 命中外資前 20 個股數 / 台股檔數 × 100

整體風控建議（從 5 儀表平均）：
  ≥ 70 → 🔴 過熱警示（市場狂歡，謹慎加碼）
  40-70 → 🟡 中性
  < 40 → 🟢 機會浮現（情緒冷卻，恐慌中找錯殺）
"""
from typing import Optional


# ─────────────────────────────────────────────
# 個別儀表計算
# ─────────────────────────────────────────────
def _散戶情緒分數(fg_score: Optional[float]) -> Optional[float]:
    """F&G 直接當分數（0=極恐慌、100=極貪婪）。"""
    if fg_score is None:
        return None
    return max(0, min(100, fg_score))


def _VIX反向分數(vix: Optional[float]) -> Optional[float]:
    """
    VIX 反向 — 低 VIX = 過度自滿（市場貪婪）
    VIX 10 → 80（過熱）
    VIX 20 → 60（中性偏熱）
    VIX 30 → 40（中性偏冷）
    VIX 50 → 0（極恐慌）
    """
    if vix is None:
        return None
    return max(0, min(100, 100 - vix * 2))


def _大盤位階分數(taiex_rsi: Optional[float],
                  otc_rsi: Optional[float],
                  sox_rsi: Optional[float]) -> Optional[float]:
    """三個指數 RSI 平均（None 跳過）。"""
    有效 = [r for r in (taiex_rsi, otc_rsi, sox_rsi) if r is not None]
    if not 有效:
        return None
    return round(sum(有效) / len(有效), 1)


def _量爆率分數(全部個股: list[dict]) -> tuple[Optional[float], int, int]:
    """
    回傳 (分數, 量爆檔數, 有效檔數)
    分數 = 量爆檔數 / 有效檔數 × 100，最高 100
    """
    有效 = [r for r in 全部個股
             if "error" not in r and r.get("量爆倍數") is not None]
    if not 有效:
        return (None, 0, 0)
    量爆檔數 = sum(1 for r in 有效 if r.get("量爆訊號"))
    分數 = round(量爆檔數 / len(有效) * 100, 1)
    return (分數, 量爆檔數, len(有效))


def _外資集中度分數(全部個股: list[dict],
                    外資前20: list[dict]) -> tuple[Optional[float], list[dict]]:
    """
    回傳 (分數, 命中清單)
    若 watchlist 中很多檔在「外資持股前 20」，代表市場熱門
    分數 = 命中數 / 20 × 100（上限 100）
    """
    if not 外資前20:
        return (None, [])
    前20_codes = {r["code"] for r in 外資前20}
    台股們 = [r for r in 全部個股
              if r.get("symbol", "").endswith(".TW")
              or r.get("symbol", "").endswith(".TWO")]
    命中 = []
    for r in 台股們:
        sym = r["symbol"]
        code = sym.replace(".TW", "").replace(".TWO", "")
        if code in 前20_codes:
            命中.append({"symbol": sym, "name": r.get("name", ""),
                          "code": code})
    分數 = min(100, len(命中) / 20 * 100)
    return (round(分數, 1), 命中)


# ─────────────────────────────────────────────
# 主整合
# ─────────────────────────────────────────────
def 計算風控儀表(fg_score: Optional[float],
                  vix: Optional[float],
                  taiex_rsi: Optional[float],
                  otc_rsi: Optional[float],
                  sox_rsi: Optional[float],
                  全部個股: list[dict],
                  外資前20: list[dict]) -> dict:
    """
    一次算 5 個儀表並回傳。
    回傳 {儀表名: {分數, 副標, 顏色提示}, 總體, ...}
    """
    fg = _散戶情緒分數(fg_score)
    vix_score = _VIX反向分數(vix)
    位階 = _大盤位階分數(taiex_rsi, otc_rsi, sox_rsi)
    量爆_score, 量爆檔, 有效檔 = _量爆率分數(全部個股)
    外資_score, 外資命中 = _外資集中度分數(全部個股, 外資前20)

    儀表 = {
        "散戶情緒": {
            "分數": fg,
            "副標": f"F&G {fg_score:.0f}" if fg_score is not None else "n/a",
            "原始值": fg_score,
        },
        "VIX 反向": {
            "分數": vix_score,
            "副標": f"VIX {vix:.1f}" if vix is not None else "n/a",
            "原始值": vix,
        },
        "大盤位階": {
            "分數": 位階,
            "副標": (f"3 指數均 RSI {位階}" if 位階 is not None else "n/a"),
            "原始值": {"taiex": taiex_rsi, "otc": otc_rsi, "sox": sox_rsi},
        },
        "量能爆衝率": {
            "分數": 量爆_score,
            "副標": f"{量爆檔}/{有效檔} 檔爆量",
            "原始值": {"量爆檔": 量爆檔, "有效檔": 有效檔},
        },
        "外資集中度": {
            "分數": 外資_score,
            "副標": f"命中 {len(外資命中)}/20",
            "原始值": {"命中數": len(外資命中)},
            "命中清單": 外資命中,
        },
    }

    有效分數 = [儀["分數"] for 儀 in 儀表.values() if 儀["分數"] is not None]
    總體 = round(sum(有效分數) / len(有效分數), 1) if 有效分數 else None

    if 總體 is None:
        建議, 文案 = "資料不足", "5 儀表均無法計算"
    elif 總體 >= 70:
        建議 = "🔴 過熱警示"
        文案 = "市場狂歡，謹慎加碼，建議減碼鎖利"
    elif 總體 >= 40:
        建議 = "🟡 中性"
        文案 = "情緒平衡，依紀律操作"
    else:
        建議 = "🟢 機會浮現"
        文案 = "情緒冷卻，恐慌中找錯殺，加碼時機"

    return {
        "儀表": 儀表,
        "總體分數": 總體,
        "建議": 建議,
        "建議文案": 文案,
    }


# ─────────────────────────────────────────────
# 取用情境（給 main.py）
# ─────────────────────────────────────────────
def 從main流程計算(fear_greed: dict, indices: list[dict],
                    全部個股: list[dict],
                    外資前20: list[dict]) -> dict:
    """
    main.py 主流程一鍵呼叫。
    fear_greed: fear_greed.取得恐慌貪婪指數() 結果
    indices: technical.掃描全部觀察清單()['indices']
    全部個股: _合併個股(掃描結果) 結果
    外資前20: tw_announcements.取得公告清單()["外資前20"]
    """
    # 從 indices 找 ^TWII / ^TWOII / ^SOX / ^VIX
    idx_map = {r.get("original_symbol") or r.get("symbol"): r
               for r in indices if "error" not in r}

    def _RSI(sym):
        r = idx_map.get(sym)
        return r.get("rsi14") if r else None

    def _close(sym):
        r = idx_map.get(sym)
        return r.get("close") if r else None

    return 計算風控儀表(
        fg_score=fear_greed.get("score") if fear_greed else None,
        vix=_close("^VIX"),
        taiex_rsi=_RSI("^TWII"),
        otc_rsi=_RSI("^TWOII"),
        sox_rsi=_RSI("^SOX"),
        全部個股=全部個股,
        外資前20=外資前20,
    )
