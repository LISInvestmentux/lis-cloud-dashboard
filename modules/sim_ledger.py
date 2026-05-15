"""
模擬盤訊號帳本（Phase 8.0）
SQLite 資料庫，記錄系統每天掃描出來的「所有」訊號（含未進場的），
用來：
1. 排除倖存者偏差（不只看買的那幾檔）
2. 驗證 +15% 停利 / -5% 停損 是否合理
3. 算「決策延遲成本」（訊號出現 vs 真實看到時間差）

DB 路徑：D:/LIS股票投資系統/數據/sim_ledger.db
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
資料庫路徑 = 專案根 / "數據" / "sim_ledger.db"


# ─────────────────────────────────────────────
# Schema 建立
# ─────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 時間戳
    signal_time         TEXT NOT NULL,          -- 訊號生成時間 ISO8601
    pushed_time         TEXT,                   -- LINE 推播時間
    mood_time           TEXT,                   -- 使用者回報情緒時間

    -- 股票識別
    symbol              TEXT NOT NULL,          -- e.g. 2330.TW / TSLA / 0050.TW
    name                TEXT,                   -- 中文名
    market              TEXT NOT NULL,          -- TW / US / ETF

    -- 訊號內容
    signal_type         TEXT NOT NULL,          -- BUY / WATCH / NONE / SELL_STOP / SELL_TAKE / HOLD
    trigger_reason      TEXT,                   -- 觸發原因（短字串）
    enjoy_index         INTEGER,                -- 當下 Enjoy Index 總分

    -- 價格
    signal_price        REAL NOT NULL,          -- 訊號當下價格（理論進場）
    assumed_exec_price  REAL NOT NULL,          -- 加滑價後的假設成交價
    friction_cost_pct   REAL NOT NULL,          -- 摩擦成本比例（手續費+稅）

    -- 部位
    suggested_shares    INTEGER,                -- 建議股數
    bullet_size         INTEGER,                -- 當下子彈額度

    -- 收盤對帳（13:30 後回填）
    close_price         REAL,
    close_date          TEXT,
    unrealized_pnl_pct  REAL,                   -- 帳面損益 %（含摩擦）

    -- 模擬平倉
    closed_date         TEXT,                   -- 平倉日
    closed_price        REAL,                   -- 平倉成交價
    closed_reason       TEXT,                   -- TAKE_PROFIT / STOP_LOSS / TIME_LIMIT
    realized_pnl_pct    REAL,                   -- 已實現損益 %（含摩擦）

    -- 心情標記
    mood_tag            TEXT,                   -- 🚀 / 🤔 / 😱

    -- 自由備註
    notes               TEXT,

    -- 建立時間（系統自動）
    created_at          TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol
    ON signals(symbol);

CREATE INDEX IF NOT EXISTS idx_signals_signal_time
    ON signals(signal_time);

CREATE INDEX IF NOT EXISTS idx_signals_open
    ON signals(closed_date) WHERE closed_date IS NULL;

-- ─────────────────────────────────────────────
-- 多套出場策略對照表（Phase 8.0b）
-- 每筆 BUY 訊號 × 3 套策略 = 3 列
-- 用來比較哪套策略最賺
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id       INTEGER NOT NULL,            -- 對應 signals.id
    strategy        TEXT NOT NULL,                -- 'A_fixed' / 'B_trailing' / 'C_ma20' / 'D_scaled'
    state           TEXT NOT NULL DEFAULT 'OPEN', -- OPEN / PARTIAL / CLOSED
    high_water_mark REAL,                         -- 進場後新高（給移動停利用）
    exit_price      REAL,
    exit_date       TEXT,
    exit_reason     TEXT,                         -- TAKE_PROFIT / STOP_LOSS / TRAILING_STOP / MA_BREAK / TIME_LIMIT / SCALED_50 / SCALED_75
    pnl_pct         REAL,
    days_held       INTEGER,
    -- Phase 11：策略 D 分批出場用
    partial_pct     INTEGER DEFAULT 0,            -- 已賣百分比 0/50/75/100
    partial_pnl_累計 REAL DEFAULT 0,              -- 部分平倉累計加權 PnL
    FOREIGN KEY(signal_id) REFERENCES signals(id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_signal
    ON strategy_results(signal_id);

CREATE INDEX IF NOT EXISTS idx_strategy_open
    ON strategy_results(state) WHERE state = 'OPEN';
"""


