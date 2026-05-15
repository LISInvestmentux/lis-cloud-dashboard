"""
L.I.S Flex Message 卡片建構器 — Phase 2.5（方舟風格版）

設計準則：
  - 純黑底色 #000000
  - 主色：亮黃 #FBBF24（強調、機會、主數字）
  - 紫色強調 #A855F7（光暈、品牌色）
  - 視覺語言統一：所有指標都用 統一儀表() 元件
  - 大數字主導（5xl / 4xl）

  字級：xxs / xs / sm / md / lg / xl / xxl / 3xl / 4xl / 5xl
"""
from typing import Optional
from . import capital_planner


# ─────────────────────────────────────────────
# Color tokens（方舟黑黃為預設）
# ─────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg_dark":      "#1A1D29",
        "bg_card":      "#252938",
        "bg_card_alt":  "#2D3245",
        "line":         "#3A3F4F",
        "text_main":    "#FFFFFF",
        "text_dim":     "#A0A4B8",
        "text_subtle":  "#6B7080",
        "bull":         "#22C55E",
        "bear":         "#EF4444",
        "wait":         "#F59E0B",
        "brand":        "#3B82F6",
        "accent":       "#A855F7",
    },
    "febforest": {
        "bg_dark":      "#FBF8F3", "bg_card": "#F5EBDC",
        "bg_card_alt":  "#EFE3D0", "line":    "#D9CDB7",
        "text_main":    "#3D2E26", "text_dim": "#8A9389",
        "text_subtle":  "#A8A399",
        "bull":         "#4A6B47", "bear":     "#C0392B",
        "wait":         "#D4A574", "brand":    "#8B5A3C",
        "accent":       "#A0322B",
    },
    "febforest_dark": {
        "bg_dark":      "#1F2A1F", "bg_card": "#2B3729",
        "bg_card_alt":  "#374634", "line":    "#4A5A47",
        "text_main":    "#F5EBDC", "text_dim": "#A8B0A0",
        "text_subtle":  "#7A8278",
        "bull":         "#7BB069", "bear":     "#E15A4C",
        "wait":         "#E6B86E", "brand":    "#C49572",
        "accent":       "#D17B6B",
    },
    # 方舟風格 Phase 33.2 升級版（語意更清楚）
    # bull=綠（直覺正向）/ wait=黃（醒目注意）/ bear=紅 / brand=紫 / accent=黃
    "ark": {
        "bg_dark":      "#000000",  # 純黑
        "bg_card":      "#0F0F14",  # 接近黑（紫調）
        "bg_card_alt":  "#1A1A22",  # 深紫黑
        "line":         "#2A2A35",
        "text_main":    "#FFFFFF",
        "text_dim":     "#B0B4C0",  # 提亮（原 #888888 太暗）
        "text_subtle":  "#7B8090",  # 提亮（原 #555555 在黑底幾乎看不到）
        "bull":         "#22C55E",  # 🟢 綠 = 上漲/機會/正向
        "bear":         "#EF4444",  # 🔴 紅 = 警示/下跌
        "wait":         "#FBBF24",  # 🟡 亮黃 = 注意/接近觸發
        "brand":        "#A855F7",  # 🟣 紫 = 品牌光暈
        "accent":       "#FBBF24",  # 黃 = 數字主強調
    },
}

CURRENT_THEME = "ark"
C = THEMES[CURRENT_THEME]


# ─────────────────────────────────────────────
# Phase 33.2 — 6 色語意系統（所有卡通用）
# 用 hex 8-digit (RRGGBBAA) — LINE 不支援 rgba()
# ─────────────────────────────────────────────
SEMANTIC = {
    "必做":   "#EF4444",  # 🔴 緊急（賣 / 停損）
    "進行":   "#3B82F6",  # 🔵 已掛單、等成交
    "預警":   "#FBBF24",  # 🟡 接近觸發
    "警告":   "#F59E0B",  # 🟠 不該追 / 過熱
    "好":     "#22C55E",  # 🟢 入帳 / 機會
    "成績":   "#A855F7",  # 🟣 累計獲利
    "中性":   "#6B7280",  # ⚪ 無動作
}
SEMANTIC_BG = {
    "必做":   "#EF44441A",
    "進行":   "#3B82F61A",
    "預警":   "#FBBF241A",
    "警告":   "#F59E0B1A",
    "好":     "#22C55E1A",
    "成績":   "#A855F71A",
    "中性":   "#6B72801A",
}


def 語意框(語意: str, 內容: list, padding: str = "10px") -> dict:
    """
    Phase 33.2 共用 box — 帶語意色背景
    語意 ∈ {必做, 進行, 預警, 警告, 好, 成績, 中性}
    """
    return {
        "type": "box", "layout": "vertical", "spacing": "xs",
        "margin": "md", "paddingAll": padding,
        "backgroundColor": SEMANTIC_BG.get(語意, "#FFFFFF1A"),
        "cornerRadius": "8px",
        "contents": 內容,
    }


def 語意標題(語意: str, 文字內容: str, size: str = "md") -> dict:
    """區塊標題 — 用語意色"""
    return 文字(文字內容, size=size,
                color=SEMANTIC.get(語意, C["text_main"]),
                weight="bold")


def 切換主題(主題名: str) -> None:
    global CURRENT_THEME, C
    if 主題名 not in THEMES:
        raise ValueError(f"未知主題：{主題名}，可選：{list(THEMES.keys())}")
    CURRENT_THEME = 主題名
    C = THEMES[主題名]


# ─────────────────────────────────────────────
# 基礎元件
# ─────────────────────────────────────────────
def 文字(內容, **kwargs) -> dict:
    # LINE 規定 text 必須 non-empty string；空/None 一律 fallback " "
    if 內容 is None:
        內容 = " "
    if not isinstance(內容, str):
        內容 = str(內容)
    if not 內容:
        內容 = " "
    base = {"type": "text", "text": 內容, "color": C["text_main"]}
    base.update(kwargs)
    return base


def 標籤(文字內容: str, 背景色: str, 文字色: str = None) -> dict:
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": 背景色,
        "cornerRadius": "100px",
        "paddingAll": "5px",
        "paddingStart": "12px",
        "paddingEnd": "12px",
        "contents": [文字(文字內容, size="xs",
                          color=文字色 or C["bg_dark"],
                          weight="bold", align="center")],
        "flex": 0,
    }


def 進度條(百分比: float, 色: str, 高度: str = "6px",
            底色: str = None, 圓角: str = "100px") -> dict:
    百分比 = max(0, min(100, 百分比))
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": 底色 or C["line"],
        "cornerRadius": 圓角,
        "height": 高度,
        "contents": [{"type": "filler"}] if 百分比 <= 0 else [{
            "type": "box",
            "layout": "vertical",
            "backgroundColor": 色,
            "cornerRadius": 圓角,
            "height": 高度,
            "width": f"{百分比}%",
            "contents": [{"type": "filler"}],
        }],
    }


def 分隔線(色: str = None, 上下間距: str = "md") -> dict:
    return {"type": "separator", "color": 色 or C["line"], "margin": 上下間距}


# ─────────────────────────────────────────────
# ⭐ 統一儀表元件（核心 — 所有指標都用這個）
# ─────────────────────────────────────────────
def 統一儀表(名稱: str, 顯示值: str, 百分比: float, 顏色: str,
             副標: str = "", 大小: str = "md") -> dict:
    """
    所有大小的 gauge 都用這個元件，保持視覺語言一致。

    大小：
      mini  — 並排放底部用（多個一行）
      md    — 一行一個
      large — 整個卡片中央（大數字）
    """
    if 大小 == "large":
        數字_size = "5xl"
        標題_size = "sm"
        副標_size = "xxs"
        bar_height = "8px"
        spacing = "md"
    elif 大小 == "md":
        數字_size = "xl"
        標題_size = "sm"
        副標_size = "xxs"
        bar_height = "6px"
        spacing = "sm"
    else:  # mini
        數字_size = "md"
        標題_size = "xxs"
        副標_size = "xxs"
        bar_height = "4px"
        spacing = "xs"

    內容 = [
        文字(名稱, size=標題_size, color=C["text_dim"],
             align="center", weight="bold"),
    ]
    if 大小 == "large":
        內容.append({"type": "box", "layout": "vertical",
                     "spacing": "none", "contents": [
            文字(顯示值, size=數字_size, color=顏色,
                 weight="bold", align="center"),
        ]})
    else:
        內容.append(文字(顯示值, size=數字_size, color=顏色,
                         weight="bold", align="center"))

    內容.append(進度條(百分比, 顏色, bar_height))

    if 副標:
        內容.append(文字(副標, size=副標_size, color=C["text_subtle"],
                         align="center"))

    return {
        "type": "box",
        "layout": "vertical",
        "spacing": spacing,
        "alignItems": "center",
        "contents": 內容,
    }


def 迷你儀表水平列(項目清單: list[dict]) -> dict:
    """把多個迷你儀表並排成一行。
    項目清單: [{"名稱":..., "顯示值":..., "百分比":..., "顏色":..., "副標":...}, ...]
    """
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "md",
        "contents": [
            {**統一儀表(**項, 大小="mini"), "flex": 1}
            for 項 in 項目清單
        ],
    }


# ─────────────────────────────────────────────
# Header 共用（方舟頂部 tab 風格）
# ─────────────────────────────────────────────
def _卡片Header(主標題: str, 副標題: str, 右側標籤文字: str = "",
                右側標籤色: str = None) -> dict:
    右contents = []
    if 右側標籤文字:
        右contents = [標籤(右側標籤文字, 右側標籤色 or C["brand"],
                            文字色="#FFFFFF")]
    return {
        "type": "box",
        "layout": "horizontal",
        "backgroundColor": C["bg_card"],
        "paddingAll": "16px",
        "alignItems": "center",
        "contents": [
            {
                "type": "box",
                "layout": "vertical",
                "flex": 1,
                "contents": [
                    文字(主標題, size="lg", color=C["text_main"], weight="bold"),
                    文字(副標題, size="xxs", color=C["text_dim"]),
                ],
            },
            *右contents,
        ],
    }


# ─────────────────────────────────────────────
# 圖片版（Phase 2.6 真圓環，hero 顯示動態生成的 PNG）
# ─────────────────────────────────────────────
def 建構Enjoy主卡_圖片版(指數: dict, 日期文字: str,
                          圓環圖URL: str) -> dict:
    """Enjoy 主卡，hero 區顯示真圓環 PNG。body 留三大分項 + 情緒拆解。"""
    if 指數["總分"] >= 70:
        建議色 = C["bull"]
    elif 指數["總分"] >= 40:
        建議色 = C["wait"]
    else:
        建議色 = C["bear"]

    三大分項 = [
        {"名稱": "情緒 /35", "顯示值": f"{指數['情緒']['total']}",
         "百分比": (指數['情緒']['total'] / 35) * 100, "顏色": C["brand"]},
        {"名稱": "技術 /35", "顯示值": f"{指數['技術']['total']}",
         "百分比": (指數['技術']['total'] / 35) * 100, "顏色": C["accent"]},
        {"名稱": "基本 /30", "顯示值": f"{指數['基本']['total']}",
         "百分比": (指數['基本']['total'] / 30) * 100, "顏色": C["wait"]},
    ]
    情緒分項 = _計算情緒分配對應(指數)

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("L.I.S 風控運算", 日期文字, "LIVE", C["brand"]),
        "hero": {
            "type": "image",
            "url": 圓環圖URL,
            "size": "full",
            "aspectRatio": "1:1",
            "aspectMode": "fit",
            "backgroundColor": C["bg_dark"],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "lg",
            "contents": [
                # 建議文案（圖內已有大數字 + 狀態，這裡補一句話）
                文字(指數["建議文案"], size="sm", color=C["text_dim"],
                     align="center", wrap=True),
                分隔線(上下間距="md"),
                文字("三大分項", size="xs", color=C["text_dim"], weight="bold"),
                迷你儀表水平列(三大分項),
                分隔線(上下間距="lg"),
                文字("情緒拆解", size="xs", color=C["text_dim"], weight="bold"),
                迷你儀表水平列(情緒分項[:3]),
                {"type": "box", "layout": "vertical", "margin": "md",
                 "contents": [迷你儀表水平列(情緒分項[3:])]},
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body":   {"backgroundColor": C["bg_dark"]},
                   "hero":   {"backgroundColor": C["bg_dark"]}},
    }


def 建構風險指針卡_圖片版(vix值: Optional[float],
                            半圓圖URL: str) -> dict:
    """VIX 風險卡，hero 顯示真半圓指針 PNG。"""
    狀態, 顏色, _, 副標 = _VIX對應(vix值)
    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("⚡ 大盤風險指針",
                              "VIX Volatility Gauge",
                              狀態, 顏色),
        "hero": {
            "type": "image",
            "url": 半圓圖URL,
            "size": "full",
            "aspectRatio": "7:6",  # 跟生成圖的比例對齊
            "aspectMode": "fit",
            "backgroundColor": C["bg_dark"],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": C["bg_card"],
                    "cornerRadius": "12px",
                    "paddingAll": "12px",
                    "contents": [
                        文字("📌 系統解讀", size="xs",
                             color=C["text_dim"], weight="bold"),
                        文字(副標, size="sm",
                             color=C["text_main"], margin="sm", wrap=True),
                    ],
                },
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body":   {"backgroundColor": C["bg_dark"]},
                   "hero":   {"backgroundColor": C["bg_dark"]}},
    }


