"""Pluggable technical indicators + IndicatorManager（初始化时注册所有指标）, MarketSnapshot, SnapshotProcessedV1。"""

from indicators.example.base import BaseIndicator, CandleLike
from indicators.example.ma import EMAIndicator, SMAIndicator
from indicators.example.macd import MACDIndicator
from indicators.example.atr import ATRIndicator
from indicators.example.volume import VolumeSMAIndicator
from indicators.indicator_manager import IndicatorManager
from indicators.data import (
    MarketSnapshot,
    SnapshotProcessedV1,
    SnapshotProcessedV2,
)

__all__ = [
    "BaseIndicator",
    "CandleLike",
    "SMAIndicator",
    "EMAIndicator",
    "MACDIndicator",
    "ATRIndicator",
    "VolumeSMAIndicator",
    "IndicatorManager",
    "MarketSnapshot",
    "SnapshotProcessedV1",
    "SnapshotProcessedV2",
]
