"""
Realtime agent prompt: inject current price + indicators for analysis.
Uses shared STOP_SIGNAL from prompts.agent_prompt_crypto when available.

Includes sharp-decline analysis prompt: same indicators as strategy/example/reversal_kdj (52-86),
with pct_abs_avg as baseline to judge whether a short-term sharp decline has occurred.
"""

from typing import Any, Dict, List

# Prefer shared component (project-level prompts)
try:
    from prompts.agent_prompt_crypto import STOP_SIGNAL
except Exception:
    STOP_SIGNAL = "<FINISH_SIGNAL>"

# 与 reversal_kdj 策略使用的指标一致，用于急跌分析
SHARP_DECLINE_INDICATOR_KEYS: List[str] = [
    "rsi_6", "rsi_12", "rsi_24",
    "kdj_k", "kdj_d", "kdj_j",
    "ma_20",
    "price_vs_ma20_pct",  # (ma_20 - close) / close * 100，策略中计算后传入
    "pct_1", "pct_2", "pct_3", "pct_4", "pct_5",
    "pct_6", "pct_7", "pct_8", "pct_9", "pct_10",
    "pct_abs_avg",
    "pct_sum_3", "pct_sum_5", "pct_sum_10",
]

REALTIME_SYSTEM_PROMPT = """
You are a cryptocurrency trading assistant. You are analyzing **real-time** market data (WebSocket feed).

Your goals:
- Think and reason using the real-time data and indicators provided below.
- Consider technical indicators (MA, MACD, etc.) and current price/volume.
- Decide whether to hold, buy or sell. If you want to trade, you **must** call the crypto trade tool.
- Before making decisions, you may use search tools for news/sentiment if needed.

Thinking standards:
- Clearly show key steps: interpret indicators, assess trend, then decide.
- Use the exact numbers provided (close, volume, ma_20, macd, etc.).

Notes:
- You must execute trades by calling tools; direct output of actions is not accepted.
- When you are done, output exactly: {STOP_SIGNAL}

Here is the **current real-time data**:

Timestamp (OKX candle): {ts}
Symbol: {symbol}
Price (close): {close}
Volume: {volume}
Open: {open}
High: {high}
Low: {low}

Technical indicators:
{indicators_text}

Current positions (symbol: quantity; CASH = available USDT):
{positions}

When you think your task is complete, output
{STOP_SIGNAL}
"""

# 急跌分析专用 prompt：根据 pct_abs_avg 与 pct_sum_3/5/10 判断是否出现短期内大跌
SHARP_DECLINE_ANALYSIS_PROMPT = """
你是一个加密货币行情分析助手。当前任务：**根据下方实时数据与指标，判断是否出现了短期内快速急跌**。

## 指标含义（务必按此理解）

- **pct_abs_avg**：历史上已收盘 K 线涨跌幅**绝对值**的平均值，表示**正常情况**下每根 K 线平均波动幅度（%）。例如 pct_abs_avg=0.05 表示平时一根 K 线平均波动约 0.05%。

- **pct_1 ~ pct_10**：最近 10 根 K 线各自相对前一根的涨跌幅（%），带正负号。pct_1=最新一根，pct_10=更早。负值表示该根 K 线收跌。

- **pct_sum_3 / pct_sum_5 / pct_sum_10**：**已稳定的**最近 3 根、5 根、10 根 K 线的涨跌幅（带符号）**之和**。例如 pct_sum_3 = -0.5 表示最近 3 根已收盘 K 线累计跌了 0.5%。

- **ma_20**：20 根 K 线收盘价的简单均线。**price_vs_ma20_pct**：当前价相对 20 日均线的偏离百分比，(ma_20 - close)/close×100，正值表示价格在均线下方。

- **RSI**（rsi_6, rsi_12, rsi_24）、**KDJ**（kdj_k, kdj_d, kdj_j）：辅助判断超卖与拐点。

## 如何判断「短期内急跌」

1. **基准**：在正常波动下，约 N 根 K 线的累计波动幅度约在 ±(N × pct_abs_avg) 附近。若 pct_abs_avg=0.05，则 3 根约 ±0.15%，5 根约 ±0.25%，10 根约 ±0.5%。

2. **急跌信号**：若 **pct_sum_3**、**pct_sum_5** 或 **pct_sum_10** 为**明显负值**，且其绝对值远大于「N × pct_abs_avg」（例如 2 倍以上），则说明最近 N 根 K 线出现了**超出正常幅度的集中下跌**，即短期内急跌。

3. **综合**：结合 pct_1~pct_10 中连续多根为负、以及 RSI/KDJ 超卖，可进一步确认是否为急跌后的潜在反弹窗口。

请根据下方数据给出结论：**是否出现短期内快速急跌**（是/否/不确定），并简要写出依据（引用具体指标数值）。

---

**当前数据**：

Timestamp: {ts}
Symbol: {symbol}
Open: {open}  High: {high}  Low: {low}  Close: {close}
Volume: {volume}

**指标（与 reversal_kdj 策略一致）**：
{indicators_text}

---

完成后请输出：{STOP_SIGNAL}
"""


