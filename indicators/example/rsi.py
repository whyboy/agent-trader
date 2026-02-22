"""RSI (Relative Strength Index)，简单平均（不用 Wilder 平滑）。"""

import logging
from collections import deque
from typing import Any, Dict, List, Optional

from indicators.example.base import BaseIndicator, CandleLike

logger = logging.getLogger(__name__)


class RSIIndicator(BaseIndicator):
    """
    RSI(period)：取最近 period 根 K 线的涨跌，用简单算术平均算 avg_gain、avg_loss，
    RSI = 100 - 100/(1 + avg_gain/avg_loss)。同 ts 的推送会替换最后一根。
    不同 period（如 6 与 12）差异更明显。
    """

    def __init__(self, name: str, period: int = 14, **kwargs: Any) -> None:
        super().__init__(name, period=period, **kwargs)
        self.period = max(2, int(period))
        self._buffer: deque = deque()

    def _rsi_from_closes(self, closes: List[float]) -> Optional[float]:
        """从 close 序列计算 RSI：最近 period 个涨跌的简单平均（无 Wilder 平滑）。"""
        if len(closes) < self.period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(0.0, d))
            losses.append(max(0.0, -d))
        # 只用最近 period 个变化：简单算术平均
        use_g = gains[-self.period :]
        use_l = losses[-self.period :]
        avg_g = sum(use_g) / self.period
        avg_l = sum(use_l) / self.period
        if avg_l <= 0:
            return 100.0
        rs = avg_g / avg_l
        return 100.0 - (100.0 / (1.0 + rs))

    def update(self, candle: CandleLike) -> None:
        self._ingest_candle(candle, self._buffer, self.period + 5)

    def get_value(self) -> Dict[str, Any]:
        closes = [c.close for c in self._buffer]
        logger.info("RSI %s 当前队列长度=%d", self.name, len(self._buffer))
        val = self._rsi_from_closes(closes)
        return {self.name: val}

    def reset(self) -> None:
        self._buffer.clear()
