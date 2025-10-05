import datetime
import time
from threading import Thread
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ..store import SharedStore

from ..config import PulseWaveConfig
from ..data import (
    StoreClockPulse,
)
from .update import UpdateManager


class ClockPulseGenerator:
    def __init__(
        self,
        store: "SharedStore",
        update_manager: UpdateManager,
        db_config: PulseWaveConfig,
    ):
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.update")
        self.store = store
        self.update_manager = update_manager
        self.db_config = db_config
        self.thread = Thread(target=self.consistency_thread, daemon=True)
        self.thread.start()

    def consistency_thread(self):
        while True:
            consistancy = self.store.get_consistency()
            consistancy.clock_pulse = StoreClockPulse(
                date=datetime.datetime.now(datetime.timezone.utc)
            )
            time.sleep(self.db_config.clock_pulse_interval)

    def stop(self):
        self.logger.info("Stopping ClockPulseGenerator")
        # TODO: Implement proper stopping mechanism
