"""RSI (Relative Strength Index) with Wilder smoothing."""

import logging
from collections import deque
from typing import Any, Dict, List, Optional

from indicators.example.base import BaseIndicator, CandleLike

logger = logging.getLogger(__name__)


class RSIIndicator(BaseIndicator):
    """RSI(period): Wilder 平滑。首 period 根用算术平均，之后用 Wilder 递推。同 ts 的推送会替换最后一根。"""

    def __init__(self, name: str, period: int = 14, **kwargs: Any) -> None:
        super().__init__(name, period=period, **kwargs)
        self.period = max(2, int(period))
        self._buffer: deque = deque()

    def _rsi_from_closes_wilder(self, closes: List[float]) -> Optional[float]:
        """从 close 序列按 Wilder 规则计算 RSI（支持同 ts 替换后重算）。"""
        if len(closes) < self.period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(0.0, d))
            losses.append(max(0.0, -d))
        # 首 period 个变化：算术平均
        avg_g = sum(gains[: self.period]) / self.period
        avg_l = sum(losses[: self.period]) / self.period
        # 之后逐根 Wilder 递推: avg = (prev_avg * (period-1) + current) / period
        for j in range(self.period, len(gains)):
            avg_g = (avg_g * (self.period - 1) + gains[j]) / self.period
            avg_l = (avg_l * (self.period - 1) + losses[j]) / self.period
        if avg_l <= 0:
            return 100.0
        rs = avg_g / avg_l
        return 100.0 - (100.0 / (1.0 + rs))

    def update(self, candle: CandleLike) -> None:
        self._ingest_candle(candle, self._buffer, self.period + 5)

    def get_value(self) -> Dict[str, Any]:
        closes = [c.close for c in self._buffer]
        logger.info("RSI %s 当前队列长度=%d", self.name, len(self._buffer))
        val = self._rsi_from_closes_wilder(closes)
        return {self.name: val}

    def reset(self) -> None:
        self._buffer.clear()
