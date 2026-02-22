"""Example indicator set: base, MA, MACD, ATR, volume. MACD cross in macd_cross module (avoids circular import with strategy/processor)."""

from indicators.example.base import BaseIndicator, CandleLike
from indicators.example.ma import EMAIndicator, SMAIndicator
from indicators.example.macd import MACDIndicator
from indicators.example.atr import ATRIndicator
from indicators.example.volume import VolumeSMAIndicator
from indicators.example.rsi import RSIIndicator

__all__ = [
    "BaseIndicator",
    "CandleLike",
    "SMAIndicator",
    "EMAIndicator",
    "MACDIndicator",
    "ATRIndicator",
    "VolumeSMAIndicator",
    "RSIIndicator",
]
