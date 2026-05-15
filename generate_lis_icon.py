"""一次性工具：生成 LIS 系統 icon 並上傳到圖床。"""
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from modules import image_uploader


# ─── 畫 icon（512x512）───
fig, ax = plt.subplots(figsize=(5.12, 5.12), dpi=100)
fig.patch.set_facecolor("#000000")
ax.set_facecolor("#000000")
ax.set_aspect("equal")
ax.axis("off")
ax.set_xlim(-1.3, 1.3)
ax.set_ylim(-1.3, 1.3)

# 黃色圓環外框
ax.add_patch(patches.Wedge((0, 0), 1.1, 0, 360, width=0.10,
                            facecolor="#FBBF24", edgecolor="none"))
# 內部黑色填滿（讓中間是純黑）
ax.add_patch(patches.Circle((0, 0), 0.98, facecolor="#000000",
                              edgecolor="none"))

# 中央 LIS 大字（黃色粗體）
ax.text(0, 0.05, "L.I.S",
        ha="center", va="center",
        fontsize=72, color="#FBBF24",
        fontweight="bold",
        family=["Arial Black", "Helvetica", "DejaVu Sans"])

# 下方小字
ax.text(0, -0.55, "INVESTMENT",
        ha="center", va="center",
        fontsize=12, color="#888888",
        family=["Arial", "DejaVu Sans"],
        weight="bold")

# 存圖
buf = io.BytesIO()
fig.savefig(buf, format="png", facecolor="#000000",
            bbox_inches="tight", pad_inches=0.05)
plt.close(fig)
png = buf.getvalue()

# 同時存一份到本機方便預覽
out_path = Path(r"D:\LIS股票投資系統\數據\lis_logo.png")
out_path.write_bytes(png)
print(f"本機已存：{out_path}（{len(png):,} bytes）")

# 上傳到圖床
print("\n上傳到 catbox.moe...")
url = image_uploader.上傳圖片(png, "lis_logo.png")
print(f"\n✅ Icon URL: {url}")
print("\n請把這個 URL 貼給 Claude，他會更新 portfolio_form.py")
