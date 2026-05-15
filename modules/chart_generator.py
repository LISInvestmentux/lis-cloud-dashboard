"""
真圓環圖表生成模組（Phase 2.6）
用 matplotlib 動態畫圓環 / 半圓 gauge → PNG bytes
之後由 image_uploader 上傳到 0x0.st 取得 URL，塞進 Flex Message。
"""
import io
import math
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # 不需要 GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.font_manager import FontProperties


# 中文字型（Windows 標配的微軟正黑體）
中文字型 = FontProperties(family="Microsoft JhengHei")

# 方舟黑黃配色（與 flex_builder 同步）
COLORS = {
    "bg":       "#000000",
    "card":     "#0F0F14",
    "ring_bg":  "#1F1F28",
    "text":     "#FFFFFF",
    "text_dim": "#888888",
    "bull":     "#FBBF24",  # 亮黃 — 機會
    "bear":     "#EF4444",  # 紅 — 警示
    "wait":     "#888888",
    "brand":    "#A855F7",
}


def _圖to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png",
                facecolor=COLORS["bg"],
                bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _依分數取色(score: float, 滿分: float = 100,
                  bull_threshold: float = 70, wait_threshold: float = 40) -> str:
    pct = (score / 滿分) * 100
    if pct >= bull_threshold:
        return COLORS["bull"]
    if pct >= wait_threshold:
        return "#F59E0B"  # 偏黃
    return COLORS["bear"]


# ─────────────────────────────────────────────
# 1. Enjoy Index 圓環（360° 環，中央大數字）
# ─────────────────────────────────────────────
def 生成Enjoy圓環(score: float, status: str = "HOLD",
                    副標: str = "Enjoy Index") -> bytes:
    色 = _依分數取色(score)
    fig, ax = plt.subplots(figsize=(7, 7), dpi=120)
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)

    # 1) 灰色底環
    底環 = patches.Wedge((0, 0), 1.0, 0, 360, width=0.18,
                           facecolor=COLORS["ring_bg"], edgecolor="none")
    ax.add_patch(底環)

    # 2) 進度弧（從正上方 12 點開始順時針）
    end_angle = 90 - (score / 100) * 360
    if end_angle < -270:
        end_angle = -270
    進度弧 = patches.Wedge((0, 0), 1.0, end_angle, 90, width=0.18,
                            facecolor=色, edgecolor="none")
    ax.add_patch(進度弧)

    # 3) 端點圓點（仿方舟那種小亮點，提示進度位置）
    end_rad = math.radians(end_angle)
    端點x = 0.91 * math.cos(end_rad)
    端點y = 0.91 * math.sin(end_rad)
    ax.add_patch(patches.Circle((端點x, 端點y), 0.04,
                                  facecolor=色, edgecolor="white", linewidth=1.5,
                                  zorder=10))

    # 4) 中央文字
    ax.text(0, 0.30, 副標, ha="center", va="center",
            fontsize=14, color=COLORS["text_dim"], fontproperties=中文字型)
    ax.text(0, -0.02, f"{score}", ha="center", va="center",
            fontsize=72, color=色, fontweight="bold")
    ax.text(0, -0.30, "/ 100", ha="center", va="center",
            fontsize=14, color=COLORS["text_dim"])
    # 拿掉 status 開頭的 emoji（matplotlib 字型不支援 🔴🟢🟡）
    乾淨status = status.lstrip("🔴🟢🟡⚪ ").strip()
    ax.text(0, -0.50, 乾淨status, ha="center", va="center",
            fontsize=20, color=色, fontweight="bold", fontproperties=中文字型)

    return _圖to_bytes(fig)


