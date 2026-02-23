"""过去 N 根 K 线的涨跌幅，每根 K 线单独一个指标（非 list）。涨跌幅 = (当前 close - 前一根 close) / 前一根 close * 100。"""

import logging
from collections import deque
from typing import Any, Dict, Optional

from indicators.example.base import BaseIndicator, CandleLike

logger = logging.getLogger(__name__)


class CandlePctIndicator(BaseIndicator):
    """
    过去 window 根 K 线的涨跌幅（每根 (当前 close - 前一根 close) / 前一根 close * 100），
    输出为独立指标：pct_1（最新一根）, pct_2, ..., pct_N（最早一根）；
    pct_abs_avg：所有已收到 K 线的涨跌幅绝对值的平均，用递推 (count*prev+new)/(count+1) 维护。
    pct_sum_3/5/10：前 3、5、10 根已稳定 K 线的涨跌幅（带符号）之和。
    _buffer 为有界队列，避免内存无限增长。
    """

    def __init__(self, name: str, window: int = 10, max_buffer: int = 500, **kwargs: Any) -> None:
        super().__init__(name, window=window, max_buffer=max_buffer, **kwargs)
        self.window = max(1, min(int(window), 20))
        self._max_buffer = max(2, int(max_buffer))
        self._buffer: deque = deque(maxlen=self._max_buffer)
        self._pct_abs_avg: float = 0.0
        self._pct_abs_count: int = 0
        self._last_abs_pct: Optional[float] = None
        # 已稳定 K 线的涨跌幅（带符号），从旧到新，最多保留 10 根，用于 pct_sum_3/5/10
        self._pcts: deque = deque(maxlen=10)

    @staticmethod
    def _pct(current: CandleLike, prev: CandleLike) -> Optional[float]:
        if prev.close == 0:
            return None
        return round((current.close - prev.close) / prev.close * 100.0, 6)

    def update(self, candle: CandleLike) -> None:
        last_ts_before = self._buffer[-1].ts if self._buffer else None
        self._ingest_candle(candle, self._buffer, self._max_buffer)
        is_new_candle = self._buffer[-1].ts != last_ts_before
        # 新 K 线出现时，用「刚收盘的那根」相对「再前一根」的涨跌幅（已固定的 K 线），不用当前这根未定型的
        abs_pct: Optional[float] = None
        if is_new_candle and len(self._buffer) >= 3:
            pct_prev = self._pct(self._buffer[-2], self._buffer[-3])
            abs_pct = round(abs(pct_prev), 6) if pct_prev is not None else None
            if pct_prev is not None:
                self._pcts.append(pct_prev)
        if is_new_candle and abs_pct is not None:
            self._pct_abs_avg = (self._pct_abs_count * self._pct_abs_avg + abs_pct) / (self._pct_abs_count + 1)
            self._pct_abs_count += 1
            self._last_abs_pct = abs_pct

    def get_value(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        candles = list(self._buffer)
        for i in range(self.window):
            if len(candles) < i + 2:
                result[f"{self.name}_{i + 1}"] = None
            else:
                pct = self._pct(candles[-(i + 1)], candles[-(i + 2)])
                result[f"{self.name}_{i + 1}"] = pct

        result[f"{self.name}_abs_avg"] = round(self._pct_abs_avg, 6) if self._pct_abs_count > 0 else None
        # 前 3、5、10 根已稳定 K 线的涨跌幅之和（倒数第1～3/1～5/1～10 根）
        pcts_list = list(self._pcts)
        for n in (3, 5, 10):
            result[f"{self.name}_sum_{n}"] = (
                round(sum(pcts_list[-n:]), 6) if len(pcts_list) >= n else None
            )
        parts = [f"{k}={v:.6f}%" if v is not None else f"{k}=None" for k, v in result.items()]
        # logger.info("CandlePct %s 计算结果: %s", self.name, ", ".join(parts))
        return result


    def reset(self) -> None:
        self._buffer.clear()
        self._pct_abs_avg = 0.0
        self._pct_abs_count = 0
        self._last_abs_pct = None
        self._pcts.clear()
