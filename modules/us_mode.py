"""
一鍵切換 ARK 美股戰法 mode（Phase 32.7）

三個 mode：
  stepped (A) — 依訊號等級分級限額（推薦）
  off     (B) — 取消美股限額，回用 LIS 原算法
  strict  (C) — 固定 $100 嚴格限制（新手保護）

用法：
  python -m modules.us_mode               # 互動選單
  python -m modules.us_mode stepped       # 直接設成 stepped
  python -m modules.us_mode show          # 顯示目前設定
"""
import json
import sys
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
portfolio_path = 專案根 / "API" / "portfolio.json"

模式介紹 = {
    "stepped": "A 分級限額（推薦）— 紀律 $100 / 順勢 $150 / 加碼 $200 / 重押 $300 / 黑天鵝 $500",
    "off":     "B 完全取消 — 跟 LIS 原算法跑，金額不限",
    "strict":  "C 嚴格 $100 — 新手保護，任何美股訊號最多 $100",
}


def 顯示目前() -> dict:
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    us = cfg.get("us_strategy", {})
    mode = us.get("mode", "stepped")
    print(f"\n目前 ARK 美股戰法 mode = {mode}")
    print(f"  → {模式介紹.get(mode, '未知')}")
    return us


def 設定(mode: str) -> bool:
    if mode not in 模式介紹:
        print(f"❌ 不認識的 mode: {mode}（可用：stepped / off / strict）")
        return False
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    cfg.setdefault("us_strategy", {})
    舊 = cfg["us_strategy"].get("mode", "stepped")
    cfg["us_strategy"]["mode"] = mode
    portfolio_path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 已切換 ARK 美股 mode: {舊} → {mode}")
    print(f"   {模式介紹[mode]}")
    return True


def 主CLI():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()
        if cmd == "show":
            顯示目前()
        elif cmd in 模式介紹:
            設定(cmd)
        else:
            print(f"未知指令 '{sys.argv[1]}'，可用：stepped / off / strict / show")
        return

    # 互動模式
    print("=" * 60)
    print("🇺🇸 ARK 美股戰法 mode 切換")
    print("=" * 60)
    顯示目前()
    print("\n可選 mode：")
    print("  [1] stepped (A) — 分級限額（推薦）")
    print("  [2] off     (B) — 取消限額，LIS 原算法")
    print("  [3] strict  (C) — 固定 $100 嚴格")
    print("  [Q] 退出，不修改\n")
    sel = input("選擇 [1/2/3/Q]: ").strip().upper()
    mapping = {"1": "stepped", "2": "off", "3": "strict"}
    if sel in mapping:
        設定(mapping[sel])
    elif sel == "Q":
        print("退出，未修改")
    else:
        print(f"未知選項 '{sel}'，未修改")


if __name__ == "__main__":
    主CLI()