def 建構資金規劃卡_圖片版(規劃: dict, 圓環圖URL: str) -> dict:
    """資金規劃卡，hero 顯示真圓環。"""
    建議色 = (C["bull"] if 規劃["建議"] == "BE HAPPY"
              else C["wait"] if 規劃["建議"] == "WAIT"
              else C["bear"])
    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("💰 今日資金規劃",
                              f"火力 {規劃['火力比例']}%",
                              規劃["建議"], 建議色),
        "hero": {
            "type": "image",
            "url": 圓環圖URL,
            "size": "full",
            "aspectRatio": "1:1",
            "aspectMode": "fit",
            "backgroundColor": C["bg_dark"],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                _資金明細列("股票配置上限", f"NT$ {規劃['股票配置']:,.0f}"),
                _資金明細列("目前現金", f"NT$ {規劃['目前現金']:,.0f}"),
                _資金明細列("最小現金保留", f"NT$ {規劃['最小現金保留']:,.0f}",
                             顏色=C["text_subtle"]),
                _資金明細列("單檔上限 (20%)",
                             f"NT$ {規劃['單檔上限_twd']:,.0f}"),
                _資金明細列("匯率 USD/TWD",
                             f"{規劃['USD_TWD']}", 顏色=C["text_subtle"]),
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": C["bg_card"],
                    "cornerRadius": "12px",
                    "paddingAll": "12px",
                    "margin": "md",
                    "contents": [
                        文字("📌 操作建議", size="xs",
                             color=C["text_dim"], weight="bold"),
                        文字(_資金建議文案(規劃), size="sm",
                             color=C["text_main"], margin="sm", wrap=True),
                    ],
                },
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body":   {"backgroundColor": C["bg_dark"]},
                   "hero":   {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 1. Enjoy Index 主卡（方舟版）
# ─────────────────────────────────────────────
def _計算情緒分配對應(指數: dict) -> list[dict]:
    """把情緒拆解轉成 5 個迷你儀表項目（同樣式並排）。"""
    滿分對照 = {"F&G": 10, "VIX": 5, "加權": 10, "櫃買": 5, "費半": 5}
    結果 = []
    for 名, 分, 原值 in 指數["情緒"]["breakdown"]:
        滿分 = 滿分對照.get(名, 10)
        百分比 = (分 / 滿分) * 100 if 滿分 > 0 else 0
        # 統一邏輯：「給分高 = 進場機會 = 黃色」
        if 百分比 >= 60:
            色 = C["bull"]
        elif 百分比 >= 30:
            色 = C["wait"]
        else:
            色 = C["bear"]
        結果.append({
            "名稱": 名,
            "顯示值": f"{原值:.1f}" if 原值 is not None else "—",
            "百分比": 百分比,
            "顏色": 色,
            "副標": f"+{分}",
        })
    return 結果


def 建構Enjoy主卡(指數: dict, 日期文字: str) -> dict:
    if 指數["總分"] >= 70:
        建議色 = C["bull"]
    elif 指數["總分"] >= 40:
        建議色 = C["wait"]
    else:
        建議色 = C["bear"]

    指針位置 = max(2, min(98, 指數["總分"]))

    # 三大分項（mini gauge 同樣式並排）
    三大分項 = [
        {"名稱": "情緒 /35", "顯示值": f"{指數['情緒']['total']}",
         "百分比": (指數['情緒']['total'] / 35) * 100, "顏色": C["brand"]},
        {"名稱": "技術 /35", "顯示值": f"{指數['技術']['total']}",
         "百分比": (指數['技術']['total'] / 35) * 100, "顏色": C["accent"]},
        {"名稱": "基本 /30", "顯示值": f"{指數['基本']['total']}",
         "百分比": (指數['基本']['total'] / 30) * 100, "顏色": C["wait"]},
    ]

    # 情緒拆解 5 個（mini gauge 並排）
    情緒分項 = _計算情緒分配對應(指數)

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("L.I.S 風控運算", 日期文字, "LIVE", C["brand"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "lg",
            "contents": [
                # 中央：超大 Enjoy Index（仿方舟 62.3%）
                {
                    "type": "box",
                    "layout": "vertical",
                    "alignItems": "center",
                    "contents": [
                        文字("Enjoy Index", size="sm",
                             color=C["text_dim"], align="center", weight="bold"),
                        {
                            "type": "box",
                            "layout": "baseline",
                            "justifyContent": "center",
                            "margin": "sm",
                            "contents": [
                                文字(f"{指數['總分']}", size="5xl",
                                     color=建議色, weight="bold", flex=0),
                                文字(" / 100", size="md",
                                     color=C["text_dim"], flex=0),
                            ],
                        },
                        # 指針帶
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "alignItems": "flex-end",
                            "margin": "lg",
                            "contents": [
                                {"type": "filler", "flex": max(1, int(指針位置))},
                                文字("▼", size="lg", color=建議色, flex=0),
                                {"type": "filler", "flex": max(1, int(100 - 指針位置))},
                            ],
                        },
                        # 紅黃綠三段
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "none",
                            "height": "8px",
                            "cornerRadius": "100px",
                            "contents": [
                                {"type": "box", "layout": "vertical",
                                 "flex": 40, "backgroundColor": C["bear"],
                                 "contents": [{"type": "filler"}]},
                                {"type": "box", "layout": "vertical",
                                 "flex": 30, "backgroundColor": C["wait"],
                                 "contents": [{"type": "filler"}]},
                                {"type": "box", "layout": "vertical",
                                 "flex": 30, "backgroundColor": C["bull"],
                                 "contents": [{"type": "filler"}]},
                            ],
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "sm",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 40,
                                 "contents": [文字("HOLD", size="xxs",
                                                    color=C["text_subtle"], align="start")]},
                                {"type": "box", "layout": "vertical", "flex": 30,
                                 "contents": [文字("WAIT", size="xxs",
                                                    color=C["text_subtle"], align="center")]},
                                {"type": "box", "layout": "vertical", "flex": 30,
                                 "contents": [文字("BE HAPPY", size="xxs",
                                                    color=C["text_subtle"], align="end")]},
                            ],
                        },
                        # 建議藥丸
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "justifyContent": "center",
                            "margin": "lg",
                            "contents": [標籤(指數["建議"], 建議色, 文字色="#000000")],
                        },
                        文字(指數["建議文案"], size="xs", color=C["text_dim"],
                             align="center", margin="md", wrap=True),
                    ],
                },
                分隔線(上下間距="lg"),
                # 三大分項（迷你儀表並排）
                迷你儀表水平列(三大分項),
                分隔線(上下間距="lg"),
                # 情緒拆解 5 個（迷你儀表並排，5 個會擠 → 改成標題 + 2行）
                文字("情緒拆解", size="sm", color=C["text_dim"], weight="bold"),
                迷你儀表水平列(情緒分項[:3]),
                {"type": "box", "layout": "vertical", "margin": "md",
                 "contents": [迷你儀表水平列(情緒分項[3:])]},
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 2. VIX 風險指針卡（同統一儀表語言）
# ─────────────────────────────────────────────
def _VIX對應(vix值: Optional[float]) -> tuple[str, str, float, str]:
    """回傳 (狀態, 顏色, 條寬度, 副標)"""
    if vix值 is None:
        return ("—", C["text_dim"], 0, "無 VIX 資料")
    寬 = max(2, min(98, vix值 * 2))
    if vix值 >= 40:
        return ("極度恐慌", C["bull"], 寬, "黃金錯殺機會，分批進場")
    if vix值 >= 30:
        return ("恐慌", C["bull"], 寬, "進場機會浮現，逢低布局")
    if vix值 >= 20:
        return ("警戒", C["wait"], 寬, "波動加劇，控制部位")
    if vix值 >= 15:
        return ("平穩", C["text_dim"], 寬, "中性區間，照計畫操作")
    return ("自滿", C["bear"], 寬, "市場過度樂觀，風險偏高")


def 建構風險指針卡(vix值: Optional[float]) -> dict:
    狀態, 顏色, 指針位置, 副標 = _VIX對應(vix值)

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("⚡ 大盤風險指針",
                              "VIX Volatility Gauge",
                              狀態, 顏色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "lg",
            "contents": [
                # 中央大數字
                {
                    "type": "box",
                    "layout": "vertical",
                    "alignItems": "center",
                    "contents": [
                        文字("VIX", size="sm",
                             color=C["text_dim"], weight="bold"),
                        {
                            "type": "box",
                            "layout": "baseline",
                            "justifyContent": "center",
                            "margin": "sm",
                            "contents": [
                                文字(f"{vix值}" if vix值 is not None else "—",
                                     size="5xl", color=顏色, weight="bold", flex=0),
                            ],
                        },
                    ],
                },
                # 指針 ▼
                {
                    "type": "box",
                    "layout": "horizontal",
                    "alignItems": "flex-end",
                    "margin": "lg",
                    "contents": [
                        {"type": "filler", "flex": max(1, int(指針位置))},
                        文字("▼", size="xl", color=顏色, flex=0),
                        {"type": "filler", "flex": max(1, int(100 - 指針位置))},
                    ],
                },
                # 五段彩帶
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "none",
                    "height": "12px",
                    "cornerRadius": "100px",
                    "contents": [
                        {"type": "box", "layout": "vertical", "flex": 30,
                         "backgroundColor": C["bear"],
                         "contents": [{"type": "filler"}]},
                        {"type": "box", "layout": "vertical", "flex": 10,
                         "backgroundColor": C["wait"],
                         "contents": [{"type": "filler"}]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "backgroundColor": C["text_dim"],
                         "contents": [{"type": "filler"}]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "backgroundColor": C["bull"],
                         "contents": [{"type": "filler"}]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "backgroundColor": C["bull"],
                         "contents": [{"type": "filler"}]},
                    ],
                },
                # 區段名稱列
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "box", "layout": "vertical", "flex": 30,
                         "contents": [文字("自滿", size="xxs",
                                            color=C["text_subtle"], align="center")]},
                        {"type": "box", "layout": "vertical", "flex": 10,
                         "contents": [文字("平穩", size="xxs",
                                            color=C["text_subtle"], align="center")]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "contents": [文字("警戒", size="xxs",
                                            color=C["text_subtle"], align="center")]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "contents": [文字("恐慌", size="xxs",
                                            color=C["text_subtle"], align="center")]},
                        {"type": "box", "layout": "vertical", "flex": 20,
                         "contents": [文字("極恐", size="xxs",
                                            color=C["text_subtle"], align="center")]},
                    ],
                },
                # 解讀區塊
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": C["bg_card"],
                    "cornerRadius": "12px",
                    "paddingAll": "12px",
                    "margin": "lg",
                    "contents": [
                        文字("📌 系統解讀", size="xs",
                             color=C["text_dim"], weight="bold"),
                        文字(副標, size="sm", color=C["text_main"],
                             margin="sm", wrap=True),
                    ],
                },
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 3. 大盤指標卡（統一儀表語言）
# ─────────────────────────────────────────────
def _指數對應顏色(rsi: Optional[float]) -> tuple[str, str, float]:
    """RSI → (狀態, 顏色, 寬度)。"""
    if rsi is None:
        return ("—", C["text_subtle"], 0)
    if rsi >= 75:
        return ("過熱", C["bear"], min(100, rsi))
    if rsi >= 65:
        return ("偏熱", C["wait"], min(100, rsi))
    if rsi >= 45:
        return ("中性", C["text_dim"], rsi)
    if rsi >= 35:
        return ("偏弱", C["bull"], rsi)
    return ("錯殺", C["accent"], rsi)


def _格式化數字(數值: float) -> str:
    if 數值 is None:
        return "—"
    if 數值 >= 1000:
        return f"{數值:,.0f}"
    return f"{數值:.2f}"


def 建構大盤指標卡(指數結果: list[dict]) -> dict:
    指對應 = {(r.get("original_symbol") or r.get("symbol")): r for r in 指數結果}

    分組 = [
        ("台股", [("^TWII", "加權"), ("^TWOII", "櫃買")]),
        ("美股", [("^GSPC", "S&P 500"), ("^IXIC", "那斯達克")]),
        ("半導體", [("^SOX", "費城半導體")]),
    ]

    body_contents = []
    for 組名, items in 分組:
        # 分組標題
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "lg",
            "alignItems": "center",
            "contents": [
                {"type": "box", "layout": "vertical", "width": "3px",
                 "height": "12px", "backgroundColor": C["accent"],
                 "contents": [{"type": "filler"}]},
                文字(組名.upper(), size="xs", color=C["text_dim"],
                     weight="bold", flex=1),
            ],
        })
        # 每個指數一個迷你儀表 row
        for symbol, 顯示名 in items:
            項 = 指對應.get(symbol)
            if 項 is None or "error" in (項 or {}):
                continue
            狀態, 色, 寬 = _指數對應顏色(項.get("rsi14"))
            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "margin": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            文字(顯示名, size="sm", color=C["text_main"],
                                 weight="bold", flex=5),
                            文字(_格式化數字(項.get("close")),
                                 size="lg", color=C["text_main"],
                                 weight="bold", flex=4, align="end"),
                        ],
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "alignItems": "center",
                        "spacing": "sm",
                        "contents": [
                            {"type": "box", "layout": "vertical", "flex": 7,
                             "contents": [進度條(寬, 色, "6px")]},
                            文字(f"RSI {項.get('rsi14')}", size="xxs",
                                 color=C["text_dim"], flex=3, align="end"),
                            {**標籤(狀態, 色), "flex": 2},
                        ],
                    },
                ],
            })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📊 市場大盤指標", "Taiwan + US + Semi",
                              f"{len([x for x in 指數結果 if 'error' not in x])}",
                              C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "contents": body_contents,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 4. 個股/ETF 區域卡（美股/台股/ETF 用同一個 builder）
# ─────────────────────────────────────────────
def _訊號標籤(r: dict) -> Optional[dict]:
    """根據個股的訊號旗標，回傳對應的彩色標籤。"""
    if r.get("shakeout_low"):
        return 標籤("🔥 震盪低點", C["accent"])
    if r.get("bull_signal"):
        return 標籤("🟢 金叉", C["bull"])
    if r.get("shit_signal"):
        return 標籤("🔴 錯殺", C["bear"])
    return None


def _個股簡列(r: dict, 預算_twd: Optional[float] = None,
              USD_TWD: float = 32.0) -> dict:
    """單檔的緊湊一行展示。"""
    if "error" in r:
        return {
            "type": "box",
            "layout": "vertical",
            "margin": "sm",
            "contents": [
                文字(f"{r.get('name', '')} ({r.get('symbol')})",
                     size="xs", color=C["text_dim"]),
                文字(f"⚠️ {r['error']}", size="xxs", color=C["bear"]),
            ],
        }

    名 = r.get("name") or r.get("symbol")
    rsi = r.get("rsi14")
    close = r.get("close")
    is_tw = r["symbol"].endswith(".TW") or r["symbol"].endswith(".TWO")
    幣 = "" if is_tw else "$"

    # 顏色：RSI 越熱 → 越紅
    if rsi is not None:
        if rsi >= 75:
            rsi色 = C["bear"]
        elif rsi >= 65:
            rsi色 = C["wait"]
        elif rsi < 35:
            rsi色 = C["accent"]
        else:
            rsi色 = C["text_dim"]
    else:
        rsi色 = C["text_dim"]

    第一列contents = [
        文字(名, size="sm", color=C["text_main"], weight="bold", flex=4),
        文字(f"{幣}{close}", size="sm", color=C["text_main"],
             weight="bold", flex=3, align="end"),
        文字(f"R{rsi}" if rsi is not None else "—",
             size="xs", color=rsi色, flex=2, align="end"),
    ]

    rows = [{"type": "box", "layout": "baseline", "contents": 第一列contents}]

    # 訊號標籤 row
    訊號 = _訊號標籤(r)
    if 訊號 is not None:
        # 加上建議股數（震盪低點時才算）
        建議文字 = None
        if r.get("shakeout_low") and 預算_twd:
            股數計算 = capital_planner.計算建議股數(
                r["symbol"], close or 0, 預算_twd, USD_TWD)
            建議文字 = f"建議 {股數計算['註記']}"

        sub_contents = [訊號]
        if 建議文字:
            sub_contents.append(
                文字(建議文字, size="xxs", color=C["bull"], flex=4, align="end"))
        else:
            sub_contents.append({"type": "filler", "flex": 4})

        rows.append({
            "type": "box",
            "layout": "horizontal",
            "alignItems": "center",
            "margin": "xs",
            "contents": sub_contents,
        })

    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "none",
        "margin": "md",
        "paddingBottom": "md",
        "borderColor": C["line"],
        "borderWidth": "0px",
        "contents": rows,
    }


