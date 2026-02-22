"""KDJ 指标：RSV = (close - Ln) / (Hn - Ln) * 100，K/D 平滑，J = 3K - 2D。"""

from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from indicators.example.base import BaseIndicator, CandleLike


class KDJIndicator(BaseIndicator):
    """
    KDJ(rsv_period)：RSV 取最近 rsv_period 根 K 线的最高/最低/收盘，
    K = (2/3)*K_prev + (1/3)*RSV，D = (2/3)*D_prev + (1/3)*K，J = 3*K - 2*D。
    首值 K=D=50。同 ts 的推送会替换最后一根。
    """

    def __init__(
        self,
        name: str,
        rsv_period: int = 9,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, rsv_period=rsv_period, **kwargs)
        self.rsv_period = max(2, int(rsv_period))
        self._buffer: deque = deque()

    def _rsv(self, candles: List[CandleLike]) -> Optional[float]:
        """最近 rsv_period 根：RSV = (close - L) / (H - L) * 100，H/L 为最高/最低。"""
        if len(candles) < self.rsv_period:
            return None
        use = candles[-self.rsv_period :]
        highs = [c.high for c in use]
        lows = [c.low for c in use]
        close = use[-1].close
        h, l = max(highs), min(lows)
        if h <= l:
            return 50.0
        return (close - l) / (h - l) * 100.0

    def _kdj_from_buffer(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """从 buffer 按顺序计算 K、D、J（支持同 ts 替换后重算）。"""
        candles = list(self._buffer)
        if len(candles) < self.rsv_period:
            return None, None, None
        k, d = 50.0, 50.0
        for i in range(self.rsv_period - 1, len(candles)):
            use = candles[: i + 1][-self.rsv_period :]
            highs = [c.high for c in use]
            lows = [c.low for c in use]
            close = use[-1].close
            h, l = max(highs), min(lows)
            if h <= l:
                rsv = 50.0
            else:
                rsv = (close - l) / (h - l) * 100.0
            k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv
            d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
        j = 3.0 * k - 2.0 * d
        return k, d, j

    def update(self, candle: CandleLike) -> None:
        self._ingest_candle(candle, self._buffer, self.rsv_period + 10)

    def get_value(self) -> Dict[str, Any]:
        k, d, j = self._kdj_from_buffer()
        return {
            f"{self.name}_k": k,
            f"{self.name}_d": d,
            f"{self.name}_j": j,
        }

    def reset(self) -> None:
        self._buffer.clear()
