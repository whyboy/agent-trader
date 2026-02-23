"""Pipeline: main 入口调用的编排层。仅负责按 config 创建各模块 Manager 并串联队列。"""

import logging
from queue import Queue

from config import ServiceConfig
from indicators import IndicatorManager
from order import OrderManager
from strategy import StrategyManager
from websocket.ws_client_okx import OkxWsClient

logger = logging.getLogger(__name__)


class Pipeline:
    """
    编排层：除 websocket 外，各模块以 Manager 为入口。
    - IndicatorManager：生成指标，产出 SnapshotProcessedV1
    - StrategyManager：按 strategy_type 创建策略，从 v1 队列取 SnapshotProcessedV1，
      各策略内部按规则生成 Signal，写入 signal_queue
    - OrderManager：从 signal_queue 消费信号，策略执行完成后执行下单（或 dry_run 仅日志）
    """

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.snapshot_queue: Queue = Queue(maxsize=10000)
        self.snapshot_processed_v1_queue: Queue = Queue(maxsize=1000)
        self.signal_queue: Queue = Queue(maxsize=1000)
        self._ws: OkxWsClient = None
        self._indicator_manager: IndicatorManager = None
        self._strategy_manager: StrategyManager = None
        self._order_manager: OrderManager = None

    def start(self) -> None:
        okx = self.config.okx
        channels = okx.channels if okx.channels else [okx.channel]
        trigger_ch = channels[0] if len(channels) == 1 else channels[-1]

        self._ws = OkxWsClient(
            url=okx.url,
            symbol=okx.symbol,
            channels=channels,
            output_queue=self.snapshot_queue,
            ping_interval=okx.ping_interval,
            reconnect_delay=okx.reconnect_delay,
        )
        self._indicator_manager = IndicatorManager(
            channels=channels,
            input_queue=self.snapshot_queue,
            output_queue=self.snapshot_processed_v1_queue,
            trigger_channel=trigger_ch,
            max_candle_buffer=self.config.max_candle_buffer,
        )

        sc = self.config.strategy
        self._strategy_manager = StrategyManager(
            okx.symbol,
            self.snapshot_processed_v1_queue,
            self.signal_queue,
            sc.strategy_type or "hold",
            strategy_params=sc.strategy_params,
            history_size=sc.history_size,
            trigger_timeframe=trigger_ch,
        )

        self._order_manager = OrderManager(input_queue=self.signal_queue)
        self._ws.start()
        self._indicator_manager.start()
        self._strategy_manager.start()
        self._order_manager.start()
        logger.info("Pipeline started: %s %s", okx.symbol, channels)

    def stop(self) -> None:
        if self._order_manager is not None:
            self._order_manager.stop()
            self._order_manager = None
        if self._strategy_manager is not None:
            self._strategy_manager.stop()
            self._strategy_manager = None
        if self._indicator_manager is not None:
            self._indicator_manager.stop()
            self._indicator_manager = None
        if self._ws is not None:
            self._ws.stop()
            self._ws = None
        logger.info("Pipeline stopped")
