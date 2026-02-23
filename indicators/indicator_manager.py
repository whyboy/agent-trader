"""
IndicatorManager: 消费 CandleLike（带 channel），按周期维护 K 线缓冲与指标，
初始化时根据配置注册所有指标（sma/ema/macd/volume_sma/rsi/kdj 等），
对每根 K 线计算所有指标，生成 SnapshotProcessedV1 放入队列，供 StrategyManager 持续读取并发出买卖信号。
"""

import logging
import threading
from collections import deque
from queue import Empty, Queue
from typing import Any, Dict, List, Optional, Type

from indicators.example.base import BaseIndicator, CandleLike
from indicators.example.ma import EMAIndicator, SMAIndicator
from indicators.example.macd import MACDIndicator
from indicators.example.volume import VolumeSMAIndicator
from indicators.example.rsi import RSIIndicator
from indicators.example.kdj import KDJIndicator
from indicators.example.candle_pct import CandlePctIndicator
from indicators.data import MarketSnapshot, SnapshotProcessedV1

logger = logging.getLogger(__name__)

# 内置指标类型（indicators/example 下所有产出数值的指标）
BUILTIN_INDICATORS: Dict[str, Type[BaseIndicator]] = {
    "sma": SMAIndicator,
    "ema": EMAIndicator,
    "macd": MACDIndicator,
    "volume_sma": VolumeSMAIndicator,
    "rsi": RSIIndicator,
    "kdj": KDJIndicator,
    "candle_pct": CandlePctIndicator,
}

# 所有 example 指标：固定列表，每周期都计算，结果写入 SnapshotProcessedV1 的 MarketSnapshot.indicators
ALL_EXAMPLE_INDICATORS: List[Dict[str, Any]] = [
    # {"type": "sma", "name": "ma_20", "params": {"period": 20}},
    # {"type": "ema", "name": "ema_12", "params": {"period": 12}},
    # {"type": "macd", "name": "macd", "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9}},
    # {"type": "atr", "name": "atr_14", "params": {"period": 14}},
    # {"type": "volume_sma", "name": "volume_sma_20", "params": {"period": 20}},
    {"type": "sma", "name": "ma_20", "params": {"period": 20}},
    {"type": "rsi", "name": "rsi_6", "params": {"period": 6}},
    {"type": "rsi", "name": "rsi_12", "params": {"period": 12}},
    {"type": "rsi", "name": "rsi_24", "params": {"period": 24}},
    {"type": "kdj", "name": "kdj", "params": {"rsv_period": 9}},
    {"type": "candle_pct", "name": "pct", "params": {"window": 10}},
]


def _create_indicator(type_name: str, name: str, params: Optional[Dict[str, Any]] = None) -> BaseIndicator:
    """根据类型名和参数创建指标实例。"""
    params = params or {}
    if type_name not in BUILTIN_INDICATORS:
        raise ValueError(f"Unknown indicator type: {type_name}. Available: {list(BUILTIN_INDICATORS.keys())}")
    return BUILTIN_INDICATORS[type_name](name=name, **params)


def _build_all_example_indicators() -> List[BaseIndicator]:
    """注册 indicators/example 下所有指标（默认参数），每周期共用同一套。"""
    return [
        _create_indicator(
            item.get("type", ""),
            item.get("name", item.get("type", "?")),
            item.get("params", {}),
        )
        for item in ALL_EXAMPLE_INDICATORS
    ]


class IndicatorManager:
    """
    消费 CandleLike（带 channel），按周期维护缓冲与指标；每来一根 K 线则更新该周期所有指标，
    在触发周期上生成 SnapshotProcessedV1（含各周期 MarketSnapshot 及全部指标），放入 output_queue，
    供 StrategyManager 从队列中持续读取并按策略发出买卖信号。
    """

    def __init__(
        self,
        channels: List[str],
        input_queue: Queue,
        output_queue: Optional[Queue] = None,
        trigger_channel: str = "candle15m",  # 触发写入的 channel
        max_candle_buffer: int = 500,
    ) -> None:
        self.channels = channels
        self.input_queue = input_queue
        self.output_queue = output_queue or Queue()
        self.trigger_channel = trigger_channel
        self.max_candle_buffer = max_candle_buffer

        self._buffers: Dict[str, deque] = {
            ch: deque(maxlen=max_candle_buffer) for ch in channels
        }
        # 每 channel 都注册 indicators/example 下全部指标，结果写入 SnapshotProcessedV1（含 MarketSnapshot + 全部指标）
        self._indicators_per_channel: Dict[str, List[BaseIndicator]] = {
            ch: _build_all_example_indicators() for ch in channels
        }

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                candle = self.input_queue.get(timeout=0.5)
            except Empty:
                continue

            # 按 ts 归并：同一 ts 的多次推送合并为一根 K 线（open=首次，high=max，low=min，close=最后一次，volume=按累加）
            ch = candle.channel
            buf = self._buffers[ch]
            if buf and buf[-1].ts == candle.ts:
                last = buf.pop()
                merged_volume = last.volume + candle.volume  # 同一 ts 内 volume 累加
                merged_candle = CandleLike(
                    ts=last.ts,
                    open=last.open,
                    high=max(last.high, candle.high),
                    low=min(last.low, candle.low),
                    close=candle.close,
                    volume=merged_volume,
                    channel=ch,
                )
                buf.append(merged_candle)
            else:
                buf.append(candle)
            current = buf[-1]
            for ind in self._indicators_per_channel[ch]:
                ind.update(current)
            indicators = {}
            for ind in self._indicators_per_channel[ch]:
                indicators.update(ind.get_value())
            # ma_20 来自 ALL_EXAMPLE_INDICATORS 中的 sma（name="ma_20"），已通过 get_value() 合并；此处注入 price_vs_ma20_pct
            _ma20 = indicators.get("ma_20")
            if _ma20 is not None and current.close and current.close != 0:
                indicators["price_vs_ma20_pct"] = round((_ma20 - current.close) / current.close * 100.0, 6)

            snapshot = MarketSnapshot(
                channel=ch,
                ts=current.ts,
                open=current.open,
                high=current.high,
                low=current.low,
                close=current.close,
                volume=current.volume,
                indicators=indicators
            )

            compose_snapshot: Dict[str, MarketSnapshot] = {}
            for c in self.channels:
                if c == ch:
                    compose_snapshot[c] = snapshot
                else:
                    buf = self._buffers[c]
                    if buf:
                        last = buf[-1]
                        ind_vals = {}
                        for ind in self._indicators_per_channel[c]:
                            ind_vals.update(ind.get_value())
                        _ma20 = ind_vals.get("ma_20")
                        if _ma20 is not None and last.close and last.close != 0:
                            ind_vals["price_vs_ma20_pct"] = round((_ma20 - last.close) / last.close * 100.0, 6)

                        compose_snapshot[c] = MarketSnapshot(
                            channel=c,
                            ts=last.ts,
                            open=last.open,
                            high=last.high,
                            low=last.low,
                            close=last.close,
                            volume=last.volume,
                            indicators=ind_vals,
                        )

            snapshot_processedV1 = SnapshotProcessedV1(
                ts=snapshot.ts,
                compose_snapshot=compose_snapshot,
            )


            print("snapshot_processedV1: ", snapshot_processedV1)
            self.output_queue.put_nowait(snapshot_processedV1)
               

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            "IndicatorManager started: channels=%s trigger_channel=%s",
            self.channels, self.trigger_channel,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        for ind_list in self._indicators_per_channel.values():
            for ind in ind_list:
                ind.reset()
        logger.info("IndicatorManager stopped")