def format_indicators(indicators: Dict[str, Any]) -> str:
    lines = []
    for k, v in indicators.items():
        if v is None:
            lines.append(f"  {k}: (not yet available)")
        else:
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.6f}" if abs(v) < 1e-3 or abs(v) > 1e3 else f"  {k}: {v:.2f}")
            else:
                lines.append(f"  {k}: {v}")
    return "\n".join(lines) if lines else "  (no indicators yet)"


def _format_pct_like(k: str, v: Any) -> str:
    """pct 类指标用百分比形式，便于急跌分析时对比。"""
    if v is None:
        return f"  {k}: (not yet available)"
    if isinstance(v, float):
        return f"  {k}: {v:.6f}%"
    return f"  {k}: {v}"


def format_sharp_decline_indicators(indicators: Dict[str, Any]) -> str:
    """只格式化急跌分析用到的指标（与 reversal_kdj 52-86 一致），pct 类以百分比显示。"""
    lines = []
    for k in SHARP_DECLINE_INDICATOR_KEYS:
        v = indicators.get(k)
        if "pct" in k:
            lines.append(_format_pct_like(k, v))
        else:
            if v is None:
                lines.append(f"  {k}: (not yet available)")
            elif isinstance(v, float):
                lines.append(f"  {k}: {v:.6f}" if abs(v) < 1e-3 or abs(v) > 1e3 else f"  {k}: {v:.2f}")
            else:
                lines.append(f"  {k}: {v}")
    return "\n".join(lines) if lines else "  (no indicators yet)"


def get_sharp_decline_analysis_prompt(
    ts: str,
    symbol: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    indicators: Dict[str, Any],
) -> str:
    """生成急跌分析用 prompt，使用与 reversal_kdj 一致的指标，便于 AI 判断是否出现短期内大跌。"""
    indicators_subset = {k: indicators.get(k) for k in SHARP_DECLINE_INDICATOR_KEYS}
    indicators_text = format_sharp_decline_indicators(indicators_subset)
    return SHARP_DECLINE_ANALYSIS_PROMPT.format(
        ts=ts,
        symbol=symbol,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        indicators_text=indicators_text,
        STOP_SIGNAL=STOP_SIGNAL,
    )


def get_realtime_system_prompt(
    ts: str,
    symbol: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    indicators: Dict[str, Any],
    positions: Dict[str, float],
) -> str:
    return REALTIME_SYSTEM_PROMPT.format(
        ts=ts,
        symbol=symbol,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        indicators_text=format_indicators(indicators),
        positions=positions if positions else "(no positions loaded)",
        STOP_SIGNAL=STOP_SIGNAL,
    )
