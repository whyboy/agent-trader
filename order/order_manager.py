"""
OrderManager: 从 signal_queue 读取策略输出的 signal（dict），
策略执行完成后由本模块执行下单逻辑（实盘/模拟）。
"""

import logging
import threading
from queue import Empty, Queue
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OrderManager:
    """
    从 input_queue（即 Pipeline 的 signal_queue）取信号 dict，
    对每条信号执行 _execute_signal；默认仅打日志，可子类或注入实现真实下单。
    """

    def __init__(self, input_queue: Queue) -> None:
        self._input_queue = input_queue
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _execute_signal(self, signal: Dict[str, Any]) -> None:
        """
        执行单条信号。默认仅日志；子类或外部可重写为真实下单。
        signal 含: symbol, action, confidence, reason, metadata, snapshot_ts（symbol 由策略侧写入队列）
        """
        action = signal.get("action")
        if action == "hold":
            return
        symbol = signal.get("symbol")
        snapshot_ts = signal.get("snapshot_ts")
        reason = signal.get("reason")
        confidence = signal.get("confidence")
        logger.info(
            "[OrderManager] symbol=%s action=%s confidence=%.2f ts=%s reason=%s",
            symbol,
            action,
            confidence,
            snapshot_ts,
            reason[:80] if reason else "",
        )
        # TODO: 接入真实下单 API

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                signal = self._input_queue.get(timeout=0.5)
            except Empty:
                continue
            if not isinstance(signal, dict):
                continue
            try:
                self._execute_signal(signal)
            except Exception as e:
                logger.exception("OrderManager _execute_signal error: %s", e)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("OrderManager started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("OrderManager stopped")
