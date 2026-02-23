"""
反转 RSI 策略（3 分钟）：连续 4 根阴线后 RSI 金叉 + 当前阳线 -> 买入；
持仓后某 K 线收盘价触及 20 均线 -> 下一根开盘价卖出。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from agent import AgentManager
from agent.prompt.reversal_kdj_prompt import get_sharp_decline_analysis_prompt
from indicators import MarketSnapshot
from strategy.data import Signal, SignalAction
from strategy.example.interface.base import BaseStrategy, StrategyContext

logger = logging.getLogger(__name__)


def _is_bearish(s: MarketSnapshot) -> bool:
    return s.close < s.open


def _is_bullish(s: MarketSnapshot) -> bool:
    return s.close > s.open


def _write_sharp_decline_prompt_to_file(ts: str, prompt: str) -> None:
    """将急跌分析 prompt 追加写入 txt 文件。"""
    path = Path("sharp_decline_prompts.txt")
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"ts: {ts}  |  记录时间: {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n\n")
            f.write(prompt)
            f.write("\n")
    except OSError as e:
        logger.warning("写入急跌分析 prompt 文件失败: %s", e)


def _write_sharp_decline_response_to_file(ts: str, response_text: str) -> None:
    """将急跌分析模型回复追加写入 txt 文件（与 prompt 同文件）。"""
    path = Path("sharp_decline_prompts.txt")
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write("\n--- 模型回复 ---\n")
            f.write(response_text)
            f.write("\n")
    except OSError as e:
        logger.warning("写入急跌分析模型回复失败: %s", e)


class ReversalKDJStrategy(BaseStrategy):
    """
    监测 3 分钟 K 线（或 trigger channel）。
    入场：连续 4 根阴线 + RSI 金叉（由下穿上 30）+ 当前 K 线阳线 -> 买入。
    出场：持仓中某 K 线收盘价触及 20 均线 -> 下一根开盘价卖出（本根发出 SELL）。
    """

    RSI_OVERBOUGHT = 30  # RSI 金叉：由 < 30 上穿 30

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.rsi_name = str(self.config.get("rsi_name", "rsi_12"))
        self.ma_name = str(self.config.get("ma_name", "ma_20"))
        self.consecutive_bearish = int(self.config.get("consecutive_bearish", 4))
        self._in_position = False
        self._entry_price: float | None = None
        self._agent_manager = AgentManager()
        self._last_rsi_low_ts: str | None = None  # rsi_12<30 上次触发时间戳（ms），用于 1 分钟冷却

    def evaluate(self, context: StrategyContext) -> Signal:
        snap = context.market_snapshot
        if snap is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reason="no_snapshot", metadata={})
        history: List[MarketSnapshot] = list(context.market_snapshot_history)
        ind = snap.indicators
        rsi = ind.get(self.rsi_name)
        ma20 = ind.get(self.ma_name)
        # 当前价格与 ma20（20 根 K 线均线）的百分比：(ma20 - current) / current
        price_vs_ma20_pct = (
            round((ma20 - snap.close) / snap.close * 100.0, 6)
            if (ma20 is not None and snap.close and snap.close != 0)
            else None
        )

        # 当 rsi_12 < 30 时：打印指标，并套用急跌分析 prompt（供 AI 判断是否短期内大跌）；1 分钟冷却
        rsi_12_val = ind.get("rsi_12")
        sharp_decline_prompt: str | None = None
        ts_ms = int(snap.ts) if snap.ts.isdigit() else 0
        cooldown_ok = (
            self._last_rsi_low_ts is None
            or ts_ms - int(self._last_rsi_low_ts) >= 60_000
        )
        if rsi_12_val is not None and rsi_12_val < 30 and cooldown_ok:
            self._last_rsi_low_ts = snap.ts
            rsi_6_val = ind.get("rsi_6")
            rsi_24_val = ind.get("rsi_24")
            kdj_k = ind.get("kdj_k")
            kdj_d = ind.get("kdj_d")
            kdj_j = ind.get("kdj_j")
            pct_1 = ind.get("pct_1")
            pct_2 = ind.get("pct_2")
            pct_3 = ind.get("pct_3")
            pct_4 = ind.get("pct_4")
            pct_5 = ind.get("pct_5")
            pct_6 = ind.get("pct_6")
            pct_7 = ind.get("pct_7")
            pct_8 = ind.get("pct_8")
            pct_9 = ind.get("pct_9")
            pct_10 = ind.get("pct_10")
            pct_abs_avg = ind.get("pct_abs_avg")
            pct_sum_3 = ind.get("pct_sum_3")
            pct_sum_5 = ind.get("pct_sum_5")
            pct_sum_10 = ind.get("pct_sum_10")
            _fmt = lambda v: "%.6f%%" % v if v is not None else "None"
            logger.info(
                "rsi_12<30 | rsi_6=%.2f rsi_12=%.2f rsi_24=%.2f | kdj_k=%.2f kdj_d=%.2f kdj_j=%.2f | "
                "ma_20=%s close=%.4f (ma20-close)/close=%s | "
                "pct_1=%s pct_2=%s pct_3=%s pct_4=%s pct_5=%s pct_6=%s pct_7=%s pct_8=%s pct_9=%s pct_10=%s | "
                "pct_abs_avg=%s | pct_sum_3=%s pct_sum_5=%s pct_sum_10=%s | ts=%s",
                rsi_6_val if rsi_6_val is not None else 0,
                rsi_12_val,
                rsi_24_val if rsi_24_val is not None else 0,
                kdj_k if kdj_k is not None else 0,
                kdj_d if kdj_d is not None else 0,
                kdj_j if kdj_j is not None else 0,
                "%.4f" % ma20 if ma20 is not None else "None",
                snap.close,
                _fmt(price_vs_ma20_pct),
                _fmt(pct_1), _fmt(pct_2), _fmt(pct_3), _fmt(pct_4), _fmt(pct_5), _fmt(pct_6), _fmt(pct_7), _fmt(pct_8), _fmt(pct_9), _fmt(pct_10),
                _fmt(pct_abs_avg), _fmt(pct_sum_3), _fmt(pct_sum_5), _fmt(pct_sum_10),
                snap.ts,
            )

            # 构建急跌分析 prompt 并调用模型获取返回值（显式注入 ma_20 与 price_vs_ma20_pct）
            ind_for_prompt = dict(ind)
            ind_for_prompt["ma_20"] = ma20
            ind_for_prompt["price_vs_ma20_pct"] = price_vs_ma20_pct
            sharp_decline_prompt = get_sharp_decline_analysis_prompt(
                ts=snap.ts,
                symbol=snap.channel,
                open_=snap.open,
                high=snap.high,
                low=snap.low,
                close=snap.close,
                volume=snap.volume,
                indicators=ind_for_prompt,
            )
            logger.info("急跌分析 prompt (rsi_12<30): %s", sharp_decline_prompt)
            _write_sharp_decline_prompt_to_file(snap.ts, sharp_decline_prompt)
            response_text = self._agent_manager.invoke(model="deepseek", prompt=sharp_decline_prompt)
            logger.info("急跌分析 模型回复: %s", response_text)
            _write_sharp_decline_response_to_file(snap.ts, response_text)

    

        # 持仓：当前收盘价超过 ma20 时卖出，否则持有
        if self._in_position and self._entry_price is not None:
            if ma20 is not None and snap.close >= ma20:
                self._in_position = False
                self._entry_price = None
                return Signal(
                    action=SignalAction.SELL,
                    confidence=0.8,
                    reason="close_above_ma20_exit",
                    metadata={},
                )
            return Signal(
                action=SignalAction.HOLD,
                confidence=0.0,
                reason="in_position_holding",
                metadata={},
            )