def 建構區域卡(區域: dict, 區域標題: str, 副標題: str,
               預算_twd: Optional[float] = None,
               USD_TWD: float = 32.0,
               最多顯示: int = 30) -> dict:
    """
    通用區域卡（給美股 / 台股 / ETF 三個都用）。
    區域 = technical.掃描全部觀察清單()["regions"][區id]

    顯示順序：
      1. 觸發訊號的（震盪低點 / 金叉 / 錯殺）置頂
      2. 其他按 RSI 由低到高排（最弱的先看）
    """
    items = 區域["items"]
    有效 = [r for r in items if "error" not in r]
    錯誤 = [r for r in items if "error" in r]

    # 訊號分類
    震盪低點清單 = [r for r in 有效 if r.get("shakeout_low")]
    金叉清單   = [r for r in 有效 if r.get("bull_signal") and not r.get("shakeout_low")]
    錯殺清單   = [r for r in 有效 if r.get("shit_signal") and not r.get("shakeout_low")]
    觸發 = 震盪低點清單 + 金叉清單 + 錯殺清單
    觸發symbols = {r["symbol"] for r in 觸發}

    # 其他按 RSI 由低→高排序
    其他 = [r for r in 有效 if r["symbol"] not in 觸發symbols]
    其他.sort(key=lambda r: (r.get("rsi14") or 50))

    body_contents = []

    # 摘要 row
    summary = (
        f"{len(有效)} 檔｜🔥{len(震盪低點清單)} 震盪低點 ｜"
        f"🟢{len(金叉清單)} 金叉 ｜🔴{len(錯殺清單)} 錯殺"
    )
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "backgroundColor": C["bg_card"],
        "cornerRadius": "8px",
        "paddingAll": "10px",
        "contents": [
            文字(summary, size="xs", color=C["text_dim"], wrap=True),
        ],
    })

    # 觸發訊號優先顯示
    if 觸發:
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "lg",
            "alignItems": "center",
            "contents": [
                {"type": "box", "layout": "vertical", "width": "3px",
                 "height": "12px", "backgroundColor": C["accent"],
                 "contents": [{"type": "filler"}]},
                文字("觸發訊號", size="xs",
                     color=C["text_dim"], weight="bold", flex=1),
            ],
        })
        for r in 觸發[:8]:
            body_contents.append(_個股簡列(r, 預算_twd, USD_TWD))

    # 其他清單
    if 其他:
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "lg",
            "alignItems": "center",
            "contents": [
                {"type": "box", "layout": "vertical", "width": "3px",
                 "height": "12px", "backgroundColor": C["text_subtle"],
                 "contents": [{"type": "filler"}]},
                文字(f"全清單（依 RSI 由弱至強）", size="xs",
                     color=C["text_dim"], weight="bold", flex=1),
            ],
        })
        for r in 其他[:最多顯示]:
            body_contents.append(_個股簡列(r))

    # 錯誤項
    if 錯誤:
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "lg",
            "alignItems": "center",
            "contents": [
                文字(f"⚠️ {len(錯誤)} 檔資料缺漏（不影響其他項）",
                     size="xxs", color=C["text_subtle"]),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header(區域標題, 副標題,
                              f"{len(觸發)}/{len(有效)}",
                              C["accent"] if 觸發 else C["text_subtle"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body_contents,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 5. 資金規劃卡（新功能：根據資金水位算建議部位）
# ─────────────────────────────────────────────
def 建構資金規劃卡(規劃: dict) -> dict:
    """capital_planner.計算今日資金規劃() 的結果視覺化。"""
    建議色 = (C["bull"] if 規劃["建議"] == "BE HAPPY"
              else C["wait"] if 規劃["建議"] == "WAIT"
              else C["bear"])

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("💰 今日資金規劃",
                              f"火力 {規劃['火力比例']}%",
                              規劃["建議"], 建議色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "lg",
            "contents": [
                # 中央大數字：今日子彈
                {
                    "type": "box",
                    "layout": "vertical",
                    "alignItems": "center",
                    "contents": [
                        文字("可動用子彈 (NT$)", size="sm",
                             color=C["text_dim"], weight="bold"),
                        文字(f"{規劃['今日可動用子彈_twd']:,.0f}",
                             size="4xl", color=建議色,
                             weight="bold", align="center", margin="sm"),
                        # 火力比例條
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "none",
                            "height": "8px",
                            "cornerRadius": "100px",
                            "margin": "lg",
                            "contents": [
                                {"type": "box", "layout": "vertical",
                                 "flex": max(1, 規劃["火力比例"]),
                                 "backgroundColor": 建議色,
                                 "contents": [{"type": "filler"}]},
                                {"type": "box", "layout": "vertical",
                                 "flex": max(1, 100 - 規劃["火力比例"]),
                                 "backgroundColor": C["line"],
                                 "contents": [{"type": "filler"}]},
                            ],
                        },
                    ],
                },
                分隔線(上下間距="lg"),
                # 細項說明
                _資金明細列("股票配置上限", f"NT$ {規劃['股票配置']:,.0f}"),
                _資金明細列("目前現金", f"NT$ {規劃['目前現金']:,.0f}"),
                _資金明細列("最小現金保留", f"NT$ {規劃['最小現金保留']:,.0f}",
                             顏色=C["text_subtle"]),
                _資金明細列("單檔上限 (20%)",
                             f"NT$ {規劃['單檔上限_twd']:,.0f}"),
                _資金明細列("匯率 USD/TWD",
                             f"{規劃['USD_TWD']}", 顏色=C["text_subtle"]),
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": C["bg_card"],
                    "cornerRadius": "12px",
                    "paddingAll": "12px",
                    "margin": "lg",
                    "contents": [
                        文字("📌 操作建議", size="xs",
                             color=C["text_dim"], weight="bold"),
                        文字(_資金建議文案(規劃), size="sm",
                             color=C["text_main"], margin="sm", wrap=True),
                    ],
                },
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def _資金明細列(標題: str, 數值: str, 顏色: str = None) -> dict:
    return {
        "type": "box",
        "layout": "baseline",
        "spacing": "sm",
        "margin": "sm",
        "contents": [
            文字(標題, size="xs", color=C["text_dim"], flex=3),
            文字(數值, size="sm",
                 color=顏色 or C["text_main"], weight="bold",
                 flex=4, align="end"),
        ],
    }


def _資金建議文案(規劃: dict) -> str:
    建議 = 規劃["建議"]
    if 建議 == "BE HAPPY":
        return "市場呈現黃金錯殺，可動用 70% 火力分批進場，按單檔上限分配。"
    if 建議 == "WAIT":
        return "市場訊號不明確，只動用 30% 火力試水溫，等更明確訊號再加碼。"
    return "市場情緒過熱或訊號不足，只動用 10% 火力保留子彈，等待錯殺機會。"


# ─────────────────────────────────────────────
# 8. KOL 觀點卡（Phase 2.8）
# ─────────────────────────────────────────────
def 建構KOL共識卡(kol結果: dict) -> dict:
    """所有 KOL 中被多位提到的標的（共識）+ 命中 watchlist 高亮。"""
    命中 = kol結果.get("watchlist_hits", {})
    多人共識 = {k: v for k, v in 命中.items() if v >= 2}
    單人提及 = {k: v for k, v in 命中.items() if v == 1}

    # 統計 KOL 成功 / 失敗 / 無觀點
    kols = kol結果.get("kols", [])
    成功 = [k for k in kols if "抓取失敗" not in k.get("summary", "")
              and "無公開觀點" not in k.get("summary", "")]
    失敗 = [k for k in kols if "抓取失敗" in k.get("summary", "")]
    無觀點 = [k for k in kols if "無公開觀點" in k.get("summary", "")
              and "抓取失敗" not in k.get("summary", "")]

    body內容 = []
    # KOL 統計列
    body內容.append({
        "type": "box",
        "layout": "horizontal",
        "backgroundColor": C["bg_card"],
        "cornerRadius": "8px",
        "paddingAll": "10px",
        "contents": [
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                文字(f"{len(成功)}", size="lg", color=C["bull"],
                     weight="bold", align="center"),
                文字("有觀點", size="xxs", color=C["text_dim"], align="center"),
            ]},
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                文字(f"{len(無觀點)}", size="lg", color=C["text_dim"],
                     weight="bold", align="center"),
                文字("無更新", size="xxs", color=C["text_dim"], align="center"),
            ]},
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                文字(f"{len(失敗)}", size="lg",
                     color=C["bear"] if 失敗 else C["text_dim"],
                     weight="bold", align="center"),
                文字("抓取失敗", size="xxs", color=C["text_dim"], align="center"),
            ]},
        ],
    })
    body內容.append(分隔線(上下間距="md"))
    if 多人共識:
        body內容.append(文字("🔥 多位 KOL 共識（值得關注）",
                              size="sm", color=C["bull"], weight="bold"))
        for 標的, n in 多人共識.items():
            body內容.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "margin": "sm",
                "contents": [
                    文字(標的, size="sm", color=C["text_main"],
                         weight="bold", flex=5),
                    {**標籤(f"{n} 位提到", C["bull"]), "flex": 0},
                ],
            })
        body內容.append(分隔線(上下間距="md"))

    if 單人提及:
        body內容.append(文字("📌 單人提及（觀察候選）",
                              size="sm", color=C["text_dim"], weight="bold",
                              margin="md"))
        for 標的, n in list(單人提及.items())[:10]:
            body內容.append(文字(f"   • {標的}",
                                  size="xs", color=C["text_dim"],
                                  margin="xs"))

    if not 多人共識 and not 單人提及:
        body內容.append(文字("今日無 KOL 提到 watchlist 內標的",
                              size="sm", color=C["text_dim"],
                              align="center", wrap=True))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎯 KOL 共識榜", "今日多位 KOL 提及",
                              f"{len(命中)} 檔", C["bull"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構單一KOL卡(kol: dict) -> dict:
    """單一 KOL 的觀點摘要卡。"""
    summary = kol.get("summary", "")
    符號s = kol.get("mentioned_symbols", [])
    # 截斷過長
    if len(summary) > 1500:
        summary = summary[:1500] + "..."

    body內容 = [
        文字(summary, size="sm", color=C["text_main"], wrap=True),
    ]
    if 符號s:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字("📌 提及標的",
                              size="xs", color=C["text_dim"],
                              weight="bold", margin="sm"))
        body內容.append(文字(
            "、".join(符號s[:15]),
            size="xs", color=C["accent"], wrap=True, margin="xs"
        ))

    platform = kol.get("platform", "")
    handle = kol.get("handle", "")
    副標 = f"{platform}".strip()
    if handle:
        副標 += f" · {handle}"
    if not 副標:
        副標 = "KOL 觀點"

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header(f"📱 {kol['name']}", 副標,
                              "AI 摘", C["brand"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構KOL_Carousel(kol結果: dict) -> dict:
    """組合：共識卡 + 各 KOL 卡。
    跳過：無公開觀點、Gemini 抓取失敗的 KOL。
    """
    bubbles = [建構KOL共識卡(kol結果)]
    for kol in kol結果.get("kols", []):
        s = kol.get("summary", "")
        # 跳過「無公開觀點」短回應
        if "無公開觀點" in s and len(s) < 50:
            continue
        # 跳過抓取失敗的（Gemini grounding 速率限制等）
        if "抓取失敗" in s or "ClientError" in s:
            continue
        bubbles.append(建構單一KOL卡(kol))
    return {"type": "carousel", "contents": bubbles[:12]}


# ─────────────────────────────────────────────
# 10. 事件警示卡（Phase 4.5）
# ─────────────────────────────────────────────
def 建構事件警示卡(diff: dict, 時段標籤: str = "") -> dict:
    """只在有新訊號時呼叫，列出新出現的觸發訊號。"""
    rows = []

    if diff["new_shakeout"]:
        rows.append(文字("🔥 新增震盪低點", size="sm",
                          color=C["accent"], weight="bold"))
        for r in diff["new_shakeout"]:
            name = r.get("name") or r["symbol"]
            rows.append(文字(
                f"   • {name} ({r['symbol']})  RSI {r.get('rsi14')}",
                size="xs", color=C["text_main"], wrap=True
            ))
        rows.append(分隔線(上下間距="md"))

    if diff["new_bull"]:
        rows.append(文字("🟢 新增 MACD 金叉", size="sm",
                          color=C["bull"], weight="bold"))
        for r in diff["new_bull"]:
            name = r.get("name") or r["symbol"]
            rows.append(文字(
                f"   • {name} ({r['symbol']})  ${r.get('close')}",
                size="xs", color=C["text_main"], wrap=True
            ))
        rows.append(分隔線(上下間距="md"))

    if diff["new_shit"]:
        rows.append(文字("🔴 新增錯殺低檔", size="sm",
                          color=C["bear"], weight="bold"))
        for r in diff["new_shit"]:
            name = r.get("name") or r["symbol"]
            rows.append(文字(
                f"   • {name} ({r['symbol']})  RSI {r.get('rsi14')}",
                size="xs", color=C["text_main"], wrap=True
            ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header(f"⚡ 新訊號警示", 時段標籤 or "事件觸發",
                              "NEW", C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": rows,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 9. ETF 布局建議卡（Phase 5 — 方舟級）
# ─────────────────────────────────────────────
def 建構ETF布局總覽卡(etf結果: list[dict], 預算文字: str = "") -> dict:
    """總覽卡：列出買方積極 + 折價深的 Top ETF。"""
    # 找買方積極（外盤 >= 60）的 ETF
    買方積極 = sorted(
        [r for r in etf結果 if r["盤比"]["外盤比"] and r["盤比"]["外盤比"] >= 60],
        key=lambda r: -r["盤比"]["外盤比"]
    )[:5]
    # 找賣方積極（內盤 >= 60）→ 警示，別買
    賣方積極 = sorted(
        [r for r in etf結果 if r["盤比"]["內盤比"] and r["盤比"]["內盤比"] >= 60],
        key=lambda r: -r["盤比"]["內盤比"]
    )[:3]

    body內容 = []

    if 預算文字:
        body內容.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_card"],
            "cornerRadius": "8px",
            "paddingAll": "10px",
            "contents": [
                文字(預算文字, size="xs", color=C["text_dim"], align="center"),
            ],
        })

    if 買方積極:
        body內容.append(文字("🟢 買方積極（值得布局）",
                              size="sm", color=C["bull"], weight="bold",
                              margin="lg"))
        for r in 買方積極:
            body內容.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "margin": "sm",
                "contents": [
                    文字(f"{r['name']}", size="xs",
                         color=C["text_main"], weight="bold", flex=5),
                    文字(f"外盤 {r['盤比']['外盤比']}%", size="xs",
                         color=C["bull"], align="end", flex=3),
                    文字(f"${r['bid_top']}", size="xs",
                         color=C["text_dim"], align="end", flex=2),
                ],
            })

    if 賣方積極:
        body內容.append(文字("🔴 賣方積極（先觀望）",
                              size="sm", color=C["bear"], weight="bold",
                              margin="lg"))
        for r in 賣方積極:
            body內容.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "margin": "sm",
                "contents": [
                    文字(f"{r['name']}", size="xs",
                         color=C["text_main"], weight="bold", flex=5),
                    文字(f"內盤 {r['盤比']['內盤比']}%", size="xs",
                         color=C["bear"], align="end", flex=3),
                    文字(f"${r['bid_top']}", size="xs",
                         color=C["text_dim"], align="end", flex=2),
                ],
            })

    body內容.append(分隔線(上下間距="md"))
    body內容.append(文字("← 滑動看個別 ETF 詳細五檔報價",
                          size="xxs", color=C["text_subtle"], align="center"))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("💎 ETF 布局即時",
                              f"{len(etf結果)} 檔 · 證交所即時資料",
                              "LIVE", C["bull"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構單檔ETF五檔卡(r: dict) -> dict:
    """單檔 ETF 詳細卡：五檔報價 + 內外盤 + 建議掛單。"""
    盤比 = r["盤比"]
    建議 = r["建議掛單"]

    # 五檔報價列（外盤紅 / 內盤綠，跟方舟一樣）
    買價list = r["bid_prices"]
    賣價list = r["ask_prices"]
    買量list = r["bid_volumes"]
    賣量list = r["ask_volumes"]

    五檔行 = []
    for i in range(min(5, len(買價list), len(賣價list))):
        買量 = 買量list[i] if i < len(買量list) else 0
        賣量 = 賣量list[i] if i < len(賣量list) else 0
        買價 = 買價list[i]
        賣價 = 賣價list[i]
        五檔行.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                文字(f"{買量}", size="xs", color=C["bear"],
                     flex=2, align="end"),
                文字(f"{買價}", size="xs", color=C["bear"],
                     flex=3, align="end", weight="bold"),
                文字(f"{賣價}", size="xs", color=C["bull"],
                     flex=3, align="start", weight="bold"),
                文字(f"{賣量}", size="xs", color=C["bull"],
                     flex=2, align="start"),
            ],
        })

    # 內外盤比 視覺化（紅綠分段）
    內 = 盤比["內盤比"] or 0
    外 = 盤比["外盤比"] or 0
    內外盤條 = {
        "type": "box",
        "layout": "horizontal",
        "height": "12px",
        "cornerRadius": "100px",
        "contents": [
            {"type": "box", "layout": "vertical",
             "flex": max(1, int(內)), "backgroundColor": C["bear"],
             "contents": [{"type": "filler"}]},
            {"type": "box", "layout": "vertical",
             "flex": max(1, int(外)), "backgroundColor": C["bull"],
             "contents": [{"type": "filler"}]},
        ],
    }

    body內容 = [
        # 上方：市價 / 中價
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                    文字("市價", size="xxs", color=C["text_dim"]),
                    文字(f"{r.get('last_price') or '—'}", size="lg",
                         color=C["text_main"], weight="bold"),
                ]},
                {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                    文字("中價", size="xxs", color=C["text_dim"], align="end"),
                    文字(f"{r['mid_price']}", size="lg",
                         color=C["accent"], weight="bold", align="end"),
                ]},
            ],
        },
        分隔線(上下間距="md"),

        # 五檔報價標題
        文字("📊 五檔報價", size="sm",
             color=C["text_dim"], weight="bold"),
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "xs",
            "contents": [
                文字("委買量", size="xxs", color=C["text_subtle"], flex=2, align="end"),
                文字("委買價", size="xxs", color=C["text_subtle"], flex=3, align="end"),
                文字("委賣價", size="xxs", color=C["text_subtle"], flex=3, align="start"),
                文字("委賣量", size="xxs", color=C["text_subtle"], flex=2, align="start"),
            ],
        },
        *五檔行,
        分隔線(上下間距="md"),

        # 內外盤比
        文字(f"內外盤比  {盤比['判讀']}", size="sm",
             color=C["text_main"], weight="bold"),
        內外盤條,
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "xs",
            "contents": [
                文字(f"內 {內}% （{盤比['內盤量']:,}）", size="xxs",
                     color=C["bear"], flex=1),
                文字(f"外 {外}% （{盤比['外盤量']:,}）", size="xxs",
                     color=C["bull"], flex=1, align="end"),
            ],
        },
        分隔線(上下間距="md"),
    ]

    # 建議掛單
    if 建議["建議價"]:
        body內容.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_card"],
            "cornerRadius": "12px",
            "paddingAll": "12px",
            "contents": [
                文字("💎 紀律布局建議",
                     size="xs", color=C["bull"], weight="bold"),
                {
                    "type": "box",
                    "layout": "baseline",
                    "margin": "sm",
                    "contents": [
                        文字(f"${建議['建議價']}", size="xxl",
                             color=C["bull"], weight="bold"),
                        文字(f"  {建議['策略']}策略", size="xs",
                             color=C["text_dim"]),
                    ],
                },
                文字(f"約 {建議['註記']}（NT$ {建議['實際金額_twd']:,.0f}）",
                     size="sm", color=C["text_main"], margin="sm"),
            ],
        })
    else:
        # Phase 33.2 — 沒建議時也要解釋「為什麼」（避免 user 以為是 bug）
        理由 = 建議.get("註記", "預算為 0")
        if "無五檔" in 理由:
            說明 = "盤後 / 無五檔 — 等開盤再看"
            色 = C["text_dim"]
        else:
            說明 = "今日 Enjoy 偏高 → HOLD 模式不加碼"
            色 = C["wait"]
        body內容.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_card"],
            "cornerRadius": "12px",
            "paddingAll": "12px",
            "contents": [
                文字("⏸ 紀律：今日不建議加碼",
                     size="xs", color=色, weight="bold"),
                文字(說明, size="xs",
                     color=C["text_dim"], margin="xs", wrap=True),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header(f"{r['name']}", f"{r['code']}",
                              "ETF", C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構ETF布局Carousel(etf結果: list[dict], 預算文字: str = "") -> dict:
    """總覽卡 + Top 7 個別 ETF 卡（按外盤積極度排序）。"""
    bubbles = [建構ETF布局總覽卡(etf結果, 預算文字)]

    # 排序：外盤越積極優先（值得布局）
    可用 = [r for r in etf結果 if r["盤比"]["外盤比"] is not None]
    可用.sort(key=lambda r: -(r["盤比"]["外盤比"] or 0))

    for r in 可用[:6]:  # 1 總覽 + 6 個別 = 7 張，控制 JSON < 50KB
        bubbles.append(建構單檔ETF五檔卡(r))

    return {"type": "carousel", "contents": bubbles[:12]}


# ─────────────────────────────────────────────
# 7. LIFF 入口卡（每日報表結尾）
# ─────────────────────────────────────────────
def 建構LIFF入口卡(liff_url: str) -> dict:
    """每日報表結尾附一張卡，按鈕可直接從 LINE 開啟 LIS 表單。"""
    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📲 即時調整配置", "從 LINE 直接開啟",
                              "LIFF", C["bull"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                文字("看到觸發訊號想調整資金？",
                     size="md", color=C["text_main"],
                     weight="bold", align="center"),
                文字("點按鈕全螢幕開啟，填完即時看新建議。",
                     size="sm", color=C["text_dim"],
                     wrap=True, align="center"),
                {
                    "type": "button",
                    "style": "primary",
                    "color": C["bull"],
                    "height": "md",
                    "margin": "lg",
                    "action": {
                        "type": "uri",
                        "label": "🚀 開啟 LIS 表單",
                        "uri": liff_url,
                    },
                },
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# 6. 新聞摘要卡
# ─────────────────────────────────────────────
def 建構新聞摘要卡(新聞摘要: dict) -> dict:
    摘要文字 = 新聞摘要.get("摘要", "今日無重點新聞")
    時間範圍 = 新聞摘要.get("時間範圍小時", 24)
    筆數 = 新聞摘要.get("新聞筆數", 0)

    # Gemini 輸出是多行 emoji 開頭的格式，按行拆
    行 = [l.strip() for l in 摘要文字.split("\n") if l.strip()]

    內容blocks = []
    for 段 in 行:
        # 抓 emoji + 內容
        內容blocks.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "none",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card"],
            "cornerRadius": "8px",
            "margin": "md",
            "contents": [
                文字(段, size="sm", color=C["text_main"], wrap=True),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📰 重點新聞",
                              f"過去 {時間範圍} 小時 · {筆數} 則來源",
                              "AI 摘要", C["brand"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": 內容blocks or [
                文字("今日無重點新聞", size="sm",
                     color=C["text_dim"], align="center"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


# ─────────────────────────────────────────────
# Phase 6.1：離職倒數卡
# ─────────────────────────────────────────────
def 建構離職倒數卡(fire: dict) -> dict:
    """fire_calculator.從portfolio計算() 或 計算財自() 的結果視覺化。"""
    if not fire or fire.get("達標年數") is None:
        return _建構離職倒數卡_未達標(fire)

    進度 = fire["達標進度_pct"]
    建議色 = (C["bull"] if 進度 >= 50
              else C["wait"] if 進度 >= 25
              else C["brand"])

    # 倒數文字
    剩餘文字 = f"{fire['剩餘_年']} 年 {fire['剩餘_月']} 月 {fire['剩餘_日']} 日"

    # 三情境對照行
    三情境列 = []
    for 名, d in fire["三情境對照"].items():
        if d["達標年數"] is None:
            數值 = "60 年內達不到"
            色 = C["text_subtle"]
        else:
            數值 = f"{d['達標年數']:.1f} 年"
            色 = (C["bull"] if 名 == "積極"
                  else C["text_main"] if 名 == "中等"
                  else C["text_subtle"])
        三情境列.append(_資金明細列(
            f"{名}（{d['年化報酬率_pct']}%）", 數值, 顏色=色
        ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📅 離職倒數",
                              f"{fire['情境']} 情境 · {fire['年化報酬率_pct']}%",
                              "FIRE", 建議色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "lg",
            "contents": [
                # 中央大數字：倒數
                {
                    "type": "box",
                    "layout": "vertical",
                    "alignItems": "center",
                    "contents": [
                        文字("離財務自由還剩", size="sm",
                             color=C["text_dim"], weight="bold"),
                        文字(剩餘文字, size="3xl", color=建議色,
                             weight="bold", align="center", margin="sm"),
                        文字(f"預估達標：{fire['達標日期']}", size="xs",
                             color=C["text_subtle"], align="center", margin="xs"),
                        # 進度條
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "none",
                            "height": "8px",
                            "cornerRadius": "100px",
                            "margin": "lg",
                            "contents": [
                                {"type": "box", "layout": "vertical",
                                 "flex": max(1, int(進度)),
                                 "backgroundColor": 建議色,
                                 "contents": [{"type": "filler"}]},
                                {"type": "box", "layout": "vertical",
                                 "flex": max(1, int(100 - 進度)),
                                 "backgroundColor": C["line"],
                                 "contents": [{"type": "filler"}]},
                            ],
                        },
                        文字(f"進度 {進度}%", size="xs",
                             color=C["text_dim"], align="center", margin="sm"),
                    ],
                },
                分隔線(上下間距="lg"),
                _資金明細列("FIRE 目標",
                             f"NT$ {fire['FIRE_目標']:,.0f}"),
                _資金明細列("目前資產",
                             f"NT$ {fire['目前資產']:,.0f}"),
                _資金明細列("月支出設定",
                             f"NT$ {fire['月支出']:,.0f}"),
                _資金明細列("月投入設定",
                             f"NT$ {fire['月投入']:,.0f}"),
                分隔線(上下間距="md"),
                文字("三情境對照", size="xs",
                     color=C["text_dim"], weight="bold", margin="md"),
                *三情境列,
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構持股健康檢查卡(健康: dict) -> Optional[dict]:
    """
    Phase 7.3：持股集中度 + 重複曝險警示卡。
    健康: portfolio_health.診斷持股健康() 結果
    """
    if not 健康 or 健康.get("持股數", 0) == 0:
        return None

    警示 = 健康.get("警示等級", "")
    主色 = (C["bear"] if "🔴" in 警示
            else C["wait"] if "🟡" in 警示
            else C["bull"] if "🟢" in 警示
            else C["text_subtle"])

    產業分布 = 健康.get("產業分布", [])

    # 產業分布列（前 5）
    產業列 = []
    for r in 產業分布[:5]:
        # 進度條
        占比 = r["占比_pct"]
        色 = (C["bear"] if 占比 >= 30
              else C["wait"] if 占比 >= 20
              else C["bull"] if 占比 >= 10
              else C["text_subtle"])
        產業列.append({
            "type": "box", "layout": "vertical", "margin": "sm",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{r['產業']} ({r['檔數']})", size="xs",
                             color=C["text_main"], flex=4, weight="bold"),
                        文字(f"{r['占比_pct']:.1f}%", size="xs",
                             color=色, weight="bold", flex=2, align="end"),
                    ],
                },
                # 占比進度條
                {
                    "type": "box", "layout": "horizontal",
                    "spacing": "none", "height": "5px",
                    "cornerRadius": "100px", "margin": "xs",
                    "contents": [
                        {"type": "box", "layout": "vertical",
                         "flex": max(1, int(占比)),
                         "backgroundColor": 色,
                         "contents": [{"type": "filler"}]},
                        {"type": "box", "layout": "vertical",
                         "flex": max(1, int(100 - 占比)),
                         "backgroundColor": C["line"],
                         "contents": [{"type": "filler"}]},
                    ],
                },
            ],
        })

    if len(產業分布) > 5:
        產業列.append(文字(
            f"…其他 {len(產業分布) - 5} 產業", size="xxs",
            color=C["text_subtle"], align="center", margin="sm"
        ))

    body_內容 = [
        # 總覽
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字(警示, size="xl", color=主色,
                     weight="bold", align="center"),
                文字(健康.get("建議", ""), size="xs",
                     color=C["text_dim"], align="center",
                     wrap=True, margin="xs"),
            ],
        },
        分隔線(上下間距="md"),
        # 統計
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("持股", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{健康['持股數']}", size="lg",
                          color=C["text_main"], weight="bold",
                          align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("產業", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{健康['產業數']}", size="lg",
                          color=C["text_main"], weight="bold",
                          align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("最大占比", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{健康['最大占比_pct']:.0f}%", size="lg",
                          color=主色, weight="bold", align="center"),
                 ]},
            ],
        },
        分隔線(上下間距="md"),
        文字("📊 產業分布", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
        *產業列,
    ]

    # 重複曝險警示
    重複 = 健康.get("重複曝險", [])
    if 重複:
        body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字(
            "⚠️ 重複曝險", size="xs",
            color=C["bear"], weight="bold", margin="md"
        ))
        for r in 重複[:3]:
            標的字串 = "、".join(
                f"{x['symbol'].replace('.TW', '').replace('.TWO', '')}"
                for x in r["標的"][:6]
            )
            if len(r["標的"]) > 6:
                標的字串 += f"…等 {len(r['標的'])}"
            body_內容.append({
                "type": "box", "layout": "vertical", "margin": "sm",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"{r['產業']} × {r['檔數']} 檔",
                                 size="xs", color=C["text_main"],
                                 weight="bold", flex=4),
                            文字(f"{r['占比_pct']:.1f}%",
                                 size="xs", color=C["bear"],
                                 weight="bold", flex=2, align="end"),
                        ],
                    },
                    文字(標的字串, size="xxs",
                         color=C["text_subtle"], wrap=True, margin="xs"),
                ],
            })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🩺 持股健康檢查",
                              "產業集中度 + 重複曝險",
                              警示.split(" ")[0] if 警示 else "",
                              主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構產業氣溫卡(產業聚合: dict) -> Optional[dict]:
    """
    Phase 6.3：watchlist 按產業聚合的氣溫表。
    產業聚合: industry_heatmap.聚合產業氣溫() 結果
    """
    if not 產業聚合 or not 產業聚合.get("產業"):
        return None

    產業們 = 產業聚合["產業"]
    最熱 = 產業聚合.get("最熱")
    最冷 = 產業聚合.get("最冷")

    def _溫度色(溫度: str) -> str:
        return (C["bear"] if 溫度 == "hot"
                else C["bull"] if 溫度 == "cold"
                else C["wait"])

    def _溫度emoji(溫度: str) -> str:
        return "🔥" if 溫度 == "hot" else "❄️" if 溫度 == "cold" else "🌤"

    產業列 = []
    for r in 產業們[:10]:  # 顯示前 10 個產業
        色 = _溫度色(r["溫度"])
        emoji = _溫度emoji(r["溫度"])
        訊號摘要 = []
        if r["震盪低點"] > 0:
            訊號摘要.append(f"震盪{r['震盪低點']}")
        if r["金叉"] > 0:
            訊號摘要.append(f"金叉{r['金叉']}")
        if r["量爆"] > 0:
            訊號摘要.append(f"量爆{r['量爆']}")
        訊號str = " · ".join(訊號摘要) if 訊號摘要 else "—"

        RSI字 = f"{r['平均RSI']:.0f}" if r['平均RSI'] is not None else "n/a"
        漲幅字 = (f"{r['平均漲幅20d']:+.1f}%" if r['平均漲幅20d'] is not None
                  else "n/a")

        產業列.append({
            "type": "box", "layout": "vertical", "margin": "sm",
            "paddingAll": "8px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "6px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{emoji} {r['產業']}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=4),
                        文字(f"RSI {RSI字}",
                             size="xs", color=色,
                             weight="bold", flex=2, align="end"),
                        文字(f"({r['檔數']}檔)",
                             size="xxs", color=C["text_dim"],
                             flex=2, align="end"),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "xs",
                    "contents": [
                        文字(f"20d {漲幅字}",
                             size="xxs", color=C["text_dim"], flex=3),
                        文字(訊號str, size="xxs",
                             color=C["text_dim"], flex=5, align="end"),
                    ],
                },
            ],
        })

    body_內容 = [
        # 最熱 / 最冷
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("🔥 最熱", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(最熱["產業"] if 最熱 else "—",
                          size="sm", color=C["bear"],
                          weight="bold", align="center"),
                     文字(f"RSI {最熱['平均RSI']:.0f}"
                          if 最熱 and 最熱.get("平均RSI") else "",
                          size="xxs", color=C["text_dim"], align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("❄️ 最冷", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(最冷["產業"] if 最冷 else "—",
                          size="sm", color=C["bull"],
                          weight="bold", align="center"),
                     文字(f"RSI {最冷['平均RSI']:.0f}"
                          if 最冷 and 最冷.get("平均RSI") else "",
                          size="xxs", color=C["text_dim"], align="center"),
                 ]},
            ],
        },
        分隔線(上下間距="md"),
        文字("📊 watchlist 各產業氣溫", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
        *產業列,
        分隔線(上下間距="md"),
        文字("🔥=過熱（RSI>65 或量爆多）　❄️=冷淡（RSI<40 或震盪多）",
             size="xxs", color=C["text_subtle"],
             align="center", wrap=True),
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🌡 產業氣溫表",
                              "watchlist 聚合視角",
                              f"{產業聚合['產業數']} 產業", C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構階段目標卡(fire: dict) -> Optional[dict]:
    """
    Phase 9：階段性目標進度卡（短期 / 中期 / 長期 FIRE + 生命週期階段）。
    fire: fire_calculator.從portfolio計算() 結果
    """
    if not fire or not fire.get("階段目標"):
        return None

    階段目標 = fire["階段目標"]
    生命週期 = fire.get("生命週期", {})

    階段名 = 生命週期.get("階段", "—")
    階段說明 = 生命週期.get("說明", "")
    階段建議 = 生命週期.get("建議", "")

    主色 = (C["bull"] if "衝刺" in 階段名
            else C["wait"] if "平衡" in 階段名
            else C["bear"] if "保本" in 階段名
            else C["accent"])

    def _進度條(進度_pct: float, 色: str) -> dict:
        return {
            "type": "box", "layout": "horizontal",
            "spacing": "none", "height": "6px",
            "cornerRadius": "100px", "margin": "xs",
            "contents": [
                {"type": "box", "layout": "vertical",
                 "flex": max(1, int(進度_pct)),
                 "backgroundColor": 色,
                 "contents": [{"type": "filler"}]},
                {"type": "box", "layout": "vertical",
                 "flex": max(1, int(100 - 進度_pct)),
                 "backgroundColor": C["line"],
                 "contents": [{"type": "filler"}]},
            ],
        }

    def _目標列(段名: str, d: dict, 色: str) -> dict:
        達標 = d.get("已達標", False)
        進度 = d.get("進度_pct", 0)
        return {
            "type": "box", "layout": "vertical", "margin": "md",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{段名} · {d.get('目標名', '')[:14]}",
                             size="xs", color=C["text_main"],
                             weight="bold", flex=5),
                        文字("✅ 達標" if 達標 else f"{進度}%",
                             size="xs", color=色, weight="bold",
                             flex=2, align="end"),
                    ],
                },
                _進度條(進度, 色),
                {
                    "type": "box", "layout": "horizontal", "margin": "xs",
                    "contents": [
                        文字(f"目標 NT$ {d.get('目標_twd', 0):,.0f}",
                             size="xxs", color=C["text_dim"], flex=4),
                        文字(("達標" if 達標 else
                              f"差 NT$ {d.get('差距_twd', 0):,.0f}"),
                             size="xxs", color=C["text_dim"],
                             flex=3, align="end"),
                    ],
                },
            ],
        }

    body_內容 = [
        # 生命週期階段
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("目前階段", size="xs",
                     color=C["text_dim"], align="center"),
                文字(階段名, size="xxl", color=主色,
                     weight="bold", align="center", margin="xs"),
                文字(階段說明, size="xs",
                     color=C["text_dim"], align="center"),
                文字(階段建議, size="xs", color=主色,
                     align="center", margin="xs", wrap=True),
            ],
        },
        分隔線(上下間距="lg"),
        文字("📍 階段性目標進度", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
    ]

    if 階段目標.get("短期"):
        body_內容.append(_目標列("短期", 階段目標["短期"], C["bull"]))
    if 階段目標.get("中期"):
        body_內容.append(_目標列("中期", 階段目標["中期"], C["wait"]))
    if 階段目標.get("長期FIRE"):
        body_內容.append(_目標列("FIRE", 階段目標["長期FIRE"], C["accent"]))

    body_內容.append(分隔線(上下間距="md"))
    body_內容.append(文字(
        "💡 系統依進度自動調整火力（衝刺期+10%、保本期-20%）",
        size="xxs", color=C["text_subtle"],
        align="center", wrap=True,
    ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎯 階段性目標",
                              "短期 + 中期 + FIRE",
                              階段名, 主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構今日心法卡(心法: dict) -> dict:
    """
    Phase 7.1：30 天心法輪播教學。
    心法: ai_explainer.今日心法() 結果
    """
    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📚 今日心法",
                              f"Day {心法.get('day', 1)} / 30",
                              心法.get("標題", ""), C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "md",
            "contents": [
                文字("💡", size="3xl", align="center"),
                文字(心法.get("心法", ""),
                     size="lg", color=C["text_main"],
                     weight="bold", align="center", wrap=True, margin="md"),
                分隔線(上下間距="lg"),
                文字(心法.get("說明", ""),
                     size="sm", color=C["text_dim"],
                     align="center", wrap=True),
                分隔線(上下間距="md"),
                文字("LIS 核心 ▸ 恐慌布局，貪婪調節",
                     size="xs", color=C["text_subtle"],
                     align="center", weight="bold", margin="md"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構AI訊號解釋卡(解釋清單: list[dict]) -> Optional[dict]:
    """
    Phase 7.1：AI 對關鍵訊號的人話解釋。
    解釋清單: ai_explainer.解釋關鍵訊號() 結果，
              [{symbol, name, 類型, 解釋}, ...]
    """
    if not 解釋清單:
        return None

    項列 = []
    for r in 解釋清單:
        類型色 = (C["bull"] if r["類型"] == "金叉突破"
                  else C["wait"] if r["類型"] == "震盪低點"
                  else C["bear"])
        項列.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{r['symbol']} {r.get('name', '')}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=5),
                        文字(r["類型"], size="xs", color=類型色,
                             weight="bold", flex=2, align="end"),
                    ],
                },
                文字(r["解釋"], size="xs", color=C["text_dim"],
                     wrap=True, margin="xs"),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🤖 AI 訊號解釋",
                              "用人話翻譯今日訊號",
                              f"{len(解釋清單)} 則", C["brand"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                文字("Gemini AI 從 LIS 心法觀點解讀",
                     size="xs", color=C["text_dim"], align="center"),
                *項列,
                文字("⚠️ AI 解釋僅供參考，不構成投資建議",
                     size="xxs", color=C["text_subtle"],
                     align="center", margin="md"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構持股總覽卡(真倉: dict) -> Optional[dict]:
    """
    Phase 8.3：你 portfolio.json 真實持股總覽。
    Phase 9.5：分台股 / 美股小計顯示。
    真倉: portfolio_tracker.追蹤真倉() 結果
    """
    if not 真倉:
        return None
    總計 = 真倉.get("總計", {})
    if 總計.get("總檔數", 0) == 0:
        return None

    持股 = 真倉["持股"]
    損益_twd = 總計["損益_twd"]
    損益率 = 總計["損益率_pct"]
    主色 = C["bull"] if 損益_twd >= 0 else C["bear"]
    箭頭 = "▲" if 損益_twd >= 0 else "▼"

    台 = 真倉.get("台股小計", {})
    美 = 真倉.get("美股小計", {})
    有台 = 台.get("檔數", 0) > 0
    有美 = 美.get("檔數", 0) > 0

    # 上漲前 3 / 下跌前 3
    有資料 = [r for r in 持股 if r.get("pnl_pct") is not None]
    漲前3 = 有資料[:3]
    跌前3 = sorted(
        [r for r in 有資料 if r.get("pnl_pct", 0) < 0],
        key=lambda r: r.get("pnl_pct", 0),
    )[:3]

    def _個股列(r: dict) -> dict:
        色 = C["bull"] if r["pnl_pct"] >= 0 else C["bear"]
        警示 = r.get("警示_類型", "")
        emoji = (" 🎯" if 警示 == "TAKE_PROFIT"
                 else " 💀" if 警示 == "STOP_LOSS"
                 else " ⚠️" if 警示 in ("NEAR_TP", "NEAR_SL")
                 else "")
        return {
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                文字(f"{r['symbol']}{emoji}",
                     size="xs", color=C["text_main"],
                     flex=4, weight="bold"),
                文字(r.get("name", "")[:6] or "-",
                     size="xs", color=C["text_dim"], flex=3),
                文字(f"{r['pnl_pct']:+.2f}%",
                     size="xs", color=色, weight="bold",
                     flex=2, align="end"),
            ],
        }

    body_內容 = [
        # 中央大數字
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("總損益（TWD）", size="sm",
                     color=C["text_dim"], weight="bold"),
                文字(f"{箭頭} NT$ {abs(損益_twd):,.0f}",
                     size="3xl", color=主色,
                     weight="bold", align="center", margin="sm"),
                文字(f"{損益率:+.2f}%", size="md", color=主色,
                     weight="bold", align="center", margin="xs"),
            ],
        },
        分隔線(上下間距="md"),
        # 賺/賠/總
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("賺", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{總計['賺檔數']}", size="lg",
                          color=C["bull"], weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("賠", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{總計['賠檔數']}", size="lg",
                          color=C["bear"], weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("總", size="xxs", color=C["text_dim"],
                          align="center"),
                     文字(f"{總計['總檔數']}", size="lg",
                          color=C["text_main"], weight="bold",
                          align="center"),
                 ]},
            ],
        },
        分隔線(上下間距="md"),
        # 細項
        _資金明細列("總成本",
                     f"NT$ {總計['成本_twd']:,.0f}"),
        _資金明細列("總市值",
                     f"NT$ {總計['市值_twd']:,.0f}",
                     顏色=主色),
    ]

    # Phase 9.5：台股 / 美股小計（兩個都有才顯示分類）
    if 有台 and 有美:
        body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("📊 市場別小計", size="xs",
                              color=C["text_dim"],
                              weight="bold", margin="md"))
        # 台股
        台損 = 台["損益_twd"]
        台率 = 台["損益率_pct"]
        台色 = C["bull"] if 台損 >= 0 else C["bear"]
        body_內容.append({
            "type": "box", "layout": "vertical", "margin": "sm",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"🇹🇼 台股 ({台['檔數']}檔)",
                             size="xs", color=C["text_main"],
                             weight="bold", flex=4),
                        文字(f"NT$ {台['市值_twd']:,.0f}",
                             size="xs", color=C["text_main"],
                             flex=3, align="end"),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "xs",
                    "contents": [
                        文字(f"成本 NT$ {台['成本_twd']:,.0f}",
                             size="xxs", color=C["text_dim"], flex=4),
                        文字(f"{台損:+,.0f} ({台率:+.2f}%)",
                             size="xxs", color=台色,
                             weight="bold", flex=3, align="end"),
                    ],
                },
            ],
        })
        # 美股（突出顯示美金總市值）
        美損_usd = 美["損益_usd"]
        美率 = 美["損益率_pct"]
        美色 = C["bull"] if 美損_usd >= 0 else C["bear"]
        body_內容.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "paddingAll": "12px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"🇺🇸 美股 ({美['檔數']}檔)",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=4),
                        文字(f"USD",
                             size="xxs", color=C["text_dim"],
                             flex=1, align="end"),
                    ],
                },
                # 大字 USD 總市值
                文字(f"$ {美['市值_usd']:,.2f}",
                     size="xl", color=C["text_main"],
                     weight="bold", align="end", margin="xs"),
                # TWD 換算（小字）
                文字(f"≈ NT$ {美['市值_twd']:,.0f} (匯率 {美['USD_TWD']:.3f})",
                     size="xxs", color=C["text_subtle"],
                     align="end"),
                {
                    "type": "box", "layout": "horizontal", "margin": "sm",
                    "contents": [
                        文字(f"成本 ${美['成本_usd']:,.2f}",
                             size="xxs", color=C["text_dim"], flex=4),
                        文字(f"${美損_usd:+,.2f} ({美率:+.2f}%)",
                             size="xxs", color=美色,
                             weight="bold", flex=3, align="end"),
                    ],
                },
            ],
        })

    if 漲前3:
        body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("🏆 漲幅前 3", size="xs",
                              color=C["text_dim"], weight="bold", margin="md"))
        for r in 漲前3:
            body_內容.append(_個股列(r))

    if 跌前3:
        body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("📉 跌幅前 3", size="xs",
                              color=C["text_dim"], weight="bold", margin="md"))
        for r in 跌前3:
            body_內容.append(_個股列(r))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header(
            "💼 持股總覽",
            f"{總計['總檔數']} 檔 · 即時 P&L",
            f"{損益率:+.2f}%", 主色,
        ),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構煙火協議卡(達標清單: list[dict]) -> Optional[dict]:
    """
    Phase 8.5：FUCK SHIT 獲利結案儀式
    達標清單: [{symbol, name, pnl_pct, source, ...}, ...]
      source: 'real'（真倉達 +20%）/ 'sim'（模擬盤達 +15% TAKE_PROFIT）
    """
    if not 達標清單:
        return None

    # 排序：最賺的在最上面
    達標清單 = sorted(達標清單, key=lambda r: r.get("pnl_pct", 0), reverse=True)

    # 統計
    總損益 = sum(r.get("pnl_twd", 0) or 0 for r in 達標清單)
    最賺 = 達標清單[0]

    爆炸列 = []
    for r in 達標清單[:6]:
        source_標 = "真倉" if r.get("source") == "real" else "模擬"
        爆炸列.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "paddingAll": "12px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"🎆 {r['symbol']} {r.get('name','')}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=5),
                        文字(f"+{r['pnl_pct']:.1f}%",
                             size="md", color=C["bull"],
                             weight="bold", flex=2, align="end"),
                    ],
                },
                文字(f"{source_標}盤 · {r.get('reason', '達停利')}",
                     size="xxs", color=C["text_dim"], margin="xs"),
            ],
        })

    body_內容 = [
        # 爆炸標語
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("🎆🎇🎆", size="3xl", align="center"),
                文字("FUCK SHIT", size="xl", color=C["bull"],
                     weight="bold", align="center", margin="sm"),
                文字("獲利結案", size="md", color=C["bull"],
                     weight="bold", align="center"),
                文字(f"{len(達標清單)} 檔達 +15% 停利目標",
                     size="xs", color=C["text_dim"],
                     align="center", margin="sm"),
            ],
        },
        分隔線(上下間距="md"),
        # 最賺那檔大字
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("最賺的一檔", size="xxs",
                     color=C["text_dim"], align="center"),
                文字(f"{最賺['symbol']}",
                     size="lg", color=C["text_main"],
                     weight="bold", align="center"),
                文字(f"+{最賺['pnl_pct']:.2f}%",
                     size="3xl", color=C["bull"],
                     weight="bold", align="center"),
            ],
        },
        分隔線(上下間距="md"),
        文字("📋 達標清單", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
        *爆炸列,
        分隔線(上下間距="md"),
        文字("⚡ 紀律執行才是真本事，繼續找下一個錯殺！",
             size="xs", color=C["bull"],
             weight="bold", align="center", wrap=True),
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎆 煙火協議",
                              "達停利目標，落袋為安",
                              "FUCK SHIT", C["bull"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構真倉警示卡(真倉: dict) -> Optional[dict]:
    """
    Phase 8.4：你 portfolio 達 +15% / -5% 的個股警示。
    真倉: portfolio_tracker.追蹤真倉() 結果
    沒警示就回 None（不擠 carousel）。
    """
    if not 真倉 or not 真倉.get("有警示"):
        return None
    警示 = 真倉["警示"]
    達停利 = 警示.get("達停利", [])
    破停損 = 警示.get("破停損", [])
    接近停利 = 警示.get("接近停利", [])
    接近停損 = 警示.get("接近停損", [])

    # 顏色：有達停利 → 綠、有破停損 → 紅、只有接近 → 黃
    if 達停利 or 破停損:
        主色 = C["bear"] if 破停損 else C["bull"]
        標籤 = "🔥 紀律觸發" if 破停損 else "🎯 達停利"
    else:
        主色 = C["wait"]
        標籤 = "⚠️ 接近"

    body_內容 = []

    def _列(r: dict, emoji: str, 文案: str, 色: str) -> dict:
        內容 = [
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{emoji} {r['symbol']} {r.get('name', '')[:8]}",
                         size="sm", color=C["text_main"],
                         weight="bold", flex=5),
                    文字(f"{r['pnl_pct']:+.2f}%",
                         size="sm", color=色, weight="bold",
                         flex=2, align="end"),
                ],
            },
            文字(f"{文案}：{r['shares']} 股 @ {r['avg_cost']:.2f} → "
                 f"{r['current_price']:.2f} "
                 f"(損益 NT$ {r['pnl_twd']:+,.0f})",
                 size="xxs", color=C["text_dim"], wrap=True),
        ]

        # Phase 11：策略 A / D 雙建議
        A建議 = r.get("策略A建議")
        D建議 = r.get("策略D建議")
        if A建議 or D建議:
            內容.append(分隔線(上下間距="xs"))
            if A建議:
                內容.append({
                    "type": "box", "layout": "horizontal",
                    "margin": "xs",
                    "contents": [
                        文字("[A 紀律]", size="xxs",
                             color=C["accent"], flex=2, weight="bold"),
                        文字(f"{A建議.get('動作', '')} {A建議.get('股數', 0)} 股",
                             size="xxs", color=C["text_main"], flex=5),
                    ],
                })
            if D建議:
                內容.append({
                    "type": "box", "layout": "horizontal",
                    "margin": "xs",
                    "contents": [
                        文字("[D 分批]", size="xxs",
                             color=C["bull"], flex=2, weight="bold"),
                        文字(f"{D建議.get('動作', '')} {D建議.get('股數', 0)} 股",
                             size="xxs", color=C["text_main"], flex=5),
                    ],
                })
                if D建議.get("下一階段"):
                    內容.append(文字(
                        f"   ▸ {D建議['下一階段']}",
                        size="xxs", color=C["text_subtle"], wrap=True,
                    ))

        return {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": 內容,
        }

    if 達停利:
        body_內容.append(文字("🎯 達停利目標 (+15%)，建議獲利了結",
                              size="sm", color=C["bull"],
                              weight="bold", align="center"))
        for r in 達停利:
            body_內容.append(_列(r, "🎯", "達標停利", C["bull"]))

    if 破停損:
        if 達停利:
            body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("💀 已破 -5% 停損紀律，建議檢視",
                              size="sm", color=C["bear"],
                              weight="bold", align="center"))
        for r in 破停損:
            body_內容.append(_列(r, "💀", "破停損", C["bear"]))

    if 接近停利:
        if 達停利 or 破停損:
            body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("📈 接近停利門檻 (≥+12%)",
                              size="xs", color=C["wait"],
                              weight="bold", align="center", margin="md"))
        for r in 接近停利:
            body_內容.append(_列(r, "📈", "接近停利", C["wait"]))

    if 接近停損:
        if 達停利 or 破停損 or 接近停利:
            body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字("📉 接近停損門檻 (≤-4%)",
                              size="xs", color=C["wait"],
                              weight="bold", align="center", margin="md"))
        for r in 接近停損:
            body_內容.append(_列(r, "📉", "接近停損", C["wait"]))

    if not body_內容:
        return None

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("⚡ 真倉紀律警示",
                              "+15% 停利 / -5% 停損",
                              標籤, 主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構零股長期清單卡(清單資料: dict) -> Optional[dict]:
    """
    Phase 11：零股長期持有定期定額清單卡。
    清單資料: dca_planner.建立零股清單() 結果
    """
    if not 清單資料 or not 清單資料.get("清單"):
        return None
    清單 = 清單資料["清單"]
    月總投入 = 清單資料.get("月總投入_twd", 0)

    項列 = []
    for r in 清單:
        if r.get("現價") is None:
            continue
        訊號色 = (C["bull"] if "🟢" in r.get("加碼訊號", "")
                    else C["bear"] if "⚠️" in r.get("加碼訊號", "")
                    else C["wait"])
        項列.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{r['symbol'].replace('.TW','')} {r['name']}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=5),
                        文字(r.get("加碼訊號", ""), size="xxs",
                             color=訊號色, weight="bold",
                             flex=3, align="end"),
                    ],
                },
                文字(f"{r['市場']} · {r.get('等價', '')}",
                     size="xxs", color=C["text_dim"], margin="xs"),
                {
                    "type": "box", "layout": "horizontal", "margin": "xs",
                    "contents": [
                        文字(f"現價 NT$ {r['現價']}",
                             size="xxs", color=C["text_dim"], flex=3),
                        文字(f"買 {r['建議買股數']} 股",
                             size="xs", color=訊號色,
                             weight="bold", flex=2, align="end"),
                        文字(f"NT$ {r['金額_twd']:,.0f}",
                             size="xxs", color=C["text_main"],
                             flex=3, align="end"),
                    ],
                },
                文字(r.get("訊號描述", ""), size="xxs",
                     color=C["text_subtle"], wrap=True, margin="xs"),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📌 零股長期清單",
                              "每月定期定額",
                              f"NT$ {月總投入:,.0f}",
                              C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                {
                    "type": "box", "layout": "vertical", "alignItems": "center",
                    "contents": [
                        文字("本月建議定期定額", size="xs",
                             color=C["text_dim"], align="center"),
                        文字(f"NT$ {月總投入:,.0f}",
                             size="3xl", color=C["bull"],
                             weight="bold", align="center"),
                        文字(清單資料.get("說明", ""), size="xxs",
                             color=C["text_dim"], align="center",
                             wrap=True, margin="xs"),
                    ],
                },
                分隔線(上下間距="md"),
                文字("📌 推薦標的（4 檔，台版美股 ETF）",
                     size="xs", color=C["text_dim"],
                     weight="bold", margin="md"),
                *項列,
                分隔線(上下間距="md"),
                文字("💡 跌時加碼買 2x、漲時跳過、平時定額",
                     size="xxs", color=C["bull"],
                     align="center", weight="bold", wrap=True),
                文字("摩擦只 0.47%（台股零股）vs 美股 8-16%",
                     size="xxs", color=C["text_subtle"],
                     align="center", margin="xs"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構ARK風控卡(ark: dict) -> Optional[dict]:
    """
    Phase 14b：仿 ARK 方舟「風控運算」頁面。
    ark: ark_dashboard.計算ARK風控() 結果
    """
    if not ark:
        return None

    建議水位 = ark.get("建議水位_pct", 60)
    實際水位 = ark.get("實際水位_pct", 0)
    差距 = ark.get("差距_pct", 0)
    狀態 = ark.get("狀態", "")
    布局金額 = ark.get("建議布局金額_twd", 0)

    主色 = (C["bull"] if "可加碼" in 狀態
            else C["bear"] if "調節" in 狀態
            else C["wait"])

    # 進度條：實際 vs 建議
    def _水位條() -> dict:
        實 = max(1, min(100, int(實際水位)))
        return {
            "type": "box", "layout": "horizontal",
            "spacing": "none", "height": "10px",
            "cornerRadius": "100px", "margin": "md",
            "contents": [
                {"type": "box", "layout": "vertical",
                 "flex": 實,
                 "backgroundColor": 主色,
                 "contents": [{"type": "filler"}]},
                {"type": "box", "layout": "vertical",
                 "flex": max(1, 100 - 實),
                 "backgroundColor": C["line"],
                 "contents": [{"type": "filler"}]},
            ],
        }

    body內容 = [
        # 大圓盤式：建議水位
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("持股配置建議", size="xs",
                     color=C["text_dim"], weight="bold"),
                文字(f"{建議水位:.1f}%", size="5xl", color=主色,
                     weight="bold", align="center"),
                文字("ARK 風控計算的目標水位", size="xxs",
                     color=C["text_subtle"], align="center"),
            ],
        },
        分隔線(上下間距="md"),

        # 實際 vs 建議
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("現在持股", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"NT$ {ark.get('持股市值_twd', 0):,.0f}",
                          size="sm", color=C["text_main"],
                          weight="bold", align="center"),
                     文字(f"{實際水位:.2f}%", size="xs",
                          color=主色, weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("資金總額", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"NT$ {ark.get('總資金_twd', 0):,.0f}",
                          size="sm", color=C["text_main"],
                          weight="bold", align="center"),
                     文字("100%", size="xs",
                          color=C["text_dim"], align="center"),
                 ]},
            ],
        },
        _水位條(),
        分隔線(上下間距="md"),

        # 建議持股 vs 建議閒錢
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("建議持股", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"NT$ {ark.get('建議持股_twd', 0):,.0f}",
                          size="sm", color=C["bull"],
                          weight="bold", align="center"),
                     文字(f"{建議水位:.1f}%", size="xs",
                          color=C["bull"], align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("建議閒錢", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"NT$ {ark.get('建議閒錢_twd', 0):,.0f}",
                          size="sm", color=C["wait"],
                          weight="bold", align="center"),
                     文字(f"{100 - 建議水位:.1f}%", size="xs",
                          color=C["wait"], align="center"),
                 ]},
            ],
        },
        分隔線(上下間距="md"),

        # 建議布局金額（大字）
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "paddingAll": "12px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                文字(狀態, size="md", color=主色,
                     weight="bold", align="center"),
                文字(("📈 建議布局金額" if 布局金額 > 0
                      else "📉 建議調節金額" if 布局金額 < 0
                      else "已對齊建議水位"),
                     size="xs", color=C["text_dim"],
                     align="center", margin="xs"),
                文字(f"TWD {abs(布局金額):,.0f}",
                     size="3xl", color=主色,
                     weight="bold", align="center"),
                文字(ark.get("動作", ""), size="xxs",
                     color=C["text_dim"], align="center",
                     wrap=True, margin="xs"),
            ],
        },
        分隔線(上下間距="md"),
        文字(
            "💡 風控水位 = 100 - 過熱程度。"
            "實際 < 建議可加；實際 > 建議須調節",
            size="xxs", color=C["text_subtle"],
            align="center", wrap=True,
        ),
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎛 ARK 風控運算",
                              "持股配置建議",
                              f"{建議水位:.1f}%", 主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構訊號狀態卡(追蹤: dict) -> Optional[dict]:
    """
    Phase 14：訊號狀態追蹤卡。
    對你的持股 + 長期 DCA + 單押標的，明確顯示「訊號還在/消失」。
    追蹤: signal_tracker.追蹤關心標的() 結果
    """
    if not 追蹤:
        return None
    持股 = 追蹤.get("持股追蹤", [])
    DCA = 追蹤.get("長期DCA追蹤", [])
    單押 = 追蹤.get("單押追蹤", [])
    新進 = 追蹤.get("今日新進入", [])
    新消 = 追蹤.get("今日新消失", [])

    if not (持股 or DCA or 單押 or 新進 or 新消):
        return None

    def _列(r: dict, 顯示動作: bool = True) -> dict:
        色 = (C["bull"] if r.get("狀態") in ("強訊號", "訊號還在")
              else C["wait"] if r.get("狀態") in ("訊號減弱",)
              else C["bear"] if r.get("狀態") in ("訊號消失", "嚴重過熱")
              else C["text_dim"])
        持續 = (f"持續 {r['持續天數']} 天"
                  if r.get("持續天數") else "")
        子內容 = [
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{r.get('emoji', '')}{r['symbol']} {r.get('name', '')[:8]}",
                         size="xs", color=C["text_main"],
                         weight="bold", flex=4),
                    文字(f"{r['分數']:.0f}" if r.get('分數') is not None else "n/a",
                         size="xs", color=色, weight="bold",
                         flex=2, align="end"),
                    文字(r.get("狀態", ""), size="xxs",
                         color=色, flex=3, align="end"),
                ],
            },
        ]
        if 顯示動作 and (持續 or r.get("動作")):
            子內容.append(文字(
                f"{持續} · {r.get('動作', '')}".strip(" ·"),
                size="xxs", color=C["text_subtle"], margin="xs",
            ))
        return {
            "type": "box", "layout": "vertical", "margin": "sm",
            "contents": 子內容,
        }

    body內容 = []

    # 🚨 今日新進入 / 新消失（最重要先顯示）
    if 新進:
        body內容.append(文字(
            f"⭐ 今日新進入價值區（{len(新進)} 檔）",
            size="sm", color=C["bull"],
            weight="bold", margin="md", wrap=True,
        ))
        for r in 新進[:5]:
            body內容.append(文字(
                f"  🟢 {r['symbol']} {r.get('name','')[:8]}: "
                f"{r['昨分']:.0f} → {r['今分']:.0f}",
                size="xxs", color=C["text_main"], wrap=True,
            ))

    if 新消:
        body內容.append(文字(
            f"⚠️ 今日訊號消失（{len(新消)} 檔，停止加碼）",
            size="sm", color=C["bear"],
            weight="bold", margin="md", wrap=True,
        ))
        for r in 新消[:5]:
            body內容.append(文字(
                f"  🔴 {r['symbol']} {r.get('name','')[:8]}: "
                f"{r['昨分']:.0f} → {r['今分']:.0f}",
                size="xxs", color=C["text_main"], wrap=True,
            ))

    # 單押標的
    if 單押:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            "🎯 單押標的", size="xs",
            color=C["accent"], weight="bold", margin="md",
        ))
        for r in 單押:
            body內容.append(_列(r))

    # 長期 DCA
    if DCA:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            "📌 長期 DCA 清單", size="xs",
            color=C["text_dim"], weight="bold", margin="md",
        ))
        for r in DCA:
            body內容.append(_列(r))

    # 持股
    if 持股:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"💼 你的持股訊號（{len(持股)} 檔）",
            size="xs", color=C["text_dim"],
            weight="bold", margin="md",
        ))
        for r in 持股[:10]:   # 最多 10 檔
            body內容.append(_列(r, 顯示動作=False))
        if len(持股) > 10:
            body內容.append(文字(
                f"…還有 {len(持股) - 10} 檔",
                size="xxs", color=C["text_subtle"],
                align="center", margin="sm",
            ))

    body內容.append(分隔線(上下間距="md"))
    body內容.append(文字(
        "💡 < 50 分=訊號還在可加 / > 50 分=訊號消失停加",
        size="xxs", color=C["text_subtle"],
        align="center", wrap=True,
    ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📡 訊號狀態追蹤",
                              "你關心的標的",
                              f"{len(新進)}入/{len(新消)}出",
                              C["bull"] if 新進 else C["bear"] if 新消 else C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構位階監測卡(位階: dict) -> Optional[dict]:
    """
    Phase 12：ARK 思路的每日位階監測。
    位階: positional_signal.掃描位階() 結果
    """
    if not 位階:
        return None
    進入 = 位階.get("今日_進入價值區", [])
    離開 = 位階.get("今日_離開價值區", [])
    深價值 = 位階.get("深價值區", [])
    超漲 = 位階.get("超漲區", [])
    統計 = 位階.get("統計", {})
    有昨日 = 位階.get("有昨日數據", False)

    def _個股列(r: dict, 色名: str) -> dict:
        色 = (C["bull"] if 色名 in ("bull", "進入")
              else C["bear"] if 色名 in ("bear", "離開")
              else C["wait"])
        變 = r.get("變化")
        變字 = f"{變:+.1f}" if 變 is not None else ""
        return {
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                文字(f"{r.get('emoji', '')}{r['symbol']} {r.get('name', '')[:6]}",
                     size="xs", color=C["text_main"],
                     weight="bold", flex=5),
                文字(f"{r['分數']:.0f}", size="xs",
                     color=色, weight="bold", flex=2, align="end"),
                文字(變字, size="xxs",
                     color=C["text_dim"], flex=2, align="end"),
            ],
        }

    body內容 = [
        # 統計概覽
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字(f"watchlist {位階.get('總檔數', 0)} 檔位階分布",
                     size="xs", color=C["text_dim"],
                     align="center", weight="bold"),
                {
                    "type": "box", "layout": "horizontal", "margin": "sm",
                    "contents": [
                        {"type": "box", "layout": "vertical", "flex": 1,
                         "contents": [
                             文字("🟢深價值", size="xxs",
                                  color=C["bull"], align="center"),
                             文字(f"{統計.get('深價值區', 0)}",
                                  size="md", color=C["bull"],
                                  weight="bold", align="center"),
                         ]},
                        {"type": "box", "layout": "vertical", "flex": 1,
                         "contents": [
                             文字("🟢進入", size="xxs",
                                  color=C["bull"], align="center"),
                             文字(f"{統計.get('進入價值區', 0)}",
                                  size="md", color=C["bull"],
                                  weight="bold", align="center"),
                         ]},
                        {"type": "box", "layout": "vertical", "flex": 1,
                         "contents": [
                             文字("⚪中性", size="xxs",
                                  color=C["text_dim"], align="center"),
                             文字(f"{統計.get('中性', 0)}",
                                  size="md", color=C["text_main"],
                                  weight="bold", align="center"),
                         ]},
                        {"type": "box", "layout": "vertical", "flex": 1,
                         "contents": [
                             文字("🟡離開", size="xxs",
                                  color=C["wait"], align="center"),
                             文字(f"{統計.get('離開價值區', 0)}",
                                  size="md", color=C["wait"],
                                  weight="bold", align="center"),
                         ]},
                        {"type": "box", "layout": "vertical", "flex": 1,
                         "contents": [
                             文字("🔴超漲", size="xxs",
                                  color=C["bear"], align="center"),
                             文字(f"{統計.get('超漲區', 0)}",
                                  size="md", color=C["bear"],
                                  weight="bold", align="center"),
                         ]},
                    ],
                },
            ],
        },
    ]

    # 今日新進入價值區
    if 進入:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"⭐ 今日新進入價值區（{len(進入)} 檔）建議買",
            size="xs", color=C["bull"],
            weight="bold", margin="md", wrap=True,
        ))
        for r in 進入[:5]:
            body內容.append(_個股列(r, "進入"))

    # 今日新離開價值區
    if 離開:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"⚠️ 今日新離開價值區（{len(離開)} 檔）建議賣",
            size="xs", color=C["wait"],
            weight="bold", margin="md", wrap=True,
        ))
        for r in 離開[:5]:
            body內容.append(_個股列(r, "離開"))

    # 深價值區（持續）
    if 深價值:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"🟢 深價值區（{len(深價值)} 檔，可加碼）",
            size="xs", color=C["bull"],
            weight="bold", margin="md",
        ))
        for r in 深價值[:5]:
            body內容.append(_個股列(r, "bull"))

    # 超漲區
    if 超漲:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"🔴 超漲區（{len(超漲)} 檔，建議減碼）",
            size="xs", color=C["bear"],
            weight="bold", margin="md",
        ))
        for r in 超漲[:5]:
            body內容.append(_個股列(r, "bear"))

    body內容.append(分隔線(上下間距="md"))
    body內容.append(文字(
        "💡 RSI+MA50+漲幅+震盪+量能 5 維加權 0-100 分",
        size="xxs", color=C["text_subtle"],
        align="center", wrap=True,
    ))

    if not 有昨日:
        body內容.append(文字(
            "📅 明日起會偵測「跨越價值區」訊號",
            size="xxs", color=C["accent"],
            align="center", margin="xs",
        ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📊 位階監測",
                              "ARK 思路 / 每日進出價值區",
                              f"{len(進入)}入 / {len(離開)}出",
                              C["accent"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構美股盤勢卡(盤勢: dict) -> Optional[dict]:
    """
    Phase 11：晚間美股盤勢深度分析卡。
    盤勢: us_market_analyzer.美股盤勢綜合() 結果
    """
    if not 盤勢:
        return None

    整體 = 盤勢.get("整體判斷", "")
    建議火力 = 盤勢.get("建議火力_pct", 30)
    vix = 盤勢.get("VIX")
    vix判讀 = 盤勢.get("VIX判讀", {})

    主色 = (C["bull"] if "🌟" in 整體 or "😰" in 整體
            else C["bear"] if "🔥" in 整體
            else C["wait"] if "🥶" in 整體
            else C["text_main"])

    # 4 大指數列
    指數列 = []
    for 指 in 盤勢.get("指數摘要", []):
        if 指["close"] is None:
            continue
        狀態色 = (C["bear"] if 指["狀態"] == "過熱"
                    else C["bull"] if 指["狀態"] in ("超賣", "偏冷")
                    else C["text_main"])
        漲幅 = 指.get("漲幅20日_pct")
        指數列.append({
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                文字(指["名"], size="xs", color=C["text_main"],
                     weight="bold", flex=3),
                文字(f"{指['close']:,.0f}", size="xs",
                     color=C["text_main"], flex=2, align="end"),
                文字(f"RSI {指['rsi']:.0f}"
                     if 指.get("rsi") else "RSI -",
                     size="xxs", color=狀態色, flex=2, align="end"),
                文字(指["狀態"], size="xxs",
                     color=狀態色, weight="bold",
                     flex=2, align="end"),
            ],
        })

    聚合 = 盤勢.get("美股聚合", {})

    body內容 = [
        # 整體判斷大字
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("整體判斷", size="xxs",
                     color=C["text_dim"], align="center"),
                文字(整體, size="xl", color=主色,
                     weight="bold", align="center"),
                文字(f"建議火力 {建議火力}%",
                     size="xs", color=主色,
                     weight="bold", align="center", margin="xs"),
            ],
        },
        分隔線(上下間距="md"),

        # VIX 判讀
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("VIX 恐慌指數", size="xxs",
                     color=C["text_dim"], align="center"),
                文字(f"{vix:.1f}" if vix else "n/a",
                     size="3xl", color=主色,
                     weight="bold", align="center"),
                文字(vix判讀.get("等級", ""), size="sm",
                     color=主色, weight="bold", align="center"),
                文字(vix判讀.get("建議", ""), size="xxs",
                     color=C["text_dim"], align="center",
                     wrap=True, margin="xs"),
            ],
        },
        分隔線(上下間距="md"),

        # 4 大指數
        文字("📊 4 大美股指數", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
        *指數列,
        分隔線(上下間距="md"),

        # 美股 watchlist 聚合
        文字(f"🌙 美股 watchlist 溫度（{聚合.get('有效檔數', 0)} 檔）",
             size="xs", color=C["text_dim"],
             weight="bold", margin="md"),
        {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("平均 RSI", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"{聚合.get('平均RSI', '?')}" if 聚合.get('平均RSI') else "n/a",
                          size="lg", color=主色,
                          weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("震盪低點", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"{聚合.get('震盪低點', 0)}", size="lg",
                          color=C["bull"], weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("金叉", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"{聚合.get('金叉突破', 0)}", size="lg",
                          color=C["bull"], weight="bold", align="center"),
                 ]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     文字("量爆", size="xxs",
                          color=C["text_dim"], align="center"),
                     文字(f"{聚合.get('量爆', 0)}", size="lg",
                          color=C["wait"], weight="bold", align="center"),
                 ]},
            ],
        },
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🌎 美股盤勢深度",
                              "S&P + NASDAQ + 半導體",
                              整體.split(" ")[-1] if 整體 else "",
                              主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構今日決策卡(決策: dict) -> Optional[dict]:
    """
    Phase 11：一張卡看完今天怎麼做。
    決策: daily_decision.整合今日決策() 結果
    """
    if not 決策:
        return None
    買 = 決策.get("建議買", [])
    賣 = 決策.get("建議賣", [])
    觀 = 決策.get("觀察", [])

    if not (買 or 賣 or 觀):
        return None  # 沒任何訊號就不出卡

    加碼模式 = 決策.get("加碼模式", "")
    火力 = 決策.get("火力_pct", 30)
    主色 = (C["bear"] if "🛑" in 加碼模式
            else C["bull"] if ("🌟" in 加碼模式 or "🚀" in 加碼模式)
            else C["wait"])

    彈藥 = 決策.get("彈藥", {})
    彈藥_twd = 彈藥.get("彈藥_twd", 0)

    body內容 = [
        # 加碼模式大標
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字(加碼模式, size="xl", color=主色,
                     weight="bold", align="center"),
                文字(f"火力 {火力}% · {決策.get('火力說明', '')}",
                     size="xxs", color=C["text_dim"],
                     align="center", wrap=True),
                文字(決策.get("今日總結", ""), size="xs",
                     color=C["text_main"], weight="bold",
                     align="center", margin="sm", wrap=True),
                文字(f"💰 今日彈藥 NT$ {彈藥_twd:,.0f}（{彈藥.get('比例_pct', 0):.2f}% 總資產）"
                     if 彈藥_twd > 0 else "",
                     size="xxs", color=C["bull"],
                     align="center", margin="sm", weight="bold"),
            ],
        },
        分隔線(上下間距="md"),
    ]

    # 🟢 建議買
    if 買:
        body內容.append(文字(
            f"🟢 建議買進（{len(買)} 檔）",
            size="sm", color=C["bull"],
            weight="bold", margin="md",
        ))
        for r in 買:
            急 = "🚨 " if r.get("急") else ""
            幣 = r.get("幣號", "NT$" if r.get("幣別") != "USD" else "$")
            body內容.append({
                "type": "box", "layout": "vertical", "margin": "sm",
                "paddingAll": "10px",
                "backgroundColor": C["bg_card_alt"],
                "cornerRadius": "8px",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"{急}{r['symbol']} {r.get('name','')[:10]}",
                                 size="sm", color=C["text_main"],
                                 weight="bold", flex=5),
                            文字(f"買 {r.get('股數估算', '?')} 股",
                                 size="xs", color=C["bull"],
                                 weight="bold", flex=2, align="end"),
                        ],
                    },
                    文字(f"{幣}{r.get('現價', '?')} × {r.get('股數估算', 0)} 股 "
                         f"≈ NT$ {r.get('金額_twd', 0):,.0f}",
                         size="xxs", color=C["text_dim"], margin="xs"),
                    文字(r.get("原因", ""), size="xxs",
                         color=C["text_dim"], wrap=True, margin="xs"),
                    文字(f"▸ {r.get('出場條件', '+15% 賣半 / -5% 全停')}",
                         size="xxs", color=C["wait"], margin="xs"),
                ],
            })

    # 🔴 建議賣
    if 賣:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"🔴 建議賣出（{len(賣)} 檔）",
            size="sm", color=C["bear"],
            weight="bold", margin="md",
        ))
        for r in 賣:
            急 = "🚨 " if r.get("急") else ""
            body內容.append({
                "type": "box", "layout": "vertical", "margin": "sm",
                "paddingAll": "10px",
                "backgroundColor": C["bg_card_alt"],
                "cornerRadius": "8px",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"{急}{r['symbol']} {r.get('name','')[:10]}",
                                 size="sm", color=C["text_main"],
                                 weight="bold", flex=5),
                            文字(f"賣 {r.get('股數', 0)} 股",
                                 size="xs", color=C["bear"],
                                 weight="bold", flex=2, align="end"),
                        ],
                    },
                    文字(r.get("原因", ""), size="xxs",
                         color=C["text_dim"], wrap=True, margin="xs"),
                    文字(f"▸ 落袋約 NT$ {r.get('落袋_twd', 0):,.0f}",
                         size="xxs", color=C["bull"], margin="xs"),
                ],
            })

    # ⚪ 觀察
    if 觀:
        body內容.append(分隔線(上下間距="md"))
        body內容.append(文字(
            f"⚪ 待觀察（{len(觀)} 檔，watchlist 外）",
            size="sm", color=C["text_dim"],
            weight="bold", margin="md",
        ))
        for r in 觀[:3]:
            body內容.append({
                "type": "box", "layout": "vertical", "margin": "sm",
                "contents": [
                    文字(f"  {r['symbol']} {r.get('name', '')[:10]}",
                         size="xs", color=C["text_main"], weight="bold"),
                    文字(f"    {r.get('原因', '')}",
                         size="xxs", color=C["text_dim"], wrap=True),
                    文字(f"    ▸ {r.get('建議', '')}",
                         size="xxs", color=C["text_subtle"], wrap=True),
                ],
            })

    body內容.append(分隔線(上下間距="md"))
    body內容.append(文字(
        "💡 5 分鐘決策完成 · 紀律 = +15% 賣半 / -5% 停損",
        size="xxs", color=C["text_subtle"],
        align="center", wrap=True,
    ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📋 今日決策",
                              加碼模式.split(" ")[-1] if 加碼模式 else "",
                              f"{len(買)}買 / {len(賣)}賣",
                              主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構全市場發現卡(掃描結果: dict, 更新時間: str = "") -> Optional[dict]:
    """
    Phase 10：全市場掃描的「黃金 5 檔」推薦卡。
    掃描結果: market_scanner.掃描全市場() 結果
    """
    if not 掃描結果 or not 掃描結果.get("Top"):
        return None
    Top = 掃描結果["Top"]
    if not Top:
        return None

    is_us_count = sum(1 for r in Top
                      if not (r["symbol"].endswith(".TW")
                              or r["symbol"].endswith(".TWO")))
    is_tw_count = len(Top) - is_us_count

    項列 = []
    for r in Top[:5]:
        symbol = r["symbol"]
        is_us = not (symbol.endswith(".TW") or symbol.endswith(".TWO"))
        flag = "🇺🇸" if is_us else "🇹🇼"
        幣 = "$" if is_us else "NT$"
        條件 = "、".join(r.get("條件", [])[:3])
        if len(r.get("條件", [])) > 3:
            條件 += f"…+{len(r['條件']) - 3}"

        項列.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{flag} {symbol} {r.get('name', '')[:10]}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=5),
                        文字(f"{r['分數']} 分",
                             size="xs", color=C["bull"],
                             weight="bold", flex=2, align="end"),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "xs",
                    "contents": [
                        文字(f"{幣}{r.get('close', 0):.2f}",
                             size="xxs", color=C["text_dim"], flex=2),
                        文字(條件, size="xxs",
                             color=C["text_dim"], flex=5,
                             wrap=True, align="end"),
                    ],
                },
            ],
        })

    body_內容 = [
        # 概覽
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("掃描 watchlist 外", size="xs",
                     color=C["text_dim"], align="center"),
                文字(f"{掃描結果.get('掃描總數', 0)} 檔",
                     size="xxl", color=C["bull"],
                     weight="bold", align="center", margin="xs"),
                文字(f"找出 Top {len(Top)} 黃金錯殺（台 {is_tw_count} / 美 {is_us_count}）",
                     size="xxs", color=C["text_dim"],
                     align="center"),
            ],
        },
        分隔線(上下間距="md"),
        文字("🔍 系統挖到的標的（不在你 watchlist）", size="xs",
             color=C["text_dim"], weight="bold", margin="md"),
        *項列,
        分隔線(上下間距="md"),
        文字(f"💡 評分: 震盪低點+50 / 金叉+30 / 跌-5%+30 / 量爆+20 / RSI<30+20",
             size="xxs", color=C["text_subtle"],
             align="center", wrap=True),
        文字(f"⚠️ 僅供參考，建議納入 watchlist 持續觀察再決定",
             size="xxs", color=C["text_subtle"],
             align="center", wrap=True, margin="xs"),
        文字(f"更新於 {更新時間}", size="xxs",
             color=C["text_subtle"], align="center", margin="xs")
        if 更新時間 else 文字(" ", size="xxs", color=C["bg_dark"]),
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🔍 系統發現",
                              "全市場自動挖掘",
                              f"Top {len(Top)}", C["bull"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構黑天鵝機會卡(黑天鵝: dict) -> Optional[dict]:
    """
    Phase 7.2b：連鎖恐慌偵測卡。
    對應心法第 5 條「市場亂殺 = 錯殺價值區」。
    黑天鵝: black_swan.掃描黑天鵝() 結果
    """
    if not 黑天鵝:
        return None
    清單 = 黑天鵝.get("黑天鵝清單", [])
    if not 清單:
        return None

    市場警示 = 黑天鵝.get("全市場警示", "")
    市場條件 = 黑天鵝.get("全市場條件", {})

    主色 = (C["bear"] if "🚨" in 市場警示
            else C["wait"] if "⚠️" in 市場警示
            else C["bull"])

    項列 = []
    for r in 清單[:6]:
        命中 = "、".join(r.get("命中條件", [])[:3])
        if len(r.get("命中條件", [])) > 3:
            命中 += f"…+{len(r['命中條件']) - 3}"
        項列.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": C["bg_card_alt"],
            "cornerRadius": "8px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"🌟 {r['symbol']} {r.get('name','')[:8]}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=4),
                        文字(f"{r['符合條件數']}/5 條件",
                             size="xs", color=C["bear"],
                             weight="bold", flex=2, align="end"),
                    ],
                },
                文字(命中, size="xxs", color=C["text_dim"],
                     wrap=True, margin="xs"),
            ],
        })

    body_內容 = [
        # 全市場警示大字
        {
            "type": "box", "layout": "vertical", "alignItems": "center",
            "contents": [
                文字("全市場恐慌指標", size="xs",
                     color=C["text_dim"], weight="bold"),
                文字(市場警示, size="xl", color=主色,
                     weight="bold", align="center", margin="sm"),
                文字(f"F&G {市場條件.get('F&G', '?')} | "
                     f"台股 {市場條件.get('台股大盤_pct', '?')}% | "
                     f"美股 {市場條件.get('美股大盤_pct', '?')}%",
                     size="xxs", color=C["text_dim"],
                     align="center", margin="xs"),
            ],
        },
        分隔線(上下間距="md"),
        文字("🌟 錯殺價值區（達 4 條件以上）",
             size="xs", color=C["text_dim"],
             weight="bold", margin="md"),
        *項列,
        分隔線(上下間距="md"),
        文字("💡 LIS 心法第 5 條：市場亂殺 = 錯殺價值區",
             size="xxs", color=C["bull"], weight="bold",
             align="center", wrap=True),
        文字("但仍要看：基本面是否真的破壞？還是純情緒？",
             size="xxs", color=C["text_subtle"],
             align="center", wrap=True, margin="xs"),
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🌟 黑天鵝機會",
                              "連鎖恐慌偵測",
                              f"{len(清單)} 檔", 主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構HOLD減碼建議卡(減碼: dict) -> Optional[dict]:
    """
    Phase 6.0：HOLD 時掃出該減碼的持股建議。
    減碼: capital_planner.計算減碼建議() 的結果
    只有「可執行 + 有實際建議」才回傳卡，否則回 None（不擠 carousel）。
    """
    if not 減碼 or not 減碼.get("可執行"):
        return None
    清單 = [r for r in 減碼.get("減碼建議", [])
            if not r.get("not_in_watchlist") and r.get("建議減股數", 0) > 0]
    if not 清單:
        return None

    # 依漲幅排序（最賺的先列）
    清單.sort(key=lambda r: r.get("pnl_pct", 0), reverse=True)
    總入袋 = sum(r.get("估入袋_twd", 0) for r in 清單)

    建議列 = []
    for r in 清單[:8]:  # 最多顯示 8 檔
        色 = (C["bull"] if r["pnl_pct"] >= 20
              else C["wait"])
        建議列.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "margin": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        文字(f"{r['symbol']} {r.get('name', '')}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=4),
                        文字(f"+{r['pnl_pct']:.1f}%",
                             size="sm", color=色, weight="bold",
                             flex=2, align="end"),
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        文字(r.get("標籤", "-"),
                             size="xxs", color=C["text_dim"], flex=2),
                        文字(f"減 {r.get('建議減股數', 0)} 股",
                             size="xxs", color=C["text_dim"],
                             flex=2, align="center"),
                        文字(f"入袋 NT$ {r.get('估入袋_twd', 0):,.0f}",
                             size="xxs", color=色,
                             flex=3, align="end"),
                    ],
                },
            ],
        })

    if len(清單) > 8:
        建議列.append(文字(
            f"…另有 {len(清單) - 8} 檔達減碼門檻（詳見 log）",
            size="xxs", color=C["text_subtle"], margin="sm", align="center",
        ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📉 HOLD 減碼建議", "市場過熱、獲利了結",
                              f"{len(清單)} 檔", C["wait"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                # 總入袋
                {
                    "type": "box",
                    "layout": "vertical",
                    "alignItems": "center",
                    "contents": [
                        文字("執行後預估入袋", size="xs",
                             color=C["text_dim"], weight="bold"),
                        文字(f"NT$ {總入袋:,.0f}",
                             size="3xl", color=C["bull"],
                             weight="bold", align="center", margin="sm"),
                    ],
                },
                分隔線(上下間距="md"),
                文字("📋 建議減碼清單", size="xs",
                     color=C["text_dim"], weight="bold", margin="md"),
                *建議列,
                分隔線(上下間距="md"),
                文字("⚠️ 減碼門檻：+10-20% 減 1/3、+20-30% 減 1/2、+30%+ 減 2/3",
                     size="xxs", color=C["text_subtle"],
                     wrap=True, align="center"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構處置股警示卡(命中清單: list[dict]) -> Optional[dict]:
    """
    Phase 8.0d：watchlist 或持股中命中處置股清單時警示。
    命中清單: [{symbol, name, end_date, reason}, ...]
    若空 list 回 None（不擠 carousel）。
    """
    if not 命中清單:
        return None

    項列 = []
    for r in 命中清單[:8]:
        項列.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "margin": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        文字(f"{r.get('symbol', '')} {r.get('name', '')}",
                             size="sm", color=C["text_main"],
                             weight="bold", flex=5),
                        文字(r.get("measure", "處置"),
                             size="xs", color=C["bear"],
                             flex=3, align="end"),
                    ],
                },
                文字(f"原因：{r.get('reason', '')} · 至 {r.get('end_date', '')}",
                     size="xxs", color=C["text_dim"], wrap=True),
            ],
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🚨 持股處置警示",
                              "你的持股在處置期間",
                              f"{len(命中清單)} 檔", C["bear"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                文字("🚨 你的持股目前在證交所處置期間",
                     size="sm", color=C["bear"],
                     weight="bold", align="center"),
                文字("流動性差、滑價放大，建議檢視是否續抱",
                     size="xs", color=C["text_dim"],
                     align="center", margin="xs", wrap=True),
                分隔線(上下間距="md"),
                *項列,
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def 建構風控5儀表卡(風控: dict) -> dict:
    """
    Phase 6.2：方舟 5 儀表風控卡（情緒/VIX/位階/量爆/外資）。
    """
    if not 風控:
        return _空風控卡()

    總體 = 風控.get("總體分數")
    建議 = 風控.get("建議", "")
    文案 = 風控.get("建議文案", "")

    主色 = (C["bear"] if 總體 and 總體 >= 70
            else C["wait"] if 總體 and 總體 >= 40
            else C["bull"])

    # 把 5 個儀表轉成迷你儀表水平列（2 行 × 各 ~2-3 個）
    儀表項 = []
    for 名, 儀 in 風控["儀表"].items():
        分 = 儀["分數"]
        if 分 is None:
            顯示值 = "n/a"
            色 = C["text_subtle"]
            百分比 = 0
        else:
            顯示值 = f"{分:.0f}"
            色 = (C["bear"] if 分 >= 70
                  else C["wait"] if 分 >= 40
                  else C["bull"])
            百分比 = 分
        儀表項.append({
            "名稱": 名,
            "顯示值": 顯示值,
            "百分比": 百分比,
            "顏色": 色,
            "副標": 儀.get("副標", ""),
        })

    # 拆成 2 行（前 3 個 + 後 2 個）
    第一行 = 迷你儀表水平列(儀表項[:3])
    第二行 = 迷你儀表水平列(儀表項[3:5])

    body_內容 = [
        # 中央大數字 — 總體分數
        {
            "type": "box",
            "layout": "vertical",
            "alignItems": "center",
            "contents": [
                文字("整體風控分數", size="sm",
                     color=C["text_dim"], weight="bold"),
                文字(f"{總體:.0f}" if 總體 is not None else "n/a",
                     size="5xl", color=主色, weight="bold",
                     align="center", margin="sm"),
                文字(建議, size="md", color=主色,
                     weight="bold", align="center", margin="xs"),
                文字(文案, size="xs", color=C["text_dim"],
                     align="center", margin="xs", wrap=True),
            ],
        },
        分隔線(上下間距="lg"),
        第一行,
        第二行,
    ]

    # 若有外資集中度命中清單，加細項
    外資儀 = 風控["儀表"].get("外資集中度", {})
    命中清單 = 外資儀.get("命中清單", [])
    if 命中清單:
        body_內容.append(分隔線(上下間距="md"))
        body_內容.append(文字(
            f"📍 你 watchlist 命中外資前 20（{len(命中清單)} 檔）",
            size="xs", color=C["text_dim"], weight="bold", margin="md",
        ))
        for r in 命中清單[:5]:
            body_內容.append(文字(
                f"  {r['code']} {r['name']}",
                size="xs", color=C["text_main"], margin="xs",
            ))
        if len(命中清單) > 5:
            body_內容.append(文字(
                f"  …還有 {len(命中清單) - 5} 檔",
                size="xs", color=C["text_subtle"], margin="xs",
            ))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎛 風控儀表", "5 維度市場情緒",
                              建議.split(" ")[0] if 建議 else "", 主色),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "spacing": "md",
            "contents": body_內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def _空風控卡() -> dict:
    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("🎛 風控儀表", "資料不足", "n/a",
                              C["text_subtle"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "20px",
            "contents": [
                文字("5 儀表均無法計算，請檢查資料源",
                     size="sm", color=C["text_dim"], align="center"),
            ],
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }


def _建構離職倒數卡_未達標(fire: dict) -> dict:
    """60 年內達不到或 fire 為 None 的 fallback 版本。"""
    if not fire:
        副標 = "未設定"
        內容 = [
            文字("尚未設定離職倒數",
                 size="md", color=C["text_main"], weight="bold",
                 align="center", margin="md"),
            文字("portfolio.json 加 fire_settings",
                 size="xs", color=C["text_dim"],
                 align="center", margin="md"),
        ]
    else:
        副標 = f"{fire['情境']} 情境"
        內容 = [
            文字("60 年內達不到 FIRE 目標",
                 size="md", color=C["bear"], weight="bold",
                 align="center", margin="md"),
            文字(f"建議調高月投入（目前 NT$ {fire['月投入']:,.0f}）"
                 if fire["月投入"] < 50000
                 else "建議降低月支出目標",
                 size="xs", color=C["text_dim"],
                 align="center", margin="md", wrap=True),
            分隔線(上下間距="lg"),
            _資金明細列("FIRE 目標",
                         f"NT$ {fire['FIRE_目標']:,.0f}"),
            _資金明細列("目前資產",
                         f"NT$ {fire['目前資產']:,.0f}"),
            _資金明細列("月支出",
                         f"NT$ {fire['月支出']:,.0f}"),
            _資金明細列("月投入",
                         f"NT$ {fire['月投入']:,.0f}"),
        ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": _卡片Header("📅 離職倒數", 副標, "FIRE", C["bear"]),
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "24px",
            "spacing": "lg",
            "contents": 內容,
        },
        "styles": {"header": {"backgroundColor": C["bg_card"]},
                   "body": {"backgroundColor": C["bg_dark"]}},
    }
