"""
反转 RSI 策略（3 分钟）：连续 4 根阴线后 RSI 金叉 + 当前阳线 -> 买入；
持仓后某 K 线收盘价触及 20 均线 -> 下一根开盘价卖出。
"""

import logging
from typing import Any, Dict, List

from indicators import MarketSnapshot
from strategy.data import Signal, SignalAction
from strategy.example.interface.base import BaseStrategy, StrategyContext

logger = logging.getLogger(__name__)


def _is_bearish(s: MarketSnapshot) -> bool:
    return s.close < s.open


def _is_bullish(s: MarketSnapshot) -> bool:
    return s.close > s.open


class ReversalRSIStrategy(BaseStrategy):
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

    def evaluate(self, context: StrategyContext) -> Signal:
        snap = context.market_snapshot
        if snap is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reason="no_snapshot", metadata={})
        history: List[MarketSnapshot] = list(context.market_snapshot_history)
        ind = snap.indicators
        rsi = ind.get(self.rsi_name)
        ma20 = ind.get(self.ma_name)

        # 当 rsi_12 < 30 时打印 rsi_6、rsi_12、rsi_24、KDJ(k,d,j)、pct_1~pct_5 及 pct_abs_avg
        rsi_12_val = ind.get("rsi_12")
        if rsi_12_val is not None and rsi_12_val < 30:
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
            pct_abs_avg = ind.get("pct_abs_avg")
            logger.info(
                "rsi_12<30 | rsi_6=%.2f rsi_12=%.2f rsi_24=%.2f | kdj_k=%.2f kdj_d=%.2f kdj_j=%.2f | pct_1=%s pct_2=%s pct_3=%s pct_4=%s pct_5=%s | pct_abs_avg=%s | ts=%s",
                rsi_6_val if rsi_6_val is not None else 0,
                rsi_12_val,
                rsi_24_val if rsi_24_val is not None else 0,
                kdj_k if kdj_k is not None else 0,
                kdj_d if kdj_d is not None else 0,
                kdj_j if kdj_j is not None else 0,
                "%.6f%%" % pct_1 if pct_1 is not None else "None",
                "%.6f%%" % pct_2 if pct_2 is not None else "None",
                "%.6f%%" % pct_3 if pct_3 is not None else "None",
                "%.6f%%" % pct_4 if pct_4 is not None else "None",
                "%.6f%%" % pct_5 if pct_5 is not None else "None",
                "%.6f%%" % pct_abs_avg if pct_abs_avg is not None else "None",
                snap.ts,
            )

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