# ─────────────────────────────────────────────
# 2. VIX 半圓指針儀表（仿方舟下方那種半圓）
# ─────────────────────────────────────────────
def 生成VIX半圓(vix值: Optional[float]) -> bytes:
    if vix值 is None:
        vix_pct = 0
        色 = COLORS["text_dim"]
        狀態 = "—"
    else:
        vix_pct = max(0, min(100, vix值 * 2))
        # 顏色對應彩帶分段（紅橘灰黃黃）
        if vix值 >= 30:
            色 = COLORS["bull"]; 狀態 = "恐慌"      # 黃
        elif vix值 >= 20:
            色 = COLORS["wait"]; 狀態 = "警戒"      # 灰
        elif vix值 >= 15:
            色 = "#F59E0B"; 狀態 = "平穩"           # 橘
        else:
            色 = COLORS["bear"]; 狀態 = "自滿"      # 紅

    fig, ax = plt.subplots(figsize=(7, 6), dpi=120)
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.85, 1.3)

    # 五段彩色半圓（從右 → 左：0% 到 100%）
    # VIX 區間：自滿 <15 (30%)、平穩 15-20 (10%)、警戒 20-30 (20%)、恐慌 30-40 (20%)、極恐 >40 (20%)
    分段 = [
        (0,   30, COLORS["bear"]),
        (30,  40, "#F59E0B"),
        (40,  60, COLORS["wait"]),
        (60,  80, COLORS["bull"]),
        (80, 100, COLORS["bull"]),
    ]
    for start_pct, end_pct, c in 分段:
        start_ang = 180 - end_pct * 1.8
        end_ang   = 180 - start_pct * 1.8
        ax.add_patch(patches.Wedge((0, 0), 1.0, start_ang, end_ang,
                                     width=0.18, facecolor=c, edgecolor="none"))

    # 指針
    needle_angle = math.radians(180 - vix_pct * 1.8)
    nx = 0.88 * math.cos(needle_angle)
    ny = 0.88 * math.sin(needle_angle)
    ax.plot([0, nx], [0, ny], color="white", linewidth=4, solid_capstyle="round", zorder=8)
    ax.add_patch(patches.Circle((0, 0), 0.07, facecolor="white",
                                  edgecolor=色, linewidth=3, zorder=10))

    # 文字（拉到指針下方，避免重疊）
    ax.text(0, -0.30, f"{vix值}" if vix值 is not None else "—",
            ha="center", va="top",
            fontsize=48, color=COLORS["text"], fontweight="bold")
    ax.text(0, -0.65, f"VIX · {狀態}", ha="center", va="top",
            fontsize=16, color=色, fontweight="bold", fontproperties=中文字型)

    return _圖to_bytes(fig)


# ─────────────────────────────────────────────
# 3. 資金規劃圓環（仿 Enjoy 圓環但用火力比例）
# ─────────────────────────────────────────────
def 生成資金規劃圓環(火力比例: int, 子彈金額: float, 建議: str) -> bytes:
    色 = (COLORS["bull"] if 建議 == "BE HAPPY"
          else "#F59E0B" if 建議 == "WAIT"
          else COLORS["bear"])

    fig, ax = plt.subplots(figsize=(7, 7), dpi=120)
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)

    ax.add_patch(patches.Wedge((0, 0), 1.0, 0, 360, width=0.18,
                                facecolor=COLORS["ring_bg"], edgecolor="none"))
    end_angle = 90 - (火力比例 / 100) * 360
    ax.add_patch(patches.Wedge((0, 0), 1.0, end_angle, 90, width=0.18,
                                facecolor=色, edgecolor="none"))

    ax.text(0, 0.35, "今日子彈", ha="center", va="center",
            fontsize=14, color=COLORS["text_dim"], fontproperties=中文字型)
    ax.text(0, 0.05, f"NT$ {子彈金額:,.0f}", ha="center", va="center",
            fontsize=32, color=色, fontweight="bold")
    ax.text(0, -0.25, f"火力 {火力比例}%", ha="center", va="center",
            fontsize=16, color=COLORS["text_dim"], fontproperties=中文字型)
    ax.text(0, -0.50, 建議, ha="center", va="center",
            fontsize=18, color=色, fontweight="bold")

    return _圖to_bytes(fig)


if __name__ == "__main__":
    # 測試：把三張圖存到本機
    from pathlib import Path
    out = Path(r"D:\LIS股票投資系統\數據\test_charts")
    out.mkdir(parents=True, exist_ok=True)

    print("生成 Enjoy 圓環 (31.3 HOLD)...")
    (out / "enjoy_31.png").write_bytes(生成Enjoy圓環(31.3, "🔴 HOLD"))

    print("生成 Enjoy 圓環 (75 BE HAPPY)...")
    (out / "enjoy_75.png").write_bytes(生成Enjoy圓環(75, "🟢 BE HAPPY"))

    print("生成 VIX 半圓 (18.92)...")
    (out / "vix_18.png").write_bytes(生成VIX半圓(18.92))

    print("生成 VIX 半圓 (35)...")
    (out / "vix_35.png").write_bytes(生成VIX半圓(35))

    print("生成 資金圓環 (HOLD 10%)...")
    (out / "capital_hold.png").write_bytes(生成資金規劃圓環(10, 12750, "HOLD"))

    print(f"\n✅ 圖檔已存到 {out}")