# ─────────────────────────────────────────────
# 連線管理
# ─────────────────────────────────────────────
def _取得連線() -> sqlite3.Connection:
    """取得 SQLite 連線（自動建 DB + 套用 schema + 遷移）。"""
    資料庫路徑.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(資料庫路徑))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Schema migration（給 Phase 11 策略 D 加欄位）
    for sql in [
        "ALTER TABLE strategy_results ADD COLUMN partial_pct INTEGER DEFAULT 0",
        "ALTER TABLE strategy_results ADD COLUMN partial_pnl_累計 REAL DEFAULT 0",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 欄位已存在
    conn.commit()
    return conn


def 初始化資料庫() -> str:
    """手動初始化（首次執行用）。回傳 DB 路徑。"""
    conn = _取得連線()
    conn.close()
    return str(資料庫路徑)


# ─────────────────────────────────────────────
# 寫入：單筆訊號
# ─────────────────────────────────────────────
def 寫入訊號(訊號: dict) -> int:
    """
    寫入單筆訊號。

    訊號 dict 應包含：
        symbol (必填), name, market (必填), signal_type (必填),
        trigger_reason, enjoy_index,
        signal_price (必填), assumed_exec_price (必填), friction_cost_pct (必填),
        suggested_shares, bullet_size,
        pushed_time (可選), notes (可選)

    回傳：新增列的 id
    """
    now_iso = datetime.now().isoformat(timespec="seconds")
    conn = _取得連線()
    cur = conn.execute("""
        INSERT INTO signals (
            signal_time, pushed_time,
            symbol, name, market,
            signal_type, trigger_reason, enjoy_index,
            signal_price, assumed_exec_price, friction_cost_pct,
            suggested_shares, bullet_size,
            notes
        ) VALUES (?,?, ?,?,?, ?,?,?, ?,?,?, ?,?, ?)
    """, (
        訊號.get("signal_time", now_iso),
        訊號.get("pushed_time"),
        訊號["symbol"],
        訊號.get("name"),
        訊號["market"],
        訊號["signal_type"],
        訊號.get("trigger_reason"),
        訊號.get("enjoy_index"),
        訊號["signal_price"],
        訊號["assumed_exec_price"],
        訊號["friction_cost_pct"],
        訊號.get("suggested_shares"),
        訊號.get("bullet_size"),
        訊號.get("notes"),
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def 批次寫入訊號(訊號列表: list[dict]) -> int:
    """批次寫入，回傳寫入筆數。"""
    count = 0
    for 訊號 in 訊號列表:
        try:
            寫入訊號(訊號)
            count += 1
        except Exception as e:
            print(f"⚠️ ledger 寫入失敗 {訊號.get('symbol')}: {e}")
    return count


# ─────────────────────────────────────────────
# 更新：收盤回填
# ─────────────────────────────────────────────
def 回填收盤(訊號id: int, close_price: float,
              close_date: Optional[str] = None) -> None:
    """
    13:30 收盤後回填當日收盤價與帳面損益。
    帳面損益 = (close_price - assumed_exec_price) / assumed_exec_price - 摩擦成本（賣方）
    這裡只回填 close 跟 unrealized，不平倉。
    """
    close_date = close_date or datetime.now().strftime("%Y-%m-%d")
    conn = _取得連線()
    row = conn.execute(
        "SELECT assumed_exec_price, friction_cost_pct, signal_type "
        "FROM signals WHERE id = ?",
        (訊號id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"訊號 id={訊號id} 不存在")

    買入價 = row["assumed_exec_price"]
    摩擦 = row["friction_cost_pct"]  # 來回摩擦
    # 帳面損益 = (現價/買入價 - 1) - 來回摩擦（假設今天賣）
    pnl_pct = (close_price / 買入價 - 1) - 摩擦
    pnl_pct = round(pnl_pct * 100, 2)  # 轉成 % 數值

    conn.execute("""
        UPDATE signals
        SET close_price = ?, close_date = ?, unrealized_pnl_pct = ?
        WHERE id = ?
    """, (close_price, close_date, pnl_pct, 訊號id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# 更新：模擬平倉
# ─────────────────────────────────────────────
def 模擬平倉(訊號id: int, closed_price: float,
              closed_reason: str,
              closed_date: Optional[str] = None) -> dict:
    """
    模擬平倉一筆訊號（觸發 +15% / -5% / 時間到了）。
    closed_reason: TAKE_PROFIT / STOP_LOSS / TIME_LIMIT
    回傳：{"realized_pnl_pct": x.xx}
    """
    closed_date = closed_date or datetime.now().strftime("%Y-%m-%d")
    conn = _取得連線()
    row = conn.execute(
        "SELECT assumed_exec_price, friction_cost_pct "
        "FROM signals WHERE id = ?",
        (訊號id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"訊號 id={訊號id} 不存在")

    買入價 = row["assumed_exec_price"]
    摩擦 = row["friction_cost_pct"]
    pnl_pct = round(((closed_price / 買入價 - 1) - 摩擦) * 100, 2)

    conn.execute("""
        UPDATE signals
        SET closed_date = ?, closed_price = ?, closed_reason = ?,
            realized_pnl_pct = ?
        WHERE id = ?
    """, (closed_date, closed_price, closed_reason, pnl_pct, 訊號id))
    conn.commit()
    conn.close()
    return {"realized_pnl_pct": pnl_pct}


# ─────────────────────────────────────────────
# 更新：心情標記
# ─────────────────────────────────────────────
def 寫入心情(訊號id: int, mood_tag: str) -> None:
    """LIFF 表單一鍵填心情。mood_tag: 🚀 / 🤔 / 😱"""
    now_iso = datetime.now().isoformat(timespec="seconds")
    conn = _取得連線()
    conn.execute("""
        UPDATE signals
        SET mood_tag = ?, mood_time = ?
        WHERE id = ?
    """, (mood_tag, now_iso, 訊號id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# 查詢
# ─────────────────────────────────────────────
def 查詢未平倉() -> list[dict]:
    """所有還沒平倉的 BUY 訊號。"""
    conn = _取得連線()
    rows = conn.execute("""
        SELECT * FROM signals
        WHERE signal_type = 'BUY' AND closed_date IS NULL
        ORDER BY signal_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def 查詢個股歷史(symbol: str, 上限: int = 100) -> list[dict]:
    """某檔股票的所有訊號歷史。"""
    conn = _取得連線()
    rows = conn.execute("""
        SELECT * FROM signals
        WHERE symbol = ?
        ORDER BY signal_time DESC
        LIMIT ?
    """, (symbol, 上限)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def 查詢最近平倉(symbol: str) -> Optional[dict]:
    """
    查某 symbol 的最近一次平倉紀錄（主表）。
    回傳 {closed_date, closed_reason, realized_pnl_pct} 或 None。
    用來判斷冷靜期。
    """
    conn = _取得連線()
    row = conn.execute("""
        SELECT closed_date, closed_reason, realized_pnl_pct
        FROM signals
        WHERE symbol = ? AND closed_date IS NOT NULL
        ORDER BY closed_date DESC
        LIMIT 1
    """, (symbol,)).fetchone()
    conn.close()
    return dict(row) if row else None


def 查詢當日新增(日期: Optional[str] = None) -> list[dict]:
    """某日新增的所有訊號（預設今天）。"""
    日期 = 日期 or datetime.now().strftime("%Y-%m-%d")
    conn = _取得連線()
    rows = conn.execute("""
        SELECT * FROM signals
        WHERE date(signal_time) = ?
        ORDER BY id ASC
    """, (日期,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def 統計概覽() -> dict:
    """整體統計（給儀表板用）。"""
    conn = _取得連線()
    總筆數 = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    買進筆數 = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE signal_type = 'BUY'"
    ).fetchone()[0]
    未平倉 = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE signal_type = 'BUY' AND closed_date IS NULL
    """).fetchone()[0]
    已平倉 = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE closed_date IS NOT NULL
    """).fetchone()[0]

    # 已平倉勝率
    勝負 = conn.execute("""
        SELECT
          SUM(CASE WHEN realized_pnl_pct > 0 THEN 1 ELSE 0 END) AS 勝,
          SUM(CASE WHEN realized_pnl_pct <= 0 THEN 1 ELSE 0 END) AS 敗,
          AVG(realized_pnl_pct) AS 平均報酬,
          MAX(realized_pnl_pct) AS 最佳,
          MIN(realized_pnl_pct) AS 最差
        FROM signals
        WHERE closed_date IS NOT NULL
    """).fetchone()
    conn.close()

    勝 = 勝負["勝"] or 0
    敗 = 勝負["敗"] or 0
    勝率 = round(勝 / (勝 + 敗) * 100, 1) if (勝 + 敗) > 0 else None

    return {
        "總筆數": 總筆數,
        "BUY 訊號": 買進筆數,
        "未平倉": 未平倉,
        "已平倉": 已平倉,
        "勝率_%": 勝率,
        "平均報酬_%": round(勝負["平均報酬"], 2) if 勝負["平均報酬"] is not None else None,
        "最佳": round(勝負["最佳"], 2) if 勝負["最佳"] is not None else None,
        "最差": round(勝負["最差"], 2) if 勝負["最差"] is not None else None,
    }


# ─────────────────────────────────────────────
# 多套出場策略對照（Phase 8.0b）
# ─────────────────────────────────────────────
策略清單 = ["A_fixed", "B_trailing", "C_ma20", "D_scaled"]

策略中文名 = {
    "A_fixed":    "A 固定停利 +15%/-5%",
    "B_trailing": "B 移動停利 +20%觸發/回落8%",
    "C_ma20":     "C 跌破20日線",
    "D_scaled":   "D 分批出場 +15%賣半/+30%賣75%/魚尾",
}


def 開立策略行(signal_id: int, 進場價: float) -> None:
    """每筆 BUY 訊號開立 3 套策略對照行（OPEN 狀態）。"""
    conn = _取得連線()
    for s in 策略清單:
        conn.execute("""
            INSERT INTO strategy_results
                (signal_id, strategy, state, high_water_mark)
            VALUES (?, ?, 'OPEN', ?)
        """, (signal_id, s, 進場價))
    conn.commit()
    conn.close()


def 更新策略高水位(signal_id: int, strategy: str, new_high: float) -> None:
    """更新某策略的進場後新高（B 策略移動停利用）。"""
    conn = _取得連線()
    conn.execute("""
        UPDATE strategy_results
        SET high_water_mark = ?
        WHERE signal_id = ? AND strategy = ? AND state = 'OPEN'
          AND (high_water_mark IS NULL OR high_water_mark < ?)
    """, (new_high, signal_id, strategy, new_high))
    conn.commit()
    conn.close()


def 平倉策略(signal_id: int, strategy: str,
              exit_price: float, exit_reason: str,
              exit_date: str, 摩擦比例: float,
              進場價: float, 持有天數: int) -> dict:
    """平倉某筆訊號的某套策略。回傳 pnl_pct。"""
    pnl_pct = round(((exit_price / 進場價 - 1) - 摩擦比例) * 100, 2)
    conn = _取得連線()
    conn.execute("""
        UPDATE strategy_results
        SET state = 'CLOSED',
            exit_price = ?, exit_date = ?, exit_reason = ?,
            pnl_pct = ?, days_held = ?
        WHERE signal_id = ? AND strategy = ? AND state = 'OPEN'
    """, (exit_price, exit_date, exit_reason, pnl_pct,
          持有天數, signal_id, strategy))
    conn.commit()
    conn.close()
    return {"pnl_pct": pnl_pct}


def 部分平倉(signal_id: int, strategy: str,
              新階段_pct: int, exit_price: float,
              exit_date: str, 摩擦比例: float,
              進場價: float) -> dict:
    """
    策略 D 分批出場用。記錄「賣 50%」或「賣 75%」階段。
    新階段_pct: 50 / 75
    回傳 {本段_pnl_pct, 累計_pnl_pct}
    """
    # 本段是 (新階段 - 舊階段) 比例賣出
    conn = _取得連線()
    舊 = conn.execute(
        "SELECT partial_pct, partial_pnl_累計 FROM strategy_results "
        "WHERE signal_id = ? AND strategy = ?",
        (signal_id, strategy),
    ).fetchone()
    舊階段 = (舊["partial_pct"] if 舊 else 0) or 0
    舊累計 = (舊["partial_pnl_累計"] if 舊 else 0) or 0

    本段比例 = (新階段_pct - 舊階段) / 100.0
    本段pnl_pct = ((exit_price / 進場價 - 1) - 摩擦比例) * 100
    本段加權 = 本段pnl_pct * 本段比例
    新累計 = 舊累計 + 本段加權

    conn.execute("""
        UPDATE strategy_results
        SET state = 'PARTIAL',
            partial_pct = ?,
            partial_pnl_累計 = ?,
            exit_reason = ?
        WHERE signal_id = ? AND strategy = ? AND state IN ('OPEN', 'PARTIAL')
    """, (新階段_pct, 新累計,
          f"SCALED_{新階段_pct}", signal_id, strategy))
    conn.commit()
    conn.close()
    return {
        "本段_pnl_pct": round(本段pnl_pct, 2),
        "本段比例": 本段比例,
        "累計_pnl_pct": round(新累計, 2),
    }


def 收尾平倉(signal_id: int, strategy: str,
              exit_price: float, exit_reason: str,
              exit_date: str, 摩擦比例: float,
              進場價: float, 持有天數: int) -> dict:
    """
    策略 D 最後一段（剩 25%）的平倉。把累計 PnL 加上最後段。
    """
    conn = _取得連線()
    舊 = conn.execute(
        "SELECT partial_pct, partial_pnl_累計 FROM strategy_results "
        "WHERE signal_id = ? AND strategy = ?",
        (signal_id, strategy),
    ).fetchone()
    舊階段 = (舊["partial_pct"] if 舊 else 0) or 0
    舊累計 = (舊["partial_pnl_累計"] if 舊 else 0) or 0

    本段比例 = (100 - 舊階段) / 100.0
    本段pnl_pct = ((exit_price / 進場價 - 1) - 摩擦比例) * 100
    本段加權 = 本段pnl_pct * 本段比例
    總pnl = 舊累計 + 本段加權

    conn.execute("""
        UPDATE strategy_results
        SET state = 'CLOSED',
            partial_pct = 100,
            partial_pnl_累計 = ?,
            exit_price = ?,
            exit_date = ?,
            exit_reason = ?,
            pnl_pct = ?,
            days_held = ?
        WHERE signal_id = ? AND strategy = ? AND state IN ('OPEN', 'PARTIAL')
    """, (總pnl, exit_price, exit_date, exit_reason,
          總pnl, 持有天數, signal_id, strategy))
    conn.commit()
    conn.close()
    return {"pnl_pct": round(總pnl, 2)}


def 查詢策略未平倉(strategy: Optional[str] = None) -> list[dict]:
    """查詢所有 OPEN / PARTIAL 狀態的策略行（含對應 signal 資料）。"""
    conn = _取得連線()
    sql = """
        SELECT sr.*, s.symbol, s.name, s.signal_time, s.assumed_exec_price,
               s.friction_cost_pct, s.market
        FROM strategy_results sr
        JOIN signals s ON sr.signal_id = s.id
        WHERE sr.state IN ('OPEN', 'PARTIAL') AND s.signal_type = 'BUY'
    """
    params = ()
    if strategy:
        sql += " AND sr.strategy = ?"
        params = (strategy,)
    sql += " ORDER BY s.signal_time DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def 策略績效比對() -> list[dict]:
    """各策略已平倉的績效統計。"""
    conn = _取得連線()
    rows = conn.execute("""
        SELECT
          strategy,
          COUNT(*) AS 平倉筆數,
          SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) AS 勝,
          SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) AS 敗,
          ROUND(AVG(pnl_pct), 2) AS 平均報酬,
          ROUND(MAX(pnl_pct), 2) AS 最佳,
          ROUND(MIN(pnl_pct), 2) AS 最差,
          ROUND(AVG(days_held), 1) AS 平均持有天數
        FROM strategy_results
        WHERE state = 'CLOSED'
        GROUP BY strategy
    """).fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        勝 = d["勝"] or 0
        敗 = d["敗"] or 0
        d["勝率_%"] = round(勝 / (勝 + 敗) * 100, 1) if (勝 + 敗) > 0 else None
        d["策略名稱"] = 策略中文名.get(d["strategy"], d["strategy"])
        out.append(d)
    return out


# ─────────────────────────────────────────────
# 從掃描結果一鍵寫入（給 main.py 主流程呼叫）
# ─────────────────────────────────────────────
def _判斷訊號類型(個股: dict) -> tuple[str, str]:
    """
    依個股 record 判斷訊號類型與原因。
    回傳：(signal_type, trigger_reason)
    signal_type: BUY / WATCH / NONE
      - BUY:   shakeout_low or bull_signal（買進訊號）
      - WATCH: shit_signal（觀察，超賣但還在跌）
      - NONE:  沒訊號（但仍寫入做對照組）
    """
    原因列表 = []
    if 個股.get("shakeout_low"):
        原因列表.append("震盪低點")
        shakeout_reasons = 個股.get("shakeout_reasons", [])
        if shakeout_reasons:
            原因列表.append("/".join(shakeout_reasons[:2]))
    if 個股.get("bull_signal"):
        原因列表.append("MACD 金叉+突破 MA50")

    if 原因列表:
        return "BUY", " | ".join(原因列表)

    if 個股.get("shit_signal"):
        return "WATCH", f"RSI {個股.get('rsi14')} 超賣 + 低於 MA200"

    return "NONE", ""


def _推斷市場(個股: dict) -> str:
    """從 symbol 推斷市場別。"""
    symbol = 個股.get("symbol", "")
    region = 個股.get("_region", "")
    if region == "tw_etf" or "ETF" in region.upper():
        return "ETF"
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return "TW"
    return "US"


冷靜期_日曆天 = 7   # 出場後 7 個日曆日 ≈ 5 個交易日


def _冷靜期內(symbol: str, 今日: datetime) -> tuple[bool, int, str]:
    """
    判斷某 symbol 是否在冷靜期內。
    回傳：(是否在冷靜期, 剩餘天數, 上次出場原因)
    """
    最近 = 查詢最近平倉(symbol)
    if not 最近 or not 最近.get("closed_date"):
        return (False, 0, "")
    try:
        出場日 = datetime.strptime(最近["closed_date"], "%Y-%m-%d")
    except (ValueError, TypeError):
        return (False, 0, "")
    距今天數 = (今日.date() - 出場日.date()).days
    if 距今天數 < 冷靜期_日曆天:
        剩餘 = 冷靜期_日曆天 - 距今天數
        return (True, 剩餘, 最近.get("closed_reason", "") or "")
    return (False, 0, "")


def 寫入今日全部訊號(全部個股: list[dict],
                       enjoy_index_總分: Optional[int] = None,
                       每檔預算: Optional[int] = None,
                       pushed_time: Optional[str] = None) -> dict:
    """
    把今日掃描結果**全部**個股寫入 ledger（包含 NONE，做對照組用）。

    全部個股: main.py 的 _合併個股(掃描結果) 結果
    enjoy_index_總分: 當下 Enjoy Index 分數（讓未來知道在什麼情緒下發訊號）
    每檔預算: 子彈額度（給 BUY 用，算 suggested_shares）

    回傳 {"BUY": x, "WATCH": y, "NONE": z, "失敗": n, "跳空漲停": a,
          "跳空跌停": b, "冷靜期降級": c}
    """
    # 延遲 import 避免循環
    try:
        from . import friction, tw_announcements
    except ImportError:
        import friction
        import tw_announcements

    now_iso = datetime.now().isoformat(timespec="seconds")
    now_dt = datetime.now()
    今日str = now_dt.strftime("%Y-%m-%d")
    統計 = {"BUY": 0, "WATCH": 0, "NONE": 0, "失敗": 0, "冷靜期降級": 0,
              "處置股加價": 0}

    # 預載入處置股清單（一次性，避免重複 HTTP 呼叫）
    try:
        公告清單 = tw_announcements.取得公告清單()
    except Exception as e:
        print(f"  ⚠️ 處置股清單抓取失敗（不影響主流程）：{e}")
        公告清單 = {"處置股": [], "注意股": []}

    統計["跳空漲停"] = 0
    統計["跳空跌停"] = 0

    for 個股 in 全部個股:
        try:
            # 略過 error record
            if "error" in 個股:
                continue
            symbol = 個股.get("symbol")
            close = 個股.get("close")
            if not symbol or close is None:
                continue

            market = _推斷市場(個股)
            signal_type, reason = _判斷訊號類型(個股)
            friction_pct = friction.來回摩擦比例(market)

            # ── 可成交性檢查（Phase 8.0a）──
            開盤 = 個股.get("open")
            最高 = 個股.get("high")
            最低 = 個股.get("low")
            昨收 = 個股.get("prev_close")
            可成交 = {"is_tradeable": True,
                       "slippage_multiplier": 1.0, "warnings": []}
            if 開盤 and 昨收:
                # 組裝符合 friction.檢查可成交性 介面的 K 線
                K線 = [
                    {"open": 開盤, "high": 最高 or close,
                     "low": 最低 or close, "close": close, "volume": 0},
                    {"close": 昨收, "open": 昨收, "high": 昨收,
                     "low": 昨收, "volume": 0},
                ]
                可成交 = friction.檢查可成交性(K線, market)

            slip = 可成交["slippage_multiplier"]
            warnings = 可成交["warnings"]
            extra_note = " | ".join(warnings) if warnings else ""

            # 跳空漲停 → 訊號降級為 WATCH（買不到）
            if not 可成交["is_tradeable"]:
                if signal_type == "BUY":
                    reason = ((reason + " | " if reason else "")
                              + "[跳空漲停買不到 → 降級 WATCH]")
                    signal_type = "WATCH"
                統計["跳空漲停"] += 1
            elif slip > 1.0:
                # 跳空跌停或大振幅 → 滑價加倍但仍可成交
                if "跌停" in extra_note:
                    統計["跳空跌停"] += 1
                reason = ((reason + " | " if reason else "") + extra_note)

            # ── 處置股檢查（Phase 8.0d）──
            # 處置股流動性差，滑價加倍但仍可 BUY
            # （exec_price 統一在下方計算，這裡只更新 slip 倍數）
            if signal_type in ("BUY", "WATCH") and market in ("TW", "ETF"):
                處置 = tw_announcements.是否處置股(symbol, 今日str, 公告清單)
                if 處置["是否處置"]:
                    slip = max(slip, 2.5)
                    extra_disp = (f"[處置股 {處置['原因']} 至 {處置['結束日']} "
                                  f"→ 滑價加倍]")
                    reason = ((reason + " | " if reason else "") + extra_disp)
                    統計["處置股加價"] += 1

            # ── 冷靜期檢查（Phase 8.0c）──
            # 若 BUY 訊號的 symbol 在主表 7 天內剛出場，降級為 WATCH
            if signal_type == "BUY":
                在冷靜期, 剩餘天, 上次出場原因 = _冷靜期內(symbol, now_dt)
                if 在冷靜期:
                    reason = ((reason + " | " if reason else "")
                              + f"[冷靜期 還剩 {剩餘天}天（上次 {上次出場原因}）→ 降級 WATCH]")
                    signal_type = "WATCH"
                    統計["冷靜期降級"] += 1

            exec_price = friction.訊號進場價_含可成交性(
                close, market, slippage_multiplier=max(slip, 1.0)
            ) or close  # 不可成交時用原始 close（之後 WATCH 不會被當作 BUY）

            # 建議股數（只 BUY 算，其他存 0 給對照用）
            suggested = 0
            if signal_type == "BUY" and 每檔預算:
                if market == "TW" or market == "ETF":
                    suggested = max(int(每檔預算 / exec_price), 0)
                elif market == "US":
                    suggested = max(int(每檔預算 / (exec_price * 32)), 0)

            new_id = 寫入訊號({
                "signal_time": now_iso,
                "pushed_time": pushed_time,
                "symbol": symbol,
                "name": 個股.get("name"),
                "market": market,
                "signal_type": signal_type,
                "trigger_reason": reason,
                "enjoy_index": enjoy_index_總分,
                "signal_price": close,
                "assumed_exec_price": exec_price,
                "friction_cost_pct": friction_pct,
                "suggested_shares": suggested,
                "bullet_size": 每檔預算,
            })
            統計[signal_type] = 統計.get(signal_type, 0) + 1

            # BUY 訊號自動開立 3 套策略對照行
            if signal_type == "BUY":
                開立策略行(new_id, exec_price)
        except Exception as e:
            print(f"  [ledger 寫入失敗] {個股.get('symbol')}: {e}")
            統計["失敗"] += 1

    return 統計


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    path = 初始化資料庫()
    print(f"[OK] DB 初始化完成：{path}")
    print(f"[統計] {統計概覽()}